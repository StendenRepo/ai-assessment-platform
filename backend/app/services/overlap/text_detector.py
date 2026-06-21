"""TF-IDF textual overlap between student evidence chunks (G2)."""

from __future__ import annotations

import difflib
import uuid
from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.config import settings

# TF-IDF prescreen scoring thresholds (env-configurable, scale 0-1).
CONFIRMED_MIN = settings.OVERLAP_TFIDF_CONFIRMED_MIN
POSSIBLE_MIN = settings.OVERLAP_TFIDF_POSSIBLE_MIN
MAX_RESULTS = 50  # cap on TF-IDF candidate pairs returned per run


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


def _longest_matching_word_block(
    words_a: list[str], words_b: list[str], *, min_words: int = 3
) -> str:
    """Find the longest contiguous matching word block anywhere in both passages."""
    if not words_a or not words_b:
        return ""
    lower_a = [w.lower() for w in words_a]
    lower_b = [w.lower() for w in words_b]
    matcher = difflib.SequenceMatcher(None, lower_a, lower_b)
    best: list[str] = []
    for block in matcher.get_matching_blocks():
        if block.size < min_words:
            continue
        if block.size > len(best):
            best = words_a[block.a : block.a + block.size]
    return " ".join(best)


def _wrap_phrase(text: str, phrase: str) -> str:
    if not phrase or phrase not in text:
        lower_text = text.lower()
        lower_phrase = phrase.lower()
        idx = lower_text.find(lower_phrase)
        if idx < 0:
            return text
        original = text[idx : idx + len(phrase)]
        return text.replace(original, f"[[{original}]]", 1)
    return text.replace(phrase, f"[[{phrase}]]", 1)


def highlight_shared(a: str, b: str) -> tuple[str, str]:
    """Mark the longest shared word block in both passages (mid-document aware)."""
    words_a = a.split()
    words_b = b.split()
    phrase = _longest_matching_word_block(words_a, words_b, min_words=3)
    if not phrase:
        return a, b
    return _wrap_phrase(a, phrase), _wrap_phrase(b, phrase)


def _append_hit(
    raw: list[dict],
    ca: EvidenceChunk,
    cb: EvidenceChunk,
    *,
    scope: str,
    score: float,
    confirmed_min: float,
    possible_min: float,
) -> None:
    if score < possible_min:
        return
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


def _pair_hits_within(
    chunks: list[EvidenceChunk],
    *,
    scope: str,
    confirmed_min: float,
    possible_min: float,
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
            ca, cb = chunks[i], chunks[j]
            if ca.student_id == cb.student_id:
                continue
            if scope == "within_group" and ca.group_id != cb.group_id:
                continue
            _append_hit(
                raw,
                ca,
                cb,
                scope=scope,
                score=float(sim[i, j]),
                confirmed_min=confirmed_min,
                possible_min=possible_min,
            )

    raw.sort(key=lambda x: x["similarity"], reverse=True)
    return raw[:MAX_RESULTS]


def _pair_hits_cross(
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
    offset = len(chunks_left)

    raw: list[dict] = []
    for i, ca in enumerate(chunks_left):
        for j, cb in enumerate(chunks_right):
            if ca.student_id == cb.student_id:
                continue
            if scope == "cross_group" and ca.group_id == cb.group_id:
                continue
            _append_hit(
                raw,
                ca,
                cb,
                scope=scope,
                score=float(sim[i, offset + j]),
                confirmed_min=confirmed_min,
                possible_min=possible_min,
            )

    raw.sort(key=lambda x: x["similarity"], reverse=True)
    return raw[:MAX_RESULTS]


def detect_within_group(
    chunks: list[EvidenceChunk],
    *,
    confirmed_min: float = CONFIRMED_MIN,
    possible_min: float = POSSIBLE_MIN,
) -> list[dict]:
    return _pair_hits_within(
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
    return _pair_hits_cross(
        chunks_a,
        chunks_b,
        scope="cross_group",
        confirmed_min=confirmed_min,
        possible_min=possible_min,
    )
