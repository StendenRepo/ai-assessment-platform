'use client';

import { useState, useEffect, useRef } from 'react';
import { useParams } from 'next/navigation';
import {
  AlertTriangle,
  Lightbulb,
  Activity,
  ChevronDown,
  ChevronRight,
  Shield,
  Bot,
  Upload,
  FileText,
  XCircle,
  Trash2,
} from 'lucide-react';
import {
  mockContributions,
  mockCriteria,
  mockAIInsights,
} from '@/lib/mockData';
import { authHeaders } from '@/lib/auth';
import RecordingPanel from '@/components/recording/RecordingPanel';
import { resolveAssessmentForStudent } from '@/lib/recording';

const API_BASE_STUDENT =
  process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
import { listProjectStudents } from '@/lib/modulesApi';

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
  suggestion: {
    icon: Lightbulb,
    label: 'Suggestion',
    severityColors: {
      high: 'bg-blue-500/10 text-blue-400 ring-1 ring-blue-500/20',
      medium: 'bg-blue-500/10 text-blue-400 ring-1 ring-blue-500/20',
      low: 'bg-secondary text-muted-foreground ring-1 ring-border',
    },
  },
  anomaly: {
    icon: Activity,
    label: 'Anomaly',
    severityColors: {
      high: 'bg-orange-500/10 text-orange-400 ring-1 ring-orange-500/20',
      medium: 'bg-orange-500/10 text-orange-400 ring-1 ring-orange-500/20',
      low: 'bg-secondary text-muted-foreground ring-1 ring-border',
    },
  },
};

