import { apiFetch } from '@/lib/api/apiClient';
import { API_PATHS } from '@/lib/routes';

export const generateAssessmentQuestions = (studentId, moduleId) =>
  apiFetch(API_PATHS.studentAssessmentQuestions(studentId), {
    method: 'POST',
    json: moduleId ? { module_id: moduleId } : {},
  });
