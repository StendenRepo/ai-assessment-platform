"""Student-to-student plagiarism detection (direct comparison, near-duplicate, LLM)."""

from __future__ import annotations

from difflib import SequenceMatcher

from app.lib.llm_json import parse_json_response
from app.services import ollama_client
from app.services.overlap.integrity.aggregation import (
    _dedupe_flags,
    _parse_flags,
    attach_integrity_metrics,
    merge_student_plagiarism_results,
)
from app.services.overlap.integrity.markers import strip_markers
from app.services.overlap.integrity.models import IntegrityFlag, IntegrityResult
from app.services.overlap.integrity.prompts import (
    _INTEGRITY_SYSTEM,
    build_excerpt_plagiarism_prompt,
    build_full_document_plagiarism_prompt,
)
from app.services.overlap.integrity.text import (
    _document_similarity,
    _merge_sentence_pairs,
    _pairs_from_sentence_alignment,
    _split_compare_units,
    _split_comparison_sentences,
)
from app.services.overlap.integrity.thresholds import (
    NEAR_DUPLICATE_DOC_MIN,
    NEAR_DUPLICATE_UNIT_MIN,
    STUDENT_AI_CONFIRMED_MIN,
    STUDENT_AI_FLAG_MIN,
    STUDENT_CONFIRMED_MIN,
    STUDENT_POSSIBLE_MIN,
    _MAX_FLAG_SNIPPET_CHARS,
    _MAX_FULL_DOC_COMBINED_CHARS,
    _MAX_PAIR_CHARS,
    _MAX_PAIR_FLAGS,
    _MAX_PAIR_VERIFY_CHUNK_PAIRS,
)
from app.services.text_chunker import chunk_text


def _flags_from_direct_text_comparison(
    clean_a: str,
    clean_b: str,
    *,
    base_confidence: float,
) -> list[IntegrityFlag]:
    """Phase 1: compare raw text directly - sentence alignment, no LLM."""
    sents_a = _split_comparison_sentences(clean_a)
    sents_b = _split_comparison_sentences(clean_b)
    pairs: list[tuple[str, str]] = []

    if sents_a and sents_b:
        aligned = _pairs_from_sentence_alignment(sents_a, sents_b)
        pairs = _merge_sentence_pairs([(a, b) for a, b, _ in aligned])

    if not pairs:
        units_a = _split_compare_units(clean_a)
        units_b = _split_compare_units(clean_b)
        used_b: set[int] = set()
        for unit_a in units_a:
            best_index = -1
            best_ratio = 0.0
            for index, unit_b in enumerate(units_b):
                if index in used_b:
                    continue
                ratio = SequenceMatcher(None, unit_a.lower(), unit_b.lower()).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_index = index
            if best_index < 0 or best_ratio < NEAR_DUPLICATE_UNIT_MIN:
                continue
            used_b.add(best_index)
            pairs.append((unit_a, units_b[best_index]))

    flags: list[IntegrityFlag] = []
    for text_a, text_b in pairs[:_MAX_PAIR_FLAGS]:
        ratio = SequenceMatcher(None, text_a.lower(), text_b.lower()).ratio()
        flags.append(
            IntegrityFlag(
                flag_type="student",
                confidence=round(min(0.99, max(base_confidence, ratio)), 2),
                reason="Identical passage"
                if ratio >= 0.98
                else "Nearly identical passage",
                text_a=text_a[:_MAX_FLAG_SNIPPET_CHARS],
                text_b=text_b[:_MAX_FLAG_SNIPPET_CHARS],
            )
        )
    return flags


def _flags_for_near_duplicate_documents(
    clean_a: str,
    clean_b: str,
    *,
    base_confidence: float,
) -> list[IntegrityFlag]:
    """Build passage flags for copied or near-copied submissions without an LLM."""
    flags = _flags_from_direct_text_comparison(
        clean_a, clean_b, base_confidence=base_confidence
    )
    if flags:
        return flags

    chunks_a = chunk_text(clean_a, chunk_size=500, overlap=0)
    chunks_b = chunk_text(clean_b, chunk_size=500, overlap=0)
    for chunk_a, chunk_b in zip(chunks_a, chunks_b):
        ratio = SequenceMatcher(None, chunk_a.lower(), chunk_b.lower()).ratio()
        if ratio < NEAR_DUPLICATE_UNIT_MIN:
            continue
        flags.append(
            IntegrityFlag(
                flag_type="student",
                confidence=round(min(0.99, max(base_confidence, ratio)), 2),
                reason="Identical section" if ratio >= 0.98 else "Matching section",
                text_a=chunk_a[:_MAX_FLAG_SNIPPET_CHARS],
                text_b=chunk_b[:_MAX_FLAG_SNIPPET_CHARS],
            )
        )

    return flags[:_MAX_PAIR_FLAGS]


