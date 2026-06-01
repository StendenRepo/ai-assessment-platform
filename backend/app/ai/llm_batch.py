"""Single batched Ollama call per student for speed (drafts + questions together)."""

from __future__ import annotations

import json
import re

from app.ai import ollama_client

SYSTEM = """You assist university lecturers with group project assessments.
AI suggests only — never final grades. Be concise.
Return ONLY valid JSON with keys:
  "drafts": [{"criterion": str, "suggestion": str, "suggestion_strength": number}],
  "questions": [{"criterion": str|null, "reason": str, "question": str}]
Use suggestion_strength from the input data for each draft."""


def generate_student_llm_bundle(
    student_name: str,
    matches: list[dict],
    overlaps: list[dict],
) -> tuple[list[dict], list[dict], bool]:
    if not (ollama_client.is_available() and ollama_client.model_is_pulled()):
        return [], [], False

    overlap_ctx = [
        o for o in overlaps
        if o.get("student_a") == student_name or o.get("student_b") == student_name
    ]
    user = json.dumps(
        {
            "student": student_name,
            "evidence_matches": matches,
            "overlaps_involving_student": overlap_ctx,
        },
        indent=2,
    )
    raw = ollama_client.chat(SYSTEM, user)
    if not raw:
        return [], [], False

    parsed = _parse_json(raw)
    if not parsed:
        return [], [], False

    drafts = [
        {
            "student": student_name,
            "criterion": d.get("criterion", ""),
            "suggestion_strength": d.get("suggestion_strength", 0),
            "suggestion": d.get("suggestion", ""),
            "generated_by": "ollama",
        }
        for d in parsed.get("drafts", [])
    ]
    questions = [
        {
            "student": student_name,
            "criterion": q.get("criterion"),
            "reason": q.get("reason", "llm_generated"),
            "question": q.get("question", ""),
            "generated_by": "ollama",
        }
        for q in parsed.get("questions", [])
    ]
    return drafts, questions, True


def _parse_json(raw: str) -> dict | None:
    text = raw.strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        text = m.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
