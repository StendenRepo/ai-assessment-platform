"""Assessment draft, override, chat refinement, and finalization (G2-146/147/150)."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher, get_db
from app.models.assessment import Assessment
from app.models.teacher import Teacher
from app.schemas.assessment import (
    ChatMessageOut,
    ChatPostIn,
    ChatResponseOut,
    DraftFormOut,
    FinalFormOut,
    FinalizeIn,
    GenerateDraftOut,
    OverridesPatchIn,
    RevertCriterionIn,
)
from app.services import draft_assessment_service
from app.services.draft_assessment_service import AssessmentLockedError

router = APIRouter()


def _get_owned_assessment(
    assessment_id: UUID, db: Session, teacher: Teacher
) -> Assessment:
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if assessment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found"
        )
    if assessment.teacher_id != teacher.id and not teacher.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage your own assessments",
        )
    return assessment


def _locked_response() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Assessment is finalized and locked from further changes",
    )


@router.get("/assessments/{assessment_id}/draft", response_model=DraftFormOut)
def get_draft(
    assessment_id: UUID,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    assessment = _get_owned_assessment(assessment_id, db, teacher)
    return draft_assessment_service.build_draft_out(assessment, db)


@router.post("/assessments/{assessment_id}/draft/generate", response_model=GenerateDraftOut)
def generate_draft(
    assessment_id: UUID,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    assessment = _get_owned_assessment(assessment_id, db, teacher)
    try:
        draft_assessment_service.generate_suggestions(
            db, assessment=assessment, teacher=teacher
        )
    except AssessmentLockedError:
        raise _locked_response()
    draft = draft_assessment_service.build_draft_out(assessment, db)
    return GenerateDraftOut(
        draft=DraftFormOut(**draft),
        message="AI suggestions generated from uploaded evidence and rubric context.",
    )


@router.patch("/assessments/{assessment_id}/draft/overrides", response_model=DraftFormOut)
def patch_overrides(
    assessment_id: UUID,
    payload: OverridesPatchIn,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    assessment = _get_owned_assessment(assessment_id, db, teacher)
    try:
        draft_assessment_service.apply_overrides(
            db,
            assessment=assessment,
            teacher=teacher,
            overrides=[o.model_dump() for o in payload.overrides],
            summary=payload.summary,
            overall_grade=payload.overall_grade,
        )
    except AssessmentLockedError:
        raise _locked_response()
    return draft_assessment_service.build_draft_out(assessment, db)


@router.post("/assessments/{assessment_id}/draft/revert", response_model=DraftFormOut)
def revert_override(
    assessment_id: UUID,
    payload: RevertCriterionIn,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    assessment = _get_owned_assessment(assessment_id, db, teacher)
    try:
        draft_assessment_service.revert_criterion(
            db,
            assessment=assessment,
            teacher=teacher,
            criterion_key=payload.criterion_key,
        )
    except AssessmentLockedError:
        raise _locked_response()
    return draft_assessment_service.build_draft_out(assessment, db)


@router.get("/assessments/{assessment_id}/chat", response_model=list[ChatMessageOut])
def get_chat(
    assessment_id: UUID,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    assessment = _get_owned_assessment(assessment_id, db, teacher)
    messages = draft_assessment_service.list_chat_messages(db, assessment.id)
    return [
        ChatMessageOut(
            id=str(m.id),
            role=m.role,
            content=m.content,
            timestamp=m.timestamp,
        )
        for m in messages
    ]


@router.post("/assessments/{assessment_id}/chat", response_model=ChatResponseOut)
def post_chat(
    assessment_id: UUID,
    payload: ChatPostIn,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    assessment = _get_owned_assessment(assessment_id, db, teacher)
    try:
        reply, _ = draft_assessment_service.chat_refine(
            db,
            assessment=assessment,
            teacher=teacher,
            message=payload.message,
        )
    except AssessmentLockedError:
        raise _locked_response()
    messages = draft_assessment_service.list_chat_messages(db, assessment.id)
    draft = draft_assessment_service.build_draft_out(assessment, db)
    return ChatResponseOut(
        messages=[
            ChatMessageOut(
                id=str(m.id),
                role=m.role,
                content=m.content,
                timestamp=m.timestamp,
            )
            for m in messages
        ],
        draft=DraftFormOut(**draft),
        assistant_reply=reply,
    )


@router.post("/assessments/{assessment_id}/finalize", response_model=FinalFormOut)
def finalize(
    assessment_id: UUID,
    payload: FinalizeIn,
    request: Request,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm must be true to finalize",
        )
    assessment = _get_owned_assessment(assessment_id, db, teacher)
    draft_assessment_service.finalize_assessment(
        db,
        assessment=assessment,
        teacher=teacher,
        teacher_notes=payload.teacher_notes,
    )
    return draft_assessment_service.build_final_out(assessment, db)


@router.get("/assessments/{assessment_id}/final", response_model=FinalFormOut)
def get_final(
    assessment_id: UUID,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    assessment = _get_owned_assessment(assessment_id, db, teacher)
    return draft_assessment_service.build_final_out(assessment, db)


@router.get("/assessments/{assessment_id}/audit-trail")
def get_audit_trail(
    assessment_id: UUID,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    assessment = _get_owned_assessment(assessment_id, db, teacher)
    events = draft_assessment_service.get_audit_trail(db, assessment.id)
    return [
        {
            "action": e.action,
            "source": e.source.value if e.source else None,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            "details": e.details_json,
        }
        for e in events
    ]
