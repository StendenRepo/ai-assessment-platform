'use client';

import { useMemo } from 'react';

/** Distinct colours for paired student-plagiarism matches (same index = linked across panes). */
export const MATCH_PALETTE = [
  {
    mark: 'bg-sky-500/30 text-foreground border border-sky-500/55',
    badge: 'bg-sky-500/20 text-sky-200 border-sky-500/45',
    swatch: 'bg-sky-500/40 border-sky-500/60',
    ring: 'ring-sky-400/80',
  },
  {
    mark: 'bg-emerald-500/30 text-foreground border border-emerald-500/55',
    badge: 'bg-emerald-500/20 text-emerald-200 border-emerald-500/45',
    swatch: 'bg-emerald-500/40 border-emerald-500/60',
    ring: 'ring-emerald-400/80',
  },
  {
    mark: 'bg-orange-500/30 text-foreground border border-orange-500/55',
    badge: 'bg-orange-500/20 text-orange-200 border-orange-500/45',
    swatch: 'bg-orange-500/40 border-orange-500/60',
    ring: 'ring-orange-400/80',
  },
  {
    mark: 'bg-rose-500/30 text-foreground border border-rose-500/55',
    badge: 'bg-rose-500/20 text-rose-200 border-rose-500/45',
    swatch: 'bg-rose-500/40 border-rose-500/60',
    ring: 'ring-rose-400/80',
  },
  {
    mark: 'bg-cyan-500/30 text-foreground border border-cyan-500/55',
    badge: 'bg-cyan-500/20 text-cyan-200 border-cyan-500/45',
    swatch: 'bg-cyan-500/40 border-cyan-500/60',
    ring: 'ring-cyan-400/80',
  },
  {
    mark: 'bg-fuchsia-500/30 text-foreground border border-fuchsia-500/55',
    badge: 'bg-fuchsia-500/20 text-fuchsia-200 border-fuchsia-500/45',
    swatch: 'bg-fuchsia-500/40 border-fuchsia-500/60',
    ring: 'ring-fuchsia-400/80',
  },
  {
    mark: 'bg-lime-500/30 text-foreground border border-lime-500/55',
    badge: 'bg-lime-500/20 text-lime-200 border-lime-500/45',
    swatch: 'bg-lime-500/40 border-lime-500/60',
    ring: 'ring-lime-400/80',
  },
  {
    mark: 'bg-indigo-500/30 text-foreground border border-indigo-500/55',
    badge: 'bg-indigo-500/20 text-indigo-200 border-indigo-500/45',
    swatch: 'bg-indigo-500/40 border-indigo-500/60',
    ring: 'ring-indigo-400/80',
  },
];

const AI_STYLE = {
  mark: 'bg-violet-500/25 text-foreground border border-violet-500/40',
  badge: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
  swatch: 'bg-violet-500/40 border-violet-500/60',
  ring: 'ring-violet-400/80',
};

const LEGACY_STYLE = {
  mark: 'bg-amber-500/20 text-foreground',
  badge: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  swatch: 'bg-amber-500/40 border-amber-500/60',
  ring: 'ring-amber-400/80',
};

// student:m2:85:reason or ai:85:reason
const TYPED_FLAG_RE =
  /⟦(ai|student):(?:m(\d+):)?(\d+):([^⟧]*)⟧([\s\S]*?)⟦\/\1⟧/g;
const LEGACY_FLAG_RE = /\[\[(.*?)\]\]/g;

export function matchStyle(matchId) {
  if (!matchId) return MATCH_PALETTE[0];
  return MATCH_PALETTE[(matchId - 1) % MATCH_PALETTE.length];
}

export function matchAnchorId(pane, matchId) {
  return `overlap-match-${pane}-${matchId}`;
}

function FlagAnnotation({ type, confidence, reason, matchId }) {
  if (type === 'ai') {
    return (
      <span
        className={`inline-flex items-center gap-1 ml-1.5 px-1.5 py-0.5 rounded text-[10px] font-medium border align-middle not-italic ${AI_STYLE.badge}`}
        title={reason}
      >
        <span className="uppercase tracking-wide">AI-generated</span>
        {confidence != null && (
          <span className="font-mono opacity-80">{confidence}%</span>
        )}
      </span>
    );
  }

  const palette = matchStyle(matchId);
  return (
    <span
      className={`inline-flex items-center gap-1 ml-1.5 px-1.5 py-0.5 rounded text-[10px] font-medium border align-middle not-italic ${palette.badge}`}
      title={reason}
    >
      <span
        className={`inline-flex items-center justify-center w-4 h-4 rounded-full font-bold text-[9px] border ${palette.swatch}`}
      >
        {matchId ?? '?'}
      </span>
      <span className="uppercase tracking-wide">Match</span>
      {confidence != null && (
        <span className="font-mono opacity-80">{confidence}%</span>
      )}
      {reason && (
        <span className="normal-case tracking-normal opacity-90 max-w-[12rem] truncate hidden sm:inline">
          — {reason}
        </span>
      )}
    </span>
  );
}

