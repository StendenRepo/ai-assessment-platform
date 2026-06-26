import uuid
from pathlib import Path

import pytest

from app.config import settings
from app.models.enums import FileType, SourceType

LOGIN_URL = "/api/v1/auth/login"

RUBRIC_TEXT = (
    "Student demonstrates clean layered architecture and design patterns\n"
    "Student writes comprehensive unit tests for the modules\n"
    "Student documents the deployment pipeline thoroughly\n"
)
EVIDENCE_TEXT = (
    "Our project is built on a clean layered architecture using well known "
    "design patterns throughout the code. We also wrote comprehensive unit "
    "tests covering the core modules of the system."
)


def _auth_headers(client):
    res = client.post(
        LOGIN_URL, json={"email": "teacher@test.com", "password": "password123"}
    )
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _supported_judge(criterion_text, candidates, model=None):
    return {"supported": True, "best": candidates[0][0], "reason": "ok"}


def _fake_questions(criterion_text, quote, basis, model=None):
    return [f"{basis} question one", f"{basis} question two"]


@pytest.fixture
def seed(db, teacher, tmp_path, monkeypatch):
    from app.models.evidence import Evidence
    from app.models.file_record import FileRecord
    from app.models.module import Module
    from app.models.project import Project
    from app.models.student import Student, student_projects

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

    rubric = FileRecord(
        id=uuid.uuid4(),
        file_name="rubric.pdf",
        path="rubric.pdf",
        file_type="pdf",
        extracted_text=RUBRIC_TEXT,
    )
    db.add(rubric)
    db.flush()

    module = Module(
        id=uuid.uuid4(),
        teacher_id=teacher.id,
        name="Software Engineering",
        rubric_file_id=rubric.id,
    )
    db.add(module)
    db.flush()

    project = Project(id=uuid.uuid4(), module_id=module.id, name="Group A")
    student = Student(student_number="S-100", name="Alice")
    db.add_all([project, student])
    db.flush()
    project.students.append(student)

    relative = "S-100/report.md"
    full = Path(tmp_path) / "evidence" / relative
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(EVIDENCE_TEXT, encoding="utf-8")

    evidence = Evidence(
        id=uuid.uuid4(),
        student_id="S-100",
        file_name="report.md",
        file_type=FileType.markdown,
        file_path=relative,
        source_type=SourceType.upload,
    )
    db.add(evidence)
    db.commit()

    yield {"module": module}

    from app.models.assessment import Assessment
    from app.models.evidence_match import EvidenceMatch
    from app.models.generation_run import GenerationRun

    db.query(EvidenceMatch).delete(synchronize_session=False)
    db.query(GenerationRun).delete(synchronize_session=False)
    db.query(Assessment).delete(synchronize_session=False)
    db.query(Evidence).filter(Evidence.student_id == "S-100").delete(
        synchronize_session=False
    )
    db.execute(student_projects.delete())
    db.query(Student).filter(Student.student_number == "S-100").delete(
        synchronize_session=False
    )
    db.query(Project).filter(Project.id == project.id).delete(
        synchronize_session=False
    )
    db.query(Module).filter(Module.id == module.id).delete(
        synchronize_session=False
    )
    db.query(FileRecord).filter(FileRecord.id == rubric.id).delete(
        synchronize_session=False
    )
    db.commit()
    db.expire_all()


class TestAssessmentQuestions:
    def test_requires_a_matching_run_first(self, client, seed):
        headers = _auth_headers(client)
        res = client.post(
            "/api/v1/students/S-100/assessment-questions", json={}, headers=headers
        )
        assert res.status_code == 422

    def test_generates_questions_with_gaps_first(self, client, seed, monkeypatch):
        monkeypatch.setattr("app.ai.ai_judge.judge_criterion", _supported_judge)
        monkeypatch.setattr(
            "app.ai.question_generator.suggest_questions", _fake_questions
        )
        headers = _auth_headers(client)

        run = client.post(
            "/api/v1/students/S-100/evidence-matches", json={}, headers=headers
        )
        assert run.status_code == 200, run.text

        res = client.post(
            "/api/v1/students/S-100/assessment-questions", json={}, headers=headers
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert len(body["questions"]) == 3
        for item in body["questions"]:
            assert item["questions"]

        bases = [q["basis"] for q in body["questions"]]
        gap_index = next(i for i, b in enumerate(bases) if b == "gap")
        assert gap_index == 0

        deployment = next(
            q for q in body["questions"] if "deployment" in q["criterion_key"].lower()
        )
        assert deployment["basis"] == "gap"
        assert deployment["covered"] is False
