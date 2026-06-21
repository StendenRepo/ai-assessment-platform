"""Backward-compatible re-exports — see app.services.overlap.integrity."""

from app.services.overlap.integrity import (
    AI_CONFIRMED_MIN,
    AI_FLAG_MIN,
    STUDENT_AI_CONFIRMED_MIN,
    STUDENT_AI_FLAG_MIN,
    STUDENT_CONFIRMED_MIN,
    STUDENT_POSSIBLE_MIN,
    IntegrityFlag,
    IntegrityResult,
    apply_flags_to_document,
    assess_student_plagiarism,
    build_ai_only_hit,
    combine_ai_results,
    detect_ai_segments,
    enrich_hit_with_ai,
    merge_integrity_results,
    scan_document_pair_plagiarism,
    scan_document_for_ai,
    score_ai_writing_heuristics,
    strip_markers,
)
from app.services.overlap.integrity import (
    assess_student_plagiarism as assess_textual_overlap,
)

__all__ = [
    "AI_CONFIRMED_MIN",
    "AI_FLAG_MIN",
    "STUDENT_AI_CONFIRMED_MIN",
    "STUDENT_AI_FLAG_MIN",
    "STUDENT_CONFIRMED_MIN",
    "STUDENT_POSSIBLE_MIN",
    "IntegrityFlag",
    "IntegrityResult",
    "apply_flags_to_document",
    "assess_student_plagiarism",
    "assess_textual_overlap",
    "build_ai_only_hit",
    "combine_ai_results",
    "detect_ai_segments",
    "enrich_hit_with_ai",
    "merge_integrity_results",
    "scan_document_pair_plagiarism",
    "scan_document_for_ai",
    "score_ai_writing_heuristics",
    "strip_markers",
]
