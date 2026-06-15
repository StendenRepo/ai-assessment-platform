"""AI-assisted academic integrity detection: AI-generated text and student plagiarism."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from app.services import ollama_client
from app.services import ai_detector_client
from app.services.text_chunker import chunk_text

# AI detection thresholds — document-level is slightly looser than per-flag.
AI_FLAG_MIN = 0.62
AI_DOCUMENT_MIN = 0.58
AI_CONFIRMED_MIN = 0.76
AI_HEURISTIC_MIN = 0.70
AI_CLASSIFIER_MIN = 0.15
AI_CLASSIFIER_CONFIRMED = 0.50
AI_CLASSIFIER_SEGMENT_MIN = 0.55
STUDENT_POSSIBLE_MIN = 0.42
STUDENT_CONFIRMED_MIN = 0.68
STUDENT_AI_FLAG_MIN = 0.72
STUDENT_AI_CONFIRMED_MIN = 0.82
NEAR_DUPLICATE_DOC_MIN = 0.90
NEAR_DUPLICATE_UNIT_MIN = 0.82

_MIN_ANCHOR_WORDS = 4
_MIN_PARTIAL_WINDOW = 10

_MAX_CHUNK_CHARS = 1200
_MAX_PAIR_CHARS = 1400
_MAX_DOC_COMPARE_CHARS = 3000
_MAX_FULL_DOC_COMBINED_CHARS = 10000
_MAX_PAIR_VERIFY_CHUNK_PAIRS = 3
_MAX_AI_CHUNKS_PER_DOC = 12
_MAX_AI_FLAGS = 12
_MAX_PAIR_FLAGS = 20
_MAX_FLAG_SNIPPET_CHARS = 1200
_DIRECT_MERGE_MAX_WORDS = 90
_MIN_COMPARISON_SENTENCE_WORDS = 4

_AI_DETECTION_SYSTEM = (
    "You are an expert detector of AI-generated student writing (ChatGPT, Claude, Gemini, etc.). "
    "Students in an Applied AI course may submit LLM-written portfolios. "
    "Be sceptical: polished, generic, uniform prose without personal project detail is likely AI. "
    "Respond with JSON only — no markdown outside the object."
)

_AI_TELL_PHRASES: tuple[tuple[str, str], ...] = (
    ("furthermore", "Generic LLM transition phrase"),
    ("additionally", "Generic LLM transition phrase"),
    ("it is important to note", "Classic AI hedging"),
    ("it's worth noting", "AI hedging phrase"),
    ("in today's", "Generic AI opener"),
    ("plays a crucial role", "AI boilerplate phrasing"),
    ("in conclusion", "Formulaic AI closing structure"),
    ("delve", "Common AI vocabulary"),
    ("comprehensive", "Overused AI adjective"),
    ("utilize", "AI prefers formal 'utilize' over 'use'"),
    ("leverage", "Corporate AI tone"),
    ("robust", "Overused AI descriptor"),
    ("seamless", "Marketing/AI tone"),
    ("multifaceted", "Typical AI vocabulary"),
    ("in the realm of", "AI boilerplate"),
    ("serves as a testament", "AI flourish"),
    ("underscores the importance", "AI boilerplate"),
    ("navigate the complexities", "AI cliché"),
    ("at its core", "AI discourse marker"),
)
_MARKER_OPEN = re.compile(
    r"⟦(ai|student):(?:m(\d+):)?(\d+):([^⟧]*)⟧(.*?)⟦/\1⟧",
    re.DOTALL,
)
_LEGACY_MARKER_RE = re.compile(r"\[\[(.*?)\]\]", re.DOTALL)

_INTEGRITY_SYSTEM = (
    "You are an academic integrity analyst for a university Applied AI course. "
    "Detect AI-generated writing and student-to-student plagiarism including subtle "
    "paraphrasing. Respond with JSON only — no markdown outside the object."
)


@dataclass
class IntegrityFlag:
    flag_type: str  # "ai" or "student"
    confidence: float
    reason: str
    text: str = ""
    text_a: str = ""
    text_b: str = ""
    match_id: int | None = None

    def to_dict(self) -> dict:
        payload = {
            "type": self.flag_type,
            "confidence": round(self.confidence, 4),
            "reason": self.reason,
        }
        if self.text:
            payload["text"] = self.text
        if self.text_a:
            payload["text_a"] = self.text_a
        if self.text_b:
            payload["text_b"] = self.text_b
        if self.match_id is not None:
            payload["match_id"] = self.match_id
        return payload


@dataclass
class IntegrityResult:
    integrity_type: str  # "ai", "student_plagiarism", "both", "none"
    confidence: float
    status: str  # "confirmed", "possible", "none"
    flags: list[IntegrityFlag] = field(default_factory=list)
    explanation: str = ""
    ai_verified: bool = False
    detection_method: str = "statistical"

    def to_dict(self) -> dict:
        return {
            "integrity_type": self.integrity_type,
            "confidence": round(self.confidence, 4),
            "status": self.status,
            "flags": [f.to_dict() for f in self.flags],
            "explanation": self.explanation,
            "ai_verified": self.ai_verified,
            "detection_method": self.detection_method,
        }


def strip_markers(text: str) -> str:
    if not text:
        return ""
    cleaned = _MARKER_OPEN.sub(r"\4", text)
    return _LEGACY_MARKER_RE.sub(r"\1", cleaned)


def _wrap_flag(
    flag_type: str,
    confidence: float,
    reason: str,
    text: str,
    *,
    match_id: int | None = None,
) -> str:
    safe_reason = (reason or "Flagged").replace("⟧", " ").replace("⟦", " ")
    pct = int(round(confidence * 100))
    prefix = f"⟦{flag_type}:"
    if flag_type == "student" and match_id is not None:
        prefix += f"m{match_id}:"
    return f"{prefix}{pct}:{safe_reason}⟧{text}⟦/{flag_type}⟧"


def has_typed_markers(text: str) -> bool:
    return bool(text and _MARKER_OPEN.search(text))


def dedupe_student_flag_dicts(flags: list[dict]) -> list[dict]:
    """Collapse overlapping student flags (no arbitrary cap — dedupe only)."""
    ai_and_other = [f for f in (flags or []) if f.get("type") != "student"]
    student = sorted(
        [f for f in (flags or []) if f.get("type") == "student"],
        key=lambda f: float(f.get("confidence", 0)),
        reverse=True,
    )
    kept: list[dict] = []
    for flag in student:
        text_a = (flag.get("text_a") or flag.get("text") or "").lower()
        text_b = (flag.get("text_b") or "").lower()
        if not text_a and not text_b:
            continue
        overlaps = False
        for existing in kept:
            ea = (existing.get("text_a") or existing.get("text") or "").lower()
            eb = (existing.get("text_b") or "").lower()
            if text_a and ea and (text_a in ea or ea in text_a):
                overlaps = True
                break
            if text_b and eb and (text_b in eb or eb in text_b):
                overlaps = True
                break
        if overlaps:
            continue
        kept.append(dict(flag))
    return [*ai_and_other, *kept]


def ensure_flag_match_ids(flags: list[dict]) -> list[dict]:
    """Assign stable match_id values to student flags for paired UI colours."""
    result: list[dict] = []
    counter = 0
    for flag in flags or []:
        row = dict(flag)
        if row.get("type") == "student":
            counter += 1
            row["match_id"] = counter
        result.append(row)
    return result


def _assign_student_match_ids(flags: list[IntegrityFlag]) -> list[IntegrityFlag]:
    """Number student plagiarism flags so the UI can pair highlights across panes."""
    counter = 0
    for flag in flags:
        if flag.flag_type != "student":
            continue
        counter += 1
        flag.match_id = counter
    return flags


def _student_match_already_marked(text: str, match_id: int) -> bool:
    return bool(re.search(rf"⟦student:m{match_id}:", text or ""))


def apply_flags_to_document(full_text: str, flags: list[dict], *, side: str = "a") -> str:
    """Embed typed markers for UI highlighting. side='a' uses text/text_a, side='b' uses text_b."""
    from app.services.overlap_highlight import (
        anchor_offset,
        excerpt_for_highlight,
        highlight_excerpt_in_document,
    )

    if not full_text or not flags:
        return full_text or ""

    flags = dedupe_student_flag_dicts(flags)
    applicable: list[tuple[str, float, str, str, int | None, int]] = []
    for flag in flags:
        ftype = flag.get("type", "")
        confidence = float(flag.get("confidence", 0))
        reason = str(flag.get("reason") or "Flagged section")
        match_id: int | None = None
        if ftype == "ai":
            snippet = flag.get("text", "")
        elif ftype == "student":
            snippet = flag.get("text_a" if side == "a" else "text_b", "") or flag.get("text", "")
            raw_id = flag.get("match_id")
            match_id = int(raw_id) if raw_id is not None else None
            if match_id is not None and _student_match_already_marked(full_text, match_id):
                continue
        else:
            continue
        snippet = " ".join(str(snippet).split())
        if ftype == "student" and len(snippet.split()) < _MIN_ANCHOR_WORDS:
            continue
        if ftype == "ai" and len(snippet.split()) < 4:
            continue
        offset = 0
        excerpt = excerpt_for_highlight(full_text, snippet)
        if excerpt:
            offset = anchor_offset(full_text, snippet)
            if offset < 0:
                offset = anchor_offset(full_text, excerpt)
        applicable.append((ftype, confidence, reason, excerpt or snippet, match_id, offset))

    applicable.sort(key=lambda row: (row[5], -len(row[3])))
    result = full_text
    applied_student_ids: set[int] = set()
    next_student_id = 0
    for ftype, confidence, reason, target, match_id, _offset in applicable:
        if ftype == "student":
            if match_id is None:
                next_student_id += 1
                match_id = next_student_id
            if match_id in applied_student_ids:
                continue

        marked = highlight_excerpt_in_document(
            result,
            target,
            match_id=match_id if ftype == "student" else None,
            flag_type=ftype,
            confidence=confidence,
            reason=reason,
        )
        if marked == result:
            continue
        result = marked
        if ftype == "student" and match_id is not None:
            applied_student_ids.add(match_id)
    return result


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


def _normalize_for_compare(text: str) -> str:
    return " ".join(strip_markers(text).lower().split())


def _document_similarity(text_a: str, text_b: str) -> float:
    left = _normalize_for_compare(text_a)
    right = _normalize_for_compare(text_b)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    return SequenceMatcher(None, left, right).ratio()


def _split_compare_units(text: str) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paragraphs) > 1:
        return [p for p in paragraphs if len(p.split()) >= 6]

    # Plain-text exports often use single newlines between paragraphs.
    line_blocks: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if current:
                block = " ".join(current)
                if len(block.split()) >= 6:
                    line_blocks.append(block)
                current = []
            continue
        current.append(stripped)
    if current:
        block = " ".join(current)
        if len(block.split()) >= 6:
            line_blocks.append(block)
    if len(line_blocks) > 1:
        return line_blocks

    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sentences if len(s.split()) >= 8]


def _split_comparison_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if len(p.strip().split()) >= _MIN_COMPARISON_SENTENCE_WORDS]


def _merge_sentence_pairs(
    pairs: list[tuple[str, str]],
    *,
    max_words: int = _DIRECT_MERGE_MAX_WORDS,
) -> list[tuple[str, str]]:
    if not pairs:
        return []
    merged: list[tuple[str, str]] = []
    cur_a: list[str] = [pairs[0][0]]
    cur_b: list[str] = [pairs[0][1]]
    word_count = len(pairs[0][0].split())

    for text_a, text_b in pairs[1:]:
        extra = len(text_a.split())
        if word_count + extra > max_words:
            merged.append((" ".join(cur_a), " ".join(cur_b)))
            cur_a, cur_b = [text_a], [text_b]
            word_count = extra
        else:
            cur_a.append(text_a)
            cur_b.append(text_b)
            word_count += extra

    if cur_a:
        merged.append((" ".join(cur_a), " ".join(cur_b)))
    return merged


def _pairs_from_sentence_alignment(
    sents_a: list[str],
    sents_b: list[str],
) -> list[tuple[str, str, float]]:
    """Align sentences in document order; equal runs first, then fuzzy replace pairs."""
    matcher = SequenceMatcher(None, sents_a, sents_b, autojunk=False)
    pairs: list[tuple[str, str, float]] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for idx in range(i1, i2):
                pairs.append((sents_a[idx], sents_b[j1 + (idx - i1)], 1.0))
        elif tag == "replace":
            used_j: set[int] = set()
            for idx in range(i1, i2):
                sa = sents_a[idx]
                best_ratio = 0.0
                best_jdx = -1
                for jdx in range(j1, j2):
                    if jdx in used_j:
                        continue
                    sb = sents_b[jdx]
                    ratio = SequenceMatcher(None, sa.lower(), sb.lower()).ratio()
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_jdx = jdx
                if best_jdx >= 0 and best_ratio >= NEAR_DUPLICATE_UNIT_MIN:
                    used_j.add(best_jdx)
                    pairs.append((sa, sents_b[best_jdx], best_ratio))
    return pairs


def _flags_from_direct_text_comparison(
    clean_a: str,
    clean_b: str,
    *,
    base_confidence: float,
) -> list[IntegrityFlag]:
    """Phase 1: compare raw text directly — sentence alignment, no LLM."""
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
    """Fast path for wholesale copying — accurate confidence and multi-passage flags."""
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
    """Compare two full submissions with on-premise LLM — finds all plagiarism instances."""
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

    prompt = f"""You are an expert plagiarism analyst. Compare these two COMPLETE student submissions.

