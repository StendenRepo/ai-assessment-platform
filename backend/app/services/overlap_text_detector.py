"""TF-IDF textual overlap between student evidence chunks (G2)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

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


def highlight_shared(a: str, b: str) -> tuple[str, str]:
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


def _pair_hits(
    chunks_left: list[EvidenceChunk],
    chunks_right: list[EvidenceChunk],
    *,
    scope: str,
    confirmed_min: float,
    possible_min: float,
) -> list[dict]:
    if not chunks_left or not chunks_right:
        return []

    combined = chunks_left + chunks_right
    texts = [c.text for c in combined]
    vectorizer = TfidfVectorizer(stop_words="english")
    matrix = vectorizer.fit_transform(texts)
    sim = cosine_similarity(matrix)

    raw: list[dict] = []

    for i in range(len(combined)):
        for j in range(i + 1, len(combined)):
            ca, cb = combined[i], combined[j]
            if ca.student_id == cb.student_id:
                continue
            if scope == "within_group" and ca.group_id != cb.group_id:
                continue
            if scope == "cross_group" and ca.group_id == cb.group_id:
                continue

            score = float(sim[i, j])
            if score < possible_min:
                continue

            status = "confirmed" if score >= confirmed_min else "possible"
            passage_a, passage_b = highlight_shared(ca.text, cb.text)
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
                    "group_a_id": ca.group_id,
                    "group_b_id": cb.group_id,
                    "group_a_name": ca.group_name,
                    "group_b_name": cb.group_name,
                }
            )

    raw.sort(key=lambda x: x["similarity"], reverse=True)
    return raw[:MAX_RESULTS]


def detect_within_group(
    chunks: list[EvidenceChunk],
    *,
    confirmed_min: float = CONFIRMED_MIN,
    possible_min: float = POSSIBLE_MIN,
) -> list[dict]:
    return _pair_hits(
        chunks,
        chunks,
        scope="within_group",
        confirmed_min=confirmed_min,
        possible_min=possible_min,
    )


def detect_cross_group(
    chunks_a: list[EvidenceChunk],
    chunks_b: list[EvidenceChunk],
    *,
    confirmed_min: float = CONFIRMED_MIN,
    possible_min: float = POSSIBLE_MIN,
) -> list[dict]:
    return _pair_hits(
        chunks_a,
        chunks_b,
        scope="cross_group",
        confirmed_min=confirmed_min,
        possible_min=possible_min,
    )
