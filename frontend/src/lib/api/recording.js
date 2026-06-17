import { apiFetch } from '@/lib/api/apiClient';
import { authHeaders } from '@/lib/auth';
import { API_PATHS } from '@/lib/routes';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
// ── Consent gate ──────────────────────────────────────────────────────────────

// Resolve (or lazily create) the current teacher's assessment for a student.
// Returns ConsentStateOut, including the real assessment_id to use everywhere else.
export function resolveAssessmentForStudent(studentId) {
  return apiFetch(API_PATHS.assessmentForStudent(studentId), {
    method: 'POST',
  });
}

export function getConsentState(assessmentId) {
  return apiFetch(API_PATHS.assessmentRecordingState(assessmentId));
}

export function setConsent(assessmentId, status) {
  // status: 'accepted' | 'declined'
  return apiFetch(API_PATHS.assessmentConsent(assessmentId), {
    method: 'POST',
    json: { status },
  });
}

// ── Recordings (many per assessment) ──────────────────────────────────────────

export function listRecordings(assessmentId) {
  return apiFetch(API_PATHS.assessmentRecordings(assessmentId));
}

export function getRecording(assessmentId, recordingId) {
  return apiFetch(API_PATHS.assessmentRecording(assessmentId, recordingId));
}

export function appendRecording(
  assessmentId,
  blob,
  filename = 'recording.webm'
) {
  const form = new FormData();
  form.append('file', blob, filename);
  return apiFetch(API_PATHS.assessmentRecordingState(assessmentId), {
    method: 'POST',
    body: form,
  });
}

export function renameRecording(assessmentId, recordingId, displayName) {
  return apiFetch(API_PATHS.assessmentRecording(assessmentId, recordingId), {
    method: 'PATCH',
    json: { display_name: displayName },
  });
}

export function extendRecordingExpiry(
  assessmentId,
  recordingId,
  { reason, extraDays = 90 }
) {
  return apiFetch(API_PATHS.assessmentRecording(assessmentId, recordingId), {
    method: 'PATCH',
    json: { extend_expiry: { reason, extra_days: extraDays } },
  });
}

export function deleteRecording(assessmentId, recordingId) {
  return apiFetch(API_PATHS.assessmentRecording(assessmentId, recordingId), {
    method: 'DELETE',
  });
}

// Fetch a recording's audio as a Blob for in-app playback.
export async function getRecordingAudioBlob(assessmentId, recordingId) {
  const res = await fetch(
    `${API_URL}/api/v1${API_PATHS.assessmentRecordingAudio(assessmentId, recordingId)}`,
    { headers: authHeaders() }
  );
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Request failed (${res.status})`);
  }
  return res.blob();
}
// ── Notifications ─────────────────────────────────────────────────────────────

export function listNotifications(unreadOnly = false) {
  return apiFetch(API_PATHS.notifications(unreadOnly));
}

export function markNotificationRead(notificationId) {
  return apiFetch(API_PATHS.notificationRead(notificationId), {
    method: 'POST',
  });
}
