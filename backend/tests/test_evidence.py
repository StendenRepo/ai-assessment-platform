"""
Tests for the evidence upload user story.

Acceptance criteria:
  1. Teacher can upload a .md file as student evidence.
  2. File is stored and linked to the student.
  3. Content is read correctly.

The service is designed to be extensible: SUPPORTED_EXTENSIONS in
evidence_service.py controls which file types are accepted.
"""

import io
import uuid

import pytest

UPLOAD_URL = "/api/v1/students/{student_id}/evidence"
LIST_URL = "/api/v1/students/{student_id}/evidence"
CONTENT_URL = "/api/v1/evidence/{evidence_id}/content"
LOGIN_URL = "/api/v1/auth/login"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _auth_header(client, teacher):
    res = client.post(LOGIN_URL, json={"email": teacher.email, "password": "password123"})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _make_md_file(content: str = "# Hello\n\nThis is evidence.", filename: str = "evidence.md"):
    return ("file", (filename, io.BytesIO(content.encode()), "text/markdown"))


@pytest.fixture
def student(db, teacher):
    """Create a minimal module + project + student linked to the teacher."""
    from app.models.module import Module
    from app.models.project import Project
    from app.models.student import Student

    module = Module(
        id=uuid.uuid4(),
        teacher_id=teacher.id,
        name="Test Module",
    )
    db.add(module)
    db.flush()

    project = Project(
        id=uuid.uuid4(),
        module_id=module.id,
        name="Test Project",
        group_name="Group A",
    )
    db.add(project)
    db.flush()

    s = Student(
        id=uuid.uuid4(),
        project_id=project.id,
        name="Alice",
        student_number="S001",
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    yield s
    db.delete(s)
    db.delete(project)
    db.delete(module)
    db.commit()


# ── AC 1: Teacher can upload a .md file as student evidence ───────────────────

class TestUploadMarkdownEvidence:
    def test_upload_md_returns_201(self, client, teacher, student):
        headers = _auth_header(client, teacher)
        url = UPLOAD_URL.format(student_id=str(student.id))
        res = client.post(url, files=[_make_md_file()], headers=headers)
        assert res.status_code == 201

    def test_upload_md_response_contains_expected_fields(self, client, teacher, student):
        headers = _auth_header(client, teacher)
        url = UPLOAD_URL.format(student_id=str(student.id))
        res = client.post(url, files=[_make_md_file()], headers=headers)
        body = res.json()
        assert body["file_name"] == "evidence.md"
        assert body["file_type"] == "markdown"
        assert body["source_type"] == "upload"
        assert body["embedding_status"] == "pending"

    def test_upload_non_md_returns_422(self, client, teacher, student):
        headers = _auth_header(client, teacher)
        url = UPLOAD_URL.format(student_id=str(student.id))
        bad_file = ("file", ("report.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf"))
        res = client.post(url, files=[bad_file], headers=headers)
        assert res.status_code == 422

    def test_upload_without_auth_returns_401(self, client, student):
        url = UPLOAD_URL.format(student_id=str(student.id))
        res = client.post(url, files=[_make_md_file()])
        assert res.status_code == 401

    def test_upload_unknown_student_returns_404(self, client, teacher):
        headers = _auth_header(client, teacher)
        url = UPLOAD_URL.format(student_id=str(uuid.uuid4()))
        res = client.post(url, files=[_make_md_file()], headers=headers)
        assert res.status_code == 404


# ── AC 2: File is stored and linked to the student ────────────────────────────

class TestEvidenceLinkedToStudent:
    def test_uploaded_evidence_appears_in_list(self, client, teacher, student):
        headers = _auth_header(client, teacher)
        url = UPLOAD_URL.format(student_id=str(student.id))
        client.post(url, files=[_make_md_file(filename="linked.md")], headers=headers)

        list_url = LIST_URL.format(student_id=str(student.id))
        res = client.get(list_url, headers=headers)
        assert res.status_code == 200
        names = [e["file_name"] for e in res.json()]
        assert "linked.md" in names

    def test_evidence_student_id_matches(self, client, teacher, student):
        headers = _auth_header(client, teacher)
        url = UPLOAD_URL.format(student_id=str(student.id))
        res = client.post(url, files=[_make_md_file()], headers=headers)
        assert res.json()["student_id"] == str(student.id)

    def test_list_unknown_student_returns_404(self, client, teacher):
        headers = _auth_header(client, teacher)
        url = LIST_URL.format(student_id=str(uuid.uuid4()))
        res = client.get(url, headers=headers)
        assert res.status_code == 404


# ── AC 3: Content is read correctly ──────────────────────────────────────────

class TestReadEvidenceContent:
    def test_content_endpoint_returns_correct_text(self, client, teacher, student, tmp_path, monkeypatch):
        # Point UPLOAD_DIR to a temp directory so the file is actually written
        monkeypatch.setattr("app.services.evidence_service.settings.UPLOAD_DIR", str(tmp_path))

        headers = _auth_header(client, teacher)
        md_content = "# My Evidence\n\nThis is the content."
        url = UPLOAD_URL.format(student_id=str(student.id))
        upload_res = client.post(
            url,
            files=[_make_md_file(content=md_content)],
            headers=headers,
        )
        assert upload_res.status_code == 201
        evidence_id = upload_res.json()["id"]

        content_url = CONTENT_URL.format(evidence_id=evidence_id)
        res = client.get(content_url, headers=headers)
        assert res.status_code == 200
        body = res.json()
        assert body["content"] == md_content
        assert body["file_name"] == "evidence.md"

    def test_content_unknown_evidence_returns_404(self, client, teacher):
        headers = _auth_header(client, teacher)
        url = CONTENT_URL.format(evidence_id=str(uuid.uuid4()))
        res = client.get(url, headers=headers)
        assert res.status_code == 404


# ── Extensibility: supported-types endpoint ───────────────────────────────────

class TestSupportedTypes:
    def test_supported_types_returns_list(self, client):
        res = client.get("/api/v1/evidence/supported-types")
        assert res.status_code == 200
        body = res.json()
        assert "supported_extensions" in body
        assert isinstance(body["supported_extensions"], list)

    def test_md_is_in_supported_types(self, client):
        res = client.get("/api/v1/evidence/supported-types")
        assert ".md" in res.json()["supported_extensions"]

    def test_unsupported_extension_error_mentions_allowed_types(self, client, teacher, student):
        headers = _auth_header(client, teacher)
        url = UPLOAD_URL.format(student_id=str(student.id))
        bad_file = ("file", ("image.png", io.BytesIO(b"\x89PNG"), "image/png"))
        res = client.post(url, files=[bad_file], headers=headers)
        assert res.status_code == 422
        # Error message should mention the allowed extensions
        assert ".md" in res.json()["detail"]
