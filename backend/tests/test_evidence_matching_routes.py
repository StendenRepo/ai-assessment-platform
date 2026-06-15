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
    from app.models.generation_run import GenerationRun
    from app.models.notification import Notification

    db.query(Notification).delete(synchronize_session=False)
    db.query(EvidenceMatch).delete(synchronize_session=False)
    db.query(GenerationRun).delete(synchronize_session=False)
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


def _fake_supported_judge(criterion_text, candidates, model=None):
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
        assert best["rationale"] and best["rationale"].startswith("AI:")

        deployment = _criterion(body, "deployment")
        assert deployment["covered"] is False
        assert deployment["matches"] == []
        assert deployment["missing_note"]

    def test_fallback_to_text_match_when_ai_unavailable(
        self, client, seed, monkeypatch
    ):
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

    def test_rerun_keeps_previous_run_and_get_can_fetch_it(
        self, client, seed, monkeypatch
    ):
        monkeypatch.setattr(
            "app.ai.ai_judge.judge_criterion", _fake_supported_judge
        )
        headers = _auth_headers(client)
        first = client.post(
            "/api/v1/students/S-100/evidence-matches", json={}, headers=headers
        ).json()
        first_run = first["run_id"]
        assert first_run is not None

        got = client.get("/api/v1/students/S-100/evidence-matches", headers=headers)
        assert got.status_code == 200
        assert got.json()["run_id"] == first_run
        assert got.json()["criteria"] == first["criteria"]

        again = client.post(
            "/api/v1/students/S-100/evidence-matches", json={}, headers=headers
        ).json()
        second_run = again["run_id"]
        assert second_run != first_run
        latest = client.get(
            "/api/v1/students/S-100/evidence-matches", headers=headers
        ).json()
        assert latest["run_id"] == second_run
        run_ids = {r["run_id"] for r in latest["runs"]}
        assert {first_run, second_run} <= run_ids

        original = client.get(
            f"/api/v1/students/S-100/evidence-matches?run_id={first_run}",
            headers=headers,
        ).json()
        assert original["run_id"] == first_run
        assert original["criteria"] == first["criteria"]

    def test_thorough_mode_is_recorded_on_the_run(self, client, seed, monkeypatch):
        monkeypatch.setattr(
            "app.ai.ai_judge.judge_criterion", _fake_supported_judge
        )
        headers = _auth_headers(client)
        body = client.post(
            "/api/v1/students/S-100/evidence-matches",
            json={"mode": "thorough"},
            headers=headers,
        ).json()
        assert body["mode"] == "thorough"
        assert body["runs"][0]["mode"] == "thorough"

    def test_delete_run_removes_it(self, client, seed, monkeypatch):
        monkeypatch.setattr(
            "app.ai.ai_judge.judge_criterion", _fake_supported_judge
        )
        headers = _auth_headers(client)
        first = client.post(
            "/api/v1/students/S-100/evidence-matches", json={}, headers=headers
        ).json()
        second = client.post(
            "/api/v1/students/S-100/evidence-matches", json={}, headers=headers
        ).json()

        res = client.delete(
            f"/api/v1/students/S-100/evidence-matches/runs/{second['run_id']}",
            headers=headers,
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["run_id"] == first["run_id"]
        assert {r["run_id"] for r in body["runs"]} == {first["run_id"]}

        gone = client.get(
            f"/api/v1/students/S-100/evidence-matches?run_id={second['run_id']}",
            headers=headers,
        )
        assert gone.status_code == 404

    def test_deleting_evidence_clears_saved_runs(
        self, client, seed, monkeypatch
    ):
        monkeypatch.setattr(
            "app.ai.ai_judge.judge_criterion", _fake_supported_judge
        )
        headers = _auth_headers(client)
        client.post(
            "/api/v1/students/S-100/evidence-matches", json={}, headers=headers
        )
        before = client.get(
            "/api/v1/students/S-100/evidence-matches", headers=headers
        ).json()
        assert before["runs"]

        ev_id = seed["evidence"].id
        res = client.delete(f"/api/v1/evidence/{ev_id}", headers=headers)
        assert res.status_code == 204, res.text

        after = client.get(
            "/api/v1/students/S-100/evidence-matches", headers=headers
        ).json()
        assert after["runs"] == []
        assert after["criteria"] == []

    def test_ai_vetoes_borderline_text_match(self, client, seed, monkeypatch):
        monkeypatch.setattr(settings, "MATCH_STRONG_THRESHOLD", 1.0)
        monkeypatch.setattr(
            "app.ai.ai_judge.judge_criterion",
            lambda *a, **k: {
                "supported": False,
                "best": None,
                "reason": "The excerpt does not address this criterion.",
            },
        )
        headers = _auth_headers(client)
        body = client.post(
            "/api/v1/students/S-100/evidence-matches", json={}, headers=headers
        ).json()
        arch = _criterion(body, "architecture")
        assert arch["covered"] is False
        assert arch["matches"] == []
        assert arch["missing_note"]

    def test_very_strong_text_match_survives_ai_rejection(
        self, client, seed, monkeypatch
    ):
        monkeypatch.setattr(settings, "MATCH_STRONG_THRESHOLD", 0.0)
        monkeypatch.setattr(
            "app.ai.ai_judge.judge_criterion",
            lambda *a, **k: {"supported": False, "best": None, "reason": "no"},
        )
        headers = _auth_headers(client)
        body = client.post(
            "/api/v1/students/S-100/evidence-matches", json={}, headers=headers
        ).json()
        assert _criterion(body, "architecture")["covered"] is True

    def test_admin_can_run_matching_on_another_teachers_module(
        self, client, db, seed, monkeypatch
    ):
        monkeypatch.setattr(
            "app.ai.ai_judge.judge_criterion", _fake_supported_judge
        )
        from app.core.security import hash_password
        from app.models.assessment import Assessment
        from app.models.evidence_match import EvidenceMatch
        from app.models.generation_run import GenerationRun
        from app.models.teacher import Teacher

        admin = Teacher(
            id=uuid.uuid4(),
            name="Admin",
            email="admin@test.com",
            password_hash=hash_password("password123"),
            is_admin=True,
        )
        db.add(admin)
        db.commit()
        try:
            res = client.post(
                LOGIN_URL,
                json={"email": "admin@test.com", "password": "password123"},
            )
            headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
            r = client.post(
                "/api/v1/students/S-100/evidence-matches",
                json={"module_id": str(seed["module"].id)},
                headers=headers,
            )
            assert r.status_code == 200, r.text
            run_id = r.json()["run_id"]
            assert any(c["covered"] for c in r.json()["criteria"])

            history = client.get(
                "/api/v1/students/S-100/evidence-matches", headers=headers
            ).json()
            assert history["run_id"] == run_id
            assert run_id in {run["run_id"] for run in history["runs"]}

            gone = client.delete(
                f"/api/v1/students/S-100/evidence-matches/runs/{run_id}",
                headers=headers,
            )
            assert gone.status_code == 200, gone.text
        finally:
            db.query(EvidenceMatch).delete(synchronize_session=False)
            db.query(GenerationRun).delete(synchronize_session=False)
            db.query(Assessment).delete(synchronize_session=False)
            db.delete(admin)
            db.commit()
            db.expire_all()

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