Pre-screen similarity: {tfidf_hint:.2f} (scale 0-1).

═══ SUBMISSION A ═══
{clean_a[:_MAX_DOC_COMPARE_CHARS]}

═══ SUBMISSION B ═══
{clean_b[:_MAX_DOC_COMPARE_CHARS]}

Find EVERY instance where one student likely copied or paraphrased the other.
Students use paraphrasing, synonym swaps, reordering — not just word-for-word copying.

Return JSON:
{{
  "plagiarism_detected": true or false,
  "overall_confidence": 0.0 to 1.0,
  "status": "confirmed" or "possible" or "none",
  "flags": [
    {{
      "order_in_a": 1,
      "text_a": "exact sentence(s) copied verbatim from submission A (min 6 words)",
      "text_b": "exact corresponding sentence(s) copied verbatim from submission B",
      "confidence": 0.0 to 1.0,
      "reason": "brief reason for teacher"
    }}
  ],
  "explanation": "one sentence summary"
}}

Rules:
- List ALL instances found (up to {_MAX_PAIR_FLAGS}), ordered by order_in_a (1 = earliest in submission A).
- text_a and text_b MUST be copied exactly from the submissions above — complete sentences only.
- Include paraphrased passages with the same ideas/structure.
- Do NOT flag content that appears in only one submission.
- Do NOT invent text. If unsure, omit the flag.
- Each flag needs confidence >= {STUDENT_AI_FLAG_MIN}.
"""

    raw = ollama_client.generate(prompt, system=_INTEGRITY_SYSTEM, temperature=0.05)
    parsed = ollama_client.parse_json_response(raw or "")
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


def _excerpt_around_phrase(text: str, phrase: str, *, radius: int = 100) -> str:
    lower = text.lower()
    idx = lower.find(phrase.lower())
    if idx < 0:
        return text[: min(200, len(text))]
    start = max(0, idx - radius)
    end = min(len(text), idx + len(phrase) + radius)
    return text[start:end].strip()


def score_ai_writing_heuristics(document_text: str) -> tuple[float, list[IntegrityFlag]]:
    """Local pattern-based signals for AI-generated prose (no cloud APIs)."""
    clean = strip_markers(document_text).strip()
    words = clean.split()
    if len(words) < 40:
        return 0.0, []

    lower = clean.lower()
    flags: list[IntegrityFlag] = []
    for phrase, reason in _AI_TELL_PHRASES:
        if phrase not in lower:
            continue
        excerpt = _excerpt_around_phrase(clean, phrase)
        if len(excerpt.split()) < 4:
            continue
        flags.append(
            IntegrityFlag(
                flag_type="ai",
                confidence=0.74,
                reason=reason,
                text=excerpt,
            )
        )

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean) if len(s.split()) >= 5]
    if len(sentences) >= 4:
        starters = [" ".join(s.split()[:3]).lower() for s in sentences]
        starter, count = Counter(starters).most_common(1)[0]
        if count >= 3 and count / len(sentences) >= 0.3:
            sample = next(s for s in sentences if " ".join(s.split()[:3]).lower() == starter)
            flags.append(
                IntegrityFlag(
                    flag_type="ai",
                    confidence=0.76,
                    reason="Repetitive sentence openings typical of templated AI output",
                    text=sample,
                )
            )

    if not flags:
        return 0.0, []

    score = min(0.9, 0.52 + 0.07 * len(flags))
    return score, _dedupe_ai_flags(flags)[:_MAX_AI_FLAGS]


def scan_document_for_ai(document_text: str) -> IntegrityResult:
    """Holistic full-document AI scan — more reliable than small chunk passes alone."""
    clean = strip_markers(document_text).strip()
    if len(clean.split()) < 40:
        return IntegrityResult(
            integrity_type="none",
            confidence=0.0,
            status="none",
            explanation="Document too short for reliable AI detection.",
        )

    prompt = f"""Analyse this COMPLETE student submission for AI-generated writing.