function AIInsightsPanel({ studentId }) {
  const insights = mockAIInsights.filter((i) =>
    i.affectedStudents.includes(studentId)
  );
  const [expanded, setExpanded] = useState(null);

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
            {insights.length} finding{insights.length !== 1 ? 's' : ''}
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

        {insights.length === 0 ? (
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
          insights.map((insight) => {
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
                    {insight.sourceFiles.length > 0 && (
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

// ─── Markdown Evidence Upload ─────────────────────────────────────────────────

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

const UUID_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function EvidenceUpload({ studentId }) {
  const fileInputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  // All evidence for this student (existing + newly uploaded this session)
  const [allEvidence, setAllEvidence] = useState([]);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [error, setError] = useState(null);
  // Allowed extensions fetched from the backend — starts with a safe default
  const [allowedExtensions, setAllowedExtensions] = useState(['.md']);

  const isValidUUID = UUID_REGEX.test(studentId);

  // Fetch supported types from the API on mount (only when we have a real UUID)
  useEffect(() => {
    if (!isValidUUID) return;
    fetch(`${API_BASE}/api/v1/evidence/supported-types`)
      .then((r) => r.json())
      .then((data) => {
        if (Array.isArray(data.supported_extensions)) {
          setAllowedExtensions(data.supported_extensions);
        }
      })
      .catch(() => {
        // Keep the default if the request fails
      });
  }, [isValidUUID]);

  // Fetch existing evidence for this student on mount
  useEffect(() => {
    if (!isValidUUID) return;
    const load = async () => {
      setEvidenceLoading(true);
      try {
        const r = await fetch(
          `${API_BASE}/api/v1/students/${studentId}/evidence`,
          { headers: authHeaders() }
        );
        const data = r.ok ? await r.json() : [];
        setAllEvidence(Array.isArray(data) ? data : []);
      } catch {
        setAllEvidence([]);
      } finally {
        setEvidenceLoading(false);
      }
    };
    load();
  }, [studentId, isValidUUID]);

  // Guard: only render the upload UI when studentId is a real UUID
  if (!isValidUUID) {
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

  const handleFile = async (file) => {
    setError(null);
    if (!isAllowed(file.name)) {
      setError(
        `Unsupported file type. Allowed: ${allowedExtensions.join(', ')}`
      );
      return;
    }

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);

      const res = await fetch(
        `${API_BASE}/api/v1/students/${studentId}/evidence`,
        {
          method: 'POST',
          headers: authHeaders(),
          body: formData,
        }
      );

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? `Upload failed (${res.status})`);
      }

      const data = await res.json();
      setAllEvidence((prev) => [data, ...prev]);
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  };

  const onInputChange = (e) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    e.target.value = '';
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  };

  const handleDelete = async (evidenceId) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/evidence/${evidenceId}`, {
        method: 'DELETE',
        headers: authHeaders(),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? `Delete failed (${res.status})`);
      }
      setAllEvidence((prev) => prev.filter((ev) => ev.id !== evidenceId));
    } catch (err) {
      setError(err.message);
    }
  };

  // Build the <input accept> string from the dynamic list
  const acceptAttr = allowedExtensions.join(',');

  return (
    <div className="rounded-lg border border-border overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-3 px-5 py-4 border-b border-border bg-secondary/30">
        <div className="w-7 h-7 rounded-md bg-primary/10 flex items-center justify-center">
          <Upload size={13} className="text-primary" />
        </div>
        <div>
          <p className="text-sm font-semibold text-foreground">
            Upload Evidence
          </p>
          <p className="text-[11px] text-muted-foreground">
            Accepted:{' '}
            <code className="font-mono">{allowedExtensions.join(', ')}</code>
          </p>
        </div>
      </div>

      <div className="p-5 space-y-4">
        {/* Drop zone */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-8 cursor-pointer transition-colors ${
            dragOver
              ? 'border-primary bg-primary/5'
              : 'border-border hover:border-primary/50 hover:bg-secondary/50'
          }`}
        >
          <Upload
            size={22}
            className={dragOver ? 'text-primary' : 'text-muted-foreground'}
          />
          <p className="text-sm font-medium text-foreground">
            {uploading ? 'Uploading…' : 'Drop a file here or click to browse'}
          </p>
          <p className="text-xs text-muted-foreground">
            Accepted: {allowedExtensions.join(', ')}
          </p>
          <input
            ref={fileInputRef}
            type="file"
            accept={acceptAttr}
            className="hidden"
            onChange={onInputChange}
          />
        </div>

        {/* Error */}
        {error && (
          <div className="flex items-center gap-2 rounded-md bg-red-500/10 border border-red-500/20 px-3 py-2">
            <XCircle size={13} className="text-red-400 shrink-0" />
            <p className="text-xs text-red-400">{error}</p>
          </div>
        )}

        {/* All evidence list */}
        <div className="space-y-2">
          <p className="text-xs font-semibold text-foreground uppercase tracking-wide">
            Evidence ({allEvidence.length})
          </p>
          {evidenceLoading ? (
            <div className="flex justify-center py-4">
              <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            </div>
          ) : allEvidence.length === 0 ? (
            <p className="text-xs text-muted-foreground py-2">
              No evidence uploaded yet.
            </p>
          ) : (
            allEvidence.map((ev) => (
              <div
                key={ev.id}
                className="flex items-center gap-3 rounded-md bg-card border border-border px-3 py-2.5"
              >
                <FileText size={14} className="text-primary shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-semibold text-foreground font-mono truncate">
                    {ev.file_name}
                  </p>
                  <p className="text-[10px] text-muted-foreground">
                    {new Date(ev.uploaded_at).toLocaleString('nl-NL')}
                    {' · '}
                    <span className="capitalize">{ev.file_type}</span>
                    {' · '}
                    <span className="capitalize">{ev.embedding_status}</span>
                  </p>
                </div>
                <button
                  onClick={() => handleDelete(ev.id)}
                  title="Delete evidence"
                  className="shrink-0 p-1 rounded text-muted-foreground hover:text-red-400 hover:bg-red-500/10 transition-colors"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Student Assessment Page ──────────────────────────────────────────────────

const contributionTypeLabel = {
  code: 'CODE',
  documentation: 'DOC',
  presentation: 'PRES',
  research: 'RES',
};
const contributionTypeColor = {
  code: 'bg-blue-500/10 text-blue-400',
  documentation: 'bg-violet-500/10 text-violet-400',
  presentation: 'bg-amber-500/10 text-amber-400',
  research: 'bg-emerald-500/10 text-emerald-400',
};

export default function StudentAssessmentPage() {
  const { moduleId, studentId } = useParams();
  const [student, setStudent] = useState(null);
  const [loadError, setLoadError] = useState('');
  const [currentTab, setCurrentTab] = useState(0);
  const [expanded, setExpanded] = useState(null);
  const [scores, setScores] = useState({});
  const [comments, setComments] = useState({});
  const [assessmentId, setAssessmentId] = useState(null);

  useEffect(() => {
    listProjectStudents(moduleId)
      .then((students) => {
        const found = students.find((s) => s.id === studentId);
        if (found) setStudent(found);
        else setLoadError('Student not found in this module.');
      })
      .catch((e) => setLoadError(e.message));
  }, [moduleId, studentId]);

  // Resolve (or lazily create) the assessment for this student so the recording
  // panel has a real assessment id to drive the recording/consent endpoints.
  useEffect(() => {
    let active = true;
    resolveAssessmentForStudent(studentId)
      .then((s) => active && setAssessmentId(s.assessment_id))
      .catch((e) => active && setLoadError(e.message));
    return () => {
      active = false;
    };
  }, [studentId]);

  if (loadError)
    return <div className="text-sm text-red-400 p-4">{loadError}</div>;

  if (!student)
    return (
      <div className="flex justify-center py-20">
        <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );

  const overallScore =
    Object.values(scores).length > 0
      ? (
          Object.values(scores).reduce((a, b) => a + b, 0) /
          Object.values(scores).length
        ).toFixed(1)
      : '—';

  return (
    <div className="space-y-6">
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
          <div className="text-center border-l border-border pl-6 shrink-0">
            <div className="text-xs text-muted-foreground mb-1">
              Current Score
            </div>
            <div className="text-3xl font-bold text-foreground font-mono">
              {overallScore}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2">
          <div className="rounded-lg bg-card border border-border overflow-hidden">
            <div className="flex border-b border-border">
              {['Contributions & Evidence', 'Assessment'].map((tab, i) => (
                <button
                  key={tab}
                  onClick={() => setCurrentTab(i)}
                  className={`px-6 py-3.5 text-sm font-medium transition-all border-b-2 cursor-pointer ${currentTab === i ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-foreground'}`}
                >
                  {tab}
                </button>
              ))}
            </div>

            <div className="p-6">
              {currentTab === 0 && (
                <div className="space-y-6">
                  <div className="space-y-3">
                    <div className="mb-4">
                      <h3 className="text-sm font-semibold text-foreground">
                        Detected Contributions
                      </h3>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        AI-detected contributions linked to supporting evidence
                      </p>
                    </div>
                    {mockContributions.map((contrib) => (
                      <div
                        key={contrib.id}
                        className="rounded-lg border border-border overflow-hidden"
                      >
                        <button
                          onClick={() =>
                            setExpanded(
                              expanded === contrib.id ? null : contrib.id
                            )
                          }
                          className="w-full flex items-center gap-4 px-5 py-4 hover:bg-secondary/50 transition-colors text-left cursor-pointer"
                        >
                          <span
                            className={`rounded-md px-2 py-1 text-[10px] font-bold tracking-wide shrink-0 ${contributionTypeColor[contrib.type]}`}
                          >
                            {contributionTypeLabel[contrib.type]}
                          </span>
                          {expanded === contrib.id ? (
                            <ChevronDown
                              size={15}
                              className="text-muted-foreground shrink-0"
                            />
                          ) : (
                            <ChevronRight
                              size={15}
                              className="text-muted-foreground shrink-0"
                            />
                          )}
                        </button>
                        {expanded === contrib.id && (
                          <div className="border-t border-border bg-secondary/30 p-5 space-y-4">
                            <p className="text-sm text-muted-foreground">
                              {contrib.description}
                            </p>
                            <div>
                              <p className="text-xs font-semibold text-foreground mb-2">
                                Evidence ({contrib.evidenceFiles.length})
                              </p>
                              <div className="space-y-2">
                                {contrib.evidenceFiles.map((ev) => (
                                  <div
                                    key={ev.id}
                                    className="rounded-md bg-card border border-border p-3"
                                  >
                                    <div className="flex items-center justify-between mb-2">
                                      <span className="text-xs font-semibold text-foreground font-mono">
                                        {ev.fileName}
                                      </span>
                                      <button className="text-xs text-primary hover:text-primary/80 transition-colors cursor-pointer">
                                        View source →
                                      </button>
                                    </div>
                                    {ev.excerpt && (
                                      <div className="rounded bg-background border border-border px-3 py-2 text-xs font-mono text-muted-foreground mb-2">
                                        {ev.excerpt}
                                      </div>
                                    )}
                                    <div className="text-[10px] text-muted-foreground">
                                      Uploaded{' '}
                                      {new Date(
                                        ev.uploadDate
                                      ).toLocaleDateString('en-US')}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                            {contrib.linkedCriteria.length > 0 && (
                              <div>
                                <p className="text-xs font-semibold text-foreground mb-2">
                                  Linked Criteria
                                </p>
                                <div className="flex flex-wrap gap-1.5">
                                  {contrib.linkedCriteria.map((cid) => {
                                    const c = mockCriteria.find(
                                      (x) => x.id === cid
                                    );
                                    return c ? (
                                      <span
                                        key={cid}
                                        className="rounded-full px-2.5 py-0.5 text-xs bg-primary/10 text-primary ring-1 ring-primary/20"
                                      >
                                        {c.name}
                                      </span>
                                    ) : null;
                                  })}
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>

                  <EvidenceUpload studentId={studentId} />
                </div>
              )}

              {currentTab === 1 && (
                <div className="space-y-4">
                  <div className="mb-4">
                    <h3 className="text-sm font-semibold text-foreground">
                      Assessment Criteria
                    </h3>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Enter a score and explanation for each criterion
                    </p>
                  </div>
                  {mockCriteria.map((criterion) => (
                    <div
                      key={criterion.id}
                      className="rounded-lg border border-border p-5"
                    >
                      <div className="flex items-start justify-between mb-4">
                        <div>
                          <h4 className="text-sm font-semibold text-foreground">
                            {criterion.name}
                          </h4>
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {criterion.description}
                          </p>
                        </div>
                        <span className="shrink-0 rounded-full px-2.5 py-0.5 text-xs bg-secondary text-muted-foreground ring-1 ring-border ml-4">
                          {criterion.category}
                        </span>
                      </div>
                      <div className="grid grid-cols-4 gap-4">
                        <div>
                          <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                            Score (max {criterion.maxScore})
                          </label>
                          <input
                            type="number"
                            min="0"
                            max={criterion.maxScore}
                            step="0.5"
                            value={scores[criterion.id] ?? ''}
                            onChange={(e) => {
                              const v = parseFloat(e.target.value);
                              if (!isNaN(v))
                                setScores((s) => ({ ...s, [criterion.id]: v }));
                            }}
                            placeholder="0"
                            className="w-full bg-secondary border border-border rounded-md px-3 py-2 text-sm text-foreground font-mono placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all"
                          />
                        </div>
                        <div className="col-span-3">
                          <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                            Explanation
                          </label>
                          <textarea
                            rows={2}
                            value={comments[criterion.id] ?? ''}
                            onChange={(e) =>
                              setComments((c) => ({
                                ...c,
                                [criterion.id]: e.target.value,
                              }))
                            }
                            placeholder="Provide your reasoning..."
                            className="w-full bg-secondary border border-border rounded-md px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all resize-none"
                          />
                        </div>
                      </div>
                    </div>
                  ))}
                  <div className="flex gap-3 justify-end pt-2">
                    <button className="px-4 py-2 rounded-md border border-border text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all cursor-pointer">
                      Save Draft
                    </button>
                    <button className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors cursor-pointer">
                      Complete Assessment
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="col-span-1 space-y-4">
          <div className="sticky top-4 space-y-4">
            {assessmentId && <RecordingPanel assessmentId={assessmentId} />}
            <AIInsightsPanel studentId={studentId} />
          </div>
        </div>
      </div>
    </div>
  );
}
