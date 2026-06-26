from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.ai import question_generator
from app.ai.rubric_criteria import extract_criteria
from app.config import settings
from app.models.student import Student
from app.models.teacher import Teacher
from app.services import evidence_match_service
from app.services.assessment_service import get_or_create_for_student

_ORDER = {"gap": 0, "unclear": 1, "covered": 2}


def _basis(covered, best_conf):
    if not covered:
        return "gap"
    if best_conf < settings.MATCH_STRONG_THRESHOLD:
        return "unclear"
    return "covered"


def generate_questions(
    db: Session, *, student_id: str, teacher: Teacher, module_id=None
) -> dict:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found")

    report = evidence_match_service.get_report(
        db, student_id=student_id, teacher=teacher
    )
    if not report["criteria"]:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Run AI matching first so questions can target the rubric coverage.",
        )

    module, rubric = evidence_match_service._resolve_module_and_rubric(
        db, student, teacher, module_id or report["module_id"]
    )
    criteria = extract_criteria(
        evidence_match_service._rubric_path(module, rubric),
        f".{rubric.file_type}" if rubric.file_type else None,
        rubric.extracted_text,
    )
    text_by_key = {c.key: c.text for c in criteria}

    results = []
    for crit in report["criteria"]:
        key = crit["criterion_key"]
        covered = crit["covered"]
        quote = None
        best_conf = 0.0
        if covered and crit["matches"]:
            best = crit["matches"][0]
            quote = best.get("supporting_quote")
            best_conf = best.get("confidence_score") or 0.0
        basis = _basis(covered, best_conf)
        questions = question_generator.suggest_questions(
            text_by_key.get(key, key), quote, basis
        )
        results.append(
            {
                "criterion_key": key,
                "basis": basis,
                "covered": covered,
                "questions": questions,
            }
        )

    results.sort(key=lambda r: _ORDER[r["basis"]])

    payload = {
        "student_id": student_id,
        "module_id": report["module_id"],
        "questions": results,
    }

    assessment = get_or_create_for_student(
        db,
        student_id=student_id,
        teacher=teacher,
        module_id=module_id or report["module_id"],
    )
    if assessment is not None:
        assessment.questions_cache_json = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "module_id": str(report["module_id"]),
            "questions": results,
        }
        db.commit()

    return payload
