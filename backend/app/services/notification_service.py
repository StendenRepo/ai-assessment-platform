"""Teacher notifications, used for recording deletion reminders (G2-142)."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.enums import NotificationType
from app.models.notification import Notification
from app.services import notification_preference_service


def create_notification(
    db: Session,
    *,
    teacher_id: UUID,
    type: NotificationType,
    message: str,
    target_path: Optional[str] = None,
    assessment_id: Optional[UUID] = None,
    recording_id: Optional[UUID] = None,
    generation_run_id: Optional[UUID] = None,
    due_date: Optional[datetime] = None,
    commit: bool = True,
) -> Notification:
    notification = Notification(
        teacher_id=teacher_id,
        assessment_id=assessment_id,
        recording_id=recording_id,
        generation_run_id=generation_run_id,
        type=type,
        message=message,
        target_path=target_path,
        due_date=due_date,
    )
    db.add(notification)
    if commit:
        db.commit()
        db.refresh(notification)
    else:
        db.flush()
    return notification


def list_for_teacher(
    db: Session, *, teacher_id: UUID, unread_only: bool = False
) -> list[Notification]:
    query = db.query(Notification).filter(Notification.teacher_id == teacher_id)
    if unread_only:
        query = query.filter(Notification.read_at.is_(None))
    # Server-side preference enforcement: drop types the teacher disabled so a
    # disabled event type never reaches the client (G2-220).
    disabled = notification_preference_service.disabled_types(db, teacher_id=teacher_id)
    if disabled:
        query = query.filter(Notification.type.notin_(disabled))
    return query.order_by(Notification.created_at.desc()).all()


def mark_read(db: Session, *, notification: Notification) -> Notification:
    if notification.read_at is None:
        notification.read_at = datetime.utcnow()
        db.commit()
        db.refresh(notification)
    return notification


def reminder_exists(db: Session, *, recording_id: UUID) -> bool:
    """Whether a deletion reminder was already created for this recording."""
    return (
        db.query(Notification)
        .filter(
            Notification.recording_id == recording_id,
            Notification.type == NotificationType.deletion_reminder,
        )
        .first()
        is not None
    )


def generation_reminder_exists(db: Session, *, generation_run_id: UUID) -> bool:
    """Whether a retention reminder was already created for this AI run."""
    return (
        db.query(Notification)
        .filter(
            Notification.generation_run_id == generation_run_id,
            Notification.type == NotificationType.deletion_reminder,
        )
        .first()
        is not None
    )
