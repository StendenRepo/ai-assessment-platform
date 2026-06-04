import { apiFetch } from '@/lib/apiFetch';

// ── Consent gate ──────────────────────────────────────────────────────────────

// Resolve (or lazily create) the current teacher's assessment for a student.
// Returns ConsentStateOut, including the real assessment_id to use everywhere else.
export function resolveAssessmentForStudent(studentId) {
  return apiFetch(`/assessments/for-student/${studentId}`, { method: 'POST' });
}

export function getConsentState(assessmentId) {
  return apiFetch(`/assessments/${assessmentId}/recording`);
}

export function setConsent(assessmentId, status) {
  // status: 'accepted' | 'declined'
  return apiFetch(`/assessments/${assessmentId}/consent`, {
    method: 'POST',
    json: { status },
  });
}

// ── Recordings (many per assessment) ──────────────────────────────────────────

export function listRecordings(assessmentId) {
  return apiFetch(`/assessments/${assessmentId}/recordings`);
}

export function getRecording(assessmentId, recordingId) {
  return apiFetch(`/assessments/${assessmentId}/recordings/${recordingId}`);
}

export function appendRecording(
  assessmentId,
  blob,
  filename = 'recording.webm'
) {
  const form = new FormData();
  form.append('file', blob, filename);
  return apiFetch(`/assessments/${assessmentId}/recording`, {
    method: 'POST',
    body: form,
  });
}

export function renameRecording(assessmentId, recordingId, displayName) {
  return apiFetch(`/assessments/${assessmentId}/recordings/${recordingId}`, {
    method: 'PATCH',
    json: { display_name: displayName },
  });
}

export function extendRecordingExpiry(
  assessmentId,
  recordingId,
  { reason, extraDays = 90 }
) {
  return apiFetch(`/assessments/${assessmentId}/recordings/${recordingId}`, {
    method: 'PATCH',
    json: { extend_expiry: { reason, extra_days: extraDays } },
  });
}

export function deleteRecording(assessmentId, recordingId) {
  return apiFetch(`/assessments/${assessmentId}/recordings/${recordingId}`, {
    method: 'DELETE',
  });
}

// ── Notifications ─────────────────────────────────────────────────────────────

export function listNotifications(unreadOnly = false) {
  return apiFetch(
    `/notifications?unread_only=${unreadOnly ? 'true' : 'false'}`
  );
}

export function markNotificationRead(notificationId) {
  return apiFetch(`/notifications/${notificationId}/read`, { method: 'POST' });
}
