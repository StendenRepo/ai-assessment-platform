import { CheckCircle2, XCircle, Clock } from 'lucide-react';

/**
 * Consent indicator for the assessment form (G2-138).
 * Shows whether the recording was accepted, declined, or is still pending.
 */
export default function ConsentBadge({ status }) {
  const config = {
    accepted: {
      icon: CheckCircle2,
      label: 'Recording accepted',
      className:
        'bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20',
    },
    declined: {
      icon: XCircle,
      label: 'Recording declined',
      className: 'bg-red-500/10 text-red-400 ring-1 ring-red-500/20',
    },
    pending: {
      icon: Clock,
      label: 'Consent pending',
      className: 'bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/20',
    },
  };

  const { icon: Icon, label, className } = config[status] ?? config.pending;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${className}`}
    >
      <Icon size={13} />
      {label}
    </span>
  );
}
