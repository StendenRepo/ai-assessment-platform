import { apiFetch } from '@/lib/api/apiClient';
import { API_PATHS } from '@/lib/routes';

export function getTeacherPreferences() {
  return apiFetch(API_PATHS.teacherPreferences());
}

export function updateTeacherPreferences(preferences) {
  return apiFetch(API_PATHS.teacherPreferences(), {
    method: 'PUT',
    json: preferences,
  });
}
