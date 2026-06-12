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
  Quote,
  Shield,
} from 'lucide-react';
import {
  getEvidenceMatches,
  runEvidenceMatching,
} from '@/lib/api/evidenceMatching';

function confidenceLabel(score) {
  if (score == null) return null;
  return `${Math.round(score * 100)}%`;
}

function CriterionRow({ criterion }) {
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
                  <span className="flex items-center gap-1.5 text-xs font-semibold text-foreground font-mono truncate">
                    <FileText size={12} className="text-muted-foreground shrink-0" />
                    {match.file_name || 'Evidence'}
                  </span>
                  {confidenceLabel(match.confidence_score) && (
                    <span className="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold bg-primary/10 text-primary ring-1 ring-primary/20">
                      {confidenceLabel(match.confidence_score)} match
                    </span>
                  )}
                </div>
                {match.supporting_quote && (
                  <div className="flex gap-2 rounded bg-background border border-border px-3 py-2">
                    <Quote size={12} className="text-muted-foreground mt-0.5 shrink-0" />
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
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');
  const [hasRun, setHasRun] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const report = await getEvidenceMatches(studentId);
      const list = report?.criteria ?? [];
      setCriteria(list);
      setHasRun(list.length > 0);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [studentId]);

  useEffect(() => {
    if (studentId) load();
  }, [studentId, load]);

  const handleRun = async () => {
    setError('');
    setRunning(true);
    try {
      const report = await runEvidenceMatching(studentId, moduleId);
      setCriteria(report?.criteria ?? []);
      setHasRun(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning(false);
    }
  };

  const coveredCount = criteria.filter((c) => c.covered).length;

  return (
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
        <button
          onClick={handleRun}
          disabled={running}
          className="shrink-0 inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-colors cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {running ? (
            <span className="w-3.5 h-3.5 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
          ) : (
            <Sparkles size={13} />
          )}
          {running ? 'Matching…' : hasRun ? 'Re-run matching' : 'Run AI matching'}
        </button>
      </div>

      <div className="p-4 space-y-3">
        <div className="flex items-start gap-2 rounded-md bg-secondary border border-border p-3">
          <Shield size={12} className="text-muted-foreground mt-0.5 shrink-0" />
          <p className="text-[11px] text-muted-foreground leading-relaxed">
            Quotes are taken verbatim from the evidence (never invented); a local
            AI model then checks whether each genuinely supports the criterion.
            Runs on-premises and never assigns grades — the final judgement stays
            with you.
          </p>
        </div>

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
            <Sparkles size={18} className="text-muted-foreground mx-auto mb-2" />
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
            <CriterionRow key={criterion.criterion_key} criterion={criterion} />
          ))
        )}
      </div>
    </div>
  );
}
