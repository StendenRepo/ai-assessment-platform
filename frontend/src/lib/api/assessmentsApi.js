import { apiFetch } from '@/lib/api/apiClient';
import { API_PATHS } from '@/lib/routes';

export function getAssessmentDraft(assessmentId) {
  return apiFetch(API_PATHS.assessmentDraft(assessmentId));
}

export function generateAssessmentSuggestions(assessmentId) {
  return apiFetch(API_PATHS.assessmentDraftGenerate(assessmentId), {
    method: 'POST',
  });
}

export function patchAssessmentOverrides(assessmentId, payload) {
  return apiFetch(API_PATHS.assessmentDraftOverrides(assessmentId), {
    method: 'PATCH',
    json: payload,
  });
}

export function revertCriterionOverride(assessmentId, criterionKey) {
  return apiFetch(API_PATHS.assessmentDraftRevert(assessmentId), {
    method: 'POST',
    json: { criterion_key: criterionKey },
  });
}

export function getAssessmentChat(assessmentId) {
  return apiFetch(API_PATHS.assessmentChat(assessmentId));
}

export function postAssessmentChat(assessmentId, message, { criterionKey } = {}) {
  return apiFetch(API_PATHS.assessmentChat(assessmentId), {
    method: 'POST',
    json: {
      message,
      ...(criterionKey ? { criterion_key: criterionKey } : {}),
    },
  });
}

export function postAssessmentChatRefine(assessmentId) {
  return apiFetch(API_PATHS.assessmentChatRefine(assessmentId), {
    method: 'POST',
  });
}

export function postAssessmentChatApply(assessmentId, proposalId) {
  return apiFetch(API_PATHS.assessmentChatApply(assessmentId), {
    method: 'POST',
    json: { proposal_id: proposalId },
  });
}

export function postAssessmentChatReject(assessmentId, proposalId) {
  return apiFetch(API_PATHS.assessmentChatReject(assessmentId), {
    method: 'POST',
    json: { proposal_id: proposalId },
  });
}

export function postAssessmentChatUndo(assessmentId) {
  return apiFetch(API_PATHS.assessmentChatUndo(assessmentId), {
    method: 'POST',
  });
}

export function finalizeAssessment(assessmentId, { teacherNotes } = {}) {
  return apiFetch(API_PATHS.assessmentFinalize(assessmentId), {
    method: 'POST',
    json: { confirm: true, teacher_notes: teacherNotes || null },
  });
}

export function getFinalizedAssessment(assessmentId) {
  return apiFetch(API_PATHS.assessmentFinal(assessmentId));
}

export function getAssessmentAuditTrail(assessmentId) {
  return apiFetch(API_PATHS.assessmentAuditTrail(assessmentId));
}
