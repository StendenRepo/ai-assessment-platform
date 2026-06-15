import { apiFetch } from '@/lib/api/apiClient';
import { API_PATHS } from '@/lib/routes';

export function listNotifications(unreadOnly = false) {
  return apiFetch(API_PATHS.notifications(unreadOnly));
}

export function markNotificationRead(notificationId) {
  return apiFetch(API_PATHS.notificationRead(notificationId), {
    method: 'POST',
  });
}
