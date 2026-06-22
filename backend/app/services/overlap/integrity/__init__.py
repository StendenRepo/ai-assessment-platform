"""Academic integrity detection facade.

The implementation is split across focused modules in this package; importing
``app.services.overlap.integrity`` re-exports the stable public surface:

- models               - IntegrityFlag / IntegrityResult data contracts
- thresholds           - tunable scoring thresholds and size limits
- text                 - text normalisation, chunking and similarity
- ai_heuristics        - local pattern-based AI writing signals
- prompts              - LLM prompt templates and builders
- aggregation          - flag parsing, merging and display metrics
- ai_detection         - AI-generated-text detection
- plagiarism_detection - student-to-student plagiarism detection
"""

from __future__ import annotations

from app.services.overlap.integrity.ai_detection import (
    detect_ai_segments,
    scan_document_for_ai,
)
from app.services.overlap.integrity.ai_heuristics import score_ai_writing_heuristics
from app.services.overlap.integrity.aggregation import (
    attach_integrity_metrics,
    build_ai_only_hit,
    build_metrics_summary,
    combine_ai_results,
    derive_signal_metrics,
    merge_integrity_results,
    merge_student_plagiarism_results,
)
from app.services.overlap.integrity.models import IntegrityFlag, IntegrityResult
from app.services.overlap.integrity.thresholds import (
    AI_CLASSIFIER_CONFIRMED,
    AI_CLASSIFIER_MIN,
    AI_CLASSIFIER_SEGMENT_MIN,
    AI_CONFIRMED_MIN,
    AI_DOCUMENT_MIN,
    AI_FLAG_MIN,
    AI_HEURISTIC_MIN,
    NEAR_DUPLICATE_DOC_MIN,
    NEAR_DUPLICATE_UNIT_MIN,
    STUDENT_AI_CONFIRMED_MIN,
    STUDENT_AI_FLAG_MIN,
    STUDENT_CONFIRMED_MIN,
    STUDENT_POSSIBLE_MIN,
)
from app.services.overlap.integrity.plagiarism_detection import (
    assess_student_plagiarism,
    enrich_hit_with_ai,
    scan_document_pair_plagiarism,
    scan_evidence_pair_plagiarism,
    _flags_from_direct_text_comparison,
    _near_duplicate_plagiarism_result,
)

__all__ = [
    # Data contracts
    "IntegrityFlag",
    "IntegrityResult",
    # Thresholds
    "AI_CLASSIFIER_CONFIRMED",
    "AI_CLASSIFIER_MIN",
    "AI_CLASSIFIER_SEGMENT_MIN",
    "AI_CONFIRMED_MIN",
    "AI_DOCUMENT_MIN",
    "AI_FLAG_MIN",
    "AI_HEURISTIC_MIN",
    "NEAR_DUPLICATE_DOC_MIN",
    "NEAR_DUPLICATE_UNIT_MIN",
    "STUDENT_AI_CONFIRMED_MIN",
    "STUDENT_AI_FLAG_MIN",
    "STUDENT_CONFIRMED_MIN",
    "STUDENT_POSSIBLE_MIN",
    # Heuristics
    "score_ai_writing_heuristics",
    # Aggregation / metrics
    "attach_integrity_metrics",
    "build_ai_only_hit",
    "build_metrics_summary",
    "combine_ai_results",
    "derive_signal_metrics",
    "merge_integrity_results",
    "merge_student_plagiarism_results",
    # AI detection
    "detect_ai_segments",
    "scan_document_for_ai",
    # Plagiarism detection
    "assess_student_plagiarism",
    "enrich_hit_with_ai",
    "scan_document_pair_plagiarism",
    "scan_evidence_pair_plagiarism",
    "_flags_from_direct_text_comparison",
    "_near_duplicate_plagiarism_result",
]
