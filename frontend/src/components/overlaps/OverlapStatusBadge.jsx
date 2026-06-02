export default function OverlapStatusBadge({ status, percent }) {
  const confirmed = status === 'confirmed';
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide shrink-0 ${
        confirmed
          ? 'bg-red-500/10 text-red-400 ring-1 ring-red-500/20'
          : 'bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/20'
      }`}
    >
      {percent != null ? `${percent}%` : status}
    </span>
  );
}
