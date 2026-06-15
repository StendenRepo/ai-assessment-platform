import { authHeaders, clearSession } from '@/lib/auth';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function hasContentType(headers) {
  return Object.keys(headers).some((k) => k.toLowerCase() === 'content-type');
}

/** Turn FastAPI error payloads into a readable string. */
export function formatApiErrorDetail(detail, fallbackStatus) {
  if (!detail) return `Request failed (${fallbackStatus})`;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item && typeof item === 'object') {
          const loc = Array.isArray(item.loc) ? item.loc.join('.') : '';
          const msg = item.msg || item.message || JSON.stringify(item);
          return loc ? `${loc}: ${msg}` : msg;
        }
        return String(item);
      })
      .join('; ');
  }
  if (typeof detail === 'object') {
    return detail.msg || detail.message || JSON.stringify(detail);
  }
  return String(detail);
}

/**
 * Shared authenticated request helper.
 */
export async function apiRequest(
  path,
  {
    json,
    body,
    headers,
    basePath = '/api/v1',
    onUnauthorized = false,
    errorMessage,
    ...options
  } = {}
) {
  const finalHeaders = { ...authHeaders(), ...(headers ?? {}) };
  let finalBody = body;

  if (json !== undefined) {
    finalHeaders['Content-Type'] = 'application/json';
    finalBody = JSON.stringify(json);
  } else if (
    finalBody !== undefined &&
    !(finalBody instanceof FormData) &&
    !hasContentType(finalHeaders)
  ) {
    finalHeaders['Content-Type'] = 'application/json';
  }

  const res = await fetch(`${API_URL}${basePath}${path}`, {
    ...options,
    headers: finalHeaders,
    body: finalBody,
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    if (res.status === 401 && onUnauthorized) {
      clearSession();
      if (typeof window !== 'undefined') window.location.assign('/');
    }
    const message = errorMessage?.(data, res);
    throw new Error(
      message || formatApiErrorDetail(data.detail, res.status)
    );
  }
  if (res.status === 204) return null;
  return res.json();
}

/**
 * General authenticated fetch against the API (v1).
 * Pass a path beginning with '/', e.g. '/notifications'.
 * For JSON bodies pass `json`; for file uploads pass `body` (FormData) and
 * omit the Content-Type so the browser sets the multipart boundary.
 */
export async function apiFetch(path, { json, body, headers, ...options } = {}) {
  return apiRequest(path, {
    json,
    body,
    headers,
    ...options,
    basePath: '/api/v1',
    onUnauthorized: true,
  });
}
