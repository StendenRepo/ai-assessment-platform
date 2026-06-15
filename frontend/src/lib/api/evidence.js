import { apiFetch } from '@/lib/api/apiClient';
import { authHeaders } from '@/lib/auth';
import { API_PATHS } from '@/lib/routes';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function fetchBlob(path) {
  const res = await fetch(`${API_URL}/api/v1${path}`, {
    headers: authHeaders(),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Request failed (${res.status})`);
  }

  return res.blob();
}

export const getSupportedEvidenceTypes = () =>
  apiFetch(API_PATHS.evidenceSupportedTypes);

export const listStudentEvidence = (studentId) =>
  apiFetch(API_PATHS.studentEvidence(studentId));

export const uploadStudentEvidence = (studentId, file) => {
  const formData = new FormData();
  formData.append('file', file);
  return apiFetch(API_PATHS.studentEvidence(studentId), {
    method: 'POST',
    body: formData,
  });
};

export const deleteEvidence = (evidenceId) =>
  apiFetch(API_PATHS.evidence(evidenceId), { method: 'DELETE' });

export const getEvidenceContent = async (evidenceId) => {
  const body = await apiFetch(API_PATHS.evidenceContent(evidenceId));
  return body.content ?? '';
};

export const getEvidenceFileBlob = (evidenceId) =>
  fetchBlob(API_PATHS.evidenceFile(evidenceId));
