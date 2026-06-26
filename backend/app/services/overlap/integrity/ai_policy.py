"""AI detection decision policy.

Classifier, LLM, and heuristic modules emit scores and flags; this module is
the single place that converts those signals into an ``IntegrityResult`` status,
report confidence, and display-ready result shape.
"""

from __future__ import annotations

from app.services.overlap.integrity.aggregation import _dedupe_ai_flags, _summarise_flags
from app.services.overlap.integrity.models import IntegrityFlag, IntegrityResult
from app.services.overlap.integrity.thresholds import (
    AI_CLASSIFIER_CONFIRMED,
    AI_CLASSIFIER_MIN,
    AI_CONFIRMED_MIN,
    _MAX_AI_FLAGS,
)

CLASSIFIER_METHOD = "classifier_roberta"


def ai_status_for_confidence(confidence: float, *, method: str) -> str:
    """Return the AI result status for a method-specific report confidence."""
    if method == CLASSIFIER_METHOD:
        if confidence >= AI_CLASSIFIER_CONFIRMED:
            return "confirmed"
        if confidence >= AI_CLASSIFIER_MIN:
            return "possible"
        return "none"
    if confidence >= AI_CONFIRMED_MIN:
        return "confirmed"
    return "possible"


def _report_confidence(
    confidence: float,
    flags: list[IntegrityFlag],
    *,
    detection_method: str,
) -> float:
    if detection_method == CLASSIFIER_METHOD:
        return confidence
    return max(confidence, max(flag.confidence for flag in flags))


def build_no_ai_result(
    *,
    confidence: float = 0.0,
    explanation: str = "No AI-generated passages detected.",
    ai_verified: bool,
    detection_method: str,
) -> IntegrityResult:
    """Build the consistent negative/skip result for AI detection."""
    return IntegrityResult(
        integrity_type="none",
        confidence=confidence,
        status="none",
        explanation=explanation,
        ai_verified=ai_verified,
        detection_method=detection_method,
    )


def build_ai_result(
    flags: list[IntegrityFlag],
    *,
    confidence: float,
    ai_verified: bool,
    detection_method: str,
    explanation: str = "",
) -> IntegrityResult:
    """Build an AI result from detector signals using one shared policy."""
    deduped = _dedupe_ai_flags(flags)
    if not deduped:
        return build_no_ai_result(
            explanation=explanation or "No AI-generated passages detected.",
            ai_verified=ai_verified,
            detection_method=detection_method,
        )

    report_confidence = _report_confidence(
        confidence,
        deduped,
        detection_method=detection_method,
    )
    return IntegrityResult(
        integrity_type="ai",
        confidence=report_confidence,
        status=ai_status_for_confidence(report_confidence, method=detection_method),
        flags=deduped[:_MAX_AI_FLAGS],
        explanation=explanation or _summarise_flags(deduped, "AI-generated"),
        ai_verified=ai_verified,
        detection_method=detection_method,
    )


def is_confirmed_ai_result(result: IntegrityResult) -> bool:
    """Return True when an AI result meets the centralized confirmed policy."""
    return (
        result.integrity_type == "ai"
        and result.status == "confirmed"
        and result.confidence >= AI_CONFIRMED_MIN
    )
