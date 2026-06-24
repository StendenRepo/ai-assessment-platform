import { apiFetch } from '@/lib/api/apiClient';
import { API_PATHS } from '@/lib/routes';

export const listRubricScores = (studentId) =>
  apiFetch(API_PATHS.studentRubricScores(studentId));

export const generateRubricScore = (studentId, rubricId) =>
  apiFetch(API_PATHS.studentRubricScore(studentId, rubricId), {
    method: 'POST',
  });

export const getFinalGrade = (studentId) =>
  apiFetch(API_PATHS.studentFinalGrade(studentId));
