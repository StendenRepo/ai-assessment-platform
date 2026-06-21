"""Detection of AI-generated student writing (classifier, full-doc LLM, chunks, heuristics)."""

from __future__ import annotations

from app.lib.llm_json import parse_json_response
from app.services import ai_detector_client
from app.services import ollama_client
from app.services.overlap.integrity.ai_heuristics import score_ai_writing_heuristics
from app.services.overlap.integrity.aggregation import (
    _parse_flags,
)
from app.services.overlap.integrity.ai_policy import (
    build_ai_result,
    build_no_ai_result,
    is_confirmed_ai_result,
)
from app.services.overlap.markers import strip_markers
from app.services.overlap.integrity.models import IntegrityFlag, IntegrityResult
from app.services.overlap.integrity.prompts import (
    _AI_DETECTION_SYSTEM,
    build_chunk_ai_prompt,
    build_full_document_ai_prompt,
)
from app.services.overlap.integrity.thresholds import (
    AI_CLASSIFIER_MIN,
    AI_CLASSIFIER_SEGMENT_MIN,
    AI_DOCUMENT_MIN,
    AI_FLAG_MIN,
    AI_HEURISTIC_MIN,
    _MAX_AI_CHUNKS_PER_DOC,
    _MAX_AI_FLAGS,
)
from app.services.text_chunker import chunk_text


