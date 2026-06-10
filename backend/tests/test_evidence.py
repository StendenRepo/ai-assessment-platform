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
from PIL import Image

UPLOAD_URL = "/api/v1/students/{student_id}/evidence"
LIST_URL = "/api/v1/students/{student_id}/evidence"
CONTENT_URL = "/api/v1/evidence/{evidence_id}/content"
FILE_URL = "/api/v1/evidence/{evidence_id}/file"
LOGIN_URL = "/api/v1/auth/login"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _auth_header(client, teacher):
    res = client.post(LOGIN_URL, json={"email": teacher.email, "password": "password123"})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _make_md_file(content: str = "# Hello\n\nThis is evidence.", filename: str = "evidence.md"):
    return ("file", (filename, io.BytesIO(content.encode()), "text/markdown"))


def _make_png_file(filename: str = "evidence.png"):
    image = Image.new("RGB", (2, 2), color=(255, 255, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return ("file", (filename, buffer, "image/png"))


def _evidence_root(tmp_path):
    return tmp_path / "evidence"


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
    # Delete evidence first: tests upload Evidence rows that FK to this student.
    # Deleting the student while those rows exist raises IntegrityError, which
    # rolls back the teardown and leaves a committed teacher row behind —
    # cascading into UNIQUE(teachers.email) errors in later test files.
    from app.models.evidence import Evidence

    db.query(Evidence).filter(Evidence.student_id == s.id).delete()
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
        assert body["embedding_status"] == "completed"

    def test_upload_invalid_image_returns_422(self, client, teacher, student):
        headers = _auth_header(client, teacher)
        url = UPLOAD_URL.format(student_id=str(student.id))
        bad_file = ("file", ("broken.png", io.BytesIO(b"not-an-image"), "image/png"))
        res = client.post(url, files=[bad_file], headers=headers)
        assert res.status_code == 422


class TestUploadImageEvidence:
    def test_upload_png_returns_201(self, client, teacher, student):
        headers = _auth_header(client, teacher)
        url = UPLOAD_URL.format(student_id=str(student.id))
        res = client.post(url, files=[_make_png_file()], headers=headers)
        assert res.status_code == 201

    def test_upload_png_response_marks_image_type(self, client, teacher, student):
        headers = _auth_header(client, teacher)
        url = UPLOAD_URL.format(student_id=str(student.id))
        res = client.post(url, files=[_make_png_file(filename="diagram.png")], headers=headers)
        body = res.json()
        assert body["file_name"] == "diagram.png"
        assert body["file_type"] == "image"
        assert body["source_type"] == "upload"
        assert body["embedding_status"] == "completed"

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

    def test_upload_preserves_raw_image_and_writes_text_sidecar(self, client, teacher, student, tmp_path, monkeypatch):
        monkeypatch.setattr("app.services.evidence_service.settings.UPLOAD_DIR", str(tmp_path))

        headers = _auth_header(client, teacher)
        url = UPLOAD_URL.format(student_id=str(student.id))
        res = client.post(url, files=[_make_png_file(filename="proof.png")], headers=headers)
        assert res.status_code == 201

        saved_path = _evidence_root(tmp_path) / res.json()["file_path"]
        assert saved_path.exists()
        assert saved_path.read_bytes().startswith(b"\x89PNG")

        text_path = saved_path.with_name(f"{saved_path.name}.txt")
        assert text_path.exists()
        assert text_path.read_text(encoding="utf-8") == "[Image evidence uploaded: proof.png]"


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

    def test_image_content_endpoint_returns_fallback_text(self, client, teacher, student, tmp_path, monkeypatch):
        monkeypatch.setattr("app.services.evidence_service.settings.UPLOAD_DIR", str(tmp_path))
        # No vision model configured — should fall back to placeholder

        headers = _auth_header(client, teacher)
        url = UPLOAD_URL.format(student_id=str(student.id))
        upload_res = client.post(
            url,
            files=[_make_png_file(filename="whiteboard.png")],
            headers=headers,
        )
        assert upload_res.status_code == 201
        evidence_id = upload_res.json()["id"]

        content_url = CONTENT_URL.format(evidence_id=evidence_id)
        res = client.get(content_url, headers=headers)
        assert res.status_code == 200
        body = res.json()
        assert body["file_name"] == "whiteboard.png"
        assert body["content"] == "[Image evidence uploaded: whiteboard.png]"

    def test_service_reprocess_rebuilds_text_from_stored_file(self, client, teacher, student, db, tmp_path, monkeypatch):
        monkeypatch.setattr("app.services.evidence_service.settings.UPLOAD_DIR", str(tmp_path))

        headers = _auth_header(client, teacher)
        upload_url = UPLOAD_URL.format(student_id=str(student.id))
        upload_res = client.post(
            upload_url,
            files=[_make_png_file(filename="board.png")],
            headers=headers,
        )
        assert upload_res.status_code == 201

        relative_path = upload_res.json()["file_path"]
        text_path = _evidence_root(tmp_path) / relative_path
        text_sidecar = text_path.with_name(f"{text_path.name}.txt")
        text_sidecar.write_text("stale text", encoding="utf-8")

        from app.services.evidence_service import EvidenceService

        _, content = EvidenceService.reprocess_content(upload_res.json()["id"], db)
        assert content == "[Image evidence uploaded: board.png]"
        assert text_sidecar.read_text(encoding="utf-8") == "[Image evidence uploaded: board.png]"

    def test_vision_model_text_is_saved_when_available(self, client, teacher, student, tmp_path, monkeypatch):
        monkeypatch.setattr("app.services.evidence_service.settings.UPLOAD_DIR", str(tmp_path))
        monkeypatch.setattr("app.services.evidence_service.settings.VISION_MODEL", "fake-vision")

        import httpx as _httpx

        class _FakeResponse:
            def raise_for_status(self):
                pass
            def json(self):
                return {"response": "A screenshot showing a student project dashboard."}

        class _FakeClient:
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def post(self, *_args, **_kwargs): return _FakeResponse()

        monkeypatch.setattr(_httpx, "Client", lambda **_kw: _FakeClient())

        headers = _auth_header(client, teacher)
        upload_url = UPLOAD_URL.format(student_id=str(student.id))
        upload_res = client.post(
            upload_url,
            files=[_make_png_file(filename="dashboard.png")],
            headers=headers,
        )
        assert upload_res.status_code == 201

        content_url = CONTENT_URL.format(evidence_id=upload_res.json()["id"])
        content_res = client.get(content_url, headers=headers)
        assert content_res.status_code == 200
        assert content_res.json()["content"] == "A screenshot showing a student project dashboard."


class TestReadEvidenceFile:
    def test_file_endpoint_returns_raw_image_bytes(self, client, teacher, student, tmp_path, monkeypatch):
        monkeypatch.setattr("app.services.evidence_service.settings.UPLOAD_DIR", str(tmp_path))

        headers = _auth_header(client, teacher)
        upload_url = UPLOAD_URL.format(student_id=str(student.id))
        upload_res = client.post(
            upload_url,
            files=[_make_png_file(filename="preview.png")],
            headers=headers,
        )
        assert upload_res.status_code == 201

        file_url = FILE_URL.format(evidence_id=upload_res.json()["id"])
        res = client.get(file_url, headers=headers)
        assert res.status_code == 200
        assert res.headers["content-type"] == "image/png"
        assert res.content.startswith(b"\x89PNG")

    def test_file_endpoint_requires_auth(self, client, teacher, student):
        headers = _auth_header(client, teacher)
        upload_url = UPLOAD_URL.format(student_id=str(student.id))
        upload_res = client.post(
            upload_url,
            files=[_make_png_file(filename="preview.png")],
            headers=headers,
        )
        assert upload_res.status_code == 201

        file_url = FILE_URL.format(evidence_id=upload_res.json()["id"])
        res = client.get(file_url)
        assert res.status_code == 401


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

    def test_png_is_in_supported_types(self, client):
        res = client.get("/api/v1/evidence/supported-types")
        assert ".png" in res.json()["supported_extensions"]

    def test_unsupported_extension_error_mentions_allowed_types(self, client, teacher, student):
        headers = _auth_header(client, teacher)
        url = UPLOAD_URL.format(student_id=str(student.id))
        bad_file = ("file", ("archive.zip", io.BytesIO(b"PK\x03\x04"), "application/zip"))
        res = client.post(url, files=[bad_file], headers=headers)
        assert res.status_code == 422
        # Error message should mention the allowed extensions
        assert ".md" in res.json()["detail"]
        assert ".png" in res.json()["detail"]