def _near_duplicate_plagiarism_result(
    clean_a: str,
    clean_b: str,
    *,
    tfidf_hint: float,
) -> IntegrityResult | None:
    """Fast path for wholesale copying - accurate confidence and multi-passage flags."""
    doc_ratio = _document_similarity(clean_a, clean_b)
    if doc_ratio < NEAR_DUPLICATE_DOC_MIN and tfidf_hint < 0.92:
        return None

    confidence = round(min(0.99, max(doc_ratio, tfidf_hint, 0.95)), 2)
    flags = _flags_for_near_duplicate_documents(
        clean_a,
        clean_b,
        base_confidence=confidence,
    )
    if not flags:
        return None

    pct = int(confidence * 100)
    if doc_ratio >= 0.98:
        explanation = f"Submissions are {pct}% identical (word-for-word copy)."
        detection_method = "direct_comparison"
        ai_verified = False
    else:
        explanation = f"Submissions are {pct}% similar across {len(flags)} matched passage(s)."
        detection_method = "near_duplicate"
        ai_verified = True

    return IntegrityResult(
        integrity_type="student_plagiarism",
        confidence=confidence,
        status="confirmed",
        flags=_dedupe_flags(flags),
        explanation=explanation,
        ai_verified=ai_verified,
        detection_method=detection_method,
    )


def scan_document_pair_plagiarism(
    document_a: str,
    document_b: str,
    *,
    tfidf_hint: float = 0.0,
) -> IntegrityResult:
    """Compare two full submissions with on-premise LLM - finds all plagiarism instances."""
    clean_a = strip_markers(document_a).strip()
    clean_b = strip_markers(document_b).strip()
    if len(clean_a.split()) < 25 or len(clean_b.split()) < 25:
        return IntegrityResult(
            integrity_type="none",
            confidence=0.0,
            status="none",
            explanation="Documents too short for comparison.",
        )

    near_dup = _near_duplicate_plagiarism_result(
        clean_a, clean_b, tfidf_hint=tfidf_hint
    )
    if near_dup is not None:
        return near_dup

    prompt = build_full_document_plagiarism_prompt(clean_a, clean_b, tfidf_hint)

    raw = ollama_client.generate(
        prompt,
        system=_INTEGRITY_SYSTEM,
        temperature=0.05,
        **ollama_client.assessment_llm_options(),
    )
    parsed = parse_json_response(raw or "")
    if not parsed:
        return assess_student_plagiarism(
            clean_a[:_MAX_PAIR_CHARS],
            clean_b[:_MAX_PAIR_CHARS],
            tfidf_hint,
        )

    try:
        confidence = float(parsed.get("overall_confidence", tfidf_hint))
    except (TypeError, ValueError):
        confidence = tfidf_hint
    confidence = max(0.0, min(1.0, confidence))

    status = str(parsed.get("status") or "none").lower()
    if status not in {"confirmed", "possible", "none"}:
        status = "confirmed" if confidence >= STUDENT_AI_CONFIRMED_MIN else "possible"

    detected = bool(parsed.get("plagiarism_detected", status != "none"))
    flags = _parse_flags(parsed.get("flags", []), "student", STUDENT_AI_FLAG_MIN)[:_MAX_PAIR_FLAGS]

    if not detected or status == "none" or confidence < STUDENT_AI_FLAG_MIN:
        return IntegrityResult(
            integrity_type="none",
            confidence=confidence,
            status="none",
            explanation=str(parsed.get("explanation") or "No student plagiarism detected."),
            ai_verified=True,
            detection_method="ai_full_document",
        )

    if not flags and detected:
        flags = [
            IntegrityFlag(
                flag_type="student",
                confidence=confidence,
                reason=str(parsed.get("explanation") or "Shared content between submissions."),
                text_a=clean_a[:300],
                text_b=clean_b[:300],
            )
        ]

    return IntegrityResult(
        integrity_type="student_plagiarism",
        confidence=confidence,
        status=status,
        flags=_dedupe_flags(flags),
        explanation=str(parsed.get("explanation") or "Student plagiarism detected between submissions."),
        ai_verified=True,
        detection_method="ai_full_document",
    )