function parseLegacyParts(text, studentFlags) {
  const segments = [];
  const parts = text.split(LEGACY_FLAG_RE);
  let legacyIndex = 0;
  parts.forEach((part, i) => {
    if (i % 2 === 1) {
      legacyIndex += 1;
      const flag = studentFlags[legacyIndex - 1];
      segments.push({
        kind: 'flag',
        type: 'student',
        text: part,
        matchId: flag?.match_id ?? legacyIndex,
        confidence:
          flag?.confidence != null ? Math.round(flag.confidence * 100) : null,
        reason: flag?.reason ?? `Match ${legacyIndex}`,
      });
    } else if (part) {
      segments.push({ kind: 'plain', text: part });
    }
  });
  return segments;
}

export function parseAnnotatedText(text, studentFlags = []) {
  if (!text) return [];

  const segments = [];
  let lastIndex = 0;
  let match;
  let studentAutoId = 0;

  TYPED_FLAG_RE.lastIndex = 0;
  while ((match = TYPED_FLAG_RE.exec(text)) !== null) {
    if (match.index > lastIndex) {
      const plain = text.slice(lastIndex, match.index);
      if (plain.includes('[[')) {
        segments.push(...parseLegacyParts(plain, studentFlags));
      } else if (plain) {
        segments.push({ kind: 'plain', text: plain });
      }
    }
    const type = match[1];
    let matchId = match[2] ? parseInt(match[2], 10) : null;
    if (type === 'student' && matchId == null) {
      studentAutoId += 1;
      matchId = studentAutoId;
    }
    segments.push({
      kind: 'flag',
      type,
      matchId,
      confidence: parseInt(match[3], 10),
      reason: match[4],
      text: match[5],
    });
    lastIndex = match.index + match[0].length;
  }

  const remainder = text.slice(lastIndex);
  if (!segments.length) {
    return parseLegacyParts(remainder, studentFlags);
  }

  if (remainder) {
    if (remainder.includes('[[')) {
      segments.push(...parseLegacyParts(remainder, studentFlags));
    } else {
      segments.push({ kind: 'plain', text: remainder });
    }
  }

  return segments;
}

