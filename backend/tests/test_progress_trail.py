"""Tests for assessment progress trail builder and export PDF."""
from __future__ import annotations

import io
import uuid
import zipfile
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.core.security import create_access_token
from app.models.assessment import Assessment
from app.models.chat_message import ChatMessage
from app.models.enums import AssessmentStatus, SourceType
from app.models.evidence import Evidence
from app.services.assessment_progress_trail import build_progress_trail
from app.services.progress_trail_pdf import render_progress_trail_pdf


@pytest.fixture
def student_with_evidence(db, teacher):
    from app.models.project import Project
    from app.models.student import Student, student_projects
    from app.models.module import Module
    from app.models.enums import ProjectStatus, StudentStatus

    module = Module(
        id=uuid.uuid4(),
        name="Test Module",
        teacher_id=teacher.id,
        academic_year="2025-2026",
    )
    project = Project(
        id=uuid.uuid4(),
        module_id=module.id,
        name="Group A",
        status=ProjectStatus.active,
    )
    student = Student(
        student_number="1234567",
        name="Trail Student",
        status=StudentStatus.active,
    )
    db.add_all([module, project, student])
    db.flush()
    db.execute(
        student_projects.insert().values(
            student_id=student.student_number,
            project_id=project.id,
        )
    )
    ev = Evidence(
        id=uuid.uuid4(),
        student_id=student.student_number,
        project_id=project.id,
        file_name="report.pdf",
        file_path="1234567/report.pdf",
        source_type=SourceType.upload,
        uploaded_at=datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
    )
    db.add(ev)
    db.commit()
    return student, module


