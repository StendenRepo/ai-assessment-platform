import logging

from app.ai import ollama_client

logger = logging.getLogger(__name__)

DRAFT_SYSTEM = """You assist university lecturers assessing group projects.
You provide draft assessment suggestions only — never final grades or pass/fail.
The teacher has full authority. Be concise (2-3 sentences per criterion).
Only use the evidence quotes provided; do not invent facts."""


def _template_draft(m: dict) -> str:
    strength = m["suggestion_strength"]
    return (
        f"Based on evidence in {m['source_file']}, the student appears to "
        f"address '{m['criterion']}'. Supporting excerpt: \"{m['quote']}\" "
        f"(suggestion strength {strength}% — not a grade)."
    )


def _llm_drafts_for_student(student: str, matches: list[dict]) -> dict[str, str]:
    lines = [f"Student: {student}\n"]
    for m in matches:
        lines.append(
            f"Criterion: {m['criterion']}\n"
            f"Suggestion strength: {m['suggestion_strength']}% (not a grade)\n"
            f"Source file: {m['source_file']}\n"
            f"Evidence quote: \"{m['quote']}\"\n"
        )
    user_prompt = (
        "".join(lines)
        + "\nFor each criterion, write a short draft assessment suggestion "
        "paragraph. Format exactly as:\n"
        "## Criterion Name\nYour suggestion here.\n"
        "Use the same criterion names as above."
    )

    raw = ollama_client.chat(DRAFT_SYSTEM, user_prompt)
    if not raw:
        return {}

    parsed: dict[str, str] = {}
    current_criterion: str | None = None
    buffer: list[str] = []

    for line in raw.splitlines():
        if line.startswith("## "):
            if current_criterion and buffer:
                parsed[current_criterion] = " ".join(buffer).strip()
            current_criterion = line[3:].strip()
            buffer = []
        elif current_criterion:
            buffer.append(line.strip())

    if current_criterion and buffer:
        parsed[current_criterion] = " ".join(buffer).strip()

    expected = {m["criterion"] for m in matches}
    missing = expected - set(parsed.keys())
    if missing:
        logger.warning(
            "Ollama draft parse missing criteria for %s: %s",
            student,
            ", ".join(sorted(missing)),
        )

    return parsed


def build_draft_suggestions(matches: list[dict]) -> tuple[list[dict], bool]:
    """Returns (drafts, used_llm)."""
    by_student: dict[str, list[dict]] = {}
    for m in matches:
        by_student.setdefault(m["student"], []).append(m)

    llm_by_student: dict[str, dict[str, str]] = {}
    used_llm = False

    if ollama_client.is_available() and ollama_client.model_is_pulled():
        for student, student_matches in by_student.items():
            parsed = _llm_drafts_for_student(student, student_matches)
            if parsed:
                llm_by_student[student] = parsed
                used_llm = True

    drafts: list[dict] = []
    for m in matches:
        suggestion = _template_draft(m)
        source = "template"
        student_llm = llm_by_student.get(m["student"], {})
        if m["criterion"] in student_llm:
            suggestion = student_llm[m["criterion"]]
            source = "ollama"

        drafts.append(
            {
                "student": m["student"],
                "criterion": m["criterion"],
                "suggestion_strength": m["suggestion_strength"],
                "suggestion": suggestion,
                "generated_by": source,
            }
        )

    return drafts, used_llm
