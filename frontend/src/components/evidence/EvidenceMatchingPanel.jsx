'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Bot,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  FileText,
  ExternalLink,
  Quote,
  History,
  Trash2,
  Clock,
} from 'lucide-react';
import {
  getEvidenceMatches,
  runEvidenceMatching,
  deleteEvidenceMatchRun,
} from '@/lib/api/evidenceMatching';
import { useEvidencePreview } from '@/lib/hooks/useEvidencePreview';
import EvidencePreviewDialog from '@/components/evidence/EvidencePreviewDialog';

function confidenceLabel(score) {
  if (score == null) return null;
  return `${Math.round(score * 100)}%`;
}

function formatWhen(iso) {
  if (!iso) return '';
  const utc = /[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`;
  const d = new Date(utc);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function runLabel(run) {
  const when = formatWhen(run.created_at);
  const mode = run.mode === 'thorough' ? 'Thorough' : 'Standard';
  return `${when} · ${mode} · ${run.criteria_covered}/${run.criteria_total}${
    run.expired ? ' · expired' : ''
  }`;
}

function CriterionRow({ criterion, onOpenSource }) {
  const [open, setOpen] = useState(false);
  const covered = criterion.covered;

  return (
    <div className="rounded-lg border border-border overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-secondary/50 transition-colors text-left cursor-pointer"
      >
        {covered ? (
          <CheckCircle2 size={15} className="text-emerald-400 shrink-0" />
        ) : (
          <AlertTriangle size={15} className="text-amber-400 shrink-0" />
        )}
        <span className="flex-1 text-xs font-medium text-foreground leading-snug">
          {criterion.criterion_key}
        </span>
        {covered ? (
          <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20 shrink-0">
            {criterion.matches.length} match
            {criterion.matches.length !== 1 ? 'es' : ''}
          </span>
        ) : (
          <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/20 shrink-0">
            No evidence
          </span>
        )}
        {open ? (
          <ChevronDown size={13} className="text-muted-foreground shrink-0" />
        ) : (
          <ChevronRight size={13} className="text-muted-foreground shrink-0" />
        )}
      </button>

      {open && (
        <div className="border-t border-border bg-secondary/30 px-4 py-3 space-y-3">
          {covered ? (
            criterion.matches.map((match, i) => (
              <div
                key={i}
                className="rounded-md bg-card border border-border p-3 space-y-2"
              >
                <div className="flex items-center justify-between gap-3">
                  {onOpenSource && match.evidence_id ? (
                    <button
                      onClick={() =>
                        onOpenSource(
                          {
                            id: match.evidence_id,
                            file_type: match.file_type,
                            file_name: match.file_name,
                          },
                          match.supporting_quote,
                        )
                      }
                      className="group flex items-center gap-1.5 text-xs font-semibold text-primary font-mono truncate hover:underline cursor-pointer"
                      title="Open the source evidence"
                    >
                      <FileText size={12} className="shrink-0" />
                      <span className="truncate">{match.file_name || 'Evidence'}</span>
                      <ExternalLink size={11} className="shrink-0 opacity-70" />
                    </button>
                  ) : (
                    <span className="flex items-center gap-1.5 text-xs font-semibold text-foreground font-mono truncate">
                      <FileText size={12} className="text-muted-foreground shrink-0" />
                      {match.file_name || 'Evidence'}
                    </span>
                  )}
                  {confidenceLabel(match.confidence_score) && (
                    <span className="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold bg-primary/10 text-primary ring-1 ring-primary/20">
                      {confidenceLabel(match.confidence_score)} match
                    </span>
                  )}
                </div>
                {match.supporting_quote && (
                  <div className="flex gap-2 rounded bg-background border border-border px-3 py-2">
                    <Quote
                      size={12}
                      className="text-muted-foreground mt-0.5 shrink-0"
                    />
                    <p className="text-[11px] text-muted-foreground leading-relaxed italic">
                      {match.supporting_quote}
                    </p>
                  </div>
                )}
                {match.rationale && (
                  <div className="flex gap-2 rounded bg-accent/5 border border-accent/15 px-3 py-2">
                    <Bot size={12} className="text-accent mt-0.5 shrink-0" />
                    <p className="text-[11px] text-muted-foreground leading-relaxed">
                      <span className="font-semibold text-accent">AI:</span>{' '}
                      {match.rationale}
                    </p>
                  </div>
                )}
              </div>
            ))
          ) : (
            <p className="text-[11px] text-muted-foreground leading-relaxed">
              {criterion.missing_note ||
                'No supporting evidence was found for this criterion.'}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export default function EvidenceMatchingPanel({ studentId, moduleId }) {
  const [criteria, setCriteria] = useState([]);
  const [runs, setRuns] = useState([]);
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [mode, setMode] = useState('standard');
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState('');
  const [hasRun, setHasRun] = useState(false);
  const [highlightQuote, setHighlightQuote] = useState(null);

  const {
    previewEvidence,
    previewUrl,
    previewContent,
    previewLoading,
    activePreviewKind,
    basePreviewKind,
    showImageExtractedText,
    openPreview,
    closePreview,
    toggleImageExtractedText,
  } = useEvidencePreview();

  const handleOpenSource = async (evidence, quote) => {
    setError('');
    setHighlightQuote(quote || null);
    try {
      await openPreview(evidence);
    } catch (err) {
      setError(err.message);
    }
  };

  const applyReport = useCallback((report) => {
    const list = report?.criteria ?? [];
    setCriteria(list);
    setRuns(report?.runs ?? []);
    setSelectedRunId(report?.run_id ?? null);
    setHasRun((report?.runs ?? []).length > 0);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      applyReport(await getEvidenceMatches(studentId));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [studentId, applyReport]);

  useEffect(() => {
    if (studentId) load();
  }, [studentId, load]);

  const handleRun = async () => {
    setError('');
    setRunning(true);
    try {
      applyReport(await runEvidenceMatching(studentId, moduleId, mode));
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning(false);
    }
  };

  const handleSelectRun = async (runId) => {
    if (!runId || runId === selectedRunId) return;
    setError('');
    setLoading(true);
    try {
      applyReport(await getEvidenceMatches(studentId, runId));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedRunId) return;
    setError('');
    setDeleting(true);
    try {
      applyReport(await deleteEvidenceMatchRun(studentId, selectedRunId));
    } catch (err) {
      setError(err.message);
    } finally {
      setDeleting(false);
    }
  };

  const coveredCount = criteria.filter((c) => c.covered).length;
  const selectedRun = runs.find((r) => r.run_id === selectedRunId);
  const busy = running || deleting || loading;

  return (
    <>
    <div className="rounded-lg bg-card border border-border overflow-hidden">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-border">
        <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
          <Bot size={14} className="text-accent" />
        </div>
        <div className="flex-1">
          <div className="text-sm font-semibold text-foreground">
            Rubric Coverage
          </div>
          <div className="text-[11px] text-muted-foreground">
            {hasRun
              ? `${coveredCount} of ${criteria.length} criteria have supporting evidence`
              : 'Match this student’s evidence to the rubric criteria'}
          </div>
        </div>
        <div className="shrink-0 inline-flex rounded-md border border-border overflow-hidden">
          {['standard', 'thorough'].map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              disabled={busy}
              className={`px-2.5 py-2 text-[11px] font-semibold capitalize transition-colors cursor-pointer disabled:cursor-not-allowed ${
                mode === m
                  ? 'bg-secondary text-foreground'
                  : 'bg-card text-muted-foreground hover:text-foreground'
              }`}
              title={
                m === 'thorough'
                  ? 'Slower, wider search for more accurate results'
                  : 'Quick pass'
              }
            >
              {m}
            </button>
          ))}
        </div>
        <button
          onClick={handleRun}
          disabled={busy}
          className="shrink-0 inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-colors cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {running ? (
            <span className="w-3.5 h-3.5 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
          ) : (
            <Sparkles size={13} />
          )}
          {running ? 'Matching…' : hasRun ? 'Re-run' : 'Run AI matching'}
        </button>
      </div>

      {hasRun && runs.length > 0 && (
        <div className="flex items-center gap-2 px-5 py-2.5 border-b border-border bg-secondary/30">
          <History size={13} className="text-muted-foreground shrink-0" />
          <select
            value={selectedRunId || ''}
            onChange={(e) => handleSelectRun(e.target.value)}
            disabled={busy}
            className="flex-1 min-w-0 rounded-md border border-border bg-card px-2 py-1.5 text-[11px] text-foreground cursor-pointer disabled:cursor-not-allowed"
          >
            {runs.map((run, i) => (
              <option key={run.run_id} value={run.run_id}>
                {i === 0 ? 'Latest · ' : ''}
                {runLabel(run)}
              </option>
            ))}
          </select>
          {selectedRun?.expired && (
            <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/20 shrink-0">
              <Clock size={10} /> Expired
            </span>
          )}
          <button
            onClick={handleDelete}
            disabled={busy || !selectedRunId}
            className="shrink-0 inline-flex items-center gap-1 px-2 py-1.5 rounded-md border border-border text-[11px] font-semibold text-muted-foreground hover:text-red-400 hover:border-red-500/30 transition-colors cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
            title="Delete this run"
          >
            {deleting ? (
              <span className="w-3 h-3 border-2 border-muted-foreground border-t-transparent rounded-full animate-spin" />
            ) : (
              <Trash2 size={12} />
            )}
            Delete
          </button>
        </div>
      )}

      <div className="p-4 space-y-3">
        {error && (
          <div className="flex items-start gap-2 rounded-md bg-red-500/10 border border-red-500/20 px-3 py-2">
            <AlertTriangle size={12} className="text-red-400 mt-0.5 shrink-0" />
            <p className="text-[11px] text-red-400 leading-relaxed">{error}</p>
          </div>
        )}

        {loading ? (
          <div className="flex justify-center py-6">
            <div className="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        ) : criteria.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border p-6 text-center">
            <Sparkles
              size={18}
              className="text-muted-foreground mx-auto mb-2"
            />
            <p className="text-sm font-medium text-foreground">
              No matching run yet
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Upload the rubric and evidence, then run AI matching to see which
              criteria are covered.
            </p>
          </div>
        ) : (
          criteria.map((criterion) => (
            <CriterionRow
              key={criterion.criterion_key}
              criterion={criterion}
              onOpenSource={handleOpenSource}
            />
          ))
        )}
      </div>
    </div>

    <EvidencePreviewDialog
      evidence={previewEvidence}
      previewKind={activePreviewKind}
      basePreviewKind={basePreviewKind}
      previewUrl={previewUrl}
      previewContent={previewContent}
      loading={previewLoading}
      highlightQuote={highlightQuote}
      showImageExtractedText={showImageExtractedText}
      onToggleImageExtractedText={async () => {
        try {
          await toggleImageExtractedText();
        } catch (err) {
          setError(err.message);
        }
      }}
      onClose={() => {
        setHighlightQuote(null);
        closePreview();
      }}
    />
    </>
  );
}
