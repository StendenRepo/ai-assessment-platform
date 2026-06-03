"""Recording, transcription, consent and notification endpoints (FR-06)."""
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    UploadFile,
    File,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher, get_db
from app.database import SessionLocal
from app.models.assessment import Assessment
from app.models.enums import ConsentStatus
from app.models.file_record import FileRecord
from app.models.notification import Notification
from app.models.teacher import Teacher
from app.schemas.recording import (
    ConsentUpdate,
    NotificationOut,
    RecordingStateOut,
)
from app.services import assessment_service, notification_service, recording_service

router = APIRouter()


def _get_owned_assessment(
    assessment_id: UUID, db: Session, teacher: Teacher
) -> Assessment:
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")
    if assessment.teacher_id != teacher.id and not teacher.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage recordings for your own assessments",
        )
    return assessment


def _state(db: Session, assessment: Assessment) -> RecordingStateOut:
    record = None
    if assessment.recording_file_id:
        record = db.query(FileRecord).filter(FileRecord.id == assessment.recording_file_id).first()
    return RecordingStateOut(
        assessment_id=str(assessment.id),
        has_recording=assessment.recording_file_id is not None,
        consent_status=assessment.consent_status,
        consent_confirmed_at=assessment.consent_confirmed_at,
        transcription_status=assessment.transcription_status,
        transcript_text=assessment.transcript_text,
        delete_after=record.delete_after if record else None,
        flagged_for_deletion=record.flagged_for_deletion if record else False,
    )


def _transcribe_in_background(assessment_id: UUID, teacher_id: UUID) -> None:
    """Run transcription in its own DB session after the upload response."""
    db = SessionLocal()
    try:
        assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
        teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
        if assessment and teacher:
            recording_service.transcribe_recording(db, assessment=assessment, teacher=teacher)
    except Exception:
        # Failure is already persisted (transcription_status=failed) and audited.
        pass
    finally:
        db.close()


@router.get("/assessments/{assessment_id}/recording", response_model=RecordingStateOut)
def get_recording_state(
    assessment_id: UUID,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    assessment = _get_owned_assessment(assessment_id, db, teacher)
    return _state(db, assessment)


@router.post(
    "/assessments/{assessment_id}/recording",
    response_model=RecordingStateOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_recording(
    assessment_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    """Upload an assessment recording (G2-136) and queue transcription (G2-140).

    The recording's opening segment holds the oral consent statement (G2-137);
    the teacher reviews the transcript and confirms consent separately.
    """
    assessment = _get_owned_assessment(assessment_id, db, teacher)
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty audio upload")

    recording_service.save_recording(
        db,
        assessment=assessment,
        teacher=teacher,
        audio_bytes=audio_bytes,
        content_type=file.content_type,
        filename=file.filename,
        ip_address=request.client.host if request.client else None,
    )
    background_tasks.add_task(_transcribe_in_background, assessment.id, teacher.id)
    return _state(db, assessment)


@router.post("/assessments/{assessment_id}/consent", response_model=RecordingStateOut)
def set_consent(
    assessment_id: UUID,
    body: ConsentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    """Teacher confirms the student's oral consent decision (G2-137, G2-138).

    ``declined`` lets the assessment proceed without audio; the form then shows
    "recording declined".
    """
    if body.status == ConsentStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Consent status must be 'accepted' or 'declined'",
        )
    assessment = _get_owned_assessment(assessment_id, db, teacher)
    assessment_service.set_consent(
        db,
        assessment=assessment,
        teacher=teacher,
        status=body.status,
        ip_address=request.client.host if request.client else None,
    )
    return _state(db, assessment)


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(
    unread_only: bool = False,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    items = notification_service.list_for_teacher(
        db, teacher_id=teacher.id, unread_only=unread_only
    )
    return [
        NotificationOut(
            id=str(n.id),
            type=n.type,
            message=n.message,
            assessment_id=str(n.assessment_id) if n.assessment_id else None,
            due_date=n.due_date,
            created_at=n.created_at,
            read_at=n.read_at,
        )
        for n in items
    ]


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notification_id: str,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.teacher_id == teacher.id)
        .first()
    )
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    notification_service.mark_read(db, notification=notification)
    return NotificationOut(
        id=str(notification.id),
        type=notification.type,
        message=notification.message,
        assessment_id=str(notification.assessment_id) if notification.assessment_id else None,
        due_date=notification.due_date,
        created_at=notification.created_at,
        read_at=notification.read_at,
    )