def scan_document_for_ai(document_text: str) -> IntegrityResult:
    """Holistic full-document AI scan - more reliable than small chunk passes alone."""
    clean = strip_markers(document_text).strip()
    if len(clean.split()) < 40:
        return build_no_ai_result(
            explanation="Document too short for reliable AI detection.",
            ai_verified=False,
            detection_method="skipped",
        )

    prompt = build_full_document_ai_prompt(clean)

    raw = ollama_client.generate(
        prompt,
        system=_AI_DETECTION_SYSTEM,
        temperature=0.05,
        **ollama_client.assessment_llm_options(),
    )
    parsed = parse_json_response(raw or "")
    if not parsed:
        return build_no_ai_result(
            explanation="AI model unavailable — full-document scan skipped.",
            ai_verified=False,
            detection_method="skipped",
        )

    try:
        confidence = float(parsed.get("overall_confidence", 0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    detected = bool(parsed.get("ai_detected", False))
    flags = _parse_flags(parsed.get("flags", []), "ai", AI_FLAG_MIN)[:_MAX_AI_FLAGS]

    if detected and confidence >= AI_DOCUMENT_MIN and not flags:
        flags = [
            IntegrityFlag(
                flag_type="ai",
                confidence=confidence,
                reason=str(parsed.get("explanation") or "Document reads as AI-generated."),
                text=clean[: min(400, len(clean))],
            )
        ]

    if not detected or confidence < AI_DOCUMENT_MIN or not flags:
        return build_no_ai_result(
            confidence=confidence,
            explanation=str(parsed.get("explanation") or "No AI-generated passages detected."),
            ai_verified=True,
            detection_method="ai_full_document",
        )

    return build_ai_result(
        flags,
        confidence=confidence,
        explanation=str(parsed.get("explanation") or ""),
        ai_verified=True,
        detection_method="ai_full_document",
    )


def _detect_ai_via_classifier(clean: str) -> IntegrityResult | None:
    """Primary path: dedicated on-premise RoBERTa AI-text classifier."""
    payload = ai_detector_client.classify_text(clean)
    if not payload:
        return None

    try:
        probability = float(payload.get("ai_probability", 0))
    except (TypeError, ValueError):
        return None

    if probability < AI_CLASSIFIER_MIN:
        return None

    flags: list[IntegrityFlag] = []
    for segment in payload.get("segments") or []:
        try:
            seg_prob = float(segment.get("ai_probability", 0))
        except (TypeError, ValueError):
            continue
        if seg_prob < AI_CLASSIFIER_SEGMENT_MIN:
            continue
        excerpt = str(segment.get("text") or "").strip()
        if len(excerpt.split()) < 4:
            continue
        flags.append(
            IntegrityFlag(
                flag_type="ai",
                confidence=seg_prob,
                reason="Section flagged by on-premise AI detector (classifier)",
                text=excerpt[:400],
            )
        )

    if not flags and probability >= AI_CLASSIFIER_MIN:
        flags = [
            IntegrityFlag(
                flag_type="ai",
                confidence=probability,
                reason="Mixed or partial AI writing patterns detected",
                text=clean[:400],
            )
        ]

    model_name = str(payload.get("model") or "classifier")
    pct = int(round(probability * 100))
    explanation = str(
        payload.get("explanation")
        or f"On-premise classifier ({model_name}) estimates ~{pct}% AI-like content."
    )
    return build_ai_result(
        flags,
        confidence=probability,
        ai_verified=True,
        detection_method="classifier_roberta",
        explanation=explanation,
    )


def detect_ai_segments(document_text: str) -> IntegrityResult:
    """Scan a single submission for AI-generated passages (full-doc + chunks + heuristics)."""
    clean = strip_markers(document_text).strip()
    if len(clean.split()) < 40:
        return build_no_ai_result(
            explanation="Document too short for reliable AI detection.",
            ai_verified=False,
            detection_method="skipped",
        )

    classifier_result = _detect_ai_via_classifier(clean)
    if classifier_result is not None:
        return classifier_result

    all_flags: list[IntegrityFlag] = []
    chunk_verified = False
    doc_confidence = 0.0

    full_result = scan_document_for_ai(clean)
    if is_confirmed_ai_result(full_result):
        return full_result
    if full_result.integrity_type == "ai":
        all_flags.extend(full_result.flags)
        doc_confidence = full_result.confidence

    chunks = chunk_text(clean, chunk_size=800, overlap=100)[:_MAX_AI_CHUNKS_PER_DOC]
    for idx, chunk in enumerate(chunks):
        prompt = build_chunk_ai_prompt(chunk, idx, len(chunks))
        raw = ollama_client.generate(
            prompt,
            system=_AI_DETECTION_SYSTEM,
            temperature=0.05,
            **ollama_client.assessment_llm_options(),
        )
        parsed = parse_json_response(raw or "")
        if not parsed:
            continue
        chunk_verified = True
        try:
            chunk_conf = float(parsed.get("overall_confidence", 0))
        except (TypeError, ValueError):
            chunk_conf = 0.0

        if not parsed.get("ai_detected") and chunk_conf < AI_DOCUMENT_MIN:
            continue

        chunk_flags = _parse_flags(parsed.get("flags", []), "ai", AI_FLAG_MIN)
        if not chunk_flags and chunk_conf >= AI_DOCUMENT_MIN:
            chunk_flags = [
                IntegrityFlag(
                    flag_type="ai",
                    confidence=chunk_conf,
                    reason="Chunk reads as AI-generated prose",
                    text=chunk[: min(300, len(chunk))],
                )
            ]
        all_flags.extend(chunk_flags)
        doc_confidence = max(doc_confidence, chunk_conf)

    heuristic_score, heuristic_flags = score_ai_writing_heuristics(clean)
    ai_verified = full_result.ai_verified or chunk_verified

    if all_flags:
        return build_ai_result(
            all_flags,
            confidence=doc_confidence,
            ai_verified=ai_verified,
            detection_method="ai_scan" if chunk_verified else "ai_full_document",
        )

    if heuristic_score >= AI_HEURISTIC_MIN and heuristic_flags:
        return build_ai_result(
            heuristic_flags,
            confidence=heuristic_score,
            ai_verified=False,
            detection_method="heuristic_ai",
            explanation=(
                "Local pattern analysis detected AI writing markers "
                f"({int(heuristic_score * 100)}% confidence)."
            ),
        )

    if ai_verified:
        return build_no_ai_result(
            explanation="No AI-generated passages detected.",
            ai_verified=True,
            detection_method="ai_scan",
        )

    return build_no_ai_result(
        explanation="AI model unavailable — AI scan skipped.",
        ai_verified=False,
        detection_method="skipped",
    )
