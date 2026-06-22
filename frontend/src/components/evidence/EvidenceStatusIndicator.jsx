'use client';

import { AlertCircle, CheckCircle2, XCircle } from 'lucide-react';

function statusConfig(status) {
  if (status === 'completed') {
    return {
      Icon: CheckCircle2,
      className: 'text-emerald-500',
      label: 'Ready',
    };
  }

  if (status === 'failed') {
    return {
      Icon: XCircle,
      className: 'text-red-500',
      label: 'Failed',
    };
  }

  return {
    Icon: AlertCircle,
    className: 'text-amber-400',
    label: 'In progress',
  };
}

export default function EvidenceStatusIndicator({ status, size = 12 }) {
  const { Icon, className, label } = statusConfig(status);

  return (
    <span className="inline-flex align-middle" title={label} aria-label={label}>
      <Icon size={size} className={className} />
    </span>
  );
}
