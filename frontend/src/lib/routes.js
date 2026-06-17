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
  authLogin: '/auth/login',
  authMe: '/auth/me',
  authUsers: '/auth/users',
  evidenceSupportedTypes: '/evidence/supported-types',
  evidence: (evidenceId) => `/evidence/${evidenceId}`,
  evidenceContent: (evidenceId) => `/evidence/${evidenceId}/content`,
  evidenceFile: (evidenceId) => `/evidence/${evidenceId}/file`,
  modules: '/modules',
  module: (moduleId) => `/modules/${moduleId}`,
  moduleRubric: (moduleId) => `/modules/${moduleId}/rubric`,
  moduleRubricFile: (moduleId) => `/modules/${moduleId}/rubric/file`,
  moduleRubricContent: (moduleId) => `/modules/${moduleId}/rubric/content`,
  moduleBook: (moduleId) => `/modules/${moduleId}/module-book`,
  moduleBookFile: (moduleId) => `/modules/${moduleId}/module-book/file`,
  moduleBookContent: (moduleId) => `/modules/${moduleId}/module-book/content`,
  moduleGroups: (moduleId) => `/modules/${moduleId}/groups`,
  moduleGroup: (moduleId, groupId) => `/modules/${moduleId}/groups/${groupId}`,
  projectEvidence: (projectId) => `/projects/${projectId}/evidence`,
  moduleStudents: (moduleId) => `/modules/${moduleId}/students`,
  moduleStudent: (moduleId, studentId) =>
    `/modules/${moduleId}/students/${studentId}`,
  studentEvidence: (studentId) => `/students/${studentId}/evidence`,
  studentDossierExport: (studentId) => `/students/${studentId}/export/dossier`,
  studentEvidenceMatches: (studentId) =>
    `/students/${studentId}/evidence-matches`,
  studentEvidenceMatchRun: (studentId, runId) =>
    `/students/${studentId}/evidence-matches/runs/${runId}`,
  moduleGradesExport: (moduleId) => `/modules/${moduleId}/export/grades`,
  moduleArchiveExport: (moduleId) => `/modules/${moduleId}/export/archive`,
  moduleStudentImports: (moduleId, targetGroupId = '') => {
    const query = targetGroupId
      ? `?project_id=${encodeURIComponent(targetGroupId)}`
      : '';
    return `/modules/${moduleId}/students/import${query}`;
  },
  assessmentForStudent: (studentId) => `/assessments/for-student/${studentId}`,
  assessmentRecordingState: (assessmentId) =>
    `/assessments/${assessmentId}/recording`,
  assessmentConsent: (assessmentId) => `/assessments/${assessmentId}/consent`,
  assessmentRecordings: (assessmentId) =>
    `/assessments/${assessmentId}/recordings`,
  assessmentRecording: (assessmentId, recordingId) =>
    `/assessments/${assessmentId}/recordings/${recordingId}`,
  notifications: (unreadOnly = false) =>
    `/notifications?unread_only=${unreadOnly ? 'true' : 'false'}`,
  notificationRead: (notificationId) => `/notifications/${notificationId}/read`,
};
