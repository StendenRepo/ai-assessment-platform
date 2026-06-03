'use client';

import { useState } from 'react';
import { useParams } from 'next/navigation';
import {
  AlertTriangle,
  Lightbulb,
  Activity,
  ChevronDown,
  ChevronRight,
  Shield,
  Bot,
} from 'lucide-react';
import {
  mockStudents,
  mockContributions,
  mockCriteria,
  mockAIInsights,
} from '@/lib/mockData';
import RecordingPanel from '@/components/recording/RecordingPanel';

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

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
  const { studentId } = useParams();
  const student = mockStudents.find((s) => s.id === studentId);
  const [currentTab, setCurrentTab] = useState(0);
  const [expanded, setExpanded] = useState(null);
  const [scores, setScores] = useState({});
  const [comments, setComments] = useState({});

  // TODO: replace mock students with real assessment data. Recording endpoints
  // are keyed on assessment UUIDs, not the mock student ids used by this page.
  const assessmentId = student?.assessmentId;

  if (!student)
    return <div className="text-muted-foreground">Student not found</div>;

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
          <div className="sticky top-4 space-y-4">
            <RecordingPanel
              assessmentId={assessmentId ?? studentId}
              backendEnabled={UUID_PATTERN.test(assessmentId ?? '')}
            />
            <AIInsightsPanel studentId={studentId} />
          </div>
        </div>
      </div>
    </div>
  );
}
