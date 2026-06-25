'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams } from 'next/navigation';
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Shield,
  Bot,
  Upload,
  CheckCircle2,
  XCircle,
  Mail,
  Github,
  GitBranch,
} from 'lucide-react';
import { authHeaders } from '@/lib/auth';
import RecordingPanel from '@/components/recording/RecordingPanel';
import EvidenceListSections from '@/components/evidence/EvidenceListSections';
import EvidencePreviewDialog from '@/components/evidence/EvidencePreviewDialog';
import EvidenceUploadPanel from '@/components/evidence/EvidenceUploadPanel';
import EvidenceMatchingPanel from '@/components/evidence/EvidenceMatchingPanel';
import SuggestedQuestionsPanel from '@/components/evidence/SuggestedQuestionsPanel';
import RubricScoresPanel from '@/components/evidence/RubricScoresPanel';
import DeleteConfirmDialog from '@/components/common/DeleteConfirmDialog';
import ViewModeBanner from '@/components/common/ViewModeBanner';
import { useEvidencePreview } from '@/lib/hooks/useEvidencePreview';
import { useEvidenceUpload } from '@/context/EvidenceUploadContext';
import { resolveAssessmentForStudent } from '@/lib/api/recording';
import { getAssessmentDraft } from '@/lib/api/assessmentsApi';
import { useDeleteConfirm } from '@/lib/hooks/useDeleteConfirm';
import {
  deleteEvidence,
  getSupportedEvidenceTypes,
  listStudentEvidence,
} from '@/lib/api/evidence';

import {
  listModuleOverlapSignals,
  listProjectStudents,
  getProject,
  setStudentGithubRepo,
  updateModuleStudent,
  verifyGithubRepo,
} from '@/lib/api/modulesApi';
import { APP_PATHS } from '@/lib/routes';
import { useModuleViewOnly } from '@/lib/hooks/useModuleViewOnly';
import AssessmentFormPanel from '@/components/assessment/AssessmentFormPanel';
import ChatHistoryPanel from '@/components/assessment/ChatHistoryPanel';
import FloatingAssessmentChat from '@/components/assessment/FloatingAssessmentChat';
import TransparencyPanel from '@/components/assessment/TransparencyPanel';
import EmailDraftModal from '@/components/assessment/EmailDraftModal';
import { UI_STATUS_LABELS } from '@/lib/uiStatusLabels';

const inputClass =
  'w-full bg-secondary border border-border rounded-md px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all';
const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// ─── AI Insights Panel ───────────────────────────────────────────────────────

const insightConfig = {
  overlap: {
    icon: AlertTriangle,
    label: 'Overlap',
    severityColors: {
      high: 'bg-red-500/10 text-red-400 ring-1 ring-red-500/20',
      medium: 'bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/20',
      low: 'bg-yellow-500/10 text-yellow-400 ring-1 ring-yellow-500/20',
    },
  },
};

function overlapToInsight(signal, studentId, studentNames = {}) {
  const integrityType = signal.integrity_type || 'student_plagiarism';
  const isA = signal.student_a_id === studentId;
  const otherId = isA ? signal.student_b_id : signal.student_a_id;
  const otherName =
    (isA ? signal.student_b_name : signal.student_a_name) ||
    studentNames[otherId] ||
    otherId;
  const severity =
    signal.status === 'confirmed' && signal.confidence >= 0.7
      ? 'high'
      : signal.status === 'confirmed'
        ? 'medium'
        : 'low';

  let title = `Possible overlap with ${otherName}`;
  if (integrityType === 'ai') {
    title = 'Possible AI-assisted text';
  } else if (integrityType === 'both') {
    title = `Possible AI + overlap with ${otherName}`;
  } else if (integrityType === 'student_plagiarism') {
    title = `Possible overlap with ${otherName}`;
  }

  const typeLabel =
    integrityType === 'ai'
      ? 'Possible AI-assisted'
      : integrityType === 'both'
        ? 'Possible AI + student overlap'
        : 'Possible student overlap';

  return {
    id: signal.id,
    type: 'overlap',
    title,
    severity,
    description:
      signal.ai_explanation ||
      signal.passage_a ||
      signal.snippet ||
      `${typeLabel} (estimated confidence ${Math.round((signal.confidence || 0) * 100)}%). Manual review recommended.`,
    sourceFiles: [signal.evidence_a_name, signal.evidence_b_name].filter(
      (f, i) => f && (integrityType !== 'ai' || i === 0)
    ),
    link: null,
  };
}

