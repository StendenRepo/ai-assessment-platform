import { apiFetch } from '@/lib/api/apiClient';
import { API_PATHS } from '@/lib/routes';

export const getEvidenceMatches = (studentId) =>
  apiFetch(API_PATHS.studentEvidenceMatches(studentId));

export const runEvidenceMatching = (studentId, moduleId) =>
  apiFetch(API_PATHS.studentEvidenceMatches(studentId), {
    method: 'POST',
    json: moduleId ? { module_id: moduleId } : {},
  });
