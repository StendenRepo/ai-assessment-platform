"""Recording, transcription, consent and notification endpoints (FR-06).

An assessment has ONE consent decision (up front) and MANY recordings. Each
recording has its own file, transcript, status and expiry.
"""
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    UploadFile,
    File,
    Form,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher, get_db
from app.database import SessionLocal
from app.models.assessment import Assessment
from app.models.enums import ConsentStatus
from app.models.file_record import FileRecord
from app.models.notification import Notification
from app.models.recording import Recording
from app.models.teacher import Teacher
from app.schemas.recording import (
    ConsentStateOut,
    ConsentUpdate,
    NotificationOut,
    RecordingDetail,
    RecordingPatchIn,
    RecordingSummary,
)
from app.services import assessment_service, notification_service, recording_service

router = APIRouter()


# ── helpers ───────────────────────────────────────────────────────────────────

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


def _get_recording(db: Session, assessment: Assessment, recording_id: UUID) -> Recording:
    recording = (
        db.query(Recording)
        .filter(
            Recording.id == recording_id,
            Recording.assessment_id == assessment.id,
            Recording.deleted_at.is_(None),
        )
        .first()
    )
    if recording is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recording not found")
    return recording


def _summary(db: Session, recording: Recording) -> RecordingSummary:
    record = None
    if recording.file_id:
        record = db.query(FileRecord).filter(FileRecord.id == recording.file_id).first()
    return RecordingSummary(
        id=str(recording.id),
        display_name=recording.display_name,
        sequence_number=recording.sequence_number,
        transcription_status=recording.transcription_status,
        created_at=recording.created_at,
        delete_after=record.delete_after if record else None,
        flagged_for_deletion=record.flagged_for_deletion if record else False,
        extension_count=record.extension_count if record else 0,
    )


def _detail(db: Session, recording: Recording) -> RecordingDetail:
    summary = _summary(db, recording)
    return RecordingDetail(**summary.model_dump(), transcript_text=recording.transcript_text)


def _transcribe_in_background(
    recording_id: UUID, teacher_id: UUID, language: str | None = None
) -> None:
    """Run transcription in its own DB session after the upload response."""
    db = SessionLocal()
    try:
        recording = db.query(Recording).filter(Recording.id == recording_id).first()
        teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
        if recording and teacher:
            recording_service.transcribe_recording(
                db, recording=recording, teacher=teacher, language=language
            )
    except Exception:
        # Failure is already persisted (transcription_status=failed) and audited.
        pass
    finally:
        db.close()


# ── consent gate ────────────────────────────────────────────────────────────--

