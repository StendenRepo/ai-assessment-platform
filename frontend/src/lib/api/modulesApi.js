import { apiRequest } from '@/lib/api/apiClient';
import { normalizeErrorDetail } from '@/lib/api/apiErrors';
import { API_PATHS } from '@/lib/routes';

async function request(path, options = {}) {
  return apiRequest(path, {
    ...options,
    basePath: '/api/v1',
    onUnauthorized: false,
    errorMessage: (data, res) =>
      normalizeErrorDetail(data.detail) || `Request failed (${res.status})`,
  });
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
