'use client';

const styles = {
  confirmed: 'bg-red-500/10 text-red-400 ring-1 ring-red-500/20',
  possible: 'bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/20',
  within_group: 'bg-blue-500/10 text-blue-400 ring-1 ring-blue-500/20',
  cross_group: 'bg-violet-500/10 text-violet-400 ring-1 ring-violet-500/20',
};

export default function OverlapStatusBadge({ kind, label }) {
  const text = label || kind?.replace('_', ' ');
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${styles[kind] || 'bg-secondary text-muted-foreground ring-1 ring-border'}`}
    >
      {text}
    </span>
  );
}
