'use client';

import { useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, FileText } from 'lucide-react';
import { matchStyle } from '@/components/overlaps/AnnotatedDocument';

function pct(confidence) {
  if (confidence == null) return null;
  const n = confidence <= 1 ? Math.round(confidence * 100) : Math.round(confidence);
  return n;
}


function MatchExcerpt({ text, palette, label }) {
  if (!text) {
    return (
      <p className="text-xs text-muted-foreground italic">No excerpt available.</p>
    );
  }
  return (
    <div className="min-h-0 flex flex-col h-full">
      <p className="text-[9px] font-semibold uppercase tracking-wide text-muted-foreground mb-1 shrink-0">
        {label}
      </p>
      <div
        className={`flex-1 min-h-0 overflow-y-auto text-xs leading-relaxed rounded-md border px-3 py-2 whitespace-pre-wrap text-foreground ${palette.mark}`}
      >
        {text}
      </div>
    </div>
  );
}

function MatchJumpList({ entries, activeId, onSelect }) {
  if (!entries.length) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {entries.map((entry) => {
        const palette = matchStyle(entry.matchId);
        const isActive = activeId === entry.matchId;
        return (
          <button
            key={entry.matchId}
            type="button"
            onClick={() => onSelect(entry.matchId)}
            className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-medium transition-colors ${
              isActive
                ? 'border-primary/50 bg-primary/10 text-foreground'
                : 'border-border bg-secondary/30 text-muted-foreground hover:text-foreground hover:bg-secondary/50'
            }`}
          >
            <span
              className={`flex h-5 w-5 items-center justify-center rounded-full border text-[10px] font-bold ${palette.swatch}`}
            >
              {entry.matchId}
            </span>
            {pct(entry.confidence) != null && (
              <span className="font-mono text-[10px] opacity-80">
                {pct(entry.confidence)}%
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

function StudentMatchPanel({
  entry,
  leftLabel,
  rightLabel,
  onViewInDocument,
  compact = false,
}) {
  const palette = matchStyle(entry.matchId);
  const confidence = pct(entry.confidence);

  return (
    <article
      className={`rounded-lg border border-border bg-card overflow-hidden flex flex-col min-h-0 ${
        compact ? 'flex-1' : ''
      }`}
    >
      <div className="px-3 py-2 border-b border-border/60 bg-secondary/10 shrink-0 flex items-center gap-2">
        <span
          className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[11px] font-bold ${palette.swatch}`}
        >
          {entry.matchId}
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="text-xs font-semibold text-foreground truncate">
            Match {entry.matchId}
            {entry.reason && (
              <span className="font-normal text-muted-foreground ml-1">
                — {entry.reason}
              </span>
            )}
          </h3>
        </div>
        {confidence != null && (
          <span className="text-[10px] font-mono text-muted-foreground shrink-0">
            {confidence}%
          </span>
        )}
        {onViewInDocument && (
          <button
            type="button"
            onClick={() => onViewInDocument(entry.matchId)}
            className="inline-flex items-center gap-1 rounded border border-border bg-secondary/30 px-2 py-1 text-[10px] font-medium text-foreground hover:bg-secondary/50 shrink-0"
          >
            <FileText size={11} className="text-primary" />
            Full doc
          </button>
        )}
      </div>

      <div
        className={`p-3 min-h-0 ${
          compact ? 'flex-1 grid grid-cols-1 lg:grid-cols-2 gap-3' : 'grid grid-cols-1 lg:grid-cols-2 gap-4'
        }`}
      >
        <MatchExcerpt
          label={leftLabel}
          text={entry.text_a || entry.text}
          palette={palette}
        />
        <MatchExcerpt
          label={rightLabel}
          text={entry.text_b || entry.text}
          palette={palette}
        />
      </div>
    </article>
  );
}

function AiFlagCard({ flag, index }) {
  const confidence = pct(flag.confidence);
  return (
    <article className="rounded-xl border border-violet-500/25 bg-violet-500/[0.04] overflow-hidden">
      <div className="px-5 py-4 border-b border-violet-500/20 bg-violet-500/[0.06]">
        <div className="flex flex-wrap items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-violet-500/40 bg-violet-500/20 text-[10px] font-bold uppercase text-violet-300">
            AI
          </span>
          <h3 className="text-base font-semibold text-foreground">
            AI-generated section {index + 1}
          </h3>
          {confidence != null && (
            <span className="ml-auto text-sm font-mono text-muted-foreground">
              {confidence}%
            </span>
          )}
        </div>
        {flag.reason && (
          <p className="text-sm text-muted-foreground mt-2 pl-12">{flag.reason}</p>
        )}
      </div>
      <div className="p-5">
        <p className="text-sm leading-relaxed rounded-lg border border-violet-500/30 bg-violet-500/10 px-4 py-3 whitespace-pre-wrap text-foreground">
          {flag.text}
        </p>
      </div>
    </article>
  );
}

export function buildMatchEntries(flags = []) {
  const student = (flags || [])
    .filter((f) => f.type === 'student')
    .map((f, i) => ({
      matchId: f.match_id ?? i + 1,
      confidence: f.confidence,
      reason: f.reason,
      text_a: f.text_a || f.text || '',
      text_b: f.text_b || '',
    }))
    .sort((a, b) => a.matchId - b.matchId)
    .filter(
      (entry, index, arr) =>
        arr.findIndex((e) => e.matchId === entry.matchId) === index
    );

  const ai = (flags || []).filter((f) => f.type === 'ai' && f.text);
  return { student, ai };
}

export default function OverlapMatchReview({
  flags = [],
  leftLabel,
  rightLabel,
  singlePane = false,
  onViewInDocument,
  compact = false,
}) {
  const { student, ai } = useMemo(() => buildMatchEntries(flags), [flags]);
  const [activeId, setActiveId] = useState(student[0]?.matchId ?? null);

  const activeEntry = student.find((s) => s.matchId === activeId) ?? student[0];

  const navigate = (dir) => {
    if (!student.length) return;
    const ids = student.map((s) => s.matchId);
    const idx = activeId != null ? ids.indexOf(activeId) : -1;
    const next =
      dir < 0
        ? idx <= 0
          ? ids[ids.length - 1]
          : ids[idx - 1]
        : idx < 0 || idx >= ids.length - 1
          ? ids[0]
          : ids[idx + 1];
    setActiveId(next);
  };

  if (!student.length && !ai.length) {
    return (
      <p className="text-sm text-muted-foreground rounded-xl border border-dashed border-border px-6 py-10 text-center">
        No matched passages were extracted for this signal. Switch to full documents
        if submission text is available.
      </p>
    );
  }

  return (
    <div className={`${compact ? 'flex flex-col flex-1 min-h-0 gap-2' : 'space-y-4'}`}>
      {student.length > 0 && activeEntry && (
        <>
          <div className="flex flex-wrap items-center gap-2 shrink-0">
            <MatchJumpList
              entries={student}
              activeId={activeId}
              onSelect={setActiveId}
            />
            <div className="inline-flex items-center gap-0.5 rounded-md border border-border bg-secondary/30 px-0.5 py-0.5 ml-auto">
              <button
                type="button"
                onClick={() => navigate(-1)}
                className="p-1 rounded hover:bg-secondary text-muted-foreground hover:text-foreground"
                aria-label="Previous match"
              >
                <ChevronLeft size={14} />
              </button>
              <span className="text-[10px] font-medium text-foreground px-1.5 min-w-[3.5rem] text-center">
                {activeId != null ? `${activeId}/${student.length}` : student.length}
              </span>
              <button
                type="button"
                onClick={() => navigate(1)}
                className="p-1 rounded hover:bg-secondary text-muted-foreground hover:text-foreground"
                aria-label="Next match"
              >
                <ChevronRight size={14} />
              </button>
            </div>
          </div>

          <StudentMatchPanel
            key={activeEntry.matchId}
            entry={activeEntry}
            leftLabel={leftLabel}
            rightLabel={rightLabel}
            onViewInDocument={onViewInDocument}
            compact={compact}
          />
        </>
      )}

      {ai.length > 0 && (
        <div className="space-y-3 pt-2">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            AI-generated sections
          </h2>
          {ai.map((flag, i) => (
            <AiFlagCard key={`ai-${i}`} flag={flag} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}
