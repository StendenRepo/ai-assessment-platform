from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher, get_db
from app.models.teacher import Teacher
from app.schemas.assessment_questions import (
    AssessmentQuestionsReport,
    GenerateQuestionsRequest,
)
from app.services import assessment_questions_service

router = APIRouter()


@router.post(
    "/{student_id}/assessment-questions",
    response_model=AssessmentQuestionsReport,
    summary="Suggest questions to ask the student, targeting rubric gaps",
)
def generate_assessment_questions(
    student_id: str,
    payload: GenerateQuestionsRequest = Body(default=GenerateQuestionsRequest()),
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    return assessment_questions_service.generate_questions(
        db, student_id=student_id, teacher=teacher, module_id=payload.module_id
    )
