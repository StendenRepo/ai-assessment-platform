"""Build highlighted overlap documents and collect shared phrases."""

from __future__ import annotations

import re
from typing import Iterable, Optional, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session

from app.models.evidence import Evidence
from app.models.overlap_signal import OverlapSignal
from app.services.overlap_highlight import (
    apply_paired_student_highlights,
    highlight_phrases_paired,
)
from app.services.overlap_integrity_detector import (
    apply_flags_to_document,
    dedupe_student_flag_dicts,
)
from app.services.overlap_signal_codec import parse_signal_detail
from app.services.overlap_text_detector import POSSIBLE_MIN, highlight_shared
from app.services.text_chunker import chunk_text
from app.services.text_extraction import read_stored_evidence_text

_HIGHLIGHT_MARKER_RE = re.compile(r"\[\[(.*?)\]\]", re.DOTALL)


def read_evidence_text(evidence: Evidence) -> str:
    from app.services.evidence_service import EVIDENCE_UPLOAD_DIR

    return read_stored_evidence_text(evidence, EVIDENCE_UPLOAD_DIR)


def extract_highlight_phrase(passage: Optional[str]) -> Optional[str]:
    if not passage:
        return None
    match = _HIGHLIGHT_MARKER_RE.search(passage)
    if match:
        return match.group(1).strip()
    return passage.strip()


def _dedupe_phrases(phrases: Iterable[str]) -> list[str]:
    ordered = sorted({p.strip() for p in phrases if p and p.strip()}, key=len, reverse=True)
    kept: list[str] = []
    for phrase in ordered:
        lower = phrase.lower()
        if any(lower in existing.lower() or existing.lower() in lower for existing in kept):
            continue
        kept.append(phrase)
    return kept


def shared_phrases_between_documents(
    full_a: str,
    full_b: str,
    *,
    min_similarity: float = POSSIBLE_MIN,
) -> list[str]:
    """Collect shared phrases from chunk and paragraph pairs between two documents."""
    phrases: list[str] = []

    def _collect_from_pairs(left_chunks: list[str], right_chunks: list[str]) -> None:
        if not left_chunks or not right_chunks:
            return
        combined = left_chunks + right_chunks
        matrix = TfidfVectorizer(stop_words="english").fit_transform(combined)
        sim = cosine_similarity(matrix)
        offset = len(left_chunks)
        for i, chunk_a in enumerate(left_chunks):
            for j, chunk_b in enumerate(right_chunks):
                if float(sim[i, offset + j]) < min_similarity:
                    continue
                marked_a, marked_b = highlight_shared(chunk_a, chunk_b)
                for marked in (marked_a, marked_b):
                    for match in _HIGHLIGHT_MARKER_RE.finditer(marked):
                        phrase = match.group(1).strip()
                        if len(phrase.split()) >= 8:
                            phrases.append(phrase)

    _collect_from_pairs(chunk_text(full_a), chunk_text(full_b))

    paragraphs_a = [p.strip() for p in re.split(r"\n\s*\n", full_a) if p.strip()]
    paragraphs_b = [p.strip() for p in re.split(r"\n\s*\n", full_b) if p.strip()]
    _collect_from_pairs(paragraphs_a, paragraphs_b)

    return _dedupe_phrases(phrases)


def build_highlighted_documents(
    db: Session,
    signal: OverlapSignal,
    *,
    detail: Optional[dict] = None,
) -> Tuple[Optional[str], Optional[str], list[dict]]:
    detail = detail if detail is not None else parse_signal_detail(signal.snippet)
    integrity_type = detail.get("integrity_type") or "student_plagiarism"
    flags = dedupe_student_flag_dicts(detail.get("flags") or [])
    effective_flags = flags

    evidence_a = db.query(Evidence).filter(Evidence.id == signal.evidence_a_id).first()
    if not evidence_a:
        return None, None, []

    full_a = read_evidence_text(evidence_a)
    if not full_a:
        return None, None, []

    ai_flags = [f for f in flags if f.get("type") == "ai"]
    student_flags = [f for f in flags if f.get("type") == "student"]

    if integrity_type == "ai":
        document_a = apply_flags_to_document(full_a, flags, side="a")
        return document_a, None, effective_flags

    evidence_b = db.query(Evidence).filter(Evidence.id == signal.evidence_b_id).first()
    if not evidence_b:
        document_a = apply_flags_to_document(full_a, flags, side="a")
        return document_a, None, effective_flags

    full_b = read_evidence_text(evidence_b)
    if not full_b:
        return apply_flags_to_document(full_a, flags, side="a"), None, effective_flags

    if student_flags:
        document_a, document_b, effective_flags = apply_paired_student_highlights(
            full_a,
            full_b,
            flags,
        )
    else:
        document_a, document_b = full_a, full_b

    if ai_flags:
        document_a = apply_flags_to_document(document_a, ai_flags, side="a")
        document_b = apply_flags_to_document(document_b, ai_flags, side="b")

    if student_flags:
        return document_a, document_b, effective_flags

    phrases = shared_phrases_between_documents(full_a, full_b)
    if not phrases:
        fallback = extract_highlight_phrase(detail.get("passage_a")) or extract_highlight_phrase(
            detail.get("passage_b")
        )
        if fallback:
            phrases = [fallback]
    ai_excerpt = (detail.get("ai_shared_excerpt") or "").strip()
    if ai_excerpt:
        phrases = _dedupe_phrases([*phrases, ai_excerpt])

    return (*highlight_phrases_paired(full_a, full_b, phrases), effective_flags)
