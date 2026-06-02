import { authHeaders } from '@/lib/auth';
import { API_PATHS } from '@/lib/routes';

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

export const listModules = () => request(API_PATHS.modules);

export const getProject = (projectId) => request(API_PATHS.module(projectId));

export const createModule = (payload) =>
  request(API_PATHS.modules, {
    method: 'POST',
    body: JSON.stringify(payload),
  });

export const listProjectGroups = (projectId) =>
  request(API_PATHS.moduleGroups(projectId));

export const createProjectGroup = (projectId, payload) =>
  request(API_PATHS.moduleGroups(projectId), {
    method: 'POST',
    body: JSON.stringify(payload),
  });

export const listProjectStudents = (projectId) =>
  request(API_PATHS.moduleStudents(projectId));

export const addProjectStudent = (projectId, payload) =>
  request(API_PATHS.moduleStudents(projectId), {
    method: 'POST',
    body: JSON.stringify(payload),
  });

export const moveStudentToGroup = (moduleId, studentId, projectId) =>
  request(API_PATHS.moduleStudent(moduleId, studentId), {
    method: 'PATCH',
    body: JSON.stringify({ project_id: projectId }),
  });

export const importProjectStudents = (projectId, file, targetGroupId = '') => {
  const formData = new FormData();
  formData.append('file', file);
  return request(API_PATHS.moduleStudentImports(projectId, targetGroupId), {
    method: 'POST',
    body: formData,
  });
};
