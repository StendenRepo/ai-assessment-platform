"""Tunable thresholds and size limits for integrity detection.

Scoring thresholds are sourced from ``app.config.settings`` so detection
behaviour can be tuned per-environment (see the ``OVERLAP_*`` settings) instead
of being hard-coded magic numbers. The names below are kept stable so the rest
of the package can import them directly.

All scoring values are confidences on a 0-1 scale and form three tiers:

- ``*_FLAG_MIN``     - minimum confidence to keep one flagged passage/segment.
- ``*_DOCUMENT_MIN`` - minimum document-level confidence to report the document
  as AI-written at all (looser than the per-flag bar).
- ``*_CONFIRMED_MIN``- the high-trust bar at/above which a result is shown to
  teachers as "confirmed" rather than "possible".

The classifier (RoBERTa) uses its own, lower band (``AI_CLASSIFIER_*``) because
its calibrated probabilities are not directly comparable to the LLM's
self-reported confidence. ``NEAR_DUPLICATE_*`` gate the no-LLM fast path for
wholesale copying. Invariants worth preserving when tuning:
``AI_DOCUMENT_MIN <= AI_FLAG_MIN <= AI_CONFIRMED_MIN`` and
``STUDENT_POSSIBLE_MIN <= STUDENT_AI_FLAG_MIN <= STUDENT_AI_CONFIRMED_MIN``.
"""

from __future__ import annotations

from app.config import settings

# AI-generated-text detection (LLM + RoBERTa classifier).
AI_FLAG_MIN = settings.OVERLAP_AI_FLAG_MIN
AI_DOCUMENT_MIN = settings.OVERLAP_AI_DOCUMENT_MIN
AI_CONFIRMED_MIN = settings.OVERLAP_AI_CONFIRMED_MIN
AI_HEURISTIC_MIN = settings.OVERLAP_AI_HEURISTIC_MIN
AI_CLASSIFIER_MIN = settings.OVERLAP_AI_CLASSIFIER_MIN
AI_CLASSIFIER_CONFIRMED = settings.OVERLAP_AI_CLASSIFIER_CONFIRMED
AI_CLASSIFIER_SEGMENT_MIN = settings.OVERLAP_AI_CLASSIFIER_SEGMENT_MIN

# Student-to-student plagiarism detection.
STUDENT_POSSIBLE_MIN = settings.OVERLAP_STUDENT_POSSIBLE_MIN
STUDENT_CONFIRMED_MIN = settings.OVERLAP_STUDENT_CONFIRMED_MIN
STUDENT_AI_FLAG_MIN = settings.OVERLAP_STUDENT_AI_FLAG_MIN
STUDENT_AI_CONFIRMED_MIN = settings.OVERLAP_STUDENT_AI_CONFIRMED_MIN

# No-LLM near-duplicate fast path (document- and passage-level similarity).
NEAR_DUPLICATE_DOC_MIN = settings.OVERLAP_NEAR_DUPLICATE_DOC_MIN
NEAR_DUPLICATE_UNIT_MIN = settings.OVERLAP_NEAR_DUPLICATE_UNIT_MIN

# Size and performance limits (internal tuning, not scoring thresholds).
_MIN_PARTIAL_WINDOW = 10  # sliding-window size for partial anchor matching

_MAX_CHUNK_CHARS = 1200  # cap per-chunk text sent to the LLM
_MAX_PAIR_CHARS = 1400  # cap per-excerpt text in pairwise comparison
_MAX_DOC_COMPARE_CHARS = 3000  # cap full-document text in a single prompt
_MAX_FULL_DOC_COMBINED_CHARS = 10000  # above this, compare via excerpts not full docs
_MAX_PAIR_VERIFY_CHUNK_PAIRS = 3  # max excerpt pairs verified per evidence pair
_MAX_AI_CHUNKS_PER_DOC = 12  # max chunks scanned per document for AI content
_MAX_AI_FLAGS = 12  # cap AI flags returned per document
_MAX_PAIR_FLAGS = 20  # cap plagiarism flags returned per pair
_MAX_FLAG_SNIPPET_CHARS = 1200  # cap stored snippet length per flag
_DIRECT_MERGE_MAX_WORDS = 90  # merge adjacent matched sentences up to this length
_MIN_COMPARISON_SENTENCE_WORDS = 4  # ignore sentences shorter than this in comparison
