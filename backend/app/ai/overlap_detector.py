"""TF-IDF textual overlap detection between student evidence chunks."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.ai.chunker import chunk_text

CONFIRMED_MIN = 0.55
POSSIBLE_MIN = 0.38
MAX_RESULTS = 50


@dataclass
class EvidenceChunk:
    student_id: str
    student_name: str
    evidence_id: str
    file_name: str
    chunk_index: int
    text: str
    group_id: str = ""
    group_name: str = ""


def _highlight_shared(a: str, b: str) -> tuple[str, str]:
    """Return passages with a simple shared-prefix marker for UI."""
    words_a = a.split()
    words_b = b.split()
    shared = 0
    for wa, wb in zip(words_a, words_b):
        if wa.lower() != wb.lower():
            break
        shared += 1
    if shared < 3:
        return a, b
    prefix = " ".join(words_a[:shared])
    return (
        a.replace(prefix, f"[[{prefix}]]", 1),
        b.replace(prefix, f"[[{prefix}]]", 1),
    )


def detect_group_overlaps(
    chunks: list[EvidenceChunk],
    *,
    scope: str = "within_group",
    confirmed_min: float = CONFIRMED_MIN,
    possible_min: float = POSSIBLE_MIN,
) -> list[dict]:
    if len(chunks) < 2:
        return []

    texts = [c.text for c in chunks]
    vectorizer = TfidfVectorizer(stop_words="english")
    matrix = vectorizer.fit_transform(texts)
    sim = cosine_similarity(matrix)

    raw: list[dict] = []
    for i in range(len(chunks)):
        for j in range(i + 1, len(chunks)):
            score = float(sim[i, j])
            if score < possible_min:
                continue
            ca, cb = chunks[i], chunks[j]
            if ca.student_id == cb.student_id:
                continue
            status = "confirmed" if score >= confirmed_min else "possible"
            passage_a, passage_b = _highlight_shared(ca.text, cb.text)
            raw.append(
                {
                    "id": str(uuid.uuid4()),
                    "scope": scope,
                    "status": status,
                    "student_a_id": ca.student_id,
                    "student_a_name": ca.student_name,
                    "student_b_id": cb.student_id,
                    "student_b_name": cb.student_name,
                    "evidence_a_id": ca.evidence_id,
                    "evidence_b_id": cb.evidence_id,
                    "file_a": ca.file_name,
                    "file_b": cb.file_name,
                    "passage_a": passage_a,
                    "passage_b": passage_b,
                    "similarity": round(score, 4),
                    "similarity_percent": round(score * 100, 1),
                    "group_a_id": ca.group_id,
                    "group_b_id": cb.group_id,
                    "group_a_name": ca.group_name,
                    "group_b_name": cb.group_name,
                }
            )

    raw.sort(key=lambda x: x["similarity"], reverse=True)
    return raw[:MAX_RESULTS]


def detect_cross_group_overlaps(
    chunks_a: list[EvidenceChunk],
    chunks_b: list[EvidenceChunk],
    *,
    confirmed_min: float = CONFIRMED_MIN,
    possible_min: float = POSSIBLE_MIN,
) -> list[dict]:
    """G2-123: compare evidence between two different groups only."""
    tagged_a = [
        EvidenceChunk(
            student_id=c.student_id,
            student_name=c.student_name,
            evidence_id=c.evidence_id,
            file_name=c.file_name,
            chunk_index=c.chunk_index,
            text=c.text,
            group_id=c.group_id,
            group_name=c.group_name,
        )
        for c in chunks_a
    ]
    tagged_b = [
        EvidenceChunk(
            student_id=c.student_id,
            student_name=c.student_name,
            evidence_id=c.evidence_id,
            file_name=c.file_name,
            chunk_index=c.chunk_index,
            text=c.text,
            group_id=c.group_id,
            group_name=c.group_name,
        )
        for c in chunks_b
    ]
    combined = tagged_a + tagged_b
    results = detect_group_overlaps(
        combined,
        scope="cross_group",
        confirmed_min=confirmed_min,
        possible_min=possible_min,
    )
    return [r for r in results if r.get("group_a_id") != r.get("group_b_id")]


def detect_overlaps(students: dict[str, dict]) -> list[dict]:
    """Legacy shape for analysis orchestrator (names only)."""
    chunks: list[EvidenceChunk] = []
    for name, data in students.items():
        sid = data.get("student_id", name)
        eid = data.get("evidence_id", "unknown")
        source = data.get("source_file", "unknown")
        for i, text in enumerate(chunk_text(data.get("text", ""))):
            chunks.append(
                EvidenceChunk(
                    student_id=sid,
                    student_name=name,
                    evidence_id=eid,
                    file_name=source,
                    chunk_index=i,
                    text=text,
                )
            )
    records = detect_group_overlaps(chunks)
    legacy = []
    for r in records:
        legacy.append(
            {
                "student_a": r["student_a_name"],
                "student_b": r["student_b_name"],
                "file_a": r["file_a"],
                "file_b": r["file_b"],
                "similarity": r["similarity"],
                "similarity_percent": r["similarity_percent"],
                "excerpt": r["passage_a"].replace("[[", "").replace("]]", "")[:200],
                "status": r["status"],
            }
        )
    return legacy
