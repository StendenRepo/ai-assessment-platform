import { apiFetch } from '@/lib/apiFetch';

export function getRecordingState(assessmentId) {
  return apiFetch(`/assessments/${assessmentId}/recording`);
}

export function uploadRecording(
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

export function setConsent(assessmentId, status) {
  // status: 'accepted' | 'declined'
  return apiFetch(`/assessments/${assessmentId}/consent`, {
    method: 'POST',
    json: { status },
  });
}

export function listNotifications(unreadOnly = false) {
  return apiFetch(
    `/notifications?unread_only=${unreadOnly ? 'true' : 'false'}`
  );
}

export function markNotificationRead(notificationId) {
  return apiFetch(`/notifications/${notificationId}/read`, { method: 'POST' });
}
