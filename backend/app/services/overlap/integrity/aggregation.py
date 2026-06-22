"""Flag parsing, de-duplication, result merging and human-readable metrics.

This is the "result aggregation" layer: it turns raw LLM flag payloads into
`IntegrityFlag`/`IntegrityResult` objects, combines multiple results, and derives
the display metrics shown to teachers.
"""

from __future__ import annotations

from app.services.overlap.dedupe import dedupe_by_containment
from app.services.overlap.integrity.models import IntegrityFlag, IntegrityResult
from app.services.overlap.integrity.thresholds import (
    AI_CLASSIFIER_CONFIRMED,
    AI_CLASSIFIER_MIN,
    AI_CONFIRMED_MIN,
    STUDENT_AI_CONFIRMED_MIN,
)


def _parse_flags(raw_flags: list, flag_type: str, min_confidence: float) -> list[IntegrityFlag]:
    if flag_type == "ai":
        parsed: list[IntegrityFlag] = []
        for item in raw_flags or []:
            if not isinstance(item, dict):
                continue
            try:
                confidence = float(item.get("confidence", 0))
            except (TypeError, ValueError):
                continue
            if confidence < min_confidence:
                continue
            reason = str(item.get("reason") or "").strip()
            if not reason:
                continue
            text = str(item.get("text") or "").strip()
            if len(text.split()) < 4:
                continue
            parsed.append(
                IntegrityFlag(
                    flag_type="ai",
                    confidence=confidence,
                    reason=reason,
                    text=text,
                )
            )
        return parsed

    rows: list[tuple[int, IntegrityFlag]] = []
    for item in raw_flags or []:
        if not isinstance(item, dict):
            continue
        try:
            confidence = float(item.get("confidence", 0))
        except (TypeError, ValueError):
            continue
        if confidence < min_confidence:
            continue
        reason = str(item.get("reason") or "").strip()
        if not reason:
            continue
        text_a = str(item.get("text_a") or item.get("text") or "").strip()
        text_b = str(item.get("text_b") or "").strip()
        if len(text_a.split()) < 4 and len(text_b.split()) < 4:
            continue
        try:
            order = int(item.get("order_in_a", 999))
        except (TypeError, ValueError):
            order = 999
        rows.append(
            (
                order,
                IntegrityFlag(
                    flag_type="student",
                    confidence=confidence,
                    reason=reason,
                    text_a=text_a,
                    text_b=text_b,
                ),
            )
        )
    rows.sort(key=lambda row: row[0])
    return [flag for _, flag in rows]


def _dedupe_ai_flags(flags: list[IntegrityFlag]) -> list[IntegrityFlag]:
    return dedupe_by_containment(
        flags,
        key=lambda f: (f.text or "").lower()[:80],
        sort_key=lambda f: f.confidence,
    )


def _assign_student_match_ids(flags: list[IntegrityFlag]) -> list[IntegrityFlag]:
    """Number student plagiarism flags so the UI can pair highlights across panes."""
    counter = 0
    for flag in flags:
        if flag.flag_type != "student":
            continue
        counter += 1
        flag.match_id = counter
    return flags


def _dedupe_student_integrity_flags(flags: list[IntegrityFlag]) -> list[IntegrityFlag]:
    return dedupe_by_containment(
        flags,
        key=lambda f: (f.text_a or f.text or "").lower()[:80],
        sort_key=lambda f: f.confidence,
    )


def _dedupe_flags(flags: list[IntegrityFlag]) -> list[IntegrityFlag]:
    ai_flags = [f for f in flags if f.flag_type == "ai"]
    student_flags = [f for f in flags if f.flag_type == "student"]
    return _dedupe_ai_flags(ai_flags) + _assign_student_match_ids(
        _dedupe_student_integrity_flags(student_flags)
    )


def _summarise_flags(flags: list[IntegrityFlag], label: str) -> str:
    if not flags:
        return f"No {label} content detected."
    top = max(flags, key=lambda f: f.confidence)
    return (
        f"{label} content detected ({int(top.confidence * 100)}% confidence): {top.reason}"
    )


def merge_student_plagiarism_results(results: list[IntegrityResult]) -> IntegrityResult:
    """Combine LLM checks on multiple excerpt pairs from the same evidence pair."""
    positives = [r for r in results if r.integrity_type == "student_plagiarism"]
    if not positives:
        fallback = next((r for r in results if r.explanation), None)
        if fallback:
            return fallback
        return IntegrityResult(
            integrity_type="none",
            confidence=0.0,
            status="none",
            explanation="No student plagiarism detected.",
            detection_method="ai_excerpt_chunks",
        )

    flags: list[IntegrityFlag] = []
    for result in positives:
        flags.extend(result.flags)
    deduped = _dedupe_flags(flags)
    max_conf = max(r.confidence for r in positives)
    status = "confirmed" if max_conf >= STUDENT_AI_CONFIRMED_MIN else "possible"
    if len(deduped) == 1:
        explanation = positives[0].explanation
    else:
        explanation = f"Plagiarism detected across {len(deduped)} passage(s) in matched excerpts."
    return IntegrityResult(
        integrity_type="student_plagiarism",
        confidence=max_conf,
        status=status,
        flags=deduped,
        explanation=explanation,
        ai_verified=True,
        detection_method="ai_excerpt_chunks",
    )


