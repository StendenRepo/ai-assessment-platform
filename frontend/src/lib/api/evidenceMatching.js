import { apiFetch } from '@/lib/api/apiClient';
import { API_PATHS } from '@/lib/routes';

export const getEvidenceMatches = (studentId, runId) => {
  const base = API_PATHS.studentEvidenceMatches(studentId);
  const path = runId ? `${base}?run_id=${encodeURIComponent(runId)}` : base;
  return apiFetch(path);
};

export const runEvidenceMatching = (studentId, moduleId, mode = 'standard') =>
  apiFetch(API_PATHS.studentEvidenceMatches(studentId), {
    method: 'POST',
    json: { ...(moduleId ? { module_id: moduleId } : {}), mode },
  });

export const deleteEvidenceMatchRun = (studentId, runId) =>
  apiFetch(API_PATHS.studentEvidenceMatchRun(studentId, runId), {
    method: 'DELETE',
  });
