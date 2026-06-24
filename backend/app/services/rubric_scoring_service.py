from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.ai.rubric_criteria import extract_criteria
from app.models.assessment import Assessment
from app.models.evidence import Evidence
from app.models.module import Module
from app.models.module_rubric import ModuleRubric
from app.models.rubric_score import RubricScore
from app.models.student import Student
from app.models.teacher import Teacher
from app.services import assessment_service, module_service
from app.services.assessment_draft_core import (
    _llm_assess_criterion,
    _recording_context,
    _score_to_grade,
)
from app.services.evidence_matcher import match_criterion_to_evidence

_MAX_SCORE = 10


def _resolve_rubric(db: Session, rubric_id, teacher: Teacher) -> ModuleRubric:
    rubric = db.get(ModuleRubric, rubric_id)
    if rubric is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rubric not found")
    module = db.get(Module, rubric.module_id)
    if module is None or (
        not getattr(teacher, "is_admin", False) and module.teacher_id != teacher.id
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rubric not found")
    return rubric


def _rubric_criteria(rubric: ModuleRubric):
    record = rubric.file
    if record is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Rubric file is missing."
        )
    path = module_service.RUBRIC_UPLOAD_DIR / str(rubric.module_id) / record.path
    ext = f".{record.file_type}" if record.file_type else None
    criteria = extract_criteria(path, ext, record.extracted_text)
    if not criteria:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Could not read any criteria from this rubric.",
        )
    return criteria


def generate_rubric_score(
    db: Session, *, student_id: str, teacher: Teacher, rubric_id
) -> RubricScore:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found")

    rubric = _resolve_rubric(db, rubric_id, teacher)
    criteria = _rubric_criteria(rubric)
    rubric_text = (rubric.file.extracted_text or "") if rubric.file else ""

    assessment = assessment_service.get_or_create_for_student(
        db, student_id=student_id, teacher=teacher, module_id=rubric.module_id
    )

    evidence_rows = (
        db.query(Evidence)
        .filter(Evidence.student_id == student_id)
        .order_by(Evidence.uploaded_at.desc())
        .all()
    )
    recording_text = _recording_context(db, assessment.id)

    scores: list[float] = []
    for c in criteria:
        d = {
            "key": c.key,
            "name": c.key,
            "description": c.text,
            "max_score": _MAX_SCORE,
        }
        matches = match_criterion_to_evidence(c.key, c.key, c.text, evidence_rows)
        suggestion = _llm_assess_criterion(d, matches, rubric_text, recording_text)
        if suggestion.get("score") is not None:
            scores.append(float(suggestion["score"]))

    overall = round(sum(scores) / len(scores), 2) if scores else None
    grade = _score_to_grade(overall, _MAX_SCORE) if overall is not None else None

    entry = (
        db.query(RubricScore)
        .filter(
            RubricScore.assessment_id == assessment.id,
            RubricScore.rubric_id == rubric.id,
        )
        .first()
    )
    if entry is None:
        entry = RubricScore(assessment_id=assessment.id, rubric_id=rubric.id)
        db.add(entry)
    entry.score = overall
    entry.grade = grade
    entry.generated_at = datetime.utcnow()
    db.commit()
    db.refresh(entry)
    return entry


def list_rubric_scores(db: Session, *, student_id: str, teacher: Teacher):
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found")
    assessment = (
        db.query(Assessment)
        .filter_by(student_id=student_id, teacher_id=teacher.id)
        .order_by(Assessment.created_at.desc())
        .first()
    )
    if assessment is None:
        return []
    return (
        db.query(RubricScore)
        .filter(RubricScore.assessment_id == assessment.id)
        .all()
    )


def effective_score(entry: RubricScore) -> float | None:
    if entry.teacher_score is not None:
        return entry.teacher_score
    return entry.score


def effective_grade(entry: RubricScore) -> str | None:
    eff = effective_score(entry)
    return _score_to_grade(eff, _MAX_SCORE) if eff is not None else None


def override_rubric_score(
    db: Session, *, student_id: str, teacher: Teacher, rubric_id, score: float | None
) -> RubricScore:
    if score is not None and (score < 0 or score > _MAX_SCORE):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Score must be between 0 and {_MAX_SCORE}",
        )
    rubric = _resolve_rubric(db, rubric_id, teacher)
    assessment = (
        db.query(Assessment)
        .filter_by(student_id=student_id, teacher_id=teacher.id)
        .order_by(Assessment.created_at.desc())
        .first()
    )
    entry = (
        db.query(RubricScore)
        .filter(
            RubricScore.assessment_id == assessment.id if assessment else False,
            RubricScore.rubric_id == rubric.id,
        )
        .first()
        if assessment
        else None
    )
    if entry is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Score this rubric before overriding it"
        )
    entry.teacher_score = score
    db.commit()
    db.refresh(entry)
    return entry


def compute_final_grade(db: Session, *, assessment: Assessment) -> dict | None:
    rows = (
        db.query(RubricScore, ModuleRubric)
        .join(ModuleRubric, RubricScore.rubric_id == ModuleRubric.id)
        .filter(RubricScore.assessment_id == assessment.id)
        .all()
    )
    components = []
    weighted_sum = 0.0
    total_weight = 0.0
    for score_row, rubric in rows:
        eff = effective_score(score_row)
        components.append(
            {
                "rubric_id": rubric.id,
                "rubric_name": rubric.name,
                "weight": rubric.weight,
                "score": eff,
                "grade": effective_grade(score_row),
            }
        )
        if eff is not None and rubric.weight:
            weighted_sum += float(eff) * float(rubric.weight)
            total_weight += float(rubric.weight)

    if total_weight <= 0:
        return None

    final_score = round(weighted_sum / total_weight, 2)
    return {
        "score": final_score,
        "grade": _score_to_grade(final_score, _MAX_SCORE),
        "total_weight": round(total_weight, 4),
        "components": components,
    }


def final_grade_for_student(
    db: Session, *, student_id: str, teacher: Teacher
) -> dict | None:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found")
    assessment = (
        db.query(Assessment)
        .filter_by(student_id=student_id, teacher_id=teacher.id)
        .order_by(Assessment.created_at.desc())
        .first()
    )
    if assessment is None:
        return None
    return compute_final_grade(db, assessment=assessment)