function AIInsightsPanel({ moduleId, studentId }) {
  const [overlapSignals, setOverlapSignals] = useState([]);
  const [overlapLoading, setOverlapLoading] = useState(false);
  const [expanded, setExpanded] = useState(null);

  useEffect(() => {
    if (!moduleId || !studentId) return;
    let cancelled = false;
    (async () => {
      setOverlapLoading(true);
      try {
        const signals = await listModuleOverlapSignals(moduleId);
        if (!cancelled) {
          const forStudent = (signals || []).filter(
            (s) => s.student_a_id === studentId || s.student_b_id === studentId
          );
          setOverlapSignals(forStudent);
        }
      } catch {
        if (!cancelled) setOverlapSignals([]);
      } finally {
        if (!cancelled) setOverlapLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [moduleId, studentId]);

  const overlapInsights = overlapSignals.map((s) =>
    overlapToInsight(s, studentId)
  );

  return (
    <div className="rounded-lg bg-card border border-border overflow-hidden">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-border">
        <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
          <Bot size={14} className="text-accent" />
        </div>
        <div>
          <div className="text-sm font-semibold text-foreground">
            AI Insights
          </div>
          <div className="text-[11px] text-muted-foreground">
            {overlapInsights.length} finding
            {overlapInsights.length !== 1 ? 's' : ''}
          </div>
        </div>
      </div>

      <div className="p-4 space-y-3">
        <div className="flex items-start gap-2 rounded-md bg-secondary border border-border p-3">
          <Shield size={12} className="text-muted-foreground mt-0.5 shrink-0" />
          <p className="text-[11px] text-muted-foreground leading-relaxed">
            All analyses run on-premises, GDPR-compliant. Every suggestion is
            traceable to source files.
          </p>
        </div>

        {overlapLoading ? (
          <div className="flex justify-center py-4">
            <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        ) : overlapInsights.length === 0 ? (
          <div className="rounded-lg border border-border p-6 text-center">
            <div className="text-2xl mb-2">✓</div>
            <p className="text-sm font-medium text-foreground">
              No notable findings
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              No patterns detected for this student
            </p>
          </div>
        ) : (
          overlapInsights.map((insight) => {
            const config = insightConfig[insight.type];
            const Icon = config.icon;
            const severityClass = config.severityColors[insight.severity];
            return (
              <div
                key={insight.id}
                className="rounded-lg border border-border overflow-hidden"
              >
                <button
                  onClick={() =>
                    setExpanded(expanded === insight.id ? null : insight.id)
                  }
                  className="w-full flex items-center gap-3 px-4 py-3 hover:bg-secondary/50 transition-colors text-left"
                >
                  <Icon size={14} className="text-muted-foreground shrink-0" />
                  <span className="flex-1 text-xs font-medium text-foreground leading-snug">
                    {insight.title}
                  </span>
                  <span
                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide shrink-0 ${severityClass}`}
                  >
                    {insight.severity}
                  </span>
                  {expanded === insight.id ? (
                    <ChevronDown
                      size={13}
                      className="text-muted-foreground shrink-0"
                    />
                  ) : (
                    <ChevronRight
                      size={13}
                      className="text-muted-foreground shrink-0"
                    />
                  )}
                </button>
                {expanded === insight.id && (
                  <div className="border-t border-border bg-secondary/30 px-4 py-3 space-y-3">
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${severityClass}`}
                    >
                      {config.label}
                    </span>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      {insight.description}
                    </p>
                    {insight.sourceFiles?.length > 0 && (
                      <div>
                        <p className="text-[10px] font-semibold text-foreground mb-1.5 uppercase tracking-wide">
                          Source Files
                        </p>
                        <div className="space-y-1">
                          {insight.sourceFiles.map((f, i) => (
                            <div
                              key={i}
                              className="rounded bg-background border border-border px-2 py-1 text-[11px] font-mono text-muted-foreground"
                            >
                              {f}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {insight.type === 'overlap' && moduleId && (
                      <a
                        href={APP_PATHS.moduleOverlaps(moduleId)}
                        className="text-[11px] text-primary hover:underline inline-block"
                      >
                        View overlap details →
                      </a>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}

        <div className="flex items-start gap-2 rounded-md bg-secondary border border-border p-3">
          <AlertTriangle size={12} className="text-amber-400 mt-0.5 shrink-0" />
          <p className="text-[11px] text-muted-foreground leading-relaxed">
            AI suggestions are advisory. Final assessment responsibility remains
            with the lecturer.
          </p>
        </div>
      </div>
    </div>
  );
}

// ─── Evidence Upload ──────────────────────────────────────────────────────────

const DEFAULT_EVIDENCE_EXTENSIONS = [
  '.md',
  '.docx',
  '.pdf',
  '.png',
  '.jpg',
  '.jpeg',
];

function EvidenceUpload({ studentId }) {
  const fileInputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploadSuccessMessage, setUploadSuccessMessage] = useState('');
  // Confirmed evidence from the server (existing + newly completed uploads)
  const [allEvidence, setAllEvidence] = useState([]);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [error, setError] = useState(null);
  // Allowed extensions fetched from the backend — starts with a safe default
  const [allowedExtensions, setAllowedExtensions] = useState(
    DEFAULT_EVIDENCE_EXTENSIONS
  );
  const {
    startUpload,
    registerCallbacks,
    getStudentLocalItems,
    consumeCompletedItems,
  } = useEvidenceUpload();
  const {
    previewEvidence,
    previewUrl,
    previewContent,
    previewLoading,
    activePreviewKind,
    basePreviewKind,
    showImageExtractedText,
    canPreview,
    openPreview,
    closePreview,
    toggleImageExtractedText,
    downloadEvidence,
  } = useEvidencePreview();

  const hasStudentId = Boolean(String(studentId || '').trim());

  const { pendingItem, requestDelete, cancelDelete, confirmDelete } =
    useDeleteConfirm({
      onDelete: (item) => deleteEvidence(item.id),
      onDeleted: (deletedEvidence) => {
        setAllEvidence((prev) =>
          prev.filter((ev) => ev.id !== deletedEvidence.id)
        );
      },
      onError: (err) => {
        setError(err.message);
      },
    });

  // In-flight items from the persistent context (survive navigation)
  const localItems = hasStudentId ? getStudentLocalItems(studentId) : [];
  const uploading = localItems.length > 0;
  // Show the latest in-flight filename in the upload panel
  const uploadingFileName = localItems[0]?.file_name ?? '';

  // Fetch supported types from the API on mount (only when we have a real UUID)
  useEffect(() => {
    if (!hasStudentId) return;
    getSupportedEvidenceTypes()
      .then((data) => {
        if (Array.isArray(data.supported_extensions)) {
          setAllowedExtensions(data.supported_extensions);
        }
      })
      .catch(() => {
        // Keep the default if the request fails
      });
  }, [hasStudentId]);

  // Register live callbacks with the context so completed uploads update this
  // component's state even when initiated from a previous mount of this page.
  useEffect(() => {
    if (!hasStudentId) return;
    return registerCallbacks(studentId, {
      onCompleted: (data) => {
        setAllEvidence((prev) => {
          if (prev.some((e) => e.id === data.id)) return prev;
          return [data, ...prev];
        });
        // Only show the success toast once the AI has finished processing
        if (data.embedding_status === 'completed') {
          setUploadSuccessMessage(`Upload complete: ${data.file_name}`);
          window.setTimeout(() => setUploadSuccessMessage(''), 4000);
        }
      },
      onError: (err) => {
        setError(err.message);
      },
    });
  }, [studentId, hasStudentId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch existing evidence for this student on mount; also merge any items
  // that completed while we were navigated away.
  useEffect(() => {
    if (!hasStudentId) return;
    const load = async () => {
      setEvidenceLoading(true);
      try {
        const data = await listStudentEvidence(studentId).catch(() => []);
        const fetched = Array.isArray(data) ? data : [];
        // Prepend items that finished uploading while this page was unmounted
        const stashed = consumeCompletedItems(studentId);
        const stashedIds = new Set(stashed.map((e) => e.id));
        setAllEvidence([
          ...stashed,
          ...fetched.filter((e) => !stashedIds.has(e.id)),
        ]);
      } catch {
        setAllEvidence([]);
      } finally {
        setEvidenceLoading(false);
      }
    };
    load();
  }, [studentId, hasStudentId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Poll the server while any evidence item is still being processed by the
  // background vision task (embedding_status === 'processing').
  useEffect(() => {
    if (!hasStudentId) return;
    const hasProcessing = allEvidence.some(
      (e) => e.embedding_status === 'processing'
    );
    if (!hasProcessing) return;

    const interval = setInterval(async () => {
      try {
        const fresh = await listStudentEvidence(studentId);
        if (!Array.isArray(fresh)) return;
        setAllEvidence((prev) => {
          let changed = false;
          const next = prev.map((ev) => {
            const updated = fresh.find((f) => f.id === ev.id);
            if (updated && updated.embedding_status !== ev.embedding_status) {
              changed = true;
              // Show success toast when an image finishes AI processing
              if (updated.embedding_status === 'completed') {
                setUploadSuccessMessage(
                  `Upload complete: ${updated.file_name}`
                );
                window.setTimeout(() => setUploadSuccessMessage(''), 4000);
              }
              return updated;
            }
            return ev;
          });
          return changed ? next : prev;
        });
      } catch {
        // Silently ignore polling errors — the user can still interact
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [allEvidence, studentId, hasStudentId]);

  // Show the success toast once a processing item transitions to completed
  useEffect(() => {
    const justCompleted = allEvidence.filter(
      (e) => e.embedding_status === 'completed' && e.__justCompleted
    );
    justCompleted.forEach((e) => {
      setUploadSuccessMessage(`Upload complete: ${e.file_name}`);
      window.setTimeout(() => setUploadSuccessMessage(''), 4000);
    });
  }, [allEvidence]);

  // Guard: only render the upload UI when a student identifier is available
  if (!hasStudentId) {
    return (
      <div className="rounded-lg border border-dashed border-border px-5 py-4 text-xs text-muted-foreground">
        Evidence upload is available once this student is linked to a real
        database record.
      </div>
    );
  }

  const isAllowed = (filename) => {
    const ext = filename.slice(filename.lastIndexOf('.')).toLowerCase();
    return allowedExtensions.includes(ext);
  };

  const handleSingleFile = (file) => {
    setError(null);
    if (!isAllowed(file.name)) {
      setError(
        `Unsupported file type. Allowed: ${allowedExtensions.join(', ')}`
      );
      return;
    }

    startUpload(studentId, file);
  };

  const onInputChange = (e) => {
    const files = Array.from(e.target.files || []);
    files.forEach((file) => {
      void handleSingleFile(file);
    });
    e.target.value = '';
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const files = Array.from(e.dataTransfer.files || []);
    files.forEach((file) => {
      void handleSingleFile(file);
    });
  };

  const handleDelete = (evidenceId) => {
    const evidence = allEvidence.find((ev) => ev.id === evidenceId);
    if (evidence) {
      requestDelete(evidence);
    }
  };

  // Build the <input accept> string from the dynamic list
  const acceptAttr = allowedExtensions.join(',');

  const handlePreview = async (evidence) => {
    setError(null);
    try {
      await openPreview(evidence);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleDownload = async (evidence) => {
    setError(null);
    try {
      await downloadEvidence(evidence);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="space-y-4">
      <EvidenceUploadPanel
        title="Upload Evidence"
        acceptedLabel={allowedExtensions.join(', ')}
        uploading={uploading}
        uploadingCount={localItems.length}
        uploadingFileName={uploadingFileName}
        dragOver={dragOver}
        fileInputRef={fileInputRef}
        accept={acceptAttr}
        onInputChange={onInputChange}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onOpenFilePicker={() => fileInputRef.current?.click()}
      />

      {uploadSuccessMessage && (
        <div className="flex items-center gap-2 rounded-md bg-emerald-500/10 border border-emerald-500/20 px-3 py-2">
          <CheckCircle2 size={13} className="text-emerald-400 shrink-0" />
          <p className="text-xs text-emerald-400">{uploadSuccessMessage}</p>
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 rounded-md bg-red-500/10 border border-red-500/20 px-3 py-2">
          <XCircle size={13} className="text-red-400 shrink-0" />
          <p className="text-xs text-red-400">{error}</p>
        </div>
      )}

      {(() => {
        const displayedEvidence = [...localItems, ...allEvidence];
        const studentEvidence = displayedEvidence.filter(
          (ev) => !ev.project_id
        );
        const groupEvidence = displayedEvidence.filter((ev) =>
          Boolean(ev.project_id)
        );

        return (
          <EvidenceListSections
            evidenceLoading={evidenceLoading}
            allCount={displayedEvidence.length}
            sections={[
              {
                key: 'student-evidence',
                title: 'Student evidence',
                items: studentEvidence,
                emptyText: 'No student-specific evidence yet.',
                dividerTop: false,
              },
              {
                key: 'group-evidence',
                title: 'Group shared evidence',
                items: groupEvidence,
                emptyText: 'No group shared evidence attached.',
                dividerTop: true,
              },
            ]}
            getItemCanPreview={(evidence) =>
              !evidence.__localProcessing &&
              evidence.embedding_status !== 'processing' &&
              canPreview(evidence)
            }
            onPreview={handlePreview}
            onDownload={handleDownload}
            onDelete={handleDelete}
            emptyText="No evidence uploaded yet."
          />
        );
      })()}

      <EvidencePreviewDialog
        evidence={previewEvidence}
        previewKind={activePreviewKind}
        basePreviewKind={basePreviewKind}
        previewUrl={previewUrl}
        previewContent={previewContent}
        loading={previewLoading}
        showImageExtractedText={showImageExtractedText}
        onToggleImageExtractedText={async () => {
          setError(null);
          try {
            await toggleImageExtractedText();
          } catch (err) {
            setError(err.message);
          }
        }}
        onClose={closePreview}
      />

      <DeleteConfirmDialog
        open={Boolean(pendingItem)}
        label={pendingItem?.file_name}
        onConfirm={confirmDelete}
        onCancel={cancelDelete}
      />
    </div>
  );
}

// ─── Student Assessment Page ──────────────────────────────────────────────────

export default function StudentAssessmentPage() {
  const { moduleId, studentId } = useParams();
  const [student, setStudent] = useState(null);
  const [loadError, setLoadError] = useState('');
  const [currentTab, setCurrentTab] = useState(0);
  const [assessmentId, setAssessmentId] = useState(null);
  const [moduleName, setModuleName] = useState('');
  const [moduleTeacherId, setModuleTeacherId] = useState(null);
  const [emailDraftOpen, setEmailDraftOpen] = useState(false);
  const [draftSnapshot, setDraftSnapshot] = useState(null);
  const [formKey, setFormKey] = useState(0);
  const [auditRefresh, setAuditRefresh] = useState(0);
  const [draftRefreshToken, setDraftRefreshToken] = useState(0);
  const [highlightedCriteria, setHighlightedCriteria] = useState([]);
  const chatRef = useRef(null);
  const pendingDiscussRef = useRef(null);
  const [discussTrigger, setDiscussTrigger] = useState(0);

  const [repoUrl, setRepoUrl] = useState('');
  const [repoBranch, setRepoBranch] = useState('');
  const [branches, setBranches] = useState([]);
  const [verified, setVerified] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [repoSaving, setRepoSaving] = useState(false);
  const [repoError, setRepoError] = useState('');
  const [repoSuccess, setRepoSuccess] = useState('');
  const [editing, setEditing] = useState(false);
  const [confirmRepoRemove, setConfirmRepoRemove] = useState(false);

  function handleChatDraftUpdated(draft) {
    setDraftSnapshot(draft);
    setDraftRefreshToken((k) => k + 1);
    setAuditRefresh((k) => k + 1);
  }

  function handleChatApplied(changes) {
    const keys = (changes || []).map((c) => c.criterion_key).filter(Boolean);
    if (keys.length) {
      setHighlightedCriteria(keys);
    }
    setDraftRefreshToken((k) => k + 1);
    setAuditRefresh((k) => k + 1);
  }

  function handleDiscussCriterion({ key, name, score }) {
    setCurrentTab(1);
    pendingDiscussRef.current = { key, name, score };
    setDiscussTrigger((t) => t + 1);
  }

  useEffect(() => {
    if (currentTab !== 1 || !pendingDiscussRef.current) return;
    const { key, name, score } = pendingDiscussRef.current;
    pendingDiscussRef.current = null;
    requestAnimationFrame(() => {
      chatRef.current?.focusCriterion(key, name, score);
    });
  }, [currentTab, discussTrigger]);

  useEffect(() => {
    getProject(moduleId)
      .then((m) => {
        setModuleName(m?.name || '');
        setModuleTeacherId(m?.teacher_id ?? null);
      })
      .catch(() => {});
  }, [moduleId]);

  useEffect(() => {
    listProjectStudents(moduleId)
      .then((students) => {
        const found = students.find(
          (s) => s.id === studentId || s.student_number === studentId
        );
        if (found) {
          setStudent(found);
          setRepoUrl(found.github_repo_url || '');
          setRepoBranch(found.github_branch || '');

          if (found.github_repo_url) {
            setVerified(true);
            setBranches(found.github_branch ? [found.github_branch] : []);
          } else {
            setVerified(false);
            setBranches([]);
          }

          setEditing(!found.github_repo_url);
        } else {
          setLoadError('Student not found in this module.');
        }
      })
      .catch((e) => setLoadError(e?.message || 'Failed to load student data'));
  }, [moduleId, studentId]);

  const handleVerifyRepo = async () => {
    setRepoError('');
    setRepoSuccess('');
    setVerified(false);
    setBranches([]);
    setRepoBranch('');
    if (!repoUrl.trim()) {
      setRepoError('Enter a GitHub repository URL first.');
      return;
    }
    setVerifying(true);
    try {
      const result = await verifyGithubRepo(repoUrl.trim());
      setBranches(result.branches);
      setRepoBranch(result.default_branch);
      setVerified(true);
      setRepoSuccess(
        `Repository verified. ${result.branches.length} branch${result.branches.length !== 1 ? 'es' : ''} found.`
      );
    } catch (err) {
      setRepoError(err.message);
    } finally {
      setVerifying(false);
    }
  };

  const handleSaveStudentRepo = async (e) => {
    e.preventDefault();
    setRepoError('');
    setRepoSuccess('');
    if (!verified) {
      setRepoError('Please verify the repository before saving.');
      return;
    }
    setRepoSaving(true);
    try {
      const updated = await updateModuleStudent(moduleId, studentId, {
        github_repo_url: repoUrl.trim() || null,
        github_branch: repoBranch || null,
      });
      setStudent((prev) => ({
        ...prev,
        github_repo_url: updated.github_repo_url || null,
        github_branch: updated.github_branch || null,
      }));
      setRepoUrl(updated.github_repo_url || '');
      setRepoBranch(updated.github_branch || '');
      setEditing(false);
      setRepoSuccess(
        updated.github_repo_url
          ? `Repository and branch "${updated.github_branch || repoBranch}" saved.`
          : 'Repository removed.'
      );
    } catch (err) {
      setRepoError(err.message);
    } finally {
      setRepoSaving(false);
    }
  };

  const handleRemoveStudentRepo = async () => {
    setRepoError('');
    setRepoSuccess('');
    setRepoSaving(true);
    try {
      await updateModuleStudent(moduleId, studentId, {
        github_repo_url: null,
        github_branch: null,
      });
      setStudent((prev) => ({
        ...prev,
        github_repo_url: null,
        github_branch: null,
      }));
      setRepoUrl('');
      setRepoBranch('');
      setBranches([]);
      setVerified(false);
      setEditing(true);
      setRepoSuccess('Repository removed.');
    } catch (err) {
      setRepoError(err.message);
    } finally {
      setRepoSaving(false);
    }
  };

  // Resolve (or lazily create) the assessment for this student so the recording
  // panel has a real assessment id to drive the recording/consent endpoints.
  useEffect(() => {
    let active = true;
    resolveAssessmentForStudent(studentId)
      .then((s) => active && setAssessmentId(s.assessment_id))
      .catch(
        (e) =>
          active &&
          setLoadError(e?.message || 'Failed to resolve assessment for student')
      );
    return () => {
      active = false;
    };
  }, [studentId]);

  // Load the draft once at page level so the floating AI chat has correct
  // locked/can_chat state on every tab — not only after the Assessment tab has
  // mounted the form panel. Won't clobber fresher state set later by the panel.
  useEffect(() => {
    if (!assessmentId) return;
    let active = true;
    getAssessmentDraft(assessmentId)
      .then((draft) => {
        if (active) setDraftSnapshot((prev) => prev ?? draft);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [assessmentId]);

  const handleDraftChange = useCallback((draft) => {
    setDraftSnapshot(draft);
    setAuditRefresh((k) => k + 1);
  }, []);

  const viewOnly = useModuleViewOnly(moduleTeacherId);

  if (loadError)
    return <div className="text-sm text-red-400 p-4">{loadError}</div>;

  if (!student)
    return (
      <div className="flex justify-center py-20">
        <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );

  const overallScore =
    draftSnapshot?.overall_score != null
      ? Number(draftSnapshot.overall_score).toFixed(1)
      : student.grade && student.grade !== '—'
        ? student.grade
        : '—';
  const displayGrade =
    draftSnapshot?.overall_grade?.effective ||
    (student.assessment_status === 'completed' ? student.grade : null);

  return (
    <div className="space-y-6">
      {viewOnly && <ViewModeBanner />}

      {emailDraftOpen && (
        <EmailDraftModal
          student={student}
          moduleName={moduleName}
          onClose={() => setEmailDraftOpen(false)}
        />
      )}

      {assessmentId && (
        <FloatingAssessmentChat
          ref={chatRef}
          assessmentId={assessmentId}
          disabled={draftSnapshot?.locked}
          canChat={draftSnapshot?.can_chat ?? false}
          onDraftUpdated={handleChatDraftUpdated}
          onApplied={handleChatApplied}
        />
      )}

      <div className="rounded-lg bg-card border border-border p-6">
        <div className="flex items-center gap-5">
          <div className="w-14 h-14 rounded-full bg-primary/20 flex items-center justify-center text-lg font-bold text-primary shrink-0">
            {student.name
              .split(' ')
              .map((n) => n[0])
              .join('')}
          </div>
          <div className="flex-1">
            <h1 className="text-xl font-bold text-foreground">
              {student.name}
            </h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              {student.student_number}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setEmailDraftOpen(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-md border border-border text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all"
            >
              <Mail size={14} />
              Email Draft
            </button>
            <div className="text-center border-l border-border pl-6 shrink-0">
              <div className="text-xs text-muted-foreground mb-1">
                {displayGrade ? 'Grade' : 'Avg score'}
              </div>
              <div className="text-3xl font-bold text-foreground font-mono">
                {displayGrade || overallScore}
              </div>
              {draftSnapshot?.locked && (
                <div className="text-[10px] text-emerald-400 mt-1 font-medium uppercase tracking-wide">
                  Finalized
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2">
          <div className="rounded-lg bg-card border border-border overflow-hidden">
            <div className="flex border-b border-border">
              {['Contributions & Evidence', 'Assessment', 'Chat History'].map(
                (tab, i) => (
                  <button
                    key={tab}
                    onClick={() => setCurrentTab(i)}
                    className={`px-6 py-3.5 text-sm font-medium transition-all border-b-2 cursor-pointer ${currentTab === i ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-foreground'}`}
                  >
                    {tab}
                  </button>
                )
              )}
            </div>

            <div className="p-6">
              {currentTab === 0 && (
                <div className="space-y-6">
                  <EvidenceMatchingPanel
                    studentId={studentId}
                    moduleId={moduleId}
                  />

                  <SuggestedQuestionsPanel
                    studentId={studentId}
                    moduleId={moduleId}
                  />

                  {!viewOnly && (
                    <RubricScoresPanel
                      studentId={studentId}
                      moduleId={moduleId}
                    />
                  )}

                  {!viewOnly && <EvidenceUpload studentId={studentId} />}
                </div>
              )}

              {currentTab === 1 && assessmentId && (
                <AssessmentFormPanel
                  key={formKey}
                  assessmentId={assessmentId}
                  moduleId={moduleId}
                  refreshToken={draftRefreshToken}
                  highlightedCriteria={highlightedCriteria}
                  onDiscussCriterion={handleDiscussCriterion}
                  onDraftChange={handleDraftChange}
                  onFinalized={() => {
                    setAuditRefresh((k) => k + 1);
                  }}
                />
              )}
              {currentTab === 1 && !assessmentId && (
                <div className="text-sm text-muted-foreground py-8 text-center">
                  Resolving assessment...
                </div>
              )}

              {currentTab === 2 && assessmentId && (
                <ChatHistoryPanel assessmentId={assessmentId} />
              )}
              {currentTab === 2 && !assessmentId && (
                <div className="text-sm text-muted-foreground py-8 text-center">
                  Resolving assessment...
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="col-span-1 space-y-4">
          <div className="sticky top-4 space-y-4">
            {student.github_repo_url && (!editing || viewOnly) ? (
              <div className="rounded-lg bg-card border border-border p-5 space-y-4">
                <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
                  <Github size={16} />
                  GitHub Repository
                </h2>
                <div className="rounded-lg bg-secondary/50 border border-border p-3 space-y-3">
                  <div>
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wide font-semibold mb-1">
                      Repository
                    </p>
                    <a
                      href={student.github_repo_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-primary hover:underline break-all font-mono leading-snug"
                    >
                      {student.github_repo_url.replace(
                        'https://github.com/',
                        ''
                      )}
                    </a>
                  </div>
                  {student.github_branch && (
                    <div>
                      <p className="text-[10px] text-muted-foreground uppercase tracking-wide font-semibold mb-1 flex items-center gap-1">
                        <GitBranch size={11} />
                        Branch
                      </p>
                      <span className="text-xs font-mono text-foreground">
                        {student.github_branch}
                      </span>
                    </div>
                  )}
                </div>
                {repoError && (
                  <p className="rounded-md bg-red-500/10 border border-red-500/20 px-3 py-2 text-xs text-red-400">
                    {repoError}
                  </p>
                )}
                {repoSuccess && (
                  <p className="rounded-md bg-emerald-500/10 border border-emerald-500/20 px-3 py-2 text-xs text-emerald-400">
                    {repoSuccess}
                  </p>
                )}
                {!viewOnly && (
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setEditing(true);
                        setRepoSuccess('');
                        setRepoError('');
                      }}
                      disabled={repoSaving}
                      className="w-full px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer"
                    >
                      Update Branch
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirmRepoRemove(true)}
                      disabled={repoSaving}
                      className="w-full px-4 py-2 rounded-md border border-destructive/30 text-sm font-semibold text-destructive hover:bg-destructive/10 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {repoSaving ? UI_STATUS_LABELS.removing : 'Remove'}
                    </button>
                  </div>
                )}
              </div>
            ) : !viewOnly ? (
              <form
                onSubmit={handleSaveStudentRepo}
                className="rounded-lg bg-card border border-border p-5 space-y-4"
              >
                <div className="flex items-center justify-between">
                  <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
                    <Github size={16} />
                    GitHub Repository
                  </h2>
                  {editing && student.github_repo_url && (
                    <button
                      type="button"
                      onClick={() => {
                        setEditing(false);
                        setRepoUrl(student.github_repo_url);
                        setRepoBranch(student.github_branch || '');
                        setRepoError('');
                        setRepoSuccess('');
                        setVerified(true);
                        setBranches(
                          student.github_branch ? [student.github_branch] : []
                        );
                      }}
                      className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                    >
                      Cancel
                    </button>
                  )}
                </div>
                <div className="space-y-2">
                  <input
                    value={repoUrl}
                    onChange={(e) => {
                      setRepoUrl(e.target.value);
                      setVerified(false);
                      setBranches([]);
                      setRepoBranch('');
                      setRepoSuccess('');
                      setRepoError('');
                    }}
                    placeholder="https://github.com/owner/repo"
                    className={inputClass}
                  />
                  <button
                    type="button"
                    onClick={handleVerifyRepo}
                    disabled={verifying || !repoUrl.trim()}
                    className="w-full px-4 py-2 rounded-md border border-border text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {verifying ? (
                      <span className="flex items-center justify-center gap-2">
                        <span className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
                        {UI_STATUS_LABELS.verifying}
                      </span>
                    ) : (
                      'Verify Repository'
                    )}
                  </button>
                </div>
                {verified && branches.length > 0 && (
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-muted-foreground">
                      Branch
                    </label>
                    <select
                      value={repoBranch}
                      onChange={(e) => setRepoBranch(e.target.value)}
                      className={`${inputClass} cursor-pointer`}
                    >
                      {branches.map((b) => (
                        <option key={b} value={b}>
                          {b}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
                {repoError && (
                  <p className="rounded-md bg-red-500/10 border border-red-500/20 px-3 py-2 text-xs text-red-400">
                    {repoError}
                  </p>
                )}
                {repoSuccess && (
                  <p className="rounded-md bg-emerald-500/10 border border-emerald-500/20 px-3 py-2 text-xs text-emerald-400">
                    {repoSuccess}
                  </p>
                )}
                <button
                  type="submit"
                  disabled={repoSaving || !verified}
                  className="w-full px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer"
                >
                  {repoSaving ? UI_STATUS_LABELS.saving : 'Save Repo'}
                </button>
              </form>
            ) : null}

            {!viewOnly && (
              <DeleteConfirmDialog
                open={confirmRepoRemove}
                title="Remove GitHub Repository"
                message="Are you sure you want to remove this student's GitHub repository and branch?"
                confirmLabel="Remove"
                loading={repoSaving}
                onCancel={() => setConfirmRepoRemove(false)}
                onConfirm={async () => {
                  setConfirmRepoRemove(false);
                  await handleRemoveStudentRepo();
                }}
              />
            )}

            {!viewOnly && assessmentId && (
              <RecordingPanel assessmentId={assessmentId} />
            )}
            {assessmentId && (
              <TransparencyPanel
                assessmentId={assessmentId}
                refreshKey={auditRefresh}
              />
            )}
            <AIInsightsPanel moduleId={moduleId} studentId={studentId} />
          </div>
        </div>
      </div>
    </div>
  );
}
