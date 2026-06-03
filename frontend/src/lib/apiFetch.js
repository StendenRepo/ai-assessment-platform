import { authHeaders, clearSession } from '@/lib/auth';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * General authenticated fetch against the API (v1).
 * Pass a path beginning with '/', e.g. '/notifications'.
 * For JSON bodies pass `json`; for file uploads pass `body` (FormData) and
 * omit the Content-Type so the browser sets the multipart boundary.
 */
export async function apiFetch(path, { json, body, headers, ...options } = {}) {
  const finalHeaders = { ...authHeaders(), ...(headers ?? {}) };
  let finalBody = body;

  if (json !== undefined) {
    finalHeaders['Content-Type'] = 'application/json';
    finalBody = JSON.stringify(json);
  }

  const res = await fetch(`${API_URL}/api/v1${path}`, {
    ...options,
    headers: finalHeaders,
    body: finalBody,
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    if (res.status === 401) {
      clearSession();
      if (typeof window !== 'undefined') window.location.assign('/');
    }
    throw new Error(data.detail || `Request failed (${res.status})`);
  }
  if (res.status === 204) return null;
  return res.json();
}
