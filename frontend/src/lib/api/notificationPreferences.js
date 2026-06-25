import { apiFetch } from '@/lib/api/apiClient';
import { API_PATHS } from '@/lib/routes';

export function getNotificationPreferences() {
  return apiFetch(API_PATHS.notificationPreferences());
}

export function updateNotificationPreference(notificationType, enabled) {
  return apiFetch(API_PATHS.notificationPreference(notificationType), {
    method: 'PUT',
    json: { enabled },
  });
}