def combine_ai_results(*results: IntegrityResult | None) -> IntegrityResult | None:
    """Merge AI scan results from one or more documents."""
    flags: list[IntegrityFlag] = []
    verified = False
    doc_confidences: list[float] = []
    detection_methods: list[str] = []
    for result in results:
        if not result or result.integrity_type != "ai":
            continue
        flags.extend(result.flags)
        verified = verified or result.ai_verified
        doc_confidences.append(result.confidence)
        detection_methods.append(result.detection_method or "")
    if not flags:
        return None
    deduped = _dedupe_flags(flags)
    segment_max = max(f.confidence for f in deduped)
    if any(m == "classifier_roberta" for m in detection_methods):
        report_conf = max(doc_confidences) if doc_confidences else segment_max
    else:
        report_conf = max([*doc_confidences, segment_max])
    status = "confirmed" if report_conf >= AI_CONFIRMED_MIN else "possible"
    if any(m == "classifier_roberta" for m in detection_methods):
        if report_conf >= AI_CLASSIFIER_CONFIRMED:
            status = "confirmed"
        elif report_conf >= AI_CLASSIFIER_MIN:
            status = "possible"
    return IntegrityResult(
        integrity_type="ai",
        confidence=report_conf,
        status=status,
        flags=deduped,
        explanation=_summarise_flags(deduped, "AI-generated"),
        ai_verified=verified,
        detection_method="ai_scan",
    )


def merge_integrity_results(
    ai_result: IntegrityResult | None,
    student_result: IntegrityResult | None,
) -> IntegrityResult:
    """Combine per-document AI scan with pairwise student plagiarism."""
    ai = ai_result if ai_result and ai_result.integrity_type == "ai" else None
    student = (
        student_result
        if student_result and student_result.integrity_type == "student_plagiarism"
        else None
    )

    if ai and student:
        flags = _dedupe_flags([*ai.flags, *student.flags])
        student_matches = len([f for f in student.flags if f.flag_type == "student"])
        max_conf = max(ai.confidence, student.confidence)
        status = "confirmed" if max_conf >= STUDENT_AI_CONFIRMED_MIN else "possible"
        return IntegrityResult(
            integrity_type="both",
            confidence=max_conf,
            status=status,
            flags=flags,
            explanation=(
                f"~{int(ai.confidence * 100)}% of submission estimated AI-written; "
                f"{student_matches} matched passage{'s' if student_matches != 1 else ''} "
                f"with another student ({int(student.confidence * 100)}% overlap confidence)."
            ),
            ai_verified=ai.ai_verified or student.ai_verified,
            detection_method="ai_combined",
        )

    if student:
        return student
    if ai:
        return ai

    return IntegrityResult(
        integrity_type="none",
        confidence=0.0,
        status="none",
        explanation="No integrity issues detected.",
    )


def build_ai_only_hit(
    *,
    student_id: str,
    student_name: str,
    evidence_id: str,
    file_name: str,
    group_id: str,
    group_name: str,
    ai_result: IntegrityResult,
    document_text: str,
) -> dict:
    """Build a signal payload for AI-only integrity issues (single student)."""
    excerpt = ai_result.flags[0].text if ai_result.flags else document_text[:300]
    hit = {
        "scope": "within_group",
        "status": ai_result.status,
        "student_a_id": student_id,
        "student_a_name": student_name,
        "student_b_id": student_id,
        "student_b_name": student_name,
        "evidence_a_id": evidence_id,
        "evidence_b_id": evidence_id,
        "file_a": file_name,
        "file_b": file_name,
        "passage_a": excerpt,
        "passage_b": "",
        "similarity": ai_result.confidence,
        "group_a_id": group_id,
        "group_b_id": group_id,
        "group_a_name": group_name,
        "group_b_name": group_name,
        "ai_verified": ai_result.ai_verified,
        "ai_explanation": ai_result.explanation,
        "detection_method": ai_result.detection_method,
        "integrity_type": "ai",
        "flags": [f.to_dict() for f in ai_result.flags],
        "ai_content_percent": int(round(ai_result.confidence * 100)),
        "peak_ai_section_percent": int(
            round(max((f.confidence for f in ai_result.flags), default=ai_result.confidence) * 100)
        ),
        "student_match_count": 0,
    }
    return attach_integrity_metrics(hit)


