from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query
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
        db,
        student_id=student_id,
        teacher=teacher,
        module_id=payload.module_id,
        mode=payload.mode,
    )


@router.get(
    "/{student_id}/evidence-matches",
    response_model=EvidenceMatchReport,
    summary="Read a stored evidence-to-criterion mapping (latest run by default)",
)
def get_evidence_matching(
    student_id: str,
    run_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    return evidence_match_service.get_report(
        db, student_id=student_id, teacher=teacher, run_id=run_id
    )


@router.delete(
    "/{student_id}/evidence-matches/runs/{run_id}",
    response_model=EvidenceMatchReport,
    summary="Delete a stored AI generation run for the student",
)
def delete_evidence_matching_run(
    student_id: str,
    run_id: UUID,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    return evidence_match_service.delete_run(
        db, student_id=student_id, teacher=teacher, run_id=run_id
    )
