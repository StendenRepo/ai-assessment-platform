from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher, get_db
from app.models.teacher import Teacher
from app.schemas.rubric_score import RubricScoreOut
from app.services import rubric_scoring_service

router = APIRouter()


def _out(entry) -> RubricScoreOut:
    return RubricScoreOut(
        rubric_id=entry.rubric_id,
        rubric_name=entry.rubric.name if entry.rubric else None,
        weight=entry.rubric.weight if entry.rubric else None,
        score=entry.score,
        grade=entry.grade,
        generated_at=entry.generated_at,
    )


@router.post(
    "/{student_id}/rubric-scores/{rubric_id}",
    response_model=RubricScoreOut,
    summary="Score one rubric for a student",
)
def generate_rubric_score(
    student_id: str,
    rubric_id: str,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    return _out(
        rubric_scoring_service.generate_rubric_score(
            db, student_id=student_id, teacher=teacher, rubric_id=rubric_id
        )
    )


@router.get(
    "/{student_id}/rubric-scores",
    response_model=list[RubricScoreOut],
    summary="List the per-rubric scores for a student",
)
def list_rubric_scores(
    student_id: str,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    return [
        _out(s)
        for s in rubric_scoring_service.list_rubric_scores(
            db, student_id=student_id, teacher=teacher
        )
    ]
