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

export const listAllReports = (limit = 100) =>
  request(`${API_PATHS.reportsOverview}/all?limit=${limit}`);

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

/**
 * Move multiple students to a target group in one request.
 * @param {string} moduleId
 * @param {string[]} studentIds  - array of student_number strings
 * @param {string} targetProjectId
 */
export async function listCoTeachers(moduleId) {
  return request(API_PATHS.moduleCoTeachers(moduleId));
}

export async function addCoTeacher(moduleId, email) {
  return request(API_PATHS.moduleCoTeachers(moduleId), {
    method: 'POST',
    body: JSON.stringify({ email }),
  });
}

export async function removeCoTeacher(moduleId, teacherId) {
  return request(API_PATHS.moduleCoTeacher(moduleId, teacherId), {
    method: 'DELETE',
  });
}

export const bulkMoveStudents = (moduleId, studentIds, targetProjectId) =>
  request(API_PATHS.moduleStudentsBulkMove(moduleId), {
    method: 'POST',
    body: JSON.stringify({
      student_ids: studentIds,
      target_project_id: targetProjectId,
    }),
  });

export const setStudentGithubRepo = (moduleId, studentId, githubRepoUrl) =>
  updateModuleStudent(moduleId, studentId, {
    github_repo_url: githubRepoUrl || null,
  });

export const setGroupGithubRepo = (moduleId, groupId, githubRepoUrl) =>
  updateProjectGroup(moduleId, groupId, {
    github_repo_url: githubRepoUrl || null,
  });

/**
 * Verify a GitHub repository and return its default branch + branch list.
 * Calls the public GitHub REST API directly from the browser so the backend
 * container does not need outbound internet access.
 */
export async function verifyGithubRepo(repoUrl) {
  // Normalise: strip trailing .git and extract owner/repo
  const raw = repoUrl.trim().replace(/\.git$/, '');
  const candidate = raw.startsWith('http') ? raw : `https://${raw}`;
  const { pathname } = new URL(candidate);
  const parts = pathname.split('/').filter(Boolean);
  if (parts.length < 2) {
    throw new Error('Repository URL must include owner and repository name.');
  }
  const [owner, repo] = parts;

  const ghHeaders = { Accept: 'application/vnd.github+json' };

  // 1. Verify the repo and get the default branch
  const repoRes = await fetch(`https://api.github.com/repos/${owner}/${repo}`, {
    headers: ghHeaders,
  });
  if (repoRes.status === 404) {
    throw new Error(
      `Repository '${owner}/${repo}' not found on GitHub. Check the URL and ensure it is public.`
    );
  }
  if (!repoRes.ok) {
    throw new Error(`GitHub API returned status ${repoRes.status}.`);
  }
  const repoData = await repoRes.json();
  const defaultBranch = repoData.default_branch || 'main';

  // 2. Collect all branches (paginated)
  const branches = [];
  let page = 1;
  while (page <= 5) {
    const brRes = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/branches?per_page=100&page=${page}`,
      { headers: ghHeaders }
    );
    if (!brRes.ok) break;
    const pageData = await brRes.json();
    if (!pageData.length) break;
    pageData.forEach((b) => branches.push(b.name));
    if (pageData.length < 100) break;
    page += 1;
  }

  return {
    repo_url: `https://github.com/${owner}/${repo}`,
    default_branch: defaultBranch,
    branches: branches.length ? branches : [defaultBranch],
  };
}

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

export const updateModuleStatus = (moduleId, status) =>
  request(API_PATHS.moduleStatus(moduleId), {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  });

export const deleteModule = (moduleId) =>
  request(API_PATHS.module(moduleId), { method: 'DELETE' });

/**
 * Download a student dossier as a ZIP file.
 * Returns a Blob that can be used to trigger a browser download.
 * @param {string} studentId
 * @param {string} studentName  - used to build the filename client-side
 */
export async function exportStudentDossier(
  studentId,
  studentName = '',
  format = 'zip'
) {
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
export async function exportModuleArchive(
  moduleId,
  moduleName = '',
  format = 'zip'
) {
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
export const analyzeModuleOverlap = (moduleId) =>
  request(API_PATHS.moduleOverlapAnalyze(moduleId), { method: 'POST' });

export const listModuleOverlapSignals = (moduleId, params = {}) => {
  const sp = new URLSearchParams();
  if (params.status) sp.set('status', params.status);
  if (params.scope) sp.set('scope', params.scope);
  if (params.group_id) sp.set('group_id', params.group_id);
  const qs = sp.toString();
  const path = qs
    ? `${API_PATHS.moduleOverlapSignals(moduleId)}?${qs}`
    : API_PATHS.moduleOverlapSignals(moduleId);
  return request(path);
};

export const getModuleOverlapSignal = (moduleId, signalId) =>
  request(API_PATHS.moduleOverlapSignal(moduleId, signalId));

export const getModuleOverlapWarning = (moduleId) =>
  request(API_PATHS.moduleOverlapWarning(moduleId));
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

/**
 * Download the student import template Excel file.
 * Returns a Blob that can be used to trigger a browser download.
 */
export async function downloadStudentTemplate() {
  const res = await fetch(
    `${API_URL}/api/v1${API_PATHS.moduleStudentTemplate}`,
    { headers: authHeaders() }
  );
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Template download failed (${res.status})`);
  }
  const blob = await res.blob();

  const today = new Date().toISOString().slice(0, 10); // YYYY-MM-DD
  const filename = `student_import_template_${today}.xlsx`;

  return { blob, filename };
}

/**
 * Download the rubric scoring template Excel file.
 * Returns a Blob that can be used to trigger a browser download.
 */
export async function downloadRubricTemplate() {
  const res = await fetch(
    `${API_URL}/api/v1${API_PATHS.moduleRubricTemplate}`,
    { headers: authHeaders() }
  );
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Template download failed (${res.status})`);
  }
  const blob = await res.blob();

  const today = new Date().toISOString().slice(0, 10); // YYYY-MM-DD
  const filename = `rubric_template_${today}.xlsx`;

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
