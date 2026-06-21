"""Text normalisation, sentence/paragraph chunking and similarity helpers."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from app.services.overlap.integrity.markers import strip_markers
from app.services.overlap.integrity.thresholds import (
    _DIRECT_MERGE_MAX_WORDS,
    _MIN_COMPARISON_SENTENCE_WORDS,
    NEAR_DUPLICATE_UNIT_MIN,
)


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


def _excerpt_around_phrase(text: str, phrase: str, *, radius: int = 100) -> str:
    lower = text.lower()
    idx = lower.find(phrase.lower())
    if idx < 0:
        return text[: min(200, len(text))]
    start = max(0, idx - radius)
    end = min(len(text), idx + len(phrase) + radius)
    return text[start:end].strip()
