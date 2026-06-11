"""Tests for G2-146/147/150 assessment draft, override, chat, finalize."""
import uuid
from unittest.mock import patch

import pytest

from app.core.security import create_access_token
from app.models.assessment import Assessment
from app.models.audit_event import AuditEvent
from app.models.chat_message import ChatMessage
from app.models.enums import AssessmentStatus, AuditSource
from app.models.evidence import Evidence
from app.models.enums import EmbeddingStatus, FileType, SourceType
from app.services import draft_assessment_service


@pytest.fixture
def assessment(db, teacher):
    a = Assessment(
        id=uuid.uuid4(),
        student_id="9999999",
        teacher_id=teacher.id,
        status=AssessmentStatus.draft,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    yield a
    db.query(ChatMessage).delete()
    db.query(AuditEvent).delete()
    db.query(Evidence).delete()
    db.query(Assessment).delete()
    db.commit()


def _auth(teacher):
    return {"Authorization": f"Bearer {create_access_token(subject=str(teacher.id))}"}


MOCK_LLM_CRITERION = {
    "score": 7.5,
    "comment": "Strong evidence in auth.tsx supports code quality.",
    "confidence": 0.82,
}

MOCK_CHAT_RESPONSE = """{
  "reply": "I've tightened the testing criterion based on your feedback.",
  "updates": [{"criterion_key": "crit-4", "score": 8.5, "comment": "Expanded test coverage noted."}],
  "summary": "Revised summary after chat."
}"""


class TestGenerateSuggestions:
    @patch("app.services.draft_assessment_service.ollama_client.generate")
    def test_generate_populates_draft(self, mock_gen, db, assessment, teacher):
        mock_gen.return_value = '{"score": 7.5, "comment": "Good work.", "confidence": 0.8}'
        draft_assessment_service.generate_suggestions(
            db, assessment=assessment, teacher=teacher
        )
        db.refresh(assessment)
        assert assessment.draft_form_json is not None
        assert "crit-1" in assessment.draft_form_json["criteria"]
        assert assessment.draft_form_json["criteria"]["crit-1"]["ai"]["score"] == 7.5

        event = (
            db.query(AuditEvent)
            .filter(AuditEvent.action == "assessment.suggestions_generated")
            .first()
        )
        assert event is not None
        assert event.source == AuditSource.ai


class TestOverrides:
    @patch("app.services.draft_assessment_service.ollama_client.generate")
    def test_override_skips_unchanged_values(self, mock_gen, db, assessment, teacher):
        mock_gen.return_value = '{"score": 6, "comment": "AI view.", "confidence": 0.7}'
        draft_assessment_service.generate_suggestions(
            db, assessment=assessment, teacher=teacher
        )
        draft_assessment_service.apply_overrides(
            db,
            assessment=assessment,
            teacher=teacher,
            overrides=[{"criterion_key": "crit-1", "score": 6, "comment": "AI view."}],
        )
        db.refresh(assessment)
        assert not assessment.draft_form_json["criteria"]["crit-1"].get("is_overridden")
        audit_count = (
            db.query(AuditEvent)
            .filter(AuditEvent.action == "assessment.suggestion_overridden")
            .count()
        )
        assert audit_count == 0

    @patch("app.services.draft_assessment_service.ollama_client.generate")
    def test_override_records_ai_and_teacher(self, mock_gen, db, assessment, teacher):
        mock_gen.return_value = '{"score": 6, "comment": "AI view.", "confidence": 0.7}'
        draft_assessment_service.generate_suggestions(
            db, assessment=assessment, teacher=teacher
        )
        draft_assessment_service.apply_overrides(
            db,
            assessment=assessment,
            teacher=teacher,
            overrides=[
                {
                    "criterion_key": "crit-1",
                    "score": 9,
                    "comment": "Teacher disagrees — excellent refactor.",
                }
            ],
        )
        db.refresh(assessment)
        entry = assessment.draft_form_json["criteria"]["crit-1"]
        assert entry["is_overridden"] is True
        assert entry["effective"]["score"] == 9
        assert entry["ai"]["score"] == 6
        assert entry["teacher"]["comment"].startswith("Teacher disagrees")

        audit = (
            db.query(AuditEvent)
            .filter(AuditEvent.action == "assessment.suggestion_overridden")
            .first()
        )
        assert audit is not None
        assert audit.details_json["ai"]["score"] == 6
        assert audit.details_json["teacher"]["score"] == 9


class TestChatRefine:
    @patch("app.services.draft_assessment_service.ollama_client.chat")
    @patch("app.services.draft_assessment_service.ollama_client.generate")
    def test_chat_updates_non_overridden(self, mock_gen, mock_chat, db, assessment, teacher):
        mock_gen.return_value = '{"score": 5, "comment": "Initial.", "confidence": 0.6}'
        draft_assessment_service.generate_suggestions(
            db, assessment=assessment, teacher=teacher
        )
        mock_chat.return_value = MOCK_CHAT_RESPONSE
        reply, draft = draft_assessment_service.chat_refine(
            db,
            assessment=assessment,
            teacher=teacher,
            message="Please raise the testing score — more tests were added.",
        )
        assert "testing" in reply.lower() or "tightened" in reply.lower()
        assert draft["criteria"]["crit-4"]["ai"]["score"] == 8.5
        assert draft["criteria"]["crit-4"]["ai"].get("refined_via_chat") is True
        msgs = db.query(ChatMessage).filter(ChatMessage.assessment_id == assessment.id).all()
        assert len(msgs) == 2
        assert msgs[0].role == "teacher"
        assert msgs[1].role == "assistant"

    @patch("app.services.draft_assessment_service.ollama_client.chat")
    @patch("app.services.draft_assessment_service.ollama_client.generate")
    def test_chat_skips_overridden_criterion(self, mock_gen, mock_chat, db, assessment, teacher):
        mock_gen.return_value = '{"score": 5, "comment": "Initial.", "confidence": 0.6}'
        draft_assessment_service.generate_suggestions(
            db, assessment=assessment, teacher=teacher
        )
        draft_assessment_service.apply_overrides(
            db,
            assessment=assessment,
            teacher=teacher,
            overrides=[{"criterion_key": "crit-4", "score": 10, "comment": "Teacher locked."}],
        )
        mock_chat.return_value = MOCK_CHAT_RESPONSE
        _, draft = draft_assessment_service.chat_refine(
            db,
            assessment=assessment,
            teacher=teacher,
            message="Change testing score.",
        )
        assert draft["criteria"]["crit-4"]["effective"]["score"] == 10
        assert draft["criteria"]["crit-4"]["ai"]["score"] == 5

    @patch("app.services.draft_assessment_service.ollama_client.chat")
    @patch("app.services.draft_assessment_service.ollama_client.generate")
    def test_chat_blocked_after_finalize(self, mock_gen, mock_chat, client, db, assessment, teacher):
        mock_gen.return_value = '{"score": 7, "comment": "OK.", "confidence": 0.7}'
        draft_assessment_service.generate_suggestions(
            db, assessment=assessment, teacher=teacher
        )
        client.post(
            f"/api/v1/assessments/{assessment.id}/finalize",
            json={"confirm": True},
            headers=_auth(teacher),
        )
        res = client.post(
            f"/api/v1/assessments/{assessment.id}/chat",
            json={"message": "Try to refine"},
            headers=_auth(teacher),
        )
        assert res.status_code == 409


class TestFinalize:
    @patch("app.services.draft_assessment_service.ollama_client.generate")
    def test_finalize_locks_assessment(self, mock_gen, client, db, assessment, teacher):
        mock_gen.return_value = '{"score": 7, "comment": "OK.", "confidence": 0.7}'
        draft_assessment_service.generate_suggestions(
            db, assessment=assessment, teacher=teacher
        )
        res = client.post(
            f"/api/v1/assessments/{assessment.id}/finalize",
            json={"confirm": True, "teacher_notes": "Reviewed with team."},
            headers=_auth(teacher),
        )
        assert res.status_code == 200
        body = res.json()
        assert body["overall_grade"] is not None
        assert body["form"]["teacher_notes"] == "Reviewed with team."

        db.refresh(assessment)
        assert assessment.status == AssessmentStatus.final
        assert assessment.final_form_json is not None

        blocked = client.patch(
            f"/api/v1/assessments/{assessment.id}/draft/overrides",
            json={"overrides": [{"criterion_key": "crit-1", "score": 10}]},
            headers=_auth(teacher),
        )
        assert blocked.status_code == 409

        final_get = client.get(
            f"/api/v1/assessments/{assessment.id}/final",
            headers=_auth(teacher),
        )
        assert final_get.status_code == 200


class TestDraftEndpoints:
    def test_get_empty_draft(self, client, assessment, teacher):
        res = client.get(
            f"/api/v1/assessments/{assessment.id}/draft",
            headers=_auth(teacher),
        )
        assert res.status_code == 200
        assert res.json()["status"] == "draft"
        assert len(res.json()["criteria"]) == 5
