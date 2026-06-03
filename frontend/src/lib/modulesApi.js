import { authHeaders } from '@/lib/auth';
import { normalizeErrorDetail } from '@/lib/apiErrors';
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
    const message =
      normalizeErrorDetail(data.detail) || `Request failed (${res.status})`;
    throw new Error(message);
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

export const updateProjectGroup = (moduleId, groupId, payload) =>
  request(API_PATHS.moduleGroup(moduleId, groupId), {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });

export const deleteProjectGroup = (moduleId, groupId) =>
  request(API_PATHS.moduleGroup(moduleId, groupId), {
    method: 'DELETE',
  });

export const listProjectStudents = (projectId) =>
  request(API_PATHS.moduleStudents(projectId));

export const addProjectStudent = (projectId, payload) =>
  request(API_PATHS.moduleStudents(projectId), {
    method: 'POST',
    body: JSON.stringify(payload),
  });

export const updateModuleStudent = (moduleId, studentId, payload) =>
  request(API_PATHS.moduleStudent(moduleId, studentId), {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });

export const moveStudentToGroup = (moduleId, studentId, projectId) =>
  updateModuleStudent(moduleId, studentId, { project_id: projectId });

export const importProjectStudents = (projectId, file, targetGroupId = '') => {
  const formData = new FormData();
  formData.append('file', file);
  return request(API_PATHS.moduleStudentImports(projectId, targetGroupId), {
    method: 'POST',
    body: formData,
  });
};

export const uploadRubric = (moduleId, file) => {
  const formData = new FormData();
  formData.append('file', file);
  return request(API_PATHS.moduleRubric(moduleId), {
    method: 'POST',
    body: formData,
  });
};

export const deleteRubric = (moduleId) =>
  request(API_PATHS.moduleRubric(moduleId), { method: 'DELETE' });

export const uploadModuleBook = (moduleId, file) => {
  const formData = new FormData();
  formData.append('file', file);
  return request(API_PATHS.moduleBook(moduleId), {
    method: 'POST',
    body: formData,
  });
};

export const deleteModuleBook = (moduleId) =>
  request(API_PATHS.moduleBook(moduleId), { method: 'DELETE' });

export const renameModule = (moduleId, name) =>
  request(API_PATHS.module(moduleId), {
    method: 'PATCH',
    body: JSON.stringify({ name }),
  });

export const deleteModule = (moduleId) =>
  request(API_PATHS.module(moduleId), { method: 'DELETE' });
