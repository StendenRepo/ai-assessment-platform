'use client';

import {
  aiMetricLabel,
  aiScoreLabel,
  peakSectionLabel,
} from '@/lib/overlapLabels';

function roundPct(fraction) {
  return Math.round((fraction || 0) * 100);
}

function peakFlagPct(flags, type) {
  const subset = (flags || []).filter((f) => f.type === type);
  if (!subset.length) return null;
  return roundPct(Math.max(...subset.map((f) => f.confidence || 0)));
}

/** Build display rows from fields already on every overlap signal — no extra API needed. */
export function buildOverlapMetricRows(signal) {
  const type = signal.integrity_type || 'student_plagiarism';
  const flags = signal.flags || [];
  const confPct = roundPct(signal.confidence);
  const studentFlags = flags.filter((f) => f.type === 'student');
  const rows = [];

  if (type === 'ai' || type === 'both') {
    const aiPct = signal.ai_content_percent ?? confPct;
    rows.push({
      key: 'ai',
      label: aiMetricLabel(),
      value: aiScoreLabel(aiPct),
    });
    const peak = signal.peak_ai_section_percent ?? peakFlagPct(flags, 'ai');
    if (peak != null && peak > aiPct + 5) {
      rows.push({
        key: 'peak',
        label: 'Peak section',
        value: peakSectionLabel(peak),
      });
    }
  }

  if (type === 'student_plagiarism' || type === 'both') {
    const matches = signal.student_match_count ?? studentFlags.length;
    if (matches > 0) {
      rows.push({
        key: 'matches',
        label: matches === 1 ? 'Passage' : 'Passages',
        value: String(matches),
      });
    }
    const overlapPct = signal.overlap_confidence_percent ?? confPct;
    rows.push({
      key: 'overlap',
      label: 'Similarity est.',
      value: `${overlapPct}%`,
    });
  }

  return rows;
}

const TONE_STYLES = {
  violet: 'border-violet-500/30 bg-violet-500/[0.07]',
  amber: 'border-amber-500/30 bg-amber-500/[0.07]',
  neutral: 'border-border bg-secondary/50',
};

function StatCell({ value, label, sub, tone = 'neutral', className = '' }) {
  return (
    <div
      className={`flex flex-col items-center justify-center rounded-md border px-2 py-2 text-center min-h-[4.25rem] ${TONE_STYLES[tone]} ${className}`}
    >
      <span className="text-base font-semibold font-mono tabular-nums leading-none text-foreground">
        {value}
      </span>
      <span className="text-[10px] uppercase tracking-wide text-muted-foreground mt-1.5 leading-tight">
        {label}
      </span>
      {sub && (
        <span className="text-[10px] font-mono tabular-nums text-muted-foreground/90 mt-0.5">
          {sub}
        </span>
      )}
    </div>
  );
}

function CompactMetrics({ signal }) {
  const type = signal.integrity_type || 'student_plagiarism';
  const rows = buildOverlapMetricRows(signal);
  const ai = rows.find((r) => r.key === 'ai');
  const peak = rows.find((r) => r.key === 'peak');
  const matches = rows.find((r) => r.key === 'matches');
  const overlap = rows.find((r) => r.key === 'overlap');

  if (type === 'both') {
    return (
      <div className="grid grid-cols-2 gap-1.5 w-[11.5rem] shrink-0">
        <StatCell
          value={ai?.value ?? '—'}
          label={ai?.label ?? aiMetricLabel()}
          sub={peak ? peak.value : undefined}
          tone="violet"
        />
        <StatCell
          value={matches?.value ?? '—'}
          label={matches?.label ?? 'Passages'}
          sub={overlap ? `${overlap.value} conf.` : undefined}
          tone="amber"
        />
      </div>
    );
  }

  if (type === 'ai') {
    return (
      <div className="w-[11.5rem] shrink-0">
        <StatCell
          value={ai?.value ?? '—'}
          label={ai?.label ?? aiMetricLabel()}
          sub={peak ? peak.value : undefined}
          tone="violet"
          className="w-full"
        />
      </div>
    );
  }

  return (
    <div className="w-[11.5rem] shrink-0">
      <StatCell
        value={matches?.value ?? overlap?.value ?? '—'}
        label={
          matches ? `${matches.label} matched` : (overlap?.label ?? 'Overlap')
        }
        sub={matches && overlap ? `${overlap.value} confidence` : undefined}
        tone="amber"
        className="w-full"
      />
    </div>
  );
}

function DetailMetrics({ rows }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 max-w-lg mt-3">
      {rows.map((row) => (
        <StatCell
          key={row.key ?? row.label}
          value={row.value}
          label={row.label}
          tone={
            row.key === 'ai' || row.key === 'peak'
              ? 'violet'
              : row.key === 'matches' || row.key === 'overlap'
                ? 'amber'
                : 'neutral'
          }
        />
      ))}
    </div>
  );
}

export default function OverlapSignalMetrics({ signal, compact = false }) {
  const rows = buildOverlapMetricRows(signal);
  if (!rows.length) return null;

  if (compact) {
    return <CompactMetrics signal={signal} />;
  }

  return <DetailMetrics rows={rows} />;
}

export function integrityAccentClass(type) {
  switch (type) {
    case 'ai':
      return 'border-l-violet-500/70';
    case 'student_plagiarism':
      return 'border-l-amber-500/70';
    case 'both':
      return 'border-l-red-500/70';
    default:
      return 'border-l-border';
  }
}
