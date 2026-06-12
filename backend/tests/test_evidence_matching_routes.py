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

    yield {"module": module, "student": student, "evidence": evidence}

    from app.models.assessment import Assessment
    from app.models.evidence_match import EvidenceMatch

    db.query(EvidenceMatch).delete(synchronize_session=False)
    db.query(Assessment).delete(synchronize_session=False)
    db.query(Evidence).filter(Evidence.student_id == "S-100").delete(synchronize_session=False)
    db.execute(student_projects.delete())
    db.query(Student).filter(Student.student_number == "S-100").delete(synchronize_session=False)
    db.query(Project).filter(Project.id == project.id).delete(synchronize_session=False)
    db.query(Module).filter(Module.id == module.id).delete(synchronize_session=False)
    db.query(FileRecord).filter(FileRecord.id == rubric.id).delete(synchronize_session=False)
    db.commit()
    db.expire_all()


def _criterion(body, needle):
    return next(c for c in body["criteria"] if needle in c["criterion_key"].lower())


def _fake_supported_judge(criterion_text, candidates):
    return {
        "supported": True,
        "best": candidates[0][0],
        "reason": f"AI: evidence supports {criterion_text[:25]}",
    }


class TestEvidenceMatchingRoutes:
    def test_run_links_evidence_and_flags_missing(self, client, seed, monkeypatch):
        monkeypatch.setattr(
            "app.ai.ai_judge.judge_criterion", _fake_supported_judge
        )
        headers = _auth_headers(client)
        res = client.post(
            "/api/v1/students/S-100/evidence-matches", json={}, headers=headers
        )
        assert res.status_code == 200, res.text
        body = res.json()

        assert len(body["criteria"]) == 3

        arch = _criterion(body, "architecture")
        assert arch["covered"] is True
        assert arch["matches"]
        best = arch["matches"][0]
        assert best["confidence_score"] >= settings.MATCH_CONFIDENCE_THRESHOLD
        normalized = " ".join(EVIDENCE_TEXT.split())
        assert best["supporting_quote"] in normalized
        # The AI verdict's reason is surfaced as the rationale.
        assert best["rationale"] and best["rationale"].startswith("AI:")

        deployment = _criterion(body, "deployment")
        assert deployment["covered"] is False
        assert deployment["matches"] == []
        assert deployment["missing_note"]

    def test_fallback_to_text_match_when_ai_unavailable(
        self, client, seed, monkeypatch
    ):
        # AI down → judge returns None → grounded TF-IDF threshold decides.
        monkeypatch.setattr(
            "app.ai.ai_judge.judge_criterion", lambda *a, **k: None
        )
        headers = _auth_headers(client)
        body = client.post(
            "/api/v1/students/S-100/evidence-matches", json={}, headers=headers
        ).json()
        arch = _criterion(body, "architecture")
        assert arch["covered"] is True
        assert arch["matches"][0]["rationale"] is None
        assert _criterion(body, "deployment")["covered"] is False

    def test_get_returns_stored_mapping_and_rerun_replaces(
        self, client, seed, monkeypatch
    ):
        monkeypatch.setattr(
            "app.ai.ai_judge.judge_criterion", _fake_supported_judge
        )
        headers = _auth_headers(client)
        first = client.post(
            "/api/v1/students/S-100/evidence-matches", json={}, headers=headers
        ).json()

        got = client.get("/api/v1/students/S-100/evidence-matches", headers=headers)
        assert got.status_code == 200
        assert got.json()["criteria"] == first["criteria"]

        again = client.post(
            "/api/v1/students/S-100/evidence-matches", json={}, headers=headers
        ).json()
        arch = _criterion(again, "architecture")
        assert len(arch["matches"]) == len(_criterion(first, "architecture")["matches"])

    def test_get_is_empty_before_any_run(self, client, seed):
        headers = _auth_headers(client)
        body = client.get(
            "/api/v1/students/S-100/evidence-matches", headers=headers
        ).json()
        assert body["criteria"] == []

    def test_missing_rubric_returns_422(self, client, db, teacher, monkeypatch, tmp_path):
        from app.models.module import Module
        from app.models.project import Project
        from app.models.student import Student, student_projects

        monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
        module = Module(id=uuid.uuid4(), teacher_id=teacher.id, name="No Rubric")
        project = Project(id=uuid.uuid4(), module_id=module.id, name="G")
        student = Student(student_number="S-200", name="Bob")
        db.add_all([module, project, student])
        db.flush()
        project.students.append(student)
        db.commit()

        headers = _auth_headers(client)
        try:
            res = client.post(
                "/api/v1/students/S-200/evidence-matches", json={}, headers=headers
            )
            assert res.status_code == 422
        finally:
            db.execute(student_projects.delete())
            db.query(Student).filter(Student.student_number == "S-200").delete(synchronize_session=False)
            db.query(Project).filter(Project.id == project.id).delete(synchronize_session=False)
            db.query(Module).filter(Module.id == module.id).delete(synchronize_session=False)
            db.commit()
            db.expire_all()
