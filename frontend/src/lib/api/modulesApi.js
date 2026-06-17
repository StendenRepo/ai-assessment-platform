import { apiRequest } from '@/lib/api/apiClient';
import { normalizeErrorDetail } from '@/lib/api/apiErrors';
import { authHeaders } from '@/lib/auth';
import { API_PATHS } from '@/lib/routes';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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

export const listReports = (limit = 50) =>
  request(`${API_PATHS.reportsOverview}?limit=${limit}`);

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

export const listProjectEvidence = (projectId) =>
  request(API_PATHS.projectEvidence(projectId));

export const uploadProjectEvidence = (projectId, file) => {
  const formData = new FormData();
  formData.append('file', file);
  return request(API_PATHS.projectEvidence(projectId), {
    method: 'POST',
    body: formData,
  });
};

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

/**
 * Download a student dossier as a ZIP file.
 * Returns a Blob that can be used to trigger a browser download.
 * @param {string} studentId
 * @param {string} studentName  - used to build the filename client-side
 */
export async function exportStudentDossier(studentId, studentName = '', format = 'zip') {
  const url = `${API_URL}/api/v1${API_PATHS.studentDossierExport(studentId)}?format=${format}`;
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Export failed (${res.status})`);
  }
  const blob = await res.blob();

  const today = new Date().toISOString().slice(0, 10);
  const safeName = studentName
    .replace(/[^a-zA-Z0-9_-]/g, '_')
    .replace(/^_+|_+$/g, '');
  const ext = format === 'tar' ? 'tar.gz' : 'zip';
  const filename = safeName
    ? `dossier_${safeName}_${today}.${ext}`
    : `dossier_${today}.${ext}`;

  return { blob, filename };
}

/**
 * Download the complete module archive ZIP (rubric, module book, evidence, assessments, grades).
 * @param {string} moduleId
 * @param {string} moduleName  - used to build the filename client-side
 */
export async function exportModuleArchive(moduleId, moduleName = '', format = 'zip') {
  const url = `${API_URL}/api/v1${API_PATHS.moduleArchiveExport(moduleId)}?format=${format}`;
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Export failed (${res.status})`);
  }
  const blob = await res.blob();
  const today = new Date().toISOString().slice(0, 10);
  const safeName = moduleName
    .replace(/[^a-zA-Z0-9_-]/g, '_')
    .replace(/^_+|_+$/g, '');
  const ext = format === 'tar' ? 'tar.gz' : 'zip';
  const filename = safeName
    ? `archive_${safeName}_${today}.${ext}`
    : `archive_${today}.${ext}`;
  return { blob, filename };
}

/**
 * Download the grades Excel file for a module.
 * Returns a Blob that can be used to trigger a browser download.
 * @param {string} moduleId
 * @param {string} moduleName  - used to build the filename client-side
 */
export async function exportGradesExcel(moduleId, moduleName = '') {
  const res = await fetch(
    `${API_URL}/api/v1${API_PATHS.moduleGradesExport(moduleId)}`,
    { headers: authHeaders() }
  );
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Export failed (${res.status})`);
  }
  const blob = await res.blob();

  // Build filename the same way the backend does:
  // replace every non-alphanumeric / non-underscore / non-dash char with '_'
  const today = new Date().toISOString().slice(0, 10); // YYYY-MM-DD
  const safeName = moduleName
    .replace(/[^a-zA-Z0-9_-]/g, '_')
    .replace(/^_+|_+$/g, ''); // trim leading/trailing underscores
  const filename = safeName
    ? `${safeName}_${today}.xlsx`
    : `export_${today}.xlsx`;

  return { blob, filename };
}

async function fetchModuleBlob(path) {
  const res = await fetch(`${API_URL}/api/v1${path}`, {
    headers: authHeaders(),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(
      normalizeErrorDetail(data.detail) || `Request failed (${res.status})`
    );
  }
  return res.blob();
}

export const getRubricFileBlob = (moduleId) =>
  fetchModuleBlob(API_PATHS.moduleRubricFile(moduleId));

export const getRubricContent = async (moduleId) => {
  const body = await request(API_PATHS.moduleRubricContent(moduleId));
  return body.content ?? '';
};

export const getModuleBookFileBlob = (moduleId) =>
  fetchModuleBlob(API_PATHS.moduleBookFile(moduleId));

export const getModuleBookContent = async (moduleId) => {
  const body = await request(API_PATHS.moduleBookContent(moduleId));
  return body.content ?? '';
};
