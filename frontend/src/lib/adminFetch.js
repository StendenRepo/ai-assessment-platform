import { authHeaders, clearSession } from '@/lib/auth';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function adminFetch(path, options = {}) {
  const res = await fetch(`${API_URL}/api/v1/admin${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...(options.headers ?? {}),
    },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    if (res.status === 401) {
      clearSession();
      if (typeof window !== 'undefined') {
        // Surface a reason on the login page so the user understands the redirect.
        const notice = 'Your session has expired. Please sign in again.';
        window.location.assign(`/?notice=${encodeURIComponent(notice)}`);
      }
    }
    throw new Error(data.detail || `Request failed (${res.status})`);
  }
  if (res.status === 204) return null;
  return res.json();
}