SUBMISSION:
{clean[:_MAX_DOC_COMPARE_CHARS]}

Return JSON:
{{
  "ai_detected": true or false,
  "overall_confidence": 0.0 to 1.0,
  "status": "confirmed" or "possible" or "none",
  "flags": [
    {{
      "text": "exact sentence(s) from the submission that appear AI-written (min 4 words)",
      "confidence": 0.0 to 1.0,
      "reason": "brief reason for teacher"
    }}
  ],
  "explanation": "one sentence summary"
}}

Detection rules:
- Flag writing that reads like ChatGPT/Claude: polished, generic, no first-person project detail,
  formulaic transitions, list-like structure, hedging ("it is important to note"), uniform tone.
- A submission can be MOSTLY or ENTIRELY AI-written — set ai_detected=true if likely.
- Include up to {_MAX_AI_FLAGS} flagged passages with confidence >= {AI_FLAG_MIN}.
- Copy text exactly from the submission for each flag.
- If the submission appears authentically student-written with specific project detail, set ai_detected=false.
"""

    raw = ollama_client.generate(prompt, system=_AI_DETECTION_SYSTEM, temperature=0.05)
    parsed = ollama_client.parse_json_response(raw or "")
    if not parsed:
        return IntegrityResult(
            integrity_type="none",
            confidence=0.0,
            status="none",
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
    status = str(parsed.get("status") or "none").lower()
    if status not in {"confirmed", "possible", "none"}:
        status = "confirmed" if confidence >= AI_CONFIRMED_MIN else "possible"

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
        return IntegrityResult(
            integrity_type="none",
            confidence=confidence,
            status="none",
            explanation=str(parsed.get("explanation") or "No AI-generated passages detected."),
            ai_verified=True,
            detection_method="ai_full_document",
        )

    deduped = _dedupe_ai_flags(flags)
    max_conf = max(confidence, max(f.confidence for f in deduped))
    status = "confirmed" if max_conf >= AI_CONFIRMED_MIN else "possible"
    return IntegrityResult(
        integrity_type="ai",
        confidence=max_conf,
        status=status,
        flags=deduped,
        explanation=str(parsed.get("explanation") or _summarise_flags(deduped, "AI-generated")),
        ai_verified=True,
        detection_method="ai_full_document",
    )


def _dedupe_ai_flags(flags: list[IntegrityFlag]) -> list[IntegrityFlag]:
    seen: list[IntegrityFlag] = []
    for flag in sorted(flags, key=lambda f: f.confidence, reverse=True):
        key_text = (flag.text or "").lower()[:80]
        if not key_text:
            continue
        if any(
            key_text in (existing.text or "").lower()
            or (existing.text or "").lower() in key_text
            for existing in seen
        ):
            continue
        seen.append(flag)
    return seen


def _build_ai_detection_result(
    flags: list[IntegrityFlag],
    *,
    confidence: float,
    ai_verified: bool,
    detection_method: str,
    explanation: str = "",
) -> IntegrityResult:
    deduped = _dedupe_ai_flags(flags)
    if not deduped:
        return IntegrityResult(
            integrity_type="none",
            confidence=0.0,
            status="none",
            explanation=explanation or "No AI-generated passages detected.",
            ai_verified=ai_verified,
            detection_method=detection_method,
        )
    use_document_score = detection_method == "classifier_roberta"
    report_confidence = (
        confidence
        if use_document_score
        else max(confidence, max(f.confidence for f in deduped))
    )
    status = "confirmed" if report_confidence >= AI_CONFIRMED_MIN else "possible"
    if use_document_score and report_confidence >= AI_CLASSIFIER_CONFIRMED:
        status = "confirmed"
    elif use_document_score and report_confidence >= AI_CLASSIFIER_MIN:
        status = "possible"
    return IntegrityResult(
        integrity_type="ai",
        confidence=report_confidence,
        status=status,
        flags=deduped[:_MAX_AI_FLAGS],
        explanation=explanation or _summarise_flags(deduped, "AI-generated"),
        ai_verified=ai_verified,
        detection_method=detection_method,
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
    return _build_ai_detection_result(
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
        return IntegrityResult(
            integrity_type="none",
            confidence=0.0,
            status="none",
            explanation="Document too short for reliable AI detection.",
        )

    classifier_result = _detect_ai_via_classifier(clean)
    if classifier_result is not None:
        return classifier_result

    all_flags: list[IntegrityFlag] = []
    chunk_verified = False
    doc_confidence = 0.0

    full_result = scan_document_for_ai(clean)
    if full_result.integrity_type == "ai" and full_result.confidence >= AI_CONFIRMED_MIN:
        return full_result
    if full_result.integrity_type == "ai":
        all_flags.extend(full_result.flags)
        doc_confidence = full_result.confidence

    chunks = chunk_text(clean, chunk_size=800, overlap=100)[:_MAX_AI_CHUNKS_PER_DOC]
    for idx, chunk in enumerate(chunks):
        prompt = f"""Analyse this student submission excerpt for AI-generated writing.

