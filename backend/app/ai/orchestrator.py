from collections.abc import Callable

from app.ai import ollama_client
from app.ai.draft_form import build_draft_suggestions
from app.ai.evidence_matcher import match_evidence
from app.ai.llm_batch import generate_student_llm_bundle
from app.ai.overlap_detector import detect_overlaps
from app.ai.question_generator import generate_questions

ProgressCallback = Callable[[str, int], None]


def run_analysis(
    rubric_criteria: list[str],
    students: dict[str, dict],
    *,
    use_batch_llm: bool = True,
    on_progress: ProgressCallback | None = None,
) -> dict:
    """
    students: { name: { "source_file": str, "text": str } }
    """
    with ollama_client.analysis_session():
        return _run_analysis_body(
            rubric_criteria,
            students,
            use_batch_llm=use_batch_llm,
            on_progress=on_progress,
        )


def _run_analysis_body(
    rubric_criteria: list[str],
    students: dict[str, dict],
    *,
    use_batch_llm: bool,
    on_progress: ProgressCallback | None,
) -> dict:
    if on_progress:
        on_progress("Matching evidence to rubric criteria", 12)

    evidence_matches: list[dict] = []
    for criterion in rubric_criteria:
        for name, data in students.items():
            evidence_matches.extend(
                match_evidence(
                    criterion=criterion,
                    student_name=name,
                    source_file=data.get("source_file", "unknown"),
                    text=data.get("text", ""),
                )
            )

    if on_progress:
        on_progress("Checking for overlapping text between students", 28)

    overlaps = detect_overlaps(students)
    used_llm = False
    all_drafts: list[dict] = []
    all_questions: list[dict] = []

    if use_batch_llm and ollama_client.is_available() and ollama_client.model_is_pulled():
        student_names = list(students.keys())
        total = max(len(student_names), 1)
        for idx, name in enumerate(student_names):
            if on_progress:
                pct = 40 + int(45 * (idx + 1) / total)
                on_progress(f"Generating AI suggestions for {name}", pct)
            sm = [m for m in evidence_matches if m["student"] == name]
            drafts, questions, ok = generate_student_llm_bundle(name, sm, overlaps)
            if ok:
                used_llm = True
                all_drafts.extend(drafts)
                all_questions.extend(questions)
        if not all_drafts:
            all_drafts, d_llm = build_draft_suggestions(evidence_matches)
            all_questions, q_llm = generate_questions(evidence_matches, overlaps)
            used_llm = d_llm or q_llm
        elif not all_questions:
            extra_q, _ = generate_questions(evidence_matches, overlaps)
            all_questions = extra_q
    else:
        if on_progress:
            on_progress("Building draft suggestions (local templates)", 55)
        all_drafts, d_llm = build_draft_suggestions(evidence_matches)
        if on_progress:
            on_progress("Generating oral exam questions", 75)
        all_questions, q_llm = generate_questions(evidence_matches, overlaps)
        used_llm = d_llm or q_llm

    if on_progress:
        on_progress("Finalizing assessment results", 92)

    ollama_up = ollama_client.is_available()
    model_ready = ollama_client.model_is_pulled() if ollama_up else False
    processing = "local_tfidf+ollama" if used_llm else "local_tfidf"

    return {
        "disclaimer": "AI suggestions only — teacher decides final assessment.",
        "processing": processing,
        "llm": {
            "enabled": used_llm,
            "ollama_reachable": ollama_up,
            "model_ready": model_ready,
            **ollama_client.get_config(),
            "hint": (
                None
                if model_ready
                else f"Run: ollama pull {ollama_client.OLLAMA_MODEL}"
                if ollama_up
                else "Start Ollama"
            ),
        },
        "evidence_matches": evidence_matches,
        "overlaps": overlaps,
        "draft_suggestions": all_drafts,
        "questions": all_questions,
    }
