"""Assemble highlighted overlap documents from stored signals (orchestration).

Pure orchestration layer: it reads evidence text, delegates detection to
``overlap.text_detector`` / ``overlap.integrity`` and presentation to
``overlap.markers`` / ``overlap.highlight``, then stitches the result together.
It performs no detection or marker formatting of its own.
"""

from __future__ import annotations

from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.models.evidence import Evidence
from app.models.overlap_signal import OverlapSignal
from app.services.overlap.dedupe import dedupe_by_containment
from app.services.overlap.highlight import (
    apply_paired_student_highlights,
    highlight_phrases_paired,
)
from app.services.overlap.markers import (
    LEGACY_MARKER_RE,
    apply_flags_to_document,
    dedupe_student_flag_dicts,
)
from app.services.overlap.signal_codec import parse_signal_detail
from app.services.overlap.text_detector import shared_phrases_between_documents
from app.services.text_extraction import read_stored_evidence_text


def read_evidence_text(evidence: Evidence) -> str:
    from app.services.evidence_service import EVIDENCE_UPLOAD_DIR

    return read_stored_evidence_text(evidence, EVIDENCE_UPLOAD_DIR)


def extract_highlight_phrase(passage: Optional[str]) -> Optional[str]:
    if not passage:
        return None
    match = LEGACY_MARKER_RE.search(passage)
    if match:
        return match.group(1).strip()
    return passage.strip()


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
        phrases = dedupe_by_containment(
            {p.strip() for p in [*phrases, ai_excerpt] if p and p.strip()},
            key=str.lower,
            sort_key=len,
        )

    return (*highlight_phrases_paired(full_a, full_b, phrases), effective_flags)