EXCERPT ({idx + 1}/{len(chunks)}):
{chunk[:_MAX_CHUNK_CHARS]}

Return JSON:
{{
  "ai_detected": true or false,
  "overall_confidence": 0.0 to 1.0,
  "flags": [
    {{
      "text": "exact substring from excerpt that appears AI-written (min 4 words)",
      "confidence": 0.0 to 1.0,
      "reason": "brief reason shown to teacher"
    }}
  ]
}}

Rules:
- Flag passages that sound like ChatGPT/Claude: generic, polished, no personal project detail.
- Include flags with confidence >= {AI_FLAG_MIN}.
- If this excerpt is likely AI-written, set ai_detected=true even if you cannot quote a short substring.
"""
        raw = ollama_client.generate(prompt, system=_AI_DETECTION_SYSTEM, temperature=0.05)
        parsed = ollama_client.parse_json_response(raw or "")
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
        return _build_ai_detection_result(
            all_flags,
            confidence=doc_confidence,
            ai_verified=ai_verified,
            detection_method="ai_scan" if chunk_verified else "ai_full_document",
        )

    if heuristic_score >= AI_HEURISTIC_MIN and heuristic_flags:
        return _build_ai_detection_result(
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
        return IntegrityResult(
            integrity_type="none",
            confidence=0.0,
            status="none",
            explanation="No AI-generated passages detected.",
            ai_verified=True,
            detection_method="ai_scan",
        )

    return IntegrityResult(
        integrity_type="none",
        confidence=0.0,
        status="none",
        explanation="AI model unavailable — AI scan skipped.",
        ai_verified=False,
        detection_method="skipped",
    )


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

    prompt = f"""Statistical pre-screen similarity: {tfidf_score:.2f} (scale 0-1).

