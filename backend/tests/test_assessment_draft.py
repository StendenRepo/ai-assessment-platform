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


MOCK_CHAT_RESPONSE = """{
  "reply": "I've tightened the testing criterion based on your feedback.",
  "updates": [{"criterion_key": "crit-4", "score": 8.5, "comment": "Expanded test coverage noted in evidence.pdf."}],
  "summary": "Revised summary after chat."
}"""


class TestGenerateSuggestions:
    @patch("app.services.ollama_client.generate")
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
    @patch("app.services.ollama_client.generate")
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

    @patch("app.services.ollama_client.generate")
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


class TestChatDiscuss:
    @patch("app.services.ollama_client.chat")
    @patch("app.services.ollama_client.generate")
    def test_discuss_does_not_mutate_draft(self, mock_gen, mock_chat, db, assessment, teacher):
        mock_gen.return_value = '{"score": 5, "comment": "Initial.", "confidence": 0.6}'
        draft_assessment_service.generate_suggestions(
            db, assessment=assessment, teacher=teacher
        )
        db.refresh(assessment)
        before = assessment.draft_form_json["criteria"]["crit-4"]["ai"]["score"]
        mock_chat.return_value = "Testing looks adequate given the evidence uploaded."
        reply = draft_assessment_service.chat_discuss(
            db,
            assessment=assessment,
            teacher=teacher,
            message="Why is testing only 5?",
        )
        db.refresh(assessment)
        assert "testing" in reply.lower() or "evidence" in reply.lower()
        assert assessment.draft_form_json["criteria"]["crit-4"]["ai"]["score"] == before
        msgs = db.query(ChatMessage).filter(ChatMessage.assessment_id == assessment.id).all()
        assert len(msgs) == 2
        assert msgs[0].metadata_json["type"] == "discuss"


class TestChatRefineFlow:
    @patch("app.services.ollama_client.chat")
    @patch("app.services.ollama_client.generate")
    def test_propose_then_apply_updates_draft(self, mock_gen, mock_chat, db, assessment, teacher):
        mock_gen.return_value = '{"score": 5, "comment": "Initial.", "confidence": 0.6}'
        draft_assessment_service.generate_suggestions(
            db, assessment=assessment, teacher=teacher
        )
        mock_chat.side_effect = [
            "They added more tests in the latest upload.",
            MOCK_CHAT_RESPONSE,
        ]
        draft_assessment_service.chat_discuss(
            db,
            assessment=assessment,
            teacher=teacher,
            message="Please raise the testing score — more tests were added.",
        )
        proposal = draft_assessment_service.chat_propose_refine(
            db, assessment=assessment, teacher=teacher
        )
        db.refresh(assessment)
        assert assessment.draft_form_json["criteria"]["crit-4"]["ai"]["score"] == 5
        assert proposal["proposed_changes"]
        assert proposal["proposal_id"]

        draft, applied = draft_assessment_service.chat_apply_proposal(
            db,
            assessment=assessment,
            teacher=teacher,
            proposal_id=uuid.UUID(proposal["proposal_id"]),
        )
        assert draft["criteria"]["crit-4"]["ai"]["score"] == 8.5
        assert applied
        assert draft["criteria"]["crit-4"]["ai"].get("refined_via_chat") is True

    @patch("app.services.ollama_client.chat")
    @patch("app.services.ollama_client.generate")
    def test_propose_infers_from_conversation_when_llm_empty(
        self, mock_gen, mock_chat, db, assessment, teacher
    ):
        mock_gen.return_value = '{"score": 8, "comment": "Initial.", "confidence": 0.6}'
        draft_assessment_service.generate_suggestions(
            db, assessment=assessment, teacher=teacher
        )
        mock_chat.side_effect = [
            "Code Quality should be revised from 8/10 to 0/10 — no actual code in the upload.",
            '{"reply": "No structured updates", "updates": []}',
            '{"reply": "Still empty", "updates": []}',
        ]
        draft_assessment_service.chat_discuss(
            db,
            assessment=assessment,
            teacher=teacher,
            message="I think code quality should be 0 since there is no code.",
        )
        proposal = draft_assessment_service.chat_propose_refine(
            db, assessment=assessment, teacher=teacher
        )
        crit1 = next(
            (c for c in proposal["proposed_changes"] if c["criterion_key"] == "crit-1"),
            None,
        )
        assert crit1 is not None
        assert crit1["after_score"] == 0.0
        assert crit1["before_score"] == 8.0

    @patch("app.services.ollama_client.chat")
    @patch("app.services.ollama_client.generate")
    def test_propose_infers_bulk_all_criteria_to_score(
        self, mock_gen, mock_chat, db, assessment, teacher
    ):
        mock_gen.return_value = '{"score": 3, "comment": "Initial.", "confidence": 0.6}'
        draft_assessment_service.generate_suggestions(
            db, assessment=assessment, teacher=teacher
        )
        mock_chat.side_effect = [
            "Understood — all criteria should have a score of 10.",
            '{"reply": "All criteria updated to 10", "updates": [{"criterion_key": "crit-2", "score": 2, "comment": "wrong"}]}',
        ]
        draft_assessment_service.chat_discuss(
            db,
            assessment=assessment,
            teacher=teacher,
            message="all the criteria should have a score of 10",
        )
        proposal = draft_assessment_service.chat_propose_refine(
            db, assessment=assessment, teacher=teacher
        )
        assert len(proposal["proposed_changes"]) == 5
        assert all(c["after_score"] == 10.0 for c in proposal["proposed_changes"])
        assert proposal["reply"].startswith("Proposed updates:")

    @patch("app.services.ollama_client.chat")
    @patch("app.services.ollama_client.generate")
    def test_propose_skips_overridden_criterion(self, mock_gen, mock_chat, db, assessment, teacher):
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
        mock_chat.side_effect = ["OK", MOCK_CHAT_RESPONSE]
        draft_assessment_service.chat_discuss(
            db,
            assessment=assessment,
            teacher=teacher,
            message="Change testing score.",
        )
        proposal = draft_assessment_service.chat_propose_refine(
            db, assessment=assessment, teacher=teacher
        )
        assert not any(
            c["criterion_key"] == "crit-4" for c in proposal["proposed_changes"]
        )
        db.refresh(assessment)
        assert assessment.draft_form_json["criteria"]["crit-4"]["effective"]["score"] == 10

    @patch("app.services.ollama_client.chat")
    @patch("app.services.ollama_client.generate")
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
            json={"message": "Try to discuss"},
            headers=_auth(teacher),
        )
        assert res.status_code == 409


class TestFinalize:
    @patch("app.services.ollama_client.generate")
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


class TestDraftEndpoints:
    def test_get_empty_draft(self, client, assessment, teacher):
        res = client.get(
            f"/api/v1/assessments/{assessment.id}/draft",
            headers=_auth(teacher),
        )
        assert res.status_code == 200
        assert res.json()["status"] == "draft"
        assert len(res.json()["criteria"]) == 5
