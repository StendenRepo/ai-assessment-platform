"""Typed marker handling: embed/strip the UI highlight markers in documents."""

from __future__ import annotations

import re

from app.services.overlap.integrity.thresholds import (
    _MIN_ANCHOR_WORDS,
)

_MARKER_OPEN = re.compile(
    r"⟦(ai|student):(?:m(\d+):)?(\d+):([^⟧]*)⟧(.*?)⟦/\1⟧",
    re.DOTALL,
)
_LEGACY_MARKER_RE = re.compile(r"\[\[(.*?)\]\]", re.DOTALL)


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
    """Collapse overlapping student flags (no arbitrary cap - dedupe only)."""
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


def _student_match_already_marked(text: str, match_id: int) -> bool:
    return bool(re.search(rf"⟦student:m{match_id}:", text or ""))


def apply_flags_to_document(full_text: str, flags: list[dict], *, side: str = "a") -> str:
    """Embed typed markers for UI highlighting. side='a' uses text/text_a, side='b' uses text_b."""
    from app.services.overlap.highlight import (
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
