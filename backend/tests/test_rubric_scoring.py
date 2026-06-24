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


@pytest.fixture
def seed_two(db, teacher):
    from app.models.assessment import Assessment
    from app.models.file_record import FileRecord
    from app.models.module import Module
    from app.models.module_rubric import ModuleRubric
    from app.models.project import Project
    from app.models.rubric_score import RubricScore
    from app.models.student import Student, student_projects

    fr1 = FileRecord(id=uuid.uuid4(), file_name="a.pdf", path="a.pdf", file_type="pdf", extracted_text="x x x")
    fr2 = FileRecord(id=uuid.uuid4(), file_name="b.pdf", path="b.pdf", file_type="pdf", extracted_text="y y y")
    module = Module(id=uuid.uuid4(), teacher_id=teacher.id, name="Combo")
    db.add_all([fr1, fr2, module])
    db.flush()
    r1 = ModuleRubric(id=uuid.uuid4(), module_id=module.id, file_id=fr1.id, name="Report", weight=0.6, position=0)
    r2 = ModuleRubric(id=uuid.uuid4(), module_id=module.id, file_id=fr2.id, name="Reflection", weight=0.4, position=1)
    project = Project(id=uuid.uuid4(), module_id=module.id, name="G")
    student = Student(student_number="S-301", name="Eve")
    db.add_all([r1, r2, project, student])
    db.flush()
    project.students.append(student)
    assessment = Assessment(id=uuid.uuid4(), student_id="S-301", teacher_id=teacher.id, module_id=module.id)
    db.add(assessment)
    db.flush()
    db.add_all([
        RubricScore(id=uuid.uuid4(), assessment_id=assessment.id, rubric_id=r1.id, score=9.0, grade="A"),
        RubricScore(id=uuid.uuid4(), assessment_id=assessment.id, rubric_id=r2.id, score=4.0, grade="F"),
    ])
    db.commit()

    yield

    db.query(RubricScore).delete(synchronize_session=False)
    db.query(Assessment).delete(synchronize_session=False)
    db.query(ModuleRubric).delete(synchronize_session=False)
    db.execute(student_projects.delete())
    db.query(Student).filter(Student.student_number == "S-301").delete(synchronize_session=False)
    db.query(Project).filter(Project.id == project.id).delete(synchronize_session=False)
    db.query(Module).filter(Module.id == module.id).delete(synchronize_session=False)
    db.query(FileRecord).filter(FileRecord.id.in_([fr1.id, fr2.id])).delete(synchronize_session=False)
    db.commit()
    db.expire_all()


class TestFinalGrade:
    def test_weighted_combine(self, client, seed_two):
        headers = _auth(client)
        res = client.get("/api/v1/students/S-301/final-grade", headers=headers)
        assert res.status_code == 200, res.text
        body = res.json()
        # (9*0.6 + 4*0.4) / 1.0 = 7.0
        assert body["score"] == 7.0
        assert body["grade"] == "B-"
        assert body["total_weight"] == 1.0
        assert len(body["components"]) == 2
