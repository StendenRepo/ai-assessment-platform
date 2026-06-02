const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function req(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(
      typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail)
    );
  }
  return res.json();
}

export const overlapApi = {
  detect: (projectId, groupId) =>
    req(`/api/v1/projects/${projectId}/groups/${groupId}/overlaps/detect`, {
      method: 'POST',
    }),

  detectAll: (projectId) =>
    req(`/api/v1/projects/${projectId}/overlaps/detect-all`, { method: 'POST' }),

  detectCrossGroup: (projectId) =>
    req(`/api/v1/projects/${projectId}/overlaps/cross-group/detect`, {
      method: 'POST',
    }),

  list: (projectId, groupId, { status, scope, sort = 'similarity', order = 'desc' } = {}) => {
    const q = new URLSearchParams();
    if (status) q.set('status', status);
    if (scope) q.set('scope', scope);
    q.set('sort', sort);
    q.set('order', order);
    return req(
      `/api/v1/projects/${projectId}/groups/${groupId}/overlaps?${q}`
    );
  },

  listConfirmed: (projectId, groupId, opts = {}) =>
    overlapApi.list(projectId, groupId, { ...opts, status: 'confirmed' }),

  listPossible: (projectId, groupId, opts = {}) => {
    const q = new URLSearchParams({ sort: opts.sort || 'similarity', order: opts.order || 'desc' });
    return req(
      `/api/v1/projects/${projectId}/groups/${groupId}/overlaps/possible?${q}`
    );
  },

  detail: (projectId, groupId, overlapId) =>
    req(
      `/api/v1/projects/${projectId}/groups/${groupId}/overlaps/${overlapId}`
    ),

  exportZip: (projectId, groupId) =>
    `${API}/api/v1/projects/${projectId}/groups/${groupId}/overlaps/export/zip`,
};
