/** User-facing labels for overlap / integrity signals (API values stay unchanged). */

export const OVERLAP_REVIEW_DISCLAIMER =
  'Indicators are probabilistic classifier and similarity scores. Verify evidence manually before any academic action.';

export const OVERLAP_STATUS_LABELS = {
  confirmed: 'High confidence',
  possible: 'Needs review',
  within_group: 'Within group',
  cross_group: 'Cross group',
};

export const INTEGRITY_TYPE_LABELS = {
  ai: 'Possible AI-assisted text',
  student_plagiarism: 'Possible student overlap',
  both: 'Possible AI + student overlap',
};

export function overlapStatusLabel(status) {
  if (!status) return 'Unknown';
  return OVERLAP_STATUS_LABELS[status] || status.replace(/_/g, ' ');
}

export function aiScoreLabel(percent) {
  if (percent == null || Number.isNaN(percent)) return '—';
  return `~${percent}% (est.)`;
}

export function aiMetricLabel() {
  return 'Classifier estimate';
}

export function peakSectionLabel(percent) {
  return `Peak section ~${percent}%`;
}
