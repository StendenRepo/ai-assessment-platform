"""Local, pattern-based heuristics for spotting AI-generated prose (no cloud APIs)."""

from __future__ import annotations

import re
from collections import Counter

from app.services.overlap.integrity.aggregation import _dedupe_ai_flags
from app.services.overlap.markers import strip_markers
from app.services.overlap.integrity.models import IntegrityFlag
from app.services.overlap.integrity.text import _excerpt_around_phrase
from app.services.overlap.integrity.thresholds import _MAX_AI_FLAGS

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
