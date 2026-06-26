import { apiFetch, apiRequest } from '@/lib/api/apiClient';
import { API_PATHS } from '@/lib/routes';

export function getTeacherPreferences() {
  return apiRequest(API_PATHS.teacherPreferences(), { onUnauthorized: false });
}

export function updateTeacherPreferences(preferences) {
  return apiFetch(API_PATHS.teacherPreferences(), {
    method: 'PUT',
    json: preferences,
  });
}
