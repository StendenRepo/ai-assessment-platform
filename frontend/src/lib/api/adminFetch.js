import { apiRequest } from '@/lib/api/apiClient';

export async function adminFetch(path, options = {}) {
  return apiRequest(path, {
    ...options,
    basePath: '/api/v1/admin',
    onUnauthorized: true,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers ?? {}),
    },
  });
}