Compare these two student excerpts for plagiarism. Students rarely copy word-for-word —
look for paraphrasing, synonym swaps, sentence reordering, shared unusual phrasing,
identical structure with light edits, and idea-level copying.

EXCERPT A:
{clean_a[:_MAX_PAIR_CHARS]}

EXCERPT B:
{clean_b[:_MAX_PAIR_CHARS]}

Return JSON:
{{
  "plagiarism_detected": true or false,
  "overall_confidence": 0.0 to 1.0,
  "status": "confirmed" or "possible" or "none",
  "flags": [
    {{
      "text_a": "full sentence from excerpt A containing the overlap (copy verbatim)",
      "text_b": "full sentence from excerpt B containing the overlap (copy verbatim)",
      "confidence": 0.0 to 1.0,
      "reason": "brief reason (e.g. paraphrased same paragraph, light synonym edits)"
    }}
  ],
  "explanation": "one concise sentence for a teacher"
}}

Rules:
- confirmed: clear copying or paraphrasing with same ideas/structure (confidence >= {STUDENT_AI_CONFIRMED_MIN})
- possible: suspicious similarity but not definitive (confidence >= {STUDENT_AI_FLAG_MIN})
- none: independent original work — prefer this when uncertain
- Only include flags you are confident about (confidence >= {STUDENT_AI_FLAG_MIN}).
- text_a and text_b must each be complete sentences copied exactly from the excerpts (min 8 words).
- Do NOT flag content that is unique to one student.
- Detect subtle paraphrasing, not only identical text.
- Prefer fewer high-quality flags over many weak ones.
"""

    raw = ollama_client.generate(prompt, system=_INTEGRITY_SYSTEM, temperature=0.05)
    parsed = ollama_client.parse_json_response(raw or "")
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


def _dedupe_flags(flags: list[IntegrityFlag]) -> list[IntegrityFlag]:
    ai_flags = [f for f in flags if f.flag_type == "ai"]
    student_flags = [f for f in flags if f.flag_type == "student"]
    return _dedupe_ai_flags(ai_flags) + _assign_student_match_ids(
        _dedupe_student_integrity_flags(student_flags)
    )


def _dedupe_student_integrity_flags(flags: list[IntegrityFlag]) -> list[IntegrityFlag]:
    seen: list[IntegrityFlag] = []
    for flag in sorted(flags, key=lambda f: f.confidence, reverse=True):
        key_text = (flag.text_a or flag.text or "").lower()[:80]
        if any(
            key_text in (existing.text_a or existing.text or "").lower()
            or (existing.text_a or existing.text or "").lower() in key_text
            for existing in seen
        ):
            continue
        seen.append(flag)
    return seen


def _summarise_flags(flags: list[IntegrityFlag], label: str) -> str:
    if not flags:
        return f"No {label} content detected."
    top = max(flags, key=lambda f: f.confidence)
    return (
        f"{label} content detected ({int(top.confidence * 100)}% confidence): {top.reason}"
    )


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
