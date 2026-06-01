import json
import re

from app.ai import ollama_client

LOW_CONFIDENCE_THRESHOLD = 50

QUESTION_SYSTEM = """You assist university lecturers preparing oral assessment questions.
Generate clear, fair questions to verify individual contribution.
Never accuse plagiarism — ask for clarification of personal work.
Return ONLY a JSON array of objects with keys: student, reason, question.
Optional key related_student when overlap involves another student."""


def _template_questions(matches: list[dict], overlaps: list[dict]) -> list[dict]:
    questions: list[dict] = []
    seen: set[str] = set()

    for m in matches:
        if m["suggestion_strength"] >= LOW_CONFIDENCE_THRESHOLD:
            continue
        key = f"{m['student']}:{m['criterion']}"
        if key in seen:
            continue
        seen.add(key)
        questions.append(
            {
                "student": m["student"],
                "criterion": m["criterion"],
                "reason": "low_suggestion_strength",
                "question": (
                    f"Can you walk me through your personal contribution to "
                    f"'{m['criterion']}'? The uploaded evidence was weak or missing."
                ),
                "generated_by": "template",
            }
        )

    for o in overlaps:
        key = f"{o['student_a']}:{o['student_b']}"
        if key in seen:
            continue
        seen.add(key)
        questions.append(
            {
                "student": o["student_a"],
                "related_student": o["student_b"],
                "reason": "textual_overlap",
                "question": (
                    f"Both you and {o['student_b']} submitted very similar text "
                    f"({o['similarity_percent']}% overlap). What was your specific, "
                    f"individual contribution?"
                ),
                "generated_by": "template",
            }
        )

    return questions


def _parse_llm_questions(raw: str) -> list[dict] | None:
    text = raw.strip()
    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        text = match.group(0)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list):
        return None

    out: list[dict] = []
    for item in data:
        if not isinstance(item, dict) or "student" not in item or "question" not in item:
            continue
        out.append(
            {
                "student": item["student"],
                "criterion": item.get("criterion"),
                "related_student": item.get("related_student"),
                "reason": item.get("reason", "llm_generated"),
                "question": item["question"],
                "generated_by": "ollama",
            }
        )
    return out if out else None


def _llm_questions(matches: list[dict], overlaps: list[dict]) -> list[dict] | None:
    context = {
        "weak_evidence": [
            {
                "student": m["student"],
                "criterion": m["criterion"],
                "suggestion_strength": m["suggestion_strength"],
                "quote": m["quote"],
            }
            for m in matches
            if m["suggestion_strength"] < LOW_CONFIDENCE_THRESHOLD
        ],
        "overlaps": overlaps,
    }
    if not context["weak_evidence"] and not context["overlaps"]:
        return []

    user_prompt = (
        "Based on this assessment analysis data, suggest 3-6 oral exam questions.\n"
        f"{json.dumps(context, indent=2)}"
    )
    raw = ollama_client.chat(QUESTION_SYSTEM, user_prompt)
    if not raw:
        return None
    return _parse_llm_questions(raw)


def generate_questions(
    matches: list[dict],
    overlaps: list[dict],
) -> tuple[list[dict], bool]:
    """Returns (questions, used_llm)."""
    if ollama_client.is_available() and ollama_client.model_is_pulled():
        llm_q = _llm_questions(matches, overlaps)
        if llm_q is not None:
            return llm_q, True

    return _template_questions(matches, overlaps), False
