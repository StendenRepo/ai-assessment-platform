"""Document highlighting: sentence boundaries, chronological match order, paired spans."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Callable, Iterable, Optional

from app.services.overlap.integrity import (
    _wrap_flag,
    dedupe_student_flag_dicts,
    strip_markers,
)

_MIN_ANCHOR_WORDS = 4
_MIN_PARTIAL_WINDOW = 10
_MIN_HIGHLIGHT_WORDS = 4
_MIN_PAIR_JACCARD = 0.22
_MIN_PAIR_SEQUENCE_RATIO = 0.38

_TYPED_MARKER_BLOCK_RE = re.compile(
    r"(⟦(?:ai|student):[^⟧]*⟧[\s\S]*?⟦/(?:ai|student)⟧)",
    re.DOTALL,
)

_UNICODE_NORMALIZATIONS = (
    ("\u2018", "'"),
    ("\u2019", "'"),
    ("\u201c", '"'),
    ("\u201d", '"'),
    ("\u2013", "-"),
    ("\u2014", "-"),
    ("\u00a0", " "),
)


def _normalize_match_text(text: str) -> str:
    """Normalize unicode punctuation and whitespace for resilient anchoring."""
    if not text:
        return ""
    for old, new in _UNICODE_NORMALIZATIONS:
        text = text.replace(old, new)
    return " ".join(text.split())


def _flex_pattern(snippet: str) -> re.Pattern[str]:
    words = [re.escape(w) for w in _normalize_match_text(snippet).split() if w]
    if not words:
        return re.compile(r"a^")
    return re.compile(r"\s+".join(words), re.IGNORECASE | re.DOTALL)


def _expand_span_to_sentences(text: str, start: int, end: int) -> tuple[int, int]:
    """Expand a character span to full sentence boundaries (and paragraph edges)."""
    para_before = text.rfind("\n\n", 0, start)
    sent_begin = para_before + 2 if para_before >= 0 else 0
    for m in re.finditer(r"[.!?](?:\s+|$)", text[:start]):
        if m.end() > sent_begin:
            sent_begin = m.end()

    para_after = text.find("\n\n", end)
    sent_end = para_after if para_after >= 0 else len(text)
    for m in re.finditer(r"[.!?](?:\s+|$)", text[end:sent_end]):
        sent_end = end + m.end()
        break

    sent_begin = max(0, min(sent_begin, len(text)))
    sent_end = max(sent_begin, min(sent_end, len(text)))
    return sent_begin, sent_end


def _ranges_overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _substitute_plain_segments(
    text: str,
    pattern: re.Pattern[str],
    repl: Callable[[re.Match[str]], str],
    *,
    count: int = 1,
) -> str:
    """Apply substitution only outside existing typed markers (no nested markers)."""
    if not text or count <= 0:
        return text or ""

    parts = _TYPED_MARKER_BLOCK_RE.split(text)
    applied = 0
    rebuilt: list[str] = []
    for part in parts:
        if applied >= count:
            rebuilt.append(part)
            continue
        if part.startswith("⟦"):
            rebuilt.append(part)
            continue
        new_part, n = pattern.subn(repl, part, count=count - applied)
        applied += n
        rebuilt.append(new_part)
    return "".join(rebuilt)


def _locate_snippet(clean: str, snippet: str) -> Optional[tuple[int, int]]:
    """Find snippet in clean text; exact substring first, then flexible whitespace."""
    snippet = snippet.strip()
    if not clean or not snippet:
        return None

    idx = clean.find(snippet)
    if idx >= 0:
        return idx, idx + len(snippet)

    match = _flex_pattern(snippet).search(clean)
    if match:
        return match.start(), match.end()

    norm_clean = _normalize_match_text(clean)
    norm_match = _flex_pattern(snippet).search(norm_clean)
    if not norm_match:
        return None

    words = _normalize_match_text(snippet).split()
    for window in (min(16, len(words)), 12, 8, _MIN_ANCHOR_WORDS):
        if len(words) < window:
            continue
        head = " ".join(words[:window])
        tail = " ".join(words[-window:])
        start_m = _flex_pattern(head).search(clean)
        if not start_m:
            continue
        end_m = _flex_pattern(tail).search(clean, start_m.start())
        if end_m:
            return start_m.start(), end_m.end()
        return start_m.start(), min(len(clean), start_m.start() + len(snippet) + 80)
    return None


def find_anchor_span(
    clean_text: str,
    phrase: str,
    *,
    occupied: Optional[list[tuple[int, int]]] = None,
) -> Optional[tuple[int, int]]:
    """Find the topmost phrase occurrence; prefer exact match, then long word windows only."""
    if not clean_text or not phrase:
        return None
    candidate = _normalize_match_text(phrase)
    if len(candidate.split()) < _MIN_ANCHOR_WORDS:
        return None

    occupied = occupied or []

    def _usable(span: tuple[int, int]) -> bool:
        return not any(_ranges_overlap(span, used) for used in occupied)

    located = _locate_snippet(clean_text, phrase)
    if located and _usable(located):
        return located

    words = candidate.split()
    best: Optional[tuple[int, int]] = None
    for window in (16, 14, 12, _MIN_PARTIAL_WINDOW):
        if len(words) < window:
            continue
        for start in range(0, len(words) - window + 1):
            partial = " ".join(words[start : start + window])
            m = _flex_pattern(partial).search(clean_text)
            if not m:
                continue
            span = (m.start(), m.end())
            if not _usable(span):
                continue
            if best is None or m.start() < best[0]:
                best = span
        if best:
            return best
    return None


def excerpt_for_highlight(
    full_text: str,
    phrase: str,
    *,
    occupied: Optional[list[tuple[int, int]]] = None,
    expand_sentences: bool = True,
) -> Optional[str]:
    """Return text to highlight: flag/paragraph snippets stay tight; short phrases expand to sentences."""
    clean = strip_markers(full_text)
    phrase = (phrase or "").strip()
    if not phrase:
        return None

    anchor = _locate_snippet(clean, phrase) or find_anchor_span(clean, phrase, occupied=occupied)
    if not anchor:
        return None

    word_count = len(_normalize_match_text(phrase).split())
    if word_count >= 12 and not expand_sentences:
        start, end = anchor
    elif word_count >= 20:
        # Paragraph-level near-duplicate flags: highlight the matched block, do not bleed forward.
        start, end = anchor
    else:
        start, end = _expand_span_to_sentences(clean, anchor[0], anchor[1])

    if occupied and any(_ranges_overlap((start, end), used) for used in occupied):
        return None
    excerpt = clean[start:end].strip()
    if len(excerpt.split()) < _MIN_HIGHLIGHT_WORDS:
        return None
    return excerpt


def anchor_offset(full_text: str, phrase: str) -> int:
    clean = strip_markers(full_text)
    located = _locate_snippet(clean, phrase) or find_anchor_span(clean, phrase)
    if not located:
        return -1
    return located[0]


def _span_in_clean_text(full_text: str, excerpt: str) -> Optional[tuple[int, int]]:
    clean = strip_markers(full_text)
    return _locate_snippet(clean, excerpt)


def passages_plausibly_paired(excerpt_a: str, excerpt_b: str) -> bool:
    """Algorithmic check that two excerpts are related (no LLM required)."""
    if not excerpt_a or not excerpt_b:
        return False
    tokens_a = set(re.findall(r"[a-z0-9]+", excerpt_a.lower()))
    tokens_b = set(re.findall(r"[a-z0-9]+", excerpt_b.lower()))
    tokens_a -= {"the", "a", "an", "and", "or", "to", "of", "in", "is", "it", "for", "on", "with"}
    tokens_b -= {"the", "a", "an", "and", "or", "to", "of", "in", "is", "it", "for", "on", "with"}
    if len(tokens_a) < 4 or len(tokens_b) < 4:
        return False
    union = tokens_a | tokens_b
    jaccard = len(tokens_a & tokens_b) / len(union) if union else 0.0
    if jaccard < _MIN_PAIR_JACCARD:
        return False
    ratio = SequenceMatcher(None, excerpt_a.lower(), excerpt_b.lower()).ratio()
    return ratio >= _MIN_PAIR_SEQUENCE_RATIO


def phrase_locatable_in_text(full_text: str, phrase: Optional[str]) -> bool:
    return excerpt_for_highlight(full_text, phrase or "") is not None


def highlight_excerpt_in_document(
    full_text: str,
    excerpt: str,
    *,
    match_id: Optional[int] = None,
    flag_type: str = "student",
    confidence: float = 0.85,
    reason: str = "Matching passage",
) -> str:
    if not full_text or not excerpt:
        return full_text or ""
    if match_id is not None and re.search(rf"⟦{flag_type}:m{match_id}:", full_text):
        return full_text

    clean = strip_markers(full_text)
    located = _locate_snippet(clean, excerpt)
    if not located:
        return full_text
    exact = clean[located[0] : located[1]]
    pattern = re.compile(re.escape(exact), re.DOTALL)

    def _repl(m: re.Match[str], ft=flag_type, c=confidence, r=reason, mid=match_id) -> str:
        return _wrap_flag(ft, c, r, m.group(0), match_id=mid)

    return _substitute_plain_segments(full_text, pattern, _repl, count=1)


def highlight_phrase_in_document(
    full_text: str,
    phrase: Optional[str],
    *,
    match_id: Optional[int] = None,
    confidence: float = 0.85,
    reason: str = "Matching passage",
) -> str:
    excerpt = excerpt_for_highlight(full_text, phrase or "")
    if not excerpt:
        return full_text or ""
    return highlight_excerpt_in_document(
        full_text,
        excerpt,
        match_id=match_id,
        confidence=confidence,
        reason=reason,
    )


def highlight_phrases_in_document(
    full_text: str,
    phrases: Iterable[str],
    *,
    confidence: float = 0.85,
) -> str:
    """Apply multiple phrase highlights to one document in top-to-bottom order."""
    if not full_text:
        return full_text or ""

    occupied: list[tuple[int, int]] = []
    ranked: list[tuple[int, str]] = []
    seen: set[str] = set()

    for phrase in phrases:
        key = _normalize_match_text(phrase).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        excerpt = excerpt_for_highlight(full_text, phrase, occupied=occupied)
        if not excerpt:
            continue
        offset = anchor_offset(full_text, phrase)
        if offset < 0:
            continue
        ranked.append((offset, excerpt))

    ranked.sort(key=lambda row: row[0])
    doc = full_text
    match_id = 0
    for _offset, excerpt in ranked:
        span = _span_in_clean_text(doc, excerpt)
        if not span:
            continue
        match_id += 1
        new_doc = highlight_excerpt_in_document(
            doc,
            excerpt,
            match_id=match_id,
            confidence=confidence,
            reason=f"Match {match_id} — shared or paraphrased passage",
        )
        marker = f"⟦student:m{match_id}:"
        if marker not in new_doc:
            continue
        doc = new_doc
        occupied.append(span)

    return compress_student_marker_ids(doc, doc)[0]


def _resolve_excerpt(full_text: str, snippet: str) -> Optional[str]:
    """Locate snippet in document; keep paragraph flags tight, expand short phrases to sentences."""
    if not full_text or not snippet:
        return None
    word_count = len(_normalize_match_text(snippet).split())
    if word_count >= 12:
        tight = excerpt_for_highlight(full_text, snippet, expand_sentences=False)
        if tight:
            return tight
    excerpt = excerpt_for_highlight(full_text, snippet)
    if excerpt:
        return excerpt
    clean = strip_markers(full_text)
    located = _locate_snippet(clean, snippet)
    if not located:
        return None
    start, end = _expand_span_to_sentences(clean, located[0], located[1])
    text = clean[start:end].strip()
    if len(text.split()) < _MIN_HIGHLIGHT_WORDS:
        return None
    return text


_STUDENT_MARKER_ID_RE = re.compile(r"⟦student:m(\d+):")


def compress_student_marker_ids(doc_a: str, doc_b: str) -> tuple[str, str]:
    """Renumber student markers 1..N by top-to-bottom order in doc_a (both panes)."""
    if not doc_a:
        return doc_a or "", doc_b or ""

    order: list[int] = []
    for match in _STUDENT_MARKER_ID_RE.finditer(doc_a):
        marker_id = int(match.group(1))
        if marker_id not in order:
            order.append(marker_id)

    if not order or order == list(range(1, len(order) + 1)):
        return doc_a, doc_b

    id_map = {old: new for new, old in enumerate(order, start=1)}

    def rewrite(text: str) -> str:
        if not text:
            return text

        def repl(marker_match: re.Match[str]) -> str:
            old = int(marker_match.group(1))
            new = id_map.get(old, old)
            return f"⟦student:m{new}:"

        return _STUDENT_MARKER_ID_RE.sub(repl, text)

    return rewrite(doc_a), rewrite(doc_b)


def _build_pair_candidates(
    full_a: str,
    full_b: str,
    student_flags: list[dict],
) -> list[tuple[dict, str, str, int]]:
    candidates: list[tuple[dict, str, str, int]] = []

    for flag in student_flags:
        snippet_a = flag.get("text_a") or flag.get("text") or ""
        snippet_b = flag.get("text_b") or flag.get("text") or ""
        excerpt_a = _resolve_excerpt(full_a, snippet_a)
        excerpt_b = _resolve_excerpt(full_b, snippet_b)
        if not excerpt_a or not excerpt_b:
            continue
        offset_a = anchor_offset(full_a, snippet_a)
        if offset_a < 0:
            offset_a = anchor_offset(full_a, excerpt_a)
        if offset_a < 0:
            continue
        clean_a = strip_markers(full_a)
        clean_b = strip_markers(full_b)
        if not _locate_snippet(clean_a, excerpt_a):
            continue
        if not _locate_snippet(clean_b, excerpt_b):
            continue
        candidates.append((flag, excerpt_a, excerpt_b, offset_a))

    candidates.sort(key=lambda row: row[3])
    return candidates


def _apply_confirmed_pairs(
    full_a: str,
    full_b: str,
    pairs: list[tuple[dict, str, str, int]],
) -> tuple[str, str, list[dict]]:
    """Highlight pairs with sequential IDs; drop any pair that fails on either side."""
    remaining = list(pairs)
    while remaining:
        doc_a, doc_b = full_a, full_b
        for match_id in range(len(remaining), 0, -1):
            flag, excerpt_a, excerpt_b, _offset = remaining[match_id - 1]
            confidence = float(flag.get("confidence", 0.85))
            reason = str(flag.get("reason") or f"Match {match_id}")
            doc_a = highlight_excerpt_in_document(
                doc_a, excerpt_a, match_id=match_id, confidence=confidence, reason=reason
            )
            doc_b = highlight_excerpt_in_document(
                doc_b, excerpt_b, match_id=match_id, confidence=confidence, reason=reason
            )

        failed_index: int | None = None
        for index in range(len(remaining)):
            match_id = index + 1
            marker = f"⟦student:m{match_id}:"
            if marker not in doc_a or marker not in doc_b:
                failed_index = index
                break

        if failed_index is None:
            paired_flags: list[dict] = []
            for match_id, (flag, excerpt_a, excerpt_b, _offset) in enumerate(remaining, start=1):
                paired_flags.append(
                    {
                        **dict(flag),
                        "type": "student",
                        "match_id": match_id,
                        "text_a": excerpt_a,
                        "text_b": excerpt_b,
                    }
                )
            doc_a, doc_b = compress_student_marker_ids(doc_a, doc_b)
            for index, row in enumerate(paired_flags, start=1):
                row["match_id"] = index
            return doc_a, doc_b, paired_flags

        remaining.pop(failed_index)

    return full_a, full_b, []


def apply_paired_student_highlights(
    full_a: str,
    full_b: str,
    flags: list[dict],
) -> tuple[str, str, list[dict]]:
    """Highlight student pairs in strict top-to-bottom order (1, 2, 3 — no gaps)."""
    flags = dedupe_student_flag_dicts(flags)
    student_flags = [f for f in flags if f.get("type") == "student"]
    other_flags = [f for f in flags if f.get("type") != "student"]

    if not student_flags:
        return full_a, full_b, list(flags)

    candidates = _build_pair_candidates(full_a, full_b, student_flags)
    doc_a, doc_b, paired_flags = _apply_confirmed_pairs(full_a, full_b, candidates)
    return doc_a, doc_b, other_flags + paired_flags


def highlight_phrases_paired(full_a: str, full_b: str, phrases: Iterable[str]) -> tuple[str, str]:
    """Legacy TF-IDF phrases: chronological order, full sentences, paired only."""
    if not full_a or not full_b:
        return full_a or "", full_b or ""

    ranked: list[tuple[int, str, str, str]] = []
    seen: set[str] = set()
    occupied_a: list[tuple[int, int]] = []
    occupied_b: list[tuple[int, int]] = []

    for phrase in phrases:
        key = _normalize_match_text(phrase).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        excerpt_a = excerpt_for_highlight(full_a, phrase, occupied=occupied_a)
        excerpt_b = excerpt_for_highlight(full_b, phrase, occupied=occupied_b)
        if not excerpt_a or not excerpt_b:
            continue
        if not passages_plausibly_paired(excerpt_a, excerpt_b):
            continue
        offset = anchor_offset(full_a, phrase)
        if offset < 0:
            continue
        span_a = _span_in_clean_text(full_a, excerpt_a)
        span_b = _span_in_clean_text(full_b, excerpt_b)
        if not span_a or not span_b:
            continue
        ranked.append((offset, phrase, excerpt_a, excerpt_b))
        occupied_a.append(span_a)
        occupied_b.append(span_b)

    ranked.sort(key=lambda row: row[0])
    doc_a, doc_b = full_a, full_b
    confirmed: list[tuple[str, str]] = []
    for _offset, _phrase, excerpt_a, excerpt_b in ranked:
        match_id = len(confirmed) + 1
        reason = f"Match {match_id} — shared or paraphrased passage"
        new_a = highlight_excerpt_in_document(doc_a, excerpt_a, match_id=match_id, reason=reason)
        new_b = highlight_excerpt_in_document(doc_b, excerpt_b, match_id=match_id, reason=reason)
        marker = f"⟦student:m{match_id}:"
        if marker not in new_a or marker not in new_b:
            continue
        doc_a, doc_b = new_a, new_b
        confirmed.append((excerpt_a, excerpt_b))

    doc_a, doc_b = compress_student_marker_ids(doc_a, doc_b)
    return doc_a, doc_b
