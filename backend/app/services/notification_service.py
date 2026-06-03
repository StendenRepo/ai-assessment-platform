"""Teacher notifications, used for recording deletion reminders (G2-142)."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.enums import NotificationType
from app.models.notification import Notification


def create_notification(
    db: Session,
    *,
    teacher_id: UUID,
    type: NotificationType,
    message: str,
    assessment_id: Optional[UUID] = None,
    due_date: Optional[datetime] = None,
    commit: bool = True,
) -> Notification:
    notification = Notification(
        teacher_id=teacher_id,
        assessment_id=assessment_id,
        type=type,
        message=message,
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
    return query.order_by(Notification.created_at.desc()).all()


def mark_read(db: Session, *, notification: Notification) -> Notification:
    if notification.read_at is None:
        notification.read_at = datetime.utcnow()
        db.commit()
        db.refresh(notification)
    return notification


def reminder_exists(db: Session, *, assessment_id: UUID) -> bool:
    """Whether a deletion reminder was already created for this assessment."""
    return (
        db.query(Notification)
        .filter(
            Notification.assessment_id == assessment_id,
            Notification.type == NotificationType.deletion_reminder,
        )
        .first()
        is not None
    )
