export const APP_PATHS = {
  root: '/',
  dashboard: '/dashboard',
  admin: '/admin',
  modules: '/modules',
  moduleNew: '/modules/new',
  moduleManage: (moduleId) => `/modules/${moduleId}/manage`,
  reports: '/reports',
  settings: '/settings',
};

export const API_PATHS = {
  modules: '/modules',
  module: (moduleId) => `/modules/${moduleId}`,
  moduleRubric: (moduleId) => `/modules/${moduleId}/rubric`,
  moduleBook: (moduleId) => `/modules/${moduleId}/module-book`,
  moduleGroups: (moduleId) => `/modules/${moduleId}/groups`,
  moduleGroup: (moduleId, groupId) => `/modules/${moduleId}/groups/${groupId}`,
  moduleStudents: (moduleId) => `/modules/${moduleId}/students`,
  moduleStudent: (moduleId, studentId) =>
    `/modules/${moduleId}/students/${studentId}`,
  moduleStudentImports: (moduleId, targetGroupId = '') => {
    const query = targetGroupId
      ? `?project_id=${encodeURIComponent(targetGroupId)}`
      : '';
    return `/modules/${moduleId}/students/import${query}`;
  },
};
