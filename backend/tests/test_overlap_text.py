import uuid
from unittest.mock import patch

from app.models.enums import FileType, SourceType
from app.services.evidence_service import EVIDENCE_UPLOAD_DIR
from app.services.overlap_service import OverlapService
from app.services.overlap_text_detector import (
    detect_within_group,
    EvidenceChunk,
    highlight_shared,
)
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


def test_detect_within_group_does_not_double_corpus():
    chunks = [
        EvidenceChunk("s1", "Alice", "e1", "a.txt", 0, SHARED, "g1", "Group A"),
        EvidenceChunk("s2", "Bob", "e2", "b.txt", 0, SHARED + " Extra words.", "g1", "Group A"),
        EvidenceChunk("s3", "Cara", "e3", "c.txt", 0, "Different content entirely.", "g1", "Group A"),
    ]
    seen_lengths: list[int] = []

    class RecordingVectorizer:
        def __init__(self, *args, **kwargs):
            pass

        def fit_transform(self, texts):
            seen_lengths.append(len(texts))
            from sklearn.feature_extraction.text import TfidfVectorizer

            return TfidfVectorizer(stop_words="english").fit_transform(texts)

    with patch(
        "app.services.overlap_text_detector.TfidfVectorizer",
        RecordingVectorizer,
    ):
        detect_within_group(chunks)

    assert seen_lengths == [len(chunks)]


def test_highlight_shared_finds_mid_document_phrase():
    a = "Intro paragraph. Our team implemented JWT authentication with bcrypt hashing. Outro."
    b = "Different start. Our team implemented JWT authentication with bcrypt hashing. Different end."
    marked_a, marked_b = highlight_shared(a, b)
    assert "[[" in marked_a
    assert "[[" in marked_b
    assert "JWT authentication" in marked_a or "implemented JWT" in marked_a


def test_highlight_phrase_in_full_document():
    from app.services.overlap_highlight import highlight_phrase_in_document

    full = (
        "Title line\n\n"
        "Before overlap. Shared authentication module with JWT tokens. After overlap."
    )
    phrase = "Shared authentication module with JWT tokens"
    marked = highlight_phrase_in_document(full, phrase)
    assert "⟦student:" in marked
    assert "Shared authentication module with JWT tokens" in marked
    assert marked.startswith("Title line")


def test_shared_phrases_between_documents_finds_multiple_blocks():
    from app.services.overlap_service import shared_phrases_between_documents
    from app.services.overlap_highlight import highlight_phrases_in_document

    block_one = (
        "OVERLAP_BLOCK_START: Our cohort implemented authentication using JWT tokens "
        "and bcrypt password hashing for the planning application."
    )
    block_two = (
        "OVERLAP_BLOCK_MIDDLE: For sprint testing we used pytest with fixtures "
        "for the database and httpx for API calls in continuous integration."
    )
    unique_a = "Student A wrote unique Kanban renderer notes that should not be highlighted."
    unique_b = "Student B wrote unique Docker Compose notes that should not be highlighted."

    doc_a = "\n\n".join([block_one, unique_a, block_two, unique_a, block_one])
    doc_b = "\n\n".join(
        [
            block_one.replace("cohort", "team"),
            unique_b,
            block_two.replace("pytest", "unittest"),
            unique_b,
            block_one.replace("cohort", "team"),
        ]
    )

    phrases = shared_phrases_between_documents(doc_a, doc_b)
    assert len(phrases) >= 2

    marked_a = highlight_phrases_in_document(doc_a, phrases)
    assert marked_a.count("⟦student:m") >= 2


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
    monkeypatch.setattr(
        "app.services.overlap_service.enrich_hit_with_ai",
        lambda hit, **kwargs: {
            **hit,
            "ai_verified": True,
            "ai_explanation": "AI confirmed overlap.",
            "detection_method": "ai_textual",
            "integrity_type": "student_plagiarism",
        },
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
