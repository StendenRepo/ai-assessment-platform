"""Recording retention logic (G2-141 deletion flagging, G2-142 reminders).

Pure functions invoked by the retention-worker container on a daily schedule.
Logic lives here (not in the worker entrypoint) so it can be unit-tested
against SQLite.
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.models.assessment import Assessment
from app.models.enums import AuditSource, NotificationType
from app.models.file_record import FileRecord
from app.models.generation_run import GenerationRun
from app.models.recording import Recording
from app.services import audit_service, notification_service, recording_service


def flag_expired_recordings(db: Session, *, now: datetime | None = None) -> int:
    """Flag recordings whose retention period has passed (G2-141).

    Returns the number of files newly flagged. Each flag is written to the
    audit trail by the system actor.
    """
    now = now or datetime.utcnow()
    records = (
        db.query(FileRecord)
        .filter(
            FileRecord.delete_after.isnot(None),
            FileRecord.delete_after <= now,
            FileRecord.flagged_for_deletion.is_(False),
            FileRecord.deleted_at.is_(None),
        )
        .all()
    )

    for record in records:
        record.flagged_for_deletion = True
        recording = (
            db.query(Recording)
            .filter(Recording.file_id == record.id, Recording.deleted_at.is_(None))
            .first()
        )
        audit_service.log_action(
            db,
            action="recording.flagged_for_deletion",
            source=AuditSource.system,
            assessment_id=recording.assessment_id if recording else None,
            details={
                "file_id": str(record.id),
                "recording_id": str(recording.id) if recording else None,
                "delete_after": record.delete_after.isoformat(),
            },
            commit=False,
        )

    db.commit()
    return len(records)


def create_deletion_reminders(db: Session, *, now: datetime | None = None) -> int:
    """Create reminders for recordings approaching their deletion date (G2-142).

    A reminder is created once per RECORDING for the teacher who owns the
    assessment, when the recording is within RECORDING_REMINDER_LEAD_DAYS of
    deletion. Each reminder names the specific recording.
    Returns the number of reminders created.
    """
    now = now or datetime.utcnow()
    threshold = now + timedelta(days=settings.RECORDING_REMINDER_LEAD_DAYS)

    rows = (
        db.query(Recording, FileRecord)
        .join(FileRecord, Recording.file_id == FileRecord.id)
        .filter(
            Recording.deleted_at.is_(None),
            FileRecord.delete_after.isnot(None),
            FileRecord.delete_after <= threshold,
            FileRecord.deleted_at.is_(None),
        )
        .all()
    )

    created = 0
    for recording, record in rows:
        if notification_service.reminder_exists(db, recording_id=recording.id):
            continue
        days_left = max((record.delete_after - now).days, 0)
        student = recording.assessment.student
        subject = student.name if student else "this assessment"
        notification_service.create_notification(
            db,
            teacher_id=recording.assessment.teacher_id,
            type=NotificationType.deletion_reminder,
            assessment_id=recording.assessment_id,
            recording_id=recording.id,
            message=(
                f"Recording '{recording.display_name}' for {subject} will be deleted "
                f"in {days_left} day(s) (on {record.delete_after.date().isoformat()})."
            ),
            due_date=record.delete_after,
            commit=False,
        )
        created += 1

    db.commit()
    return created


def create_generation_retention_reminders(
    db: Session, *, now: datetime | None = None
) -> int:
    now = now or datetime.utcnow()
    threshold = now + timedelta(days=settings.GENERATION_REMINDER_LEAD_DAYS)

    rows = (
        db.query(GenerationRun, Assessment)
        .join(Assessment, GenerationRun.assessment_id == Assessment.id)
        .filter(
            GenerationRun.expires_at.isnot(None),
            GenerationRun.expires_at <= threshold,
        )
        .all()
    )

    created = 0
    for run, assessment in rows:
        if notification_service.generation_reminder_exists(
            db, generation_run_id=run.id
        ):
            continue
        days_left = max((run.expires_at - now).days, 0)
        student = assessment.student
        subject = student.name if student else "a student"
        if run.expires_at <= now:
            run.flagged_for_deletion = True

        notification_service.create_notification(
            db,
            teacher_id=assessment.teacher_id,
            type=NotificationType.deletion_reminder,
            assessment_id=assessment.id,
            generation_run_id=run.id,
            message=(
                f"AI analysis run for {subject} from "
                f"{run.created_at.date().isoformat()} will be deleted in "
                f"{days_left} day(s) (on {run.expires_at.date().isoformat()}). "
                "Review or delete it."
            ),
            due_date=run.expires_at,
            commit=False,
        )
        created += 1

    db.commit()
    return created
def purge_expired_recordings(db: Session, *, now: datetime | None = None) -> int:
    """Permanently remove recordings whose deletion date has passed (G2-141).

    Inaction -> delete. A recording that was extended has a future delete_after
    and is therefore naturally excluded. The audio file is removed from disk and
    deleted_at is set, but the metadata row + audit trail are kept. Returns the
    number of recordings purged.
    """
    now = now or datetime.utcnow()

    rows = (
        db.query(Recording, FileRecord)
        .join(FileRecord, Recording.file_id == FileRecord.id)
        .filter(
            Recording.deleted_at.is_(None),
            FileRecord.delete_after.isnot(None),
            FileRecord.delete_after <= now,
            FileRecord.deleted_at.is_(None),
        )
        .all()
    )

    for recording, _record in rows:
        recording_service.auto_delete_recording(db, recording)

    return len(rows)
