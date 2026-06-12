import json
import logging
import re

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_EXCERPT_PREFIX_RE = re.compile(
    r"^\s*(the\s+)?excerpts?\s*#?\s*\d*\s*[:,-]?\s*", re.IGNORECASE
)


def _clean_reason(reason):
    reason = reason.strip()
    cleaned = _EXCERPT_PREFIX_RE.sub("", reason).strip()
    if not cleaned or cleaned == reason:
        return reason
    return cleaned[0].upper() + cleaned[1:]


def _build_prompt(criterion_text, candidates):
    numbered = "\n".join(f"[{label}] {text}" for label, text in candidates)
    return (
        "You help a teacher check whether a student's evidence supports a rubric "
        "criterion. Judge by meaning, not just shared words.\n\n"
        f"Criterion: {criterion_text}\n\n"
        f"Candidate excerpts from the student's work:\n{numbered}\n\n"
        "Pick the single excerpt that best supports the criterion, or none if "
        "none genuinely do. Reply ONLY as JSON: "
        '{"supported": true or false, "best": <excerpt number or null>, '
        '"reason": "<one short sentence in your own words>"}. '
        "Choose a number only from the list. In 'reason', briefly explain your "
        "judgement in your own words; do NOT copy the excerpt text and do NOT "
        "mention excerpt numbers."
    )


def _parse_verdict(raw, valid_labels):
    data = json.loads(raw)
    best = data.get("best")
    try:
        best = int(best)
    except (TypeError, ValueError):
        best = None
    if best not in valid_labels:
        best = None
    supported = bool(data.get("supported")) and best is not None
    reason = _clean_reason(str(data.get("reason") or "").strip()[:500])
    return {
        "supported": supported,
        "best": best if supported else None,
        "reason": reason,
    }


def judge_criterion(criterion_text, candidates):
    if not candidates:
        return None
    valid_labels = {label for label, _ in candidates}
    prompt = _build_prompt(criterion_text, candidates)
    try:
        with httpx.Client(timeout=settings.OLLAMA_TIMEOUT_SECONDS) as client:
            response = client.post(
                f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate",
                json={
                    "model": settings.MATCH_AI_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
            )
            response.raise_for_status()
            raw = (response.json().get("response") or "").strip()
        return _parse_verdict(raw, valid_labels)
    except Exception as exc:
        logger.warning("AI judge unavailable, falling back to text match: %s", exc)
        return None
