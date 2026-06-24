import uuid

import pytest

LOGIN_URL = "/api/v1/auth/login"

RUBRIC_TEXT = (
    "Student writes clean readable code\n"
    "Student documents the public API\n"
    "Student writes unit tests for the modules\n"
)


def _auth(client):
    res = client.post(
        LOGIN_URL, json={"email": "teacher@test.com", "password": "password123"}
    )
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _fake_assess(criterion, matches, rubric_excerpt, recording_text):
    return {"score": 8.0, "comment": "ok", "confidence": 0.9, "missing_gaps": None}


@pytest.fixture
def seed(db, teacher):
    from app.models.file_record import FileRecord
    from app.models.module import Module
    from app.models.module_rubric import ModuleRubric
    from app.models.project import Project
    from app.models.student import Student, student_projects

    record = FileRecord(
        id=uuid.uuid4(),
        file_name="report-rubric.pdf",
        path="report-rubric.pdf",
        file_type="pdf",
        extracted_text=RUBRIC_TEXT,
    )
    module = Module(id=uuid.uuid4(), teacher_id=teacher.id, name="SQ")
    db.add_all([record, module])
    db.flush()

    rubric = ModuleRubric(
        id=uuid.uuid4(),
        module_id=module.id,
        file_id=record.id,
        name="Report",
        weight=0.6,
        position=0,
    )
    project = Project(id=uuid.uuid4(), module_id=module.id, name="Group A")
    student = Student(student_number="S-300", name="Dana")
    db.add_all([rubric, project, student])
    db.flush()
    project.students.append(student)
    db.commit()

    yield {"rubric": rubric, "module": module}

    from app.models.assessment import Assessment
    from app.models.rubric_score import RubricScore

    db.query(RubricScore).delete(synchronize_session=False)
    db.query(Assessment).delete(synchronize_session=False)
    db.query(ModuleRubric).delete(synchronize_session=False)
    db.execute(student_projects.delete())
    db.query(Student).filter(Student.student_number == "S-300").delete(
        synchronize_session=False
    )
    db.query(Project).filter(Project.id == project.id).delete(
        synchronize_session=False
    )
    db.query(Module).filter(Module.id == module.id).delete(
        synchronize_session=False
    )
    db.query(FileRecord).filter(FileRecord.id == record.id).delete(
        synchronize_session=False
    )
    db.commit()
    db.expire_all()


class TestRubricScoring:
    def test_generate_and_list(self, client, seed, monkeypatch):
        monkeypatch.setattr(
            "app.services.rubric_scoring_service._llm_assess_criterion",
            _fake_assess,
        )
        headers = _auth(client)
        rid = str(seed["rubric"].id)

        res = client.post(
            f"/api/v1/students/S-300/rubric-scores/{rid}", headers=headers
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["score"] == 8.0
        assert body["grade"] == "B+"
        assert body["weight"] == 0.6
        assert body["rubric_name"] == "Report"

        listed = client.get(
            "/api/v1/students/S-300/rubric-scores", headers=headers
        )
        assert listed.status_code == 200
        rows = listed.json()
        assert len(rows) == 1
        assert rows[0]["rubric_id"] == rid

    def test_unknown_rubric_returns_404(self, client, seed):
        headers = _auth(client)
        res = client.post(
            f"/api/v1/students/S-300/rubric-scores/{uuid.uuid4()}", headers=headers
        )
        assert res.status_code == 404
