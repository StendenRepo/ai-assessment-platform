"""Recording retention logic (G2-141 deletion flagging, G2-142 reminders).

Pure functions invoked by the worker container on a daily schedule. Logic lives
here (not in the worker entrypoint) so it can be unit-tested against SQLite.
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.models.assessment import Assessment
from app.models.enums import AuditSource, NotificationType
from app.models.file_record import FileRecord
from app.services import audit_service, notification_service


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
        assessment = (
            db.query(Assessment)
            .filter(Assessment.recording_file_id == record.id)
            .first()
        )
        audit_service.log_action(
            db,
            action="recording.flagged_for_deletion",
            source=AuditSource.system,
            assessment_id=assessment.id if assessment else None,
            details={"file_id": str(record.id), "delete_after": record.delete_after.isoformat()},
            commit=False,
        )

    db.commit()
    return len(records)


def create_deletion_reminders(db: Session, *, now: datetime | None = None) -> int:
    """Create reminders for recordings approaching their deletion date (G2-142).

    A reminder is created once per assessment for the teacher who owns it, when
    the recording is within RECORDING_REMINDER_LEAD_DAYS of deletion.
    Returns the number of reminders created.
    """
    now = now or datetime.utcnow()
    threshold = now + timedelta(days=settings.RECORDING_REMINDER_LEAD_DAYS)

    rows = (
        db.query(Assessment, FileRecord)
        .join(FileRecord, Assessment.recording_file_id == FileRecord.id)
        .filter(
            FileRecord.delete_after.isnot(None),
            FileRecord.delete_after <= threshold,
            FileRecord.deleted_at.is_(None),
        )
        .all()
    )

    created = 0
    for assessment, record in rows:
        if notification_service.reminder_exists(db, assessment_id=assessment.id):
            continue
        days_left = max((record.delete_after - now).days, 0)
        notification_service.create_notification(
            db,
            teacher_id=assessment.teacher_id,
            type=NotificationType.deletion_reminder,
            assessment_id=assessment.id,
            message=(
                f"Recording for this assessment will be deleted in {days_left} day(s) "
                f"(on {record.delete_after.date().isoformat()})."
            ),
            due_date=record.delete_after,
            commit=False,
        )
        created += 1

    db.commit()
    return created