def scan_evidence_pair_plagiarism(
    document_a: str,
    document_b: str,
    *,
    tfidf_hint: float,
    primary_passage_a: str = "",
    primary_passage_b: str = "",
    extra_passage_pairs: list[tuple[str, str]] | None = None,
) -> IntegrityResult:
    """Verify plagiarism using excerpts for long work; full-doc only when submissions are short."""
    clean_a = strip_markers(document_a).strip()
    clean_b = strip_markers(document_b).strip()
    combined_len = len(clean_a) + len(clean_b)

    near_dup = _near_duplicate_plagiarism_result(
        clean_a, clean_b, tfidf_hint=tfidf_hint
    )
    doc_ratio = _document_similarity(clean_a, clean_b)
    if near_dup is not None and doc_ratio >= 0.98:
        return near_dup

    if (
        combined_len <= _MAX_FULL_DOC_COMBINED_CHARS
        and len(clean_a.split()) >= 25
        and len(clean_b.split()) >= 25
    ):
        ai_result = scan_document_pair_plagiarism(clean_a, clean_b, tfidf_hint=tfidf_hint)
        if near_dup is not None and ai_result.integrity_type == "student_plagiarism":
            merged_flags = _dedupe_flags([*near_dup.flags, *ai_result.flags])[:_MAX_PAIR_FLAGS]
            return IntegrityResult(
                integrity_type="student_plagiarism",
                confidence=max(near_dup.confidence, ai_result.confidence),
                status="confirmed"
                if max(near_dup.confidence, ai_result.confidence) >= STUDENT_AI_CONFIRMED_MIN
                else "possible",
                flags=merged_flags,
                explanation=(
                    f"{near_dup.explanation} "
                    f"AI review found {len(ai_result.flags)} additional paraphrased passage(s)."
                ).strip(),
                ai_verified=True,
                detection_method="direct_plus_ai",
            )
        if near_dup is not None:
            return near_dup
        if ai_result.integrity_type != "none":
            return ai_result

    if near_dup is not None:
        return near_dup

    pairs: list[tuple[str, str]] = []
    primary_a = strip_markers(primary_passage_a).strip()
    primary_b = strip_markers(primary_passage_b).strip()
    if primary_a and primary_b:
        pairs.append((primary_a, primary_b))

    seen: set[tuple[str, str]] = {(primary_a, primary_b)} if primary_a and primary_b else set()
    for passage_a, passage_b in extra_passage_pairs or []:
        a = strip_markers(passage_a).strip()
        b = strip_markers(passage_b).strip()
        key = (a, b)
        if not a or not b or key in seen:
            continue
        seen.add(key)
        pairs.append(key)

    if not pairs:
        if len(clean_a.split()) < 25 or len(clean_b.split()) < 25:
            return IntegrityResult(
                integrity_type="none",
                confidence=0.0,
                status="none",
                explanation="Documents too short for comparison.",
            )
        pairs.append((clean_a[:_MAX_PAIR_CHARS], clean_b[:_MAX_PAIR_CHARS]))

    results = [
        assess_student_plagiarism(a, b, tfidf_hint)
        for a, b in pairs[:_MAX_PAIR_VERIFY_CHUNK_PAIRS]
    ]
    return merge_student_plagiarism_results(results)


