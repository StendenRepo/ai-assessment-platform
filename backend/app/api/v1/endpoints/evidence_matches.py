from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher, get_db
from app.models.teacher import Teacher
from app.schemas.evidence_match import EvidenceMatchReport, RunMatchingRequest
from app.services import evidence_match_service

router = APIRouter()


@router.post(
    "/{student_id}/evidence-matches",
    response_model=EvidenceMatchReport,
    summary="Run AI matching of the student's evidence to the rubric criteria",
)
def run_evidence_matching(
    student_id: str,
    payload: RunMatchingRequest = Body(default=RunMatchingRequest()),
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    return evidence_match_service.run_matching(
        db, student_id=student_id, teacher=teacher, module_id=payload.module_id
    )


@router.get(
    "/{student_id}/evidence-matches",
    response_model=EvidenceMatchReport,
    summary="Read the stored evidence-to-criterion mapping for the student",
)
def get_evidence_matching(
    student_id: str,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    return evidence_match_service.get_report(db, student_id=student_id, teacher=teacher)