def build_metrics_summary(
    integrity_type: str,
    *,
    ai_content_percent: int | None = None,
    peak_ai_section_percent: int | None = None,
    student_match_count: int | None = None,
    overlap_confidence_percent: int | None = None,
    detection_confidence_percent: int | None = None,
) -> str:
    parts: list[str] = []
    if integrity_type in ("ai", "both") and ai_content_percent is not None:
        parts.append(f"~{ai_content_percent}% est. AI-written")
        if (
            peak_ai_section_percent is not None
            and peak_ai_section_percent > ai_content_percent + 5
        ):
            parts.append(f"peak section {peak_ai_section_percent}%")
    if integrity_type in ("student_plagiarism", "both"):
        if student_match_count:
            label = "passage" if student_match_count == 1 else "passages"
            parts.append(f"{student_match_count} matched {label}")
        if overlap_confidence_percent is not None:
            parts.append(f"{overlap_confidence_percent}% overlap confidence")
    elif integrity_type == "ai" and detection_confidence_percent is not None:
        parts.append(f"{detection_confidence_percent}% detection confidence")
    return " · ".join(parts)


def attach_integrity_metrics(
    hit: dict,
    *,
    ai_result: IntegrityResult | None = None,
    student_confidence: float | None = None,
) -> dict:
    """Add human-readable integrity percentages and a short summary to a hit dict."""
    flags = hit.get("flags") or []
    integrity_type = hit.get("integrity_type", "student_plagiarism")
    student_flags = [f for f in flags if f.get("type") == "student"]

    ai_content_percent = hit.get("ai_content_percent")
    peak_ai_section_percent = hit.get("peak_ai_section_percent")
    if integrity_type in ("ai", "both"):
        if ai_content_percent is None and ai_result and ai_result.integrity_type == "ai":
            ai_content_percent = int(round(ai_result.confidence * 100))
        if ai_content_percent is None and integrity_type == "ai":
            ai_content_percent = int(round(float(hit.get("similarity", 0)) * 100))
        if peak_ai_section_percent is None:
            ai_flags = [f for f in flags if f.get("type") == "ai"]
            if ai_flags:
                peak_ai_section_percent = int(
                    round(max(float(f.get("confidence", 0)) for f in ai_flags) * 100)
                )
            elif ai_result and ai_result.flags:
                peak_ai_section_percent = int(
                    round(max(f.confidence for f in ai_result.flags) * 100)
                )

    student_match_count = hit.get("student_match_count")
    overlap_confidence_percent = hit.get("overlap_confidence_percent")
    detection_confidence_percent = hit.get("detection_confidence_percent")

    if integrity_type in ("student_plagiarism", "both"):
        if student_match_count is None:
            student_match_count = len(student_flags)
        if overlap_confidence_percent is None:
            conf = (
                student_confidence
                if student_confidence is not None
                else float(hit.get("similarity", 0))
            )
            overlap_confidence_percent = int(round(conf * 100))
    elif integrity_type == "ai":
        student_match_count = 0
        if detection_confidence_percent is None:
            detection_confidence_percent = ai_content_percent

    hit["ai_content_percent"] = ai_content_percent
    hit["peak_ai_section_percent"] = peak_ai_section_percent
    hit["student_match_count"] = student_match_count
    hit["overlap_confidence_percent"] = overlap_confidence_percent
    hit["detection_confidence_percent"] = detection_confidence_percent
    hit["metrics_summary"] = build_metrics_summary(
        integrity_type,
        ai_content_percent=ai_content_percent,
        peak_ai_section_percent=peak_ai_section_percent,
        student_match_count=student_match_count,
        overlap_confidence_percent=overlap_confidence_percent,
        detection_confidence_percent=detection_confidence_percent,
    )
    return hit


def derive_signal_metrics(detail: dict, confidence: float, integrity_type: str) -> dict:
    """Compute display metrics for stored signals (including legacy rows without metrics)."""
    if detail.get("metrics_summary"):
        return {
            "ai_content_percent": detail.get("ai_content_percent"),
            "peak_ai_section_percent": detail.get("peak_ai_section_percent"),
            "student_match_count": detail.get("student_match_count"),
            "overlap_confidence_percent": detail.get("overlap_confidence_percent"),
            "detection_confidence_percent": detail.get("detection_confidence_percent"),
            "metrics_summary": detail.get("metrics_summary"),
        }
    hit = attach_integrity_metrics(
        {
            "integrity_type": integrity_type,
            "similarity": confidence,
            "flags": detail.get("flags") or [],
        }
    )
    return {
        "ai_content_percent": hit.get("ai_content_percent"),
        "peak_ai_section_percent": hit.get("peak_ai_section_percent"),
        "student_match_count": hit.get("student_match_count"),
        "overlap_confidence_percent": hit.get("overlap_confidence_percent"),
        "detection_confidence_percent": hit.get("detection_confidence_percent"),
        "metrics_summary": hit.get("metrics_summary"),
    }
