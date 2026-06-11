import uuid

from app.models.enums import FileType, SourceType
from app.services.evidence_service import EVIDENCE_UPLOAD_DIR
from app.services.overlap_service import OverlapService
from app.services.overlap_text_detector import detect_within_group, EvidenceChunk
from app.services.text_chunker import chunk_text

SHARED = (
    "Our team implemented the authentication module using JWT tokens and bcrypt hashing. "
    "We documented the API endpoints and wrote integration tests for login and logout flows."
)


def test_chunk_text_rejects_invalid_overlap():
    try:
        chunk_text("hello", chunk_size=100, overlap=100)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_tfidf_detects_similar_chunks():
    chunks = [
        EvidenceChunk("s1", "Alice", "e1", "a.txt", 0, SHARED, "g1", "Group A"),
        EvidenceChunk("s2", "Bob", "e2", "b.txt", 0, SHARED, "g1", "Group A"),
    ]
    hits = detect_within_group(chunks)
    assert hits
    assert hits[0]["similarity"] >= 0.55
    assert hits[0]["status"] == "confirmed"


def test_analyze_module_overlap_with_text_evidence(db, teacher, monkeypatch):
    from app.models.evidence import Evidence
    from app.models.module import Module
    from app.models.project import Project
    from app.models.student import Student

    monkeypatch.setattr(
        OverlapService,
        "_generate_ollama_warning",
        staticmethod(lambda _prompt: "Review overlap manually."),
    )

    module = Module(id=uuid.uuid4(), teacher_id=teacher.id, name="Text Overlap")
    db.add(module)
    db.commit()

    group = Project(id=uuid.uuid4(), module_id=module.id, name="Group A")
    db.add(group)
    db.commit()

    alice = Student(name="Alice", student_number="2002001")
    bob = Student(name="Bob", student_number="2002002")
    db.add(alice)
    db.add(bob)
    db.flush()
    alice.projects.append(group)
    bob.projects.append(group)
    db.commit()

    rel_a = "2002001/demo_a.txt"
    rel_b = "2002002/demo_b.txt"
    path_a = EVIDENCE_UPLOAD_DIR / rel_a
    path_b = EVIDENCE_UPLOAD_DIR / rel_b
    path_a.parent.mkdir(parents=True, exist_ok=True)
    path_b.parent.mkdir(parents=True, exist_ok=True)
    path_a.write_text(SHARED, encoding="utf-8")
    path_b.write_text(SHARED, encoding="utf-8")

    ev_a = Evidence(
        id=uuid.uuid4(),
        student_id=alice.student_number,
        file_name="report_a.md",
        file_type=FileType.markdown,
        file_path=rel_a,
        source_type=SourceType.upload,
    )
    ev_b = Evidence(
        id=uuid.uuid4(),
        student_id=bob.student_number,
        file_name="report_b.md",
        file_type=FileType.markdown,
        file_path=rel_b,
        source_type=SourceType.upload,
    )
    db.add(ev_a)
    db.add(ev_b)
    db.commit()

    try:
        generated = OverlapService.analyze_module_overlap(db, str(module.id))
        assert len(generated) >= 1
        assert any((s.confidence or 0) >= 0.55 for s in generated)
    finally:
        from app.models.overlap_signal import OverlapSignal
        from app.models.student import student_projects

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
        db.query(Project).filter(Project.id == group.id).delete(synchronize_session=False)
        db.query(Module).filter(Module.id == module.id).delete(synchronize_session=False)
        db.commit()
        for p in (path_a, path_b):
            if p.exists():
                p.unlink()
