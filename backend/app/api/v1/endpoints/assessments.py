"""Assessment draft, override, chat refinement, and finalization (G2-146/147/150)."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher, get_db
from app.models.assessment import Assessment
from app.models.teacher import Teacher
from app.schemas.assessment import (
    ChatApplyIn,
    ChatApplyOut,
    ChatChangeOut,
    ChatDiscussOut,
    ChatMessageOut,
    ChatPostIn,
    ChatProposalOut,
    ChatUndoOut,
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


def _chat_messages_out(db: Session, assessment_id: UUID) -> list[ChatMessageOut]:
    messages = draft_assessment_service.list_chat_messages(db, assessment_id)
    return [ChatMessageOut(**row) for row in draft_assessment_service.serialize_chat_messages(messages)]


def _changes_out(rows: list[dict]) -> list[ChatChangeOut]:
    return [ChatChangeOut(**row) for row in rows]


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
    return _chat_messages_out(db, assessment.id)


@router.post("/assessments/{assessment_id}/chat", response_model=ChatDiscussOut)
def post_chat_discuss(
    assessment_id: UUID,
    payload: ChatPostIn,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    assessment = _get_owned_assessment(assessment_id, db, teacher)
    try:
        reply = draft_assessment_service.chat_discuss(
            db,
            assessment=assessment,
            teacher=teacher,
            message=payload.message,
            criterion_key=payload.criterion_key,
        )
    except AssessmentLockedError:
        raise _locked_response()
    return ChatDiscussOut(
        messages=_chat_messages_out(db, assessment.id),
        assistant_reply=reply,
    )


@router.post("/assessments/{assessment_id}/chat/refine", response_model=ChatProposalOut)
def post_chat_refine(
    assessment_id: UUID,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    assessment = _get_owned_assessment(assessment_id, db, teacher)
    try:
        proposal = draft_assessment_service.chat_propose_refine(
            db, assessment=assessment, teacher=teacher
        )
    except AssessmentLockedError:
        raise _locked_response()
    return ChatProposalOut(
        proposal_id=proposal["proposal_id"],
        message_id=proposal["message_id"],
        reply=proposal["reply"],
        proposed_changes=_changes_out(proposal["proposed_changes"]),
        summary_proposed=proposal.get("summary_proposed"),
        updates_requested=proposal.get("updates_requested", 0),
        messages=_chat_messages_out(db, assessment.id),
    )


@router.post("/assessments/{assessment_id}/chat/apply", response_model=ChatApplyOut)
def post_chat_apply(
    assessment_id: UUID,
    payload: ChatApplyIn,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    assessment = _get_owned_assessment(assessment_id, db, teacher)
    try:
        _, applied = draft_assessment_service.chat_apply_proposal(
            db,
            assessment=assessment,
            teacher=teacher,
            proposal_id=UUID(payload.proposal_id),
        )
    except AssessmentLockedError:
        raise _locked_response()
    db.refresh(assessment)
    draft = draft_assessment_service.build_draft_out(assessment, db)
    return ChatApplyOut(
        draft=DraftFormOut(**draft),
        changes_applied=_changes_out(applied),
        messages=_chat_messages_out(db, assessment.id),
    )


@router.post("/assessments/{assessment_id}/chat/reject", response_model=list[ChatMessageOut])
def post_chat_reject(
    assessment_id: UUID,
    payload: ChatApplyIn,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    assessment = _get_owned_assessment(assessment_id, db, teacher)
    try:
        draft_assessment_service.chat_reject_proposal(
            db,
            assessment=assessment,
            teacher=teacher,
            proposal_id=UUID(payload.proposal_id),
        )
    except AssessmentLockedError:
        raise _locked_response()
    return _chat_messages_out(db, assessment.id)


@router.post("/assessments/{assessment_id}/chat/undo", response_model=ChatUndoOut)
def post_chat_undo(
    assessment_id: UUID,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    assessment = _get_owned_assessment(assessment_id, db, teacher)
    try:
        _, restored = draft_assessment_service.chat_undo_last_apply(
            db, assessment=assessment, teacher=teacher
        )
    except AssessmentLockedError:
        raise _locked_response()
    db.refresh(assessment)
    draft = draft_assessment_service.build_draft_out(assessment, db)
    return ChatUndoOut(
        draft=DraftFormOut(**draft),
        changes_restored=_changes_out(restored),
        messages=_chat_messages_out(db, assessment.id),
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
