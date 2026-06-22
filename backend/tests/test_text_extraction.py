"""Tests for multi-format evidence text extraction used by overlap detection."""

import uuid
from pathlib import Path

from app.models.enums import FileType, SourceType
from app.services.overlap.service import OverlapService
from app.services.text_extraction import read_stored_evidence_text


def _xlsx_bytes(rows: list[list[str]]) -> bytes:
    from io import BytesIO

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_read_stored_evidence_text_from_binary_xlsx(db, teacher, monkeypatch, tmp_path):
    from app.models.evidence import Evidence
    from app.models.module import Module
    from app.models.overlap_signal import OverlapSignal
    from app.models.project import Project
    from app.models.student import Student, student_projects

    upload_dir = tmp_path / "evidence"
    upload_dir.mkdir(parents=True)
    monkeypatch.setattr(
        "app.services.evidence_service.EVIDENCE_UPLOAD_DIR",
        upload_dir,
    )
    monkeypatch.setattr(
        "app.services.overlap.service.EVIDENCE_UPLOAD_DIR",
        upload_dir,
    )

    module = Module(id=uuid.uuid4(), teacher_id=teacher.id, name="Formats")
    project = Project(id=uuid.uuid4(), module_id=module.id, name="G1")
    alice = Student(name="Alice", student_number="9001001")
    bob = Student(name="Bob", student_number="9001002")
    db.add_all([module, project, alice, bob])
    db.flush()
    alice.projects.append(project)
    bob.projects.append(project)
    db.commit()

    shared = "Our team implemented the authentication module using JWT tokens"
    xlsx_a = _xlsx_bytes([["Notes"], [shared]])
    xlsx_b = _xlsx_bytes([["Notes"], [shared + " and bcrypt hashing"]])
    stored_paths: list[Path] = []

    def _store(student_number: str, filename: str, raw: bytes) -> Evidence:
        student_dir = upload_dir / student_number
        student_dir.mkdir(parents=True, exist_ok=True)
        rel = f"{student_number}/{filename}"
        path = upload_dir / rel
        path.write_bytes(raw)
        stored_paths.append(path)
        evidence = Evidence(
            id=uuid.uuid4(),
            student_id=student_number,
            file_name=filename,
            file_type=FileType.xlsx,
            file_path=rel,
            source_type=SourceType.upload,
        )
        db.add(evidence)
        return evidence

    ev_a = _store(alice.student_number, "workbook.xlsx", xlsx_a)
    ev_b = _store(bob.student_number, "workbook.xlsx", xlsx_b)
    db.commit()

    try:
        assert shared in read_stored_evidence_text(ev_a, upload_dir)
        assert "bcrypt" in read_stored_evidence_text(ev_b, upload_dir)

        signals = OverlapService.analyze_module_overlap(db, str(module.id))
        assert signals
        pair = {(s.student_a_id, s.student_b_id) for s in signals}
        assert (alice.student_number, bob.student_number) in pair or (
            bob.student_number,
            alice.student_number,
        ) in pair
    finally:
        student_ids = [alice.student_number, bob.student_number]
        db.query(OverlapSignal).filter(
            OverlapSignal.student_a_id.in_(student_ids)
        ).delete(synchronize_session=False)
        db.query(Evidence).filter(Evidence.student_id.in_(student_ids)).delete(
            synchronize_session=False
        )
        db.execute(
            student_projects.delete().where(student_projects.c.student_id.in_(student_ids))
        )
        db.query(Student).filter(Student.student_number.in_(student_ids)).delete(
            synchronize_session=False
        )
        db.query(Project).filter(Project.id == project.id).delete(synchronize_session=False)
        db.query(Module).filter(Module.id == module.id).delete(synchronize_session=False)
        db.commit()
        for path in stored_paths:
            if path.exists():
                path.unlink()
