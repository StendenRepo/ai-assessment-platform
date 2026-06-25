import { apiRequest } from '@/lib/api/apiClient';
import { API_PATHS } from '@/lib/routes';

function assessmentRequest(path, options = {}) {
  return apiRequest(path, { ...options, onUnauthorized: true });
}

export function getAssessmentDraft(assessmentId) {
  return assessmentRequest(API_PATHS.assessmentDraft(assessmentId));
}

export function generateAssessmentSuggestions(assessmentId) {
  return assessmentRequest(API_PATHS.assessmentDraftGenerate(assessmentId), {
    method: 'POST',
  });
}

export function patchAssessmentOverrides(assessmentId, payload) {
  return assessmentRequest(API_PATHS.assessmentDraftOverrides(assessmentId), {
    method: 'PATCH',
    json: payload,
  });
}

export function revertCriterionOverride(assessmentId, criterionKey) {
  return assessmentRequest(API_PATHS.assessmentDraftRevert(assessmentId), {
    method: 'POST',
    json: { criterion_key: criterionKey },
  });
}

export function getAssessmentChat(assessmentId) {
  return assessmentRequest(API_PATHS.assessmentChat(assessmentId));
}

export function postAssessmentChat(
  assessmentId,
  message,
  { criterionKey } = {}
) {
  return assessmentRequest(API_PATHS.assessmentChat(assessmentId), {
    method: 'POST',
    json: {
      message,
      ...(criterionKey ? { criterion_key: criterionKey } : {}),
    },
  });
}

export function postAssessmentChatRefine(assessmentId) {
  return assessmentRequest(API_PATHS.assessmentChatRefine(assessmentId), {
    method: 'POST',
  });
}

export function postAssessmentChatApply(assessmentId, proposalId) {
  return assessmentRequest(API_PATHS.assessmentChatApply(assessmentId), {
    method: 'POST',
    json: { proposal_id: proposalId },
  });
}

export function postAssessmentChatReject(assessmentId, proposalId) {
  return assessmentRequest(API_PATHS.assessmentChatReject(assessmentId), {
    method: 'POST',
    json: { proposal_id: proposalId },
  });
}

export function postAssessmentChatUndo(assessmentId) {
  return assessmentRequest(API_PATHS.assessmentChatUndo(assessmentId), {
    method: 'POST',
  });
}

export function finalizeAssessment(assessmentId, { teacherNotes } = {}) {
  return assessmentRequest(API_PATHS.assessmentFinalize(assessmentId), {
    method: 'POST',
    json: { confirm: true, teacher_notes: teacherNotes || null },
  });
}

export function getFinalizedAssessment(assessmentId) {
  return assessmentRequest(API_PATHS.assessmentFinal(assessmentId));
}

export function getAssessmentAuditTrail(assessmentId) {
  return assessmentRequest(API_PATHS.assessmentAuditTrail(assessmentId));
}