def assess_student_plagiarism(
    passage_a: str,
    passage_b: str,
    tfidf_score: float,
) -> IntegrityResult:
    """Detect student-to-student plagiarism including paraphrasing and light edits."""
    clean_a = strip_markers(passage_a)
    clean_b = strip_markers(passage_b)
    if not clean_a.strip() or not clean_b.strip():
        return IntegrityResult(
            integrity_type="none",
            confidence=0.0,
            status="none",
            explanation="No extractable text to compare.",
        )

    if tfidf_score < STUDENT_POSSIBLE_MIN:
        return IntegrityResult(
            integrity_type="none",
            confidence=tfidf_score,
            status="none",
            explanation="Statistical similarity below review threshold.",
            detection_method="tfidf_prescreen",
        )

    near_dup = _near_duplicate_plagiarism_result(
        clean_a, clean_b, tfidf_hint=tfidf_score
    )
    if near_dup is not None:
        return near_dup

    prompt = build_excerpt_plagiarism_prompt(clean_a, clean_b, tfidf_score)

    raw = ollama_client.generate(
        prompt,
        system=_INTEGRITY_SYSTEM,
        temperature=0.05,
        **ollama_client.assessment_llm_options(),
    )
    parsed = parse_json_response(raw or "")
    if not parsed:
        return _student_fallback(tfidf_score)

    try:
        confidence = float(parsed.get("overall_confidence", tfidf_score))
    except (TypeError, ValueError):
        confidence = tfidf_score
    confidence = max(0.0, min(1.0, confidence))

    status = str(parsed.get("status") or "none").lower()
    if status not in {"confirmed", "possible", "none"}:
        status = "confirmed" if confidence >= STUDENT_AI_CONFIRMED_MIN else "possible"

    detected = bool(parsed.get("plagiarism_detected", status != "none"))
    flags = _parse_flags(parsed.get("flags", []), "student", STUDENT_AI_FLAG_MIN)

    if not detected or status == "none" or confidence < STUDENT_AI_FLAG_MIN:
        return IntegrityResult(
            integrity_type="none",
            confidence=confidence,
            status="none",
            explanation=str(parsed.get("explanation") or "No student plagiarism detected."),
            ai_verified=True,
            detection_method="ai_plagiarism",
        )

    if not flags and detected:
        flags = [
            IntegrityFlag(
                flag_type="student",
                confidence=confidence,
                reason=str(parsed.get("explanation") or "Shared wording between submissions."),
                text_a=clean_a[:200],
                text_b=clean_b[:200],
            )
        ]

    return IntegrityResult(
        integrity_type="student_plagiarism",
        confidence=confidence,
        status=status,
        flags=_dedupe_flags(flags),
        explanation=str(parsed.get("explanation") or "Student plagiarism detected between submissions."),
        ai_verified=True,
        detection_method="ai_plagiarism",
    )


def _student_fallback(tfidf_score: float) -> IntegrityResult:
    if tfidf_score < STUDENT_POSSIBLE_MIN:
        status = "none"
        detected = False
    elif tfidf_score >= STUDENT_CONFIRMED_MIN:
        status = "confirmed"
        detected = True
    else:
        status = "possible"
        detected = True

    if not detected:
        return IntegrityResult(
            integrity_type="none",
            confidence=tfidf_score,
            status="none",
            explanation="Statistical similarity below review threshold.",
            detection_method="tfidf_fallback",
        )

    return IntegrityResult(
        integrity_type="student_plagiarism",
        confidence=tfidf_score,
        status=status,
        flags=[],
        explanation="AI model unavailable — using statistical text similarity only.",
        ai_verified=False,
        detection_method="tfidf_fallback",
    )


def enrich_hit_with_ai(
    hit: dict,
    *,
    document_a: str = "",
    document_b: str = "",
    extra_passage_pairs: list[tuple[str, str]] | None = None,
) -> dict | None:
    """Verify a TF-IDF hit with on-premise LLM plagiarism detection."""
    tfidf = float(hit.get("similarity", 0.0))
    if document_a.strip() and document_b.strip():
        student_result = scan_evidence_pair_plagiarism(
            document_a,
            document_b,
            tfidf_hint=tfidf,
            primary_passage_a=hit.get("passage_a", ""),
            primary_passage_b=hit.get("passage_b", ""),
            extra_passage_pairs=extra_passage_pairs,
        )
    else:
        student_result = assess_student_plagiarism(
            hit.get("passage_a", ""),
            hit.get("passage_b", ""),
            tfidf,
        )
    if student_result.integrity_type == "none":
        return None

    enriched = dict(hit)
    enriched["similarity"] = student_result.confidence
    enriched["status"] = student_result.status
    enriched["ai_verified"] = student_result.ai_verified
    enriched["ai_explanation"] = student_result.explanation
    enriched["detection_method"] = student_result.detection_method
    enriched["integrity_type"] = student_result.integrity_type
    enriched["flags"] = [f.to_dict() for f in student_result.flags]
    attach_integrity_metrics(enriched, student_confidence=student_result.confidence)

    for flag in student_result.flags:
        if flag.text_a:
            enriched.setdefault("ai_shared_excerpt", flag.text_a)
            break

    return enriched