@router.post("/assessments/for-student/{student_id}", response_model=ConsentStateOut)
def resolve_assessment_for_student(
    student_id: UUID,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    """Resolve (or lazily create) the current teacher's assessment for a student.

    The recording UI knows only the student; this returns the assessment id +
    consent state so the panel can drive the recording/consent endpoints.
    """
    assessment = assessment_service.get_or_create_for_student(
        db, student_id=student_id, teacher=teacher
    )
    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    count = (
        db.query(Recording)
        .filter(Recording.assessment_id == assessment.id, Recording.deleted_at.is_(None))
        .count()
    )
    return ConsentStateOut(
        assessment_id=str(assessment.id),
        consent_status=assessment.consent_status,
        consent_confirmed_at=assessment.consent_confirmed_at,
        recording_count=count,
    )


@router.get("/assessments/{assessment_id}/recording", response_model=ConsentStateOut)
def get_consent_state(
    assessment_id: UUID,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    """Consent gate state for the assessment (used by the frontend gate)."""
    assessment = _get_owned_assessment(assessment_id, db, teacher)
    count = (
        db.query(Recording)
        .filter(Recording.assessment_id == assessment.id, Recording.deleted_at.is_(None))
        .count()
    )
    return ConsentStateOut(
        assessment_id=str(assessment.id),
        consent_status=assessment.consent_status,
        consent_confirmed_at=assessment.consent_confirmed_at,
        recording_count=count,
    )


@router.post("/assessments/{assessment_id}/consent", response_model=ConsentStateOut)
def set_consent(
    assessment_id: UUID,
    body: ConsentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    """Teacher confirms the student's oral consent decision (G2-137, G2-138)."""
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
    count = (
        db.query(Recording)
        .filter(Recording.assessment_id == assessment.id, Recording.deleted_at.is_(None))
        .count()
    )
    return ConsentStateOut(
        assessment_id=str(assessment.id),
        consent_status=assessment.consent_status,
        consent_confirmed_at=assessment.consent_confirmed_at,
        recording_count=count,
    )


# ── recordings ─────────────────────────────────────────────────────────────-

@router.get("/assessments/{assessment_id}/recordings", response_model=list[RecordingSummary])
def list_recordings(
    assessment_id: UUID,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    assessment = _get_owned_assessment(assessment_id, db, teacher)
    recordings = (
        db.query(Recording)
        .filter(Recording.assessment_id == assessment.id, Recording.deleted_at.is_(None))
        .order_by(Recording.sequence_number)
        .all()
    )
    return [_summary(db, r) for r in recordings]


@router.post(
    "/assessments/{assessment_id}/recording",
    response_model=RecordingDetail,
    status_code=status.HTTP_201_CREATED,
)
async def upload_recording(
    assessment_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    language: str | None = Form(default=None),
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    """Append a new recording (G2-136) and queue its transcription (G2-140).

    Only allowed once consent has been accepted for the assessment. ``language``
    is an optional ISO code ("en", "nl", …); omit it to auto-detect.
    """
    assessment = _get_owned_assessment(assessment_id, db, teacher)
    if assessment.consent_status != ConsentStatus.accepted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Consent must be accepted before recording",
        )

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty audio upload")

    recording = recording_service.append_recording(
        db,
        assessment=assessment,
        teacher=teacher,
        audio_bytes=audio_bytes,
        content_type=file.content_type,
        filename=file.filename,
        ip_address=request.client.host if request.client else None,
    )
    background_tasks.add_task(_transcribe_in_background, recording.id, teacher.id, language)
    return _detail(db, recording)


@router.get(
    "/assessments/{assessment_id}/recordings/{recording_id}",
    response_model=RecordingDetail,
)
def get_recording(
    assessment_id: UUID,
    recording_id: UUID,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    assessment = _get_owned_assessment(assessment_id, db, teacher)
    recording = _get_recording(db, assessment, recording_id)
    return _detail(db, recording)


@router.patch(
    "/assessments/{assessment_id}/recordings/{recording_id}",
    response_model=RecordingDetail,
)
def patch_recording(
    assessment_id: UUID,
    recording_id: UUID,
    body: RecordingPatchIn,
    request: Request,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    """Rename and/or extend a recording's expiry (GDPR-capped)."""
    if body.display_name is None and body.extend_expiry is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide display_name and/or extend_expiry",
        )
    assessment = _get_owned_assessment(assessment_id, db, teacher)
    recording = _get_recording(db, assessment, recording_id)
    ip = request.client.host if request.client else None

    if body.display_name is not None:
        recording_service.rename_recording(
            db, recording=recording, teacher=teacher, new_name=body.display_name, ip_address=ip
        )

    if body.extend_expiry is not None:
        try:
            recording_service.extend_expiry(
                db,
                recording=recording,
                teacher=teacher,
                reason=body.extend_expiry.reason,
                extra_days=body.extend_expiry.extra_days,
                ip_address=ip,
            )
        except recording_service.ExtensionNotAllowed as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return _detail(db, recording)


@router.delete(
    "/assessments/{assessment_id}/recordings/{recording_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_recording(
    assessment_id: UUID,
    recording_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    """Soft-delete a recording: mark deleted + unlink the file, keep the row."""
    assessment = _get_owned_assessment(assessment_id, db, teacher)
    recording = _get_recording(db, assessment, recording_id)
    recording_service.delete_recording(
        db,
        recording=recording,
        teacher=teacher,
        ip_address=request.client.host if request.client else None,
    )


# ── notifications ────────────────────────────────────────────────────────────

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
