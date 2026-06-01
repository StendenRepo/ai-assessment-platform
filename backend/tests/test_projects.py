import uuid

import pytest

LOGIN_URL = "/api/v1/auth/login"
PROJECTS_URL = "/api/v1/projects"


def _auth_headers(client):
    res = client.post(
        LOGIN_URL, json={"email": "teacher@test.com", "password": "password123"}
    )
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _make_project(db, teacher, name="Demo Project"):
    from app.models.module import Module
    from app.models.project import Project

    module = Module(id=uuid.uuid4(), teacher_id=teacher.id, name="Demo Module")
    db.add(module)
    db.commit()

    project = Project(id=uuid.uuid4(), module_id=module.id, name=name)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project, module


@pytest.fixture
def project(db, teacher):
    project, module = _make_project(db, teacher)
    yield project
    from app.models.project import Project
    from app.models.module import Module
    from app.models.student import Student

    db.query(Student).filter(Student.project_id == project.id).delete()
    db.query(Project).filter(Project.id == project.id).delete()
    db.query(Module).filter(Module.id == module.id).delete()
    db.commit()


class TestAddStudent:
    def test_add_student_returns_201(self, client, project):
        headers = _auth_headers(client)
        res = client.post(
            f"{PROJECTS_URL}/{project.id}/students",
            json={"name": "Lisa Anderson", "student_number": "S2034567"},
            headers=headers,
        )
        assert res.status_code == 201
        body = res.json()
        assert body["name"] == "Lisa Anderson"
        assert body["student_number"] == "S2034567"
        assert body["project_id"] == str(project.id)
        assert body["status"] == "active"
        assert "id" in body

    def test_added_student_appears_in_list(self, client, project):
        headers = _auth_headers(client)
        client.post(
            f"{PROJECTS_URL}/{project.id}/students",
            json={"name": "Thomas Johnson", "student_number": "S2034789"},
            headers=headers,
        )
        res = client.get(f"{PROJECTS_URL}/{project.id}/students", headers=headers)
        assert res.status_code == 200
        numbers = [s["student_number"] for s in res.json()]
        assert "S2034789" in numbers

    def test_duplicate_student_number_same_project_rejected(self, client, project):
        headers = _auth_headers(client)
        payload = {"name": "Maya Patel", "student_number": "S2035012"}
        first = client.post(
            f"{PROJECTS_URL}/{project.id}/students", json=payload, headers=headers
        )
        assert first.status_code == 201

        dup = client.post(
            f"{PROJECTS_URL}/{project.id}/students",
            json={"name": "Different Name", "student_number": "S2035012"},
            headers=headers,
        )
        assert dup.status_code == 409

    def test_same_student_number_different_project_allowed(self, client, project, db, teacher):
        headers = _auth_headers(client)
        other, other_module = _make_project(db, teacher, name="Other Project")
        try:
            client.post(
                f"{PROJECTS_URL}/{project.id}/students",
                json={"name": "Mark Davis", "student_number": "S2034891"},
                headers=headers,
            )
            res = client.post(
                f"{PROJECTS_URL}/{other.id}/students",
                json={"name": "Mark Davis", "student_number": "S2034891"},
                headers=headers,
            )
            assert res.status_code == 201
        finally:
            from app.models.project import Project
            from app.models.module import Module
            from app.models.student import Student

            db.query(Student).filter(Student.project_id == other.id).delete()
            db.query(Project).filter(Project.id == other.id).delete()
            db.query(Module).filter(Module.id == other_module.id).delete()
            db.commit()

    def test_whitespace_is_trimmed(self, client, project):
        headers = _auth_headers(client)
        res = client.post(
            f"{PROJECTS_URL}/{project.id}/students",
            json={"name": "  Padded Name  ", "student_number": "  S999  "},
            headers=headers,
        )
        assert res.status_code == 201
        body = res.json()
        assert body["name"] == "Padded Name"
        assert body["student_number"] == "S999"

    def test_missing_name_returns_422(self, client, project):
        headers = _auth_headers(client)
        res = client.post(
            f"{PROJECTS_URL}/{project.id}/students",
            json={"student_number": "S111"},
            headers=headers,
        )
        assert res.status_code == 422

    def test_blank_name_returns_422(self, client, project):
        headers = _auth_headers(client)
        res = client.post(
            f"{PROJECTS_URL}/{project.id}/students",
            json={"name": "   ", "student_number": "S111"},
            headers=headers,
        )
        assert res.status_code == 422

    def test_missing_student_number_returns_422(self, client, project):
        headers = _auth_headers(client)
        res = client.post(
            f"{PROJECTS_URL}/{project.id}/students",
            json={"name": "No Number"},
            headers=headers,
        )
        assert res.status_code == 422

    def test_unknown_project_returns_404(self, client, teacher):
        headers = _auth_headers(client)
        res = client.post(
            f"{PROJECTS_URL}/{uuid.uuid4()}/students",
            json={"name": "Ghost", "student_number": "S000"},
            headers=headers,
        )
        assert res.status_code == 404

    def test_add_without_token_returns_401(self, client, project):
        res = client.post(
            f"{PROJECTS_URL}/{project.id}/students",
            json={"name": "Lisa", "student_number": "S1"},
        )
        assert res.status_code == 401


