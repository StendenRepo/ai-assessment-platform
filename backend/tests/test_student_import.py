import io
import uuid

import pytest
from openpyxl import Workbook

LOGIN_URL = "/api/v1/auth/login"
PROJECTS_URL = "/api/v1/projects"


def _auth_headers(client):
    res = client.post(
        LOGIN_URL, json={"email": "teacher@test.com", "password": "password123"}
    )
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _make_project(db, teacher, name="Import Project"):
    from app.models.module import Module
    from app.models.project import Project

    module = Module(id=uuid.uuid4(), teacher_id=teacher.id, name="Import Module")
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
    from app.models.module import Module
    from app.models.project import Project
    from app.models.student import Student

    db.query(Student).filter(Student.project_id == project.id).delete()
    db.query(Project).filter(Project.id == project.id).delete()
    db.query(Module).filter(Module.id == module.id).delete()
    db.commit()


def _xlsx_bytes(rows, headers=("Name", "Student Number")):
    wb = Workbook()
    ws = wb.active
    ws.append(list(headers))
    for r in rows:
        ws.append(list(r))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _upload(client, project, headers, data, filename="students.xlsx"):
    content_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if filename.endswith(".xlsx")
        else "text/csv"
    )
    return client.post(
        f"{PROJECTS_URL}/{project.id}/students/import",
        files={"file": (filename, io.BytesIO(data), content_type)},
        headers=headers,
    )


class TestImportXlsx:
    def test_valid_rows_all_imported(self, client, project):
        headers = _auth_headers(client)
        data = _xlsx_bytes([("Lisa Anderson", "S1001"), ("Tom Johnson", "S1002")])
        res = _upload(client, project, headers, data)
        assert res.status_code == 200
        body = res.json()
        assert body["imported_count"] == 2
        assert body["error_count"] == 0

        listed = client.get(f"{PROJECTS_URL}/{project.id}/students", headers=headers)
        numbers = [s["student_number"] for s in listed.json()]
        assert "S1001" in numbers and "S1002" in numbers

    def test_sixty_rows_import_all_sixty(self, client, project):
        headers = _auth_headers(client)
        rows = [(f"Student {i}", f"S{i:04d}") for i in range(1, 61)]
        res = _upload(client, project, headers, _xlsx_bytes(rows))
        assert res.status_code == 200
        assert res.json()["imported_count"] == 60

        listed = client.get(f"{PROJECTS_URL}/{project.id}/students", headers=headers)
        assert len(listed.json()) == 60

    def test_missing_name_reported_others_imported(self, client, project):
        headers = _auth_headers(client)
        data = _xlsx_bytes([("Lisa", "S1"), ("", "S2"), ("Tom", "S3")])
        body = _upload(client, project, headers, data).json()
        assert body["imported_count"] == 2
        assert body["error_count"] == 1
        assert any("Missing name" in e["message"] for e in body["errors"])

    def test_missing_number_reported(self, client, project):
        headers = _auth_headers(client)
        data = _xlsx_bytes([("Lisa", "S1"), ("NoNumber", "")])
        body = _upload(client, project, headers, data).json()
        assert body["imported_count"] == 1
        assert any("Missing student number" in e["message"] for e in body["errors"])

    def test_duplicate_in_file_reported(self, client, project):
        headers = _auth_headers(client)
        data = _xlsx_bytes([("Lisa", "S1"), ("Other", "S1")])
        body = _upload(client, project, headers, data).json()
        assert body["imported_count"] == 1
        assert any("Duplicate" in e["message"] for e in body["errors"])

    def test_duplicate_of_existing_reported(self, client, project):
        headers = _auth_headers(client)
        client.post(
            f"{PROJECTS_URL}/{project.id}/students",
            json={"name": "Existing", "student_number": "S1"},
            headers=headers,
        )
        data = _xlsx_bytes([("New", "S2"), ("Clash", "S1")])
        body = _upload(client, project, headers, data).json()
        assert body["imported_count"] == 1
        assert any("already exists" in e["message"] for e in body["errors"])

    def test_blank_rows_skipped(self, client, project):
        headers = _auth_headers(client)
        data = _xlsx_bytes([("Lisa", "S1"), ("", ""), ("Tom", "S2")])
        body = _upload(client, project, headers, data).json()
        assert body["imported_count"] == 2
        assert body["error_count"] == 0
        assert body["total_rows"] == 2

    def test_tolerant_headers(self, client, project):
        headers = _auth_headers(client)
        data = _xlsx_bytes(
            [("Lisa", "S1")], headers=("studentname", "student_nr")
        )
        body = _upload(client, project, headers, data).json()
        assert body["imported_count"] == 1

    def test_missing_columns_returns_400(self, client, project):
        headers = _auth_headers(client)
        data = _xlsx_bytes([("Lisa", "x")], headers=("Foo", "Bar"))
        res = _upload(client, project, headers, data)
        assert res.status_code == 400

    def test_unsupported_file_type_returns_400(self, client, project):
        headers = _auth_headers(client)
        res = _upload(client, project, headers, b"not a spreadsheet", filename="students.txt")
        assert res.status_code == 400


class TestImportCsv:
    def test_valid_csv_imported(self, client, project):
        headers = _auth_headers(client)
        csv_data = b"Name,Student Number\nLisa Anderson,S1001\nTom Johnson,S1002\n"
        res = _upload(client, project, headers, csv_data, filename="students.csv")
        assert res.status_code == 200
        assert res.json()["imported_count"] == 2

    def test_semicolon_csv_imported(self, client, project):
        headers = _auth_headers(client)
        csv_data = b"Name;Student Number\nLisa;S1\nTom;S2\n"
        res = _upload(client, project, headers, csv_data, filename="students.csv")
        assert res.json()["imported_count"] == 2


class TestImportAuthAndProject:
    def test_unknown_project_returns_404(self, client, teacher):
        headers = _auth_headers(client)
        data = _xlsx_bytes([("Lisa", "S1")])
        res = client.post(
            f"{PROJECTS_URL}/{uuid.uuid4()}/students/import",
            files={"file": ("students.xlsx", io.BytesIO(data), "application/octet-stream")},
            headers=headers,
        )
        assert res.status_code == 404

    def test_import_without_token_returns_401(self, client, project):
        data = _xlsx_bytes([("Lisa", "S1")])
        res = client.post(
            f"{PROJECTS_URL}/{project.id}/students/import",
            files={"file": ("students.xlsx", io.BytesIO(data), "application/octet-stream")},
        )
        assert res.status_code == 401