export function IntegrityLegend({
  showAi = true,
  studentMatches = [],
  activeMatchId = null,
  onMatchSelect,
}) {
  const hasStudentMatches = studentMatches.length > 0;
  if (!showAi && !hasStudentMatches) return null;

  return (
    <div className="space-y-2 px-1 pt-2 text-xs text-muted-foreground">
      <span className="font-semibold text-foreground">Legend</span>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
        {showAi && (
          <span className="inline-flex items-center gap-2">
            <span className={`w-3 h-3 rounded-sm border ${AI_STYLE.swatch}`} />
            Violet — AI-generated (per document)
          </span>
        )}
        {hasStudentMatches && (
          <span className="text-muted-foreground">
            {studentMatches.length} linked pair
            {studentMatches.length !== 1 ? 's' : ''} — click a match to jump to
            both sides
          </span>
        )}
      </div>
      {hasStudentMatches && (
        <div className="grid gap-1.5 sm:grid-cols-2">
          {studentMatches.map((entry) => {
            const palette = matchStyle(entry.matchId);
            const isActive = activeMatchId === entry.matchId;
            return (
              <button
                key={entry.matchId}
                type="button"
                onClick={() => onMatchSelect?.(entry.matchId)}
                className={`flex items-start gap-2 rounded-md border px-2.5 py-1.5 text-left transition-colors ${
                  isActive
                    ? 'border-primary/50 bg-primary/10'
                    : 'border-border bg-secondary/20 hover:bg-secondary/40'
                }`}
              >
                <span
                  className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[10px] font-bold text-foreground ${palette.swatch}`}
                >
                  {entry.matchId}
                </span>
                <div className="min-w-0">
                  <p className="text-[11px] font-medium text-foreground">
                    Match {entry.matchId}
                    {entry.confidence != null && (
                      <span className="ml-1 font-mono text-muted-foreground">
                        ({Math.round(entry.confidence * 100)}%)
                      </span>
                    )}
                  </p>
                  {entry.reason && (
                    <p className="text-[11px] text-muted-foreground truncate">
                      {entry.reason}
                    </p>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function buildStudentMatchLegend(flags) {
  return (flags || [])
    .filter((f) => f.type === 'student')
    .map((f, i) => ({
      matchId: f.match_id ?? i + 1,
      reason: f.reason,
      confidence: f.confidence,
    }))
    .sort((a, b) => a.matchId - b.matchId)
    .filter(
      (entry, index, arr) =>
        arr.findIndex((e) => e.matchId === entry.matchId) === index
    );
}

export default function AnnotatedDocument({
  text,
  flags = [],
  className = '',
  pane = 'left',
  activeMatchId = null,
  hoveredMatchId = null,
  onMatchActivate,
  onMatchHover,
  inlineBadges = true,
  dimInactive = false,
}) {
  const studentFlags = useMemo(
    () => (flags || []).filter((f) => f.type === 'student'),
    [flags]
  );
  const segments = useMemo(
    () => parseAnnotatedText(text, studentFlags),
    [text, studentFlags]
  );

  if (!text) {
    return (
      <p className={`text-xs text-muted-foreground italic ${className}`}>
        No document text available.
      </p>
    );
  }

  return (
    <div
      className={`text-sm leading-relaxed text-muted-foreground whitespace-pre-wrap ${className}`}
    >
      {segments.map((seg, i) => {
        if (seg.kind === 'plain') {
          return <span key={i}>{seg.text}</span>;
        }

        let style = LEGACY_STYLE;
        if (seg.type === 'ai') {
          style = AI_STYLE;
        } else if (seg.type === 'student') {
          style = matchStyle(seg.matchId);
        }

        const isStudentMatch = seg.type === 'student' && seg.matchId != null;
        const isActive = isStudentMatch && activeMatchId === seg.matchId;
        const isHovered = isStudentMatch && hoveredMatchId === seg.matchId;
        const interactive = isStudentMatch && onMatchActivate;
        const isDimmed =
          dimInactive &&
          isStudentMatch &&
          activeMatchId != null &&
          !isActive &&
          !isHovered;

        return (
          <span key={i} className="inline">
            <mark
              id={isStudentMatch ? matchAnchorId(pane, seg.matchId) : undefined}
              data-match-id={isStudentMatch ? seg.matchId : undefined}
              data-pane={pane}
              title={
                seg.reason
                  ? `${seg.type === 'ai' ? 'AI' : `Match ${seg.matchId}`}: ${seg.reason}`
                  : undefined
              }
              role={interactive ? 'button' : undefined}
              tabIndex={interactive ? 0 : undefined}
              onClick={
                interactive ? () => onMatchActivate(seg.matchId) : undefined
              }
              onKeyDown={
                interactive
                  ? (e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        onMatchActivate(seg.matchId);
                      }
                    }
                  : undefined
              }
              onMouseEnter={
                isStudentMatch && onMatchHover
                  ? () => onMatchHover(seg.matchId)
                  : undefined
              }
              onMouseLeave={
                isStudentMatch && onMatchHover
                  ? () => onMatchHover(null)
                  : undefined
              }
              className={`rounded-sm px-0.5 py-px not-italic transition-all ${
                isDimmed ? 'opacity-35' : ''
              } ${style.mark} ${interactive ? 'cursor-pointer hover:brightness-110' : ''} ${
                isActive || isHovered
                  ? `ring-2 ring-offset-1 ring-offset-background ${style.ring}`
                  : ''
              }`}
            >
              {isStudentMatch && !inlineBadges && (
                <span
                  className={`inline-flex items-center justify-center mr-1 px-1 rounded text-[9px] font-bold align-super ${style.swatch}`}
                >
                  {seg.matchId}
                </span>
              )}
              {seg.text}
            </mark>
            {inlineBadges && seg.type !== 'legacy' && (
              <FlagAnnotation
                type={seg.type}
                confidence={seg.confidence}
                reason={seg.reason}
                matchId={seg.matchId}
              />
            )}
          </span>
        );
      })}
    </div>
  );
}
