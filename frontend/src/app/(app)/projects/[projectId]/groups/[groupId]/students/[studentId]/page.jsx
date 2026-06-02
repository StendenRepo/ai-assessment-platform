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
  Mic,
  MicOff,
  Pause,
  Play,
  Square,
} from 'lucide-react';
import {
  mockStudents,
  mockContributions,
  mockCriteria,
} from '@/lib/mockData';
import { platformApi } from '@/lib/platformApi';
import AssessmentChatWidget from '@/components/assessment/AssessmentChatWidget';
import DraftSuggestionsPanel from '@/components/assessment/DraftSuggestionsPanel';

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

function AIInsightsPanel({ insights = [] }) {
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
  const { projectId, groupId, studentId } = useParams();
  const student = mockStudents.find((s) => s.id === studentId);
  const [aiInsights, setAiInsights] = useState([]);
  const [workspace, setWorkspace] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [currentTab, setCurrentTab] = useState(0);
  const [expanded, setExpanded] = useState(null);
  const [scores, setScores] = useState({});
  const [comments, setComments] = useState({});
  const [showConsent, setShowConsent] = useState(false);
  const [consentGiven, setConsentGiven] = useState(false);
  const [consentSaving, setConsentSaving] = useState(false);
  const [transcriptNote, setTranscriptNote] = useState(null);
  const transcriptInputRef = useRef(null);
  const [isRecording, setIsRecording] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef(null);

  useEffect(() => {
    if (isRecording && !isPaused) {
      timerRef.current = setInterval(() => setElapsed((t) => t + 1), 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isRecording, isPaused]);

  const loadAiData = () => {
    platformApi
      .ensureGroup(projectId, groupId)
      .catch(() => {})
      .finally(() => {
        Promise.all([
          platformApi.getInsights(projectId, groupId, studentId),
          platformApi.getStudentWorkspace(projectId, groupId, studentId),
        ])
          .then(([ins, ws]) => {
            setAiInsights(ins.insights || []);
            setWorkspace(ws);
            setConsentGiven(Boolean(ws.consent_given));
            setLoadError(null);
          })
          .catch((e) => setLoadError(e.message));
      });
  };

  useEffect(() => {
    loadAiData();
  }, [projectId, groupId, studentId]);

  const oralQuestions = workspace?.analysis?.questions || [];

  if (!student)
    return <div className="text-muted-foreground">Student not found</div>;

  const overallScore =
    Object.values(scores).length > 0
      ? (
          Object.values(scores).reduce((a, b) => a + b, 0) /
          Object.values(scores).length
        ).toFixed(1)
      : '—';

  const formatTime = (s) =>
    `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;

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
              {student.studentNumber} · {student.email}
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
          <div className="flex flex-wrap items-center gap-2 shrink-0">
            <a
              href={platformApi.exportZipUrl(projectId, groupId, studentId)}
              className="px-4 py-2 rounded-md border border-border text-sm font-semibold text-foreground hover:bg-secondary transition-colors"
            >
              Export ZIP
            </a>
            <a
              href={platformApi.exportEmlUrl(projectId, groupId, studentId)}
              className="px-4 py-2 rounded-md border border-border text-sm font-semibold text-foreground hover:bg-secondary transition-colors"
            >
              Export EML
            </a>
            {!isRecording && (
              <button
                onClick={() => setShowConsent(true)}
                className="flex items-center gap-2 px-4 py-2.5 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors"
              >
                <Mic size={15} /> Start Assessment
              </button>
            )}
          </div>
        </div>
      </div>

      {loadError && (
        <p className="text-sm text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-md px-4 py-2">
          {loadError} — run analysis on the group page first.
        </p>
      )}

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2">
          <div className="rounded-lg bg-card border border-border overflow-hidden">
            <div className="flex border-b border-border">
              {['Contributions & Evidence', 'Assessment'].map((tab, i) => (
                <button
                  key={tab}
                  onClick={() => setCurrentTab(i)}
                  className={`px-6 py-3.5 text-sm font-medium transition-all border-b-2 ${currentTab === i ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-foreground'}`}
                >
                  {tab}
                </button>
              ))}
            </div>

            <div className="p-6">
              {currentTab === 0 && (
                <div className="space-y-3">
                  <div className="mb-4">
                    <h3 className="text-sm font-semibold text-foreground">
                      Evidence & contributions
                    </h3>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Uploaded evidence from the group workspace; mock contributions below when no analysis yet
                    </p>
                  </div>
                  {workspace?.evidence?.length > 0 && (
                    <div className="rounded-lg border border-border divide-y divide-border mb-4">
                      {workspace.evidence.map((ev) => (
                        <div key={ev.id} className="px-5 py-3 flex items-center justify-between gap-3">
                          <span className="text-xs font-mono text-foreground truncate">
                            {ev.filename}
                          </span>
                          <span className="text-[10px] text-muted-foreground shrink-0">
                            {ev.file_type}
                            {ev.uploaded_at
                              ? ` · ${new Date(ev.uploaded_at).toLocaleDateString('en-US')}`
                              : ''}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                  {workspace?.transcript && (
                    <div className="rounded-md bg-secondary border border-border p-3 mb-4">
                      <p className="text-xs font-semibold text-foreground mb-1">
                        Session transcript
                      </p>
                      <p className="text-xs text-muted-foreground whitespace-pre-wrap line-clamp-4">
                        {workspace.transcript}
                      </p>
                    </div>
                  )}
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
                        className="w-full flex items-center gap-4 px-5 py-4 hover:bg-secondary/50 transition-colors text-left"
                      >
                        <span
                          className={`rounded-md px-2 py-1 text-[10px] font-bold tracking-wide shrink-0 ${contributionTypeColor[contrib.type]}`}
                        >
                          {contributionTypeLabel[contrib.type]}
                        </span>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-semibold text-foreground">
                            {contrib.title}
                          </div>
                          <div className="text-xs text-muted-foreground mt-0.5">
                            {contrib.evidenceFiles.length} evidence file
                            {contrib.evidenceFiles.length !== 1 ? 's' : ''}
                          </div>
                        </div>
                        {contrib.aiConfidence && (
                          <span className="text-xs rounded-full px-2.5 py-1 bg-accent/10 text-accent ring-1 ring-accent/20 font-medium shrink-0">
                            AI {(contrib.aiConfidence * 100).toFixed(0)}%
                          </span>
                        )}
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
                                    <button className="text-xs text-primary hover:text-primary/80 transition-colors">
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
                                    {new Date(ev.uploadDate).toLocaleDateString(
                                      'en-US'
                                    )}
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
              )}

              {currentTab === 1 && (
                <div className="space-y-6">
                  <div className="space-y-3">
                    <div>
                      <h3 className="text-sm font-semibold text-foreground">
                        AI draft suggestions
                      </h3>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        Edit AI-generated text before scoring criteria
                      </p>
                    </div>
                    <DraftSuggestionsPanel
                      projectId={projectId}
                      groupId={groupId}
                      studentId={studentId}
                      draftForm={workspace?.draft_form}
                      onSaved={loadAiData}
                    />
                  </div>
                  {oralQuestions.length > 0 && (
                    <div className="space-y-3 pt-2 border-t border-border">
                      <div>
                        <h3 className="text-sm font-semibold text-foreground">
                          Oral exam questions
                        </h3>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          Suggested questions from analysis
                        </p>
                      </div>
                      <ul className="space-y-3">
                        {oralQuestions.map((q, i) => (
                          <li
                            key={i}
                            className="rounded-lg border border-border p-4"
                          >
                            <p className="text-sm text-foreground leading-relaxed">
                              {q.question}
                            </p>
                            {q.criterion && (
                              <span className="inline-flex mt-2 rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide bg-secondary text-muted-foreground ring-1 ring-border">
                                {q.criterion}
                              </span>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  <div className="pt-4 border-t border-border">
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
                    <button className="px-4 py-2 rounded-md border border-border text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all">
                      Save Draft
                    </button>
                    <button className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors">
                      Complete Assessment
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="col-span-1 space-y-4">
          {isRecording && (
            <div className="rounded-lg bg-card border border-border p-5 space-y-4 sticky top-4">
              <h3 className="text-sm font-semibold text-foreground">
                Recording
              </h3>
              <div className="rounded-lg bg-red-500/5 border border-red-500/20 p-4 space-y-2">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                  <span className="text-xs font-semibold text-red-400 uppercase tracking-wide">
                    {isPaused ? 'Paused' : 'Recording'}
                  </span>
                </div>
                <div className="text-2xl font-bold text-foreground font-mono">
                  {formatTime(elapsed)}
                </div>
              </div>
              <div className="space-y-2">
                <button
                  onClick={() => setIsPaused((p) => !p)}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-md border border-border text-sm font-medium text-foreground hover:bg-secondary transition-all"
                >
                  {isPaused ? <Play size={14} /> : <Pause size={14} />}
                  {isPaused ? 'Resume' : 'Pause'}
                </button>
                <input
                  ref={transcriptInputRef}
                  type="file"
                  className="hidden"
                  accept=".txt,.md"
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (!file) return;
                    try {
                      await platformApi.uploadTranscript(
                        projectId,
                        groupId,
                        studentId,
                        file
                      );
                      setTranscriptNote('Transcript uploaded');
                      loadAiData();
                    } catch (err) {
                      setTranscriptNote(err.message);
                    }
                    e.target.value = '';
                  }}
                />
                <button
                  onClick={async () => {
                    const duration = formatTime(elapsed);
                    const blob = new Blob(
                      [
                        `Assessment session recording note\nDuration: ${duration}\nStudent: ${student.name}\nRecorded at: ${new Date().toISOString()}\n`,
                      ],
                      { type: 'text/plain' }
                    );
                    const file = new File([blob], `session-${studentId}.txt`, {
                      type: 'text/plain',
                    });
                    try {
                      await platformApi.uploadTranscript(
                        projectId,
                        groupId,
                        studentId,
                        file
                      );
                      setTranscriptNote(`Session saved (${duration})`);
                      loadAiData();
                    } catch (err) {
                      setTranscriptNote(err.message);
                    }
                    setIsRecording(false);
                    setElapsed(0);
                    setIsPaused(false);
                  }}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-md bg-foreground text-background text-sm font-semibold hover:bg-foreground/90 transition-colors"
                >
                  <Square size={14} /> Stop & Save
                </button>
                <button
                  type="button"
                  onClick={() => transcriptInputRef.current?.click()}
                  className="w-full text-xs text-primary hover:text-primary/80"
                >
                  Upload transcript file instead
                </button>
                {transcriptNote && (
                  <p className="text-[11px] text-muted-foreground">{transcriptNote}</p>
                )}
              </div>
              <div className="flex items-start gap-2 rounded-md bg-secondary border border-border p-3">
                <Shield
                  size={12}
                  className="text-muted-foreground mt-0.5 shrink-0"
                />
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  Recording stored securely on-premises. Accessible only to
                  authorized personnel.
                </p>
              </div>
            </div>
          )}
          <AIInsightsPanel insights={aiInsights} />
        </div>
      </div>

      <AssessmentChatWidget
        projectId={projectId}
        groupId={groupId}
        studentId={studentId}
        studentName={student.name}
      />

      {showConsent && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-card border border-border rounded-xl p-7 max-w-md w-full shadow-2xl">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center">
                <Mic size={16} className="text-primary" />
              </div>
              <h3 className="text-lg font-bold text-foreground">
                Recording Consent Required
              </h3>
            </div>
            <div className="space-y-3 text-sm text-muted-foreground mb-6">
              <p>
                Before starting, we need your consent to record this assessment
                session.
              </p>
              <p>
                The recording includes audio and video, used solely for
                assessment purposes and stored securely in accordance with GDPR
                guidelines.
              </p>
            </div>
            <label className="flex items-start gap-3 rounded-lg bg-secondary border border-border p-4 cursor-pointer mb-6">
              <input
                type="checkbox"
                checked={consentGiven}
                onChange={(e) => setConsentGiven(e.target.checked)}
                className="mt-0.5 w-4 h-4 accent-primary"
              />
              <span className="text-sm text-foreground">
                I consent to this session being recorded for assessment purposes
                and confirm I understand it will be handled in accordance with
                GDPR regulations.
              </span>
            </label>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => {
                  setShowConsent(false);
                  setConsentGiven(false);
                }}
                className="px-4 py-2 rounded-md border border-border text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all"
              >
                Cancel
              </button>
              <button
                disabled={!consentGiven || consentSaving}
                onClick={async () => {
                  setConsentSaving(true);
                  try {
                    await platformApi.recordConsent(
                      projectId,
                      groupId,
                      studentId,
                      true,
                      'Dev UI oral assessment'
                    );
                    setShowConsent(false);
                    setIsRecording(true);
                  } catch (err) {
                    setLoadError(err.message);
                  } finally {
                    setConsentSaving(false);
                  }
                }}
                className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-semibold transition-all ${consentGiven && !consentSaving ? 'bg-primary text-primary-foreground hover:bg-primary/90' : 'bg-secondary text-muted-foreground cursor-not-allowed'}`}
              >
                <Mic size={14} />{' '}
                {consentSaving ? 'Saving…' : 'Start Recording'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
