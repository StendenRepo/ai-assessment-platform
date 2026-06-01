import { authHeaders } from '@/lib/auth';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function request(path, options = {}) {
  const isFormData = options.body instanceof FormData;
  const res = await fetch(`${API_URL}/api/v1${path}`, {
    ...options,
    headers: {
      // Let the browser set the multipart boundary for FormData uploads.
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

export const listProjects = () => request('/projects');

export const getProject = (projectId) => request(`/projects/${projectId}`);

export const listProjectStudents = (projectId) =>
  request(`/projects/${projectId}/students`);

export const addProjectStudent = (projectId, payload) =>
  request(`/projects/${projectId}/students`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });

export const importProjectStudents = (projectId, file) => {
  const formData = new FormData();
  formData.append('file', file);
  return request(`/projects/${projectId}/students/import`, {
    method: 'POST',
    body: formData,
  });
};
