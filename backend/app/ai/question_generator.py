import json
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_FALLBACKS = {
    "gap": [
        "Your submission does not seem to cover this. Can you explain how you addressed it, or how you would?",
        "What could you add to demonstrate that you meet this criterion?",
    ],
    "unclear": [
        "Can you expand on how your work meets this criterion?",
        "Which part of your evidence best supports this, and why?",
    ],
    "covered": [
        "Can you walk me through how you achieved this?",
    ],
}


def _build_prompt(criterion_text, quote, basis):
    if basis == "gap":
        context = "The student's submitted work shows NO clear evidence for this criterion."
    elif basis == "unclear":
        context = (
            "The student's evidence only weakly addresses it. Relevant excerpt: "
            f'"{quote}".'
        )
    else:
        context = (
            "The student's evidence appears to address it. Relevant excerpt: "
            f'"{quote}".'
        )
    count = 1 if basis == "covered" else 2
    return (
        "You help a teacher prepare for an oral assessment with a student.\n"
        f"Criterion: {criterion_text}\n"
        f"{context}\n"
        f"Suggest {count} short, specific questions the teacher can ask the "
        "student to check whether they genuinely meet this criterion. Keep each "
        "question under 25 words. Do NOT assign grades. Reply ONLY as a JSON "
        'array of question strings, e.g. ["...", "..."]'
    )


def _parse_questions(raw):
    try:
        data = json.loads(raw)
    except Exception:
        return []
    items = None
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list):
                items = value
                break
    if not items:
        return []
    out = []
    for question in items:
        if isinstance(question, str):
            text = question.strip()
            if text:
                out.append(text[:300])
    return out[:3]


def suggest_questions(criterion_text, quote, basis, model=None):
    prompt = _build_prompt(criterion_text, quote, basis)
    try:
        with httpx.Client(timeout=settings.OLLAMA_TIMEOUT_SECONDS) as client:
            response = client.post(
                f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate",
                json={
                    "model": model or settings.MATCH_AI_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
            )
            response.raise_for_status()
            raw = (response.json().get("response") or "").strip()
        parsed = _parse_questions(raw)
        return parsed or list(_FALLBACKS[basis])
    except Exception as exc:
        logger.warning("question generator unavailable, using fallback: %s", exc)
        return list(_FALLBACKS[basis])