class TestListProjects:
    def test_list_includes_created_project(self, client, project):
        headers = _auth_headers(client)
        res = client.get(PROJECTS_URL, headers=headers)
        assert res.status_code == 200
        ids = [p["id"] for p in res.json()]
        assert str(project.id) in ids

    def test_get_project_reports_student_count(self, client, project):
        headers = _auth_headers(client)
        client.post(
            f"{PROJECTS_URL}/{project.id}/students",
            json={"name": "Counted", "student_number": "S-COUNT"},
            headers=headers,
        )
        res = client.get(f"{PROJECTS_URL}/{project.id}", headers=headers)
        assert res.status_code == 200
        assert res.json()["student_count"] >= 1

    def test_get_unknown_project_returns_404(self, client, teacher):
        headers = _auth_headers(client)
        res = client.get(f"{PROJECTS_URL}/{uuid.uuid4()}", headers=headers)
        assert res.status_code == 404

    def test_list_without_token_returns_401(self, client):
        res = client.get(PROJECTS_URL)
        assert res.status_code == 401


class TestAuthorizationScoping:
    """A teacher may only see and touch projects they own (project -> module
    -> teacher). Other teachers' projects must look like they don't exist."""

    def _other_teachers_project(self, db):
        from app.core.security import hash_password
        from app.models.module import Module
        from app.models.project import Project
        from app.models.teacher import Teacher

        other = Teacher(
            id=uuid.uuid4(),
            name="Other Teacher",
            email="other@test.com",
            password_hash=hash_password("password123"),
        )
        db.add(other)
        db.commit()
        module = Module(id=uuid.uuid4(), teacher_id=other.id, name="Other Module")
        db.add(module)
        db.commit()
        project = Project(id=uuid.uuid4(), module_id=module.id, name="Other Project")
        db.add(project)
        db.commit()
        db.refresh(project)
        return other, module, project

    def test_other_teachers_project_is_hidden(self, client, teacher, db):
        from app.models.module import Module
        from app.models.project import Project
        from app.models.student import Student
        from app.models.teacher import Teacher

        other, module, project = self._other_teachers_project(db)
        headers = _auth_headers(client)  # logs in as the fixture teacher
        try:
            # Not listed
            listed = client.get(PROJECTS_URL, headers=headers).json()
            assert str(project.id) not in [p["id"] for p in listed]
            # Direct access is 404 (not 403 — don't leak existence)
            assert client.get(f"{PROJECTS_URL}/{project.id}", headers=headers).status_code == 404
            assert (
                client.get(f"{PROJECTS_URL}/{project.id}/students", headers=headers).status_code
                == 404
            )
            # Cannot add or import into someone else's project
            assert (
                client.post(
                    f"{PROJECTS_URL}/{project.id}/students",
                    json={"name": "X", "student_number": "S1"},
                    headers=headers,
                ).status_code
                == 404
            )
        finally:
            db.query(Student).filter(Student.project_id == project.id).delete()
            db.query(Project).filter(Project.id == project.id).delete()
            db.query(Module).filter(Module.id == module.id).delete()
            db.query(Teacher).filter(Teacher.id == other.id).delete()
            db.commit()
