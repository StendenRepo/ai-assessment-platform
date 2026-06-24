"""Tests for evidence-export validation:

1. GET /api/v1/students/{id}/export/dossier returns 422 when the student has
   no evidence files (backend guard added in students.py).

2. GET /api/v1/modules/{id}/students returns has_evidence=True only for
   students that have at least one evidence record.
"""

import uuid


LOGIN_URL = "/api/v1/auth/login"
MODULES_URL = "/api/v1/modules"
STUDENTS_URL = "/api/v1/students"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _auth_headers(client):
    res = client.post(
        LOGIN_URL, json={"email": "teacher@test.com", "password": "password123"}
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _make_module_with_student(db, teacher, student_number="9900001"):
    """Create a module → group → student chain and return (module, project, student)."""
    from app.models.module import Module
    from app.models.project import Project
    from app.models.student import Student, student_projects

    module = Module(id=uuid.uuid4(), teacher_id=teacher.id, name="Export Test Module")
    db.add(module)
    db.flush()

    project = Project(id=uuid.uuid4(), module_id=module.id, name="Group A")
    db.add(project)
    db.flush()

    student = Student(name="Export Student", student_number=student_number)
    db.add(student)
    db.flush()

    db.execute(
        student_projects.insert().values(
            student_id=student.student_number, project_id=project.id
        )
    )
    db.commit()
    db.refresh(student)
    return module, project, student


def _add_evidence(db, student_number, file_name="report.pdf"):
    """Insert a minimal Evidence row for the given student."""
    from app.models.evidence import Evidence
    from app.models.enums import EvidenceFileType, EvidenceSourceType, EmbeddingStatus

    ev = Evidence(
        id=uuid.uuid4(),
        student_id=student_number,
        file_name=file_name,
        file_path=f"evidence/{student_number}/{file_name}",
        file_type=EvidenceFileType.pdf,
        source_type=EvidenceSourceType.upload,
        embedding_status=EmbeddingStatus.pending,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


# ── Tests: dossier export 422 guard ──────────────────────────────────────────


class TestDossierExportNoEvidence:
    """The dossier export endpoint must reject students with no evidence."""

    def test_export_returns_422_when_no_evidence(self, client, db, teacher):
        _, _, student = _make_module_with_student(db, teacher, "9900010")
        headers = _auth_headers(client)

        res = client.get(
            f"{STUDENTS_URL}/{student.student_number}/export/dossier",
            headers=headers,
        )

        assert res.status_code == 422
        assert "no uploaded evidence" in res.json()["detail"].lower()

    def test_export_returns_200_when_evidence_exists(self, client, db, teacher, tmp_path, monkeypatch):
        _, _, student = _make_module_with_student(db, teacher, "9900011")
        ev = _add_evidence(db, student.student_number)

        # Point the evidence upload dir to a temp directory so the file exists
        evidence_dir = tmp_path / "evidence" / student.student_number
        evidence_dir.mkdir(parents=True)
        (evidence_dir / "report.pdf").write_bytes(b"%PDF-1.4 fake content")

        # Patch the upload dir used by the export endpoint
        monkeypatch.setattr(
            "app.services.evidence_service._evidence_upload_dir",
            lambda: tmp_path / "evidence",
        )
        # Also patch the path stored in the evidence record to match tmp_path layout
        from app.models.evidence import Evidence as EvidenceModel
        ev_row = db.query(EvidenceModel).filter(EvidenceModel.id == ev.id).first()
        ev_row.file_path = f"{student.student_number}/report.pdf"
        db.commit()

        headers = _auth_headers(client)
        res = client.get(
            f"{STUDENTS_URL}/{student.student_number}/export/dossier",
            headers=headers,
        )

        assert res.status_code == 200
        assert res.headers["content-type"] in (
            "application/zip",
            "application/zip; charset=utf-8",
        )

    def test_export_tar_returns_422_when_no_evidence(self, client, db, teacher):
        _, _, student = _make_module_with_student(db, teacher, "9900012")
        headers = _auth_headers(client)

        res = client.get(
            f"{STUDENTS_URL}/{student.student_number}/export/dossier?format=tar",
            headers=headers,
        )

        assert res.status_code == 422


# ── Tests: has_evidence flag in module student list ───────────────────────────


class TestHasEvidenceFlag:
    """GET /modules/{id}/students must return has_evidence correctly."""

    def test_has_evidence_false_when_no_evidence(self, client, db, teacher):
        module, _, student = _make_module_with_student(db, teacher, "9900020")
        headers = _auth_headers(client)

        res = client.get(f"{MODULES_URL}/{module.id}/students", headers=headers)

        assert res.status_code == 200
        students = res.json()
        assert len(students) == 1
        assert students[0]["student_number"] == student.student_number
        assert students[0]["has_evidence"] is False

    def test_has_evidence_true_when_evidence_exists(self, client, db, teacher):
        module, _, student = _make_module_with_student(db, teacher, "9900021")
        _add_evidence(db, student.student_number)
        headers = _auth_headers(client)

        res = client.get(f"{MODULES_URL}/{module.id}/students", headers=headers)

        assert res.status_code == 200
        students = res.json()
        assert len(students) == 1
        assert students[0]["has_evidence"] is True

    def test_has_evidence_mixed_students(self, client, db, teacher):
        """One student with evidence, one without — flags must differ."""
        from app.models.student import Student, student_projects
        from app.models.module import Module
        from app.models.project import Project

        module = Module(id=uuid.uuid4(), teacher_id=teacher.id, name="Mixed Module")
        db.add(module)
        db.flush()

        project = Project(id=uuid.uuid4(), module_id=module.id, name="Group B")
        db.add(project)
        db.flush()

        s1 = Student(name="Alice", student_number="9900030")
        s2 = Student(name="Bob", student_number="9900031")
        db.add_all([s1, s2])
        db.flush()

        db.execute(
            student_projects.insert().values(
                student_id=s1.student_number, project_id=project.id
            )
        )
        db.execute(
            student_projects.insert().values(
                student_id=s2.student_number, project_id=project.id
            )
        )
        db.commit()

        # Only Alice gets evidence
        _add_evidence(db, s1.student_number)

        headers = _auth_headers(client)
        res = client.get(f"{MODULES_URL}/{module.id}/students", headers=headers)

        assert res.status_code == 200
        by_number = {s["student_number"]: s for s in res.json()}
        assert by_number["9900030"]["has_evidence"] is True
        assert by_number["9900031"]["has_evidence"] is False
