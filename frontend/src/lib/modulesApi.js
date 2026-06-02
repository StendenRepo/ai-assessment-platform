import { authHeaders } from '@/lib/auth';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function request(path, options = {}) {
  const isFormData = options.body instanceof FormData;
  const res = await fetch(`${API_URL}/api/v1${path}`, {
    ...options,
    headers: {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...authHeaders(),
      ...(options.headers ?? {}),
    },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Request failed (${res.status})`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const listModules = () => request('/modules');

export const getModule = (moduleId) => request(`/modules/${moduleId}`);

export const createModule = (payload) =>
  request('/modules', { method: 'POST', body: JSON.stringify(payload) });

export const uploadRubric = (moduleId, file) => {
  const formData = new FormData();
  formData.append('file', file);
  return request(`/modules/${moduleId}/rubric`, { method: 'POST', body: formData });
};

export const deleteRubric = (moduleId) =>
  request(`/modules/${moduleId}/rubric`, { method: 'DELETE' });