@pytest.fixture
def assessment(db, teacher, student_with_evidence):
    student, module = student_with_evidence
    a = Assessment(
        id=uuid.uuid4(),
        student_id=student.student_number,
        teacher_id=teacher.id,
        module_id=module.id,
        status=AssessmentStatus.draft,
        questions_cache_json={
            "generated_at": "2026-06-02T12:00:00+00:00",
            "module_id": str(module.id),
            "questions": [
                {
                    "criterion_key": "crit-1",
                    "basis": "gap",
                    "covered": False,
                    "questions": ["What architecture did you use?"],
                }
            ],
        },
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def _auth(teacher):
    return {"Authorization": f"Bearer {create_access_token(subject=str(teacher.id))}"}


class TestProgressTrailBuilder:
    def test_submission_excludes_recordings(self, db, student_with_evidence):
        student, _ = student_with_evidence
        trail = build_progress_trail(db, student=student, assessment=None)
        submission = trail["stages"][0]
        assert submission["key"] == "submission"
        assert submission["status"] == "completed"
        assert len(submission["content"]["files"]) == 1
        assert submission["content"]["files"][0]["file_name"] == "report.pdf"

    def test_ai_stage_includes_questions_cache(self, db, student_with_evidence, assessment):
        student, _ = student_with_evidence
        trail = build_progress_trail(db, student=student, assessment=assessment)
        ai_stage = trail["stages"][1]
        assert ai_stage["key"] == "ai_suggestion"
        types = {i["type"] for i in ai_stage["content"]["ai_items"]}
        assert "assessment_questions" in types

    @patch("app.services.ollama_client.generate")
    def test_teacher_accept_without_override(
        self, mock_gen, db, student_with_evidence, assessment, teacher
    ):
        from app.services import draft_assessment_service

        mock_gen.return_value = '{"score": 7, "comment": "Good.", "confidence": 0.8}'
        draft_assessment_service.generate_suggestions(
            db, assessment=assessment, teacher=teacher
        )
        draft_assessment_service.finalize_assessment(
            db, assessment=assessment, teacher=teacher
        )
        db.refresh(assessment)
        student, _ = student_with_evidence
        trail = build_progress_trail(db, student=student, assessment=assessment)
        teacher_stage = trail["stages"][2]
        final_stage = trail["stages"][3]
        assert teacher_stage["content"]["accepted_without_changes"] is True
        assert final_stage["status"] == "completed"

    def test_pending_stages_without_assessment(self, db, student_with_evidence):
        student, _ = student_with_evidence
        trail = build_progress_trail(db, student=student, assessment=None)
        assert trail["stages"][1]["status"] == "pending"
        assert trail["stages"][2]["status"] == "pending"
        assert trail["stages"][3]["status"] == "pending"

    def test_chat_in_ai_stage(self, db, student_with_evidence, assessment):
        db.add(
            ChatMessage(
                id=uuid.uuid4(),
                assessment_id=assessment.id,
                role="teacher",
                content="Why this score?",
                timestamp=datetime(2026, 6, 3, 9, 0, tzinfo=timezone.utc),
            )
        )
        db.add(
            ChatMessage(
                id=uuid.uuid4(),
                assessment_id=assessment.id,
                role="assistant",
                content="Based on the evidence file…",
                timestamp=datetime(2026, 6, 3, 9, 1, tzinfo=timezone.utc),
            )
        )
        db.commit()
        student, _ = student_with_evidence
        trail = build_progress_trail(db, student=student, assessment=assessment)
        chat_items = [i for i in trail["ai_items"] if i["type"] == "assessment_chat"]
        assert len(chat_items) == 1
        assert len(chat_items[0]["payload"]["messages"]) == 2


try:
    import weasyprint  # noqa: F401

    HAS_WEASYPRINT = True
except (ImportError, OSError):
    HAS_WEASYPRINT = False


def _pdf_text(pdf_bytes: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


@pytest.mark.skipif(not HAS_WEASYPRINT, reason="WeasyPrint system libraries unavailable")
class TestProgressTrailPdf:
    def test_pdf_smoke(self, db, student_with_evidence, assessment):
        student, _ = student_with_evidence
        trail = build_progress_trail(db, student=student, assessment=assessment)
        pdf_bytes = render_progress_trail_pdf(trail)
        assert pdf_bytes[:4] == b"%PDF"
        assert len(pdf_bytes) > 500

    def test_pdf_section_headings(self, db, student_with_evidence, assessment):
        student, _ = student_with_evidence
        trail = build_progress_trail(db, student=student, assessment=assessment)
        text = _pdf_text(render_progress_trail_pdf(trail))
        assert "Submission" in text
        assert "AI suggestion" in text
        assert "Teacher decision" in text
        assert "Final form" in text

    def test_pdf_contains_evidence_filename_only(self, db, student_with_evidence, assessment):
        student, _ = student_with_evidence
        trail = build_progress_trail(db, student=student, assessment=assessment)
        pdf_bytes = render_progress_trail_pdf(trail)
        text = _pdf_text(pdf_bytes)
        assert "report.pdf" in text

        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf_bytes))
        assert not reader.attachments

    def test_pdf_contains_full_chat_text(self, db, student_with_evidence, assessment):
        db.add(
            ChatMessage(
                id=uuid.uuid4(),
                assessment_id=assessment.id,
                role="teacher",
                content="Why this score?",
                timestamp=datetime(2026, 6, 3, 9, 0, tzinfo=timezone.utc),
            )
        )
        db.add(
            ChatMessage(
                id=uuid.uuid4(),
                assessment_id=assessment.id,
                role="assistant",
                content="Based on the evidence file the work meets the criterion.",
                timestamp=datetime(2026, 6, 3, 9, 1, tzinfo=timezone.utc),
            )
        )
        db.commit()
        student, _ = student_with_evidence
        trail = build_progress_trail(db, student=student, assessment=assessment)
        text = _pdf_text(render_progress_trail_pdf(trail))
        assert "Why this score?" in text
        assert "Based on the evidence file the work meets the criterion." in text

    def test_pdf_page_count_reasonable(self, db, student_with_evidence, assessment):
        from pypdf import PdfReader

        student, _ = student_with_evidence
        trail = build_progress_trail(db, student=student, assessment=assessment)
        reader = PdfReader(io.BytesIO(render_progress_trail_pdf(trail)))
        assert len(reader.pages) <= 80


class TestDossierExportIntegration:
    @patch("app.api.v1.endpoints.students.build_progress_trail_pdf")
    def test_dossier_contains_progress_trail(
        self, mock_pdf, client, db, teacher, student_with_evidence
    ):
        mock_pdf.return_value = b"%PDF-1.4 fake progress trail"
        student, _ = student_with_evidence
        res = client.get(
            f"/api/v1/students/{student.student_number}/export/dossier",
            headers=_auth(teacher),
        )
        assert res.status_code == 200
        zf = zipfile.ZipFile(io.BytesIO(res.content))
        assert "progress-trail.pdf" in zf.namelist()
        assert zf.read("progress-trail.pdf").startswith(b"%PDF")
