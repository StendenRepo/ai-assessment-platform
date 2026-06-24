"""Per-teacher notification preferences (G2-220).

Preferences are opt-out: a teacher with no stored row for a type is treated as
enabled. Every write goes through ``set_preference``, which records an audit
event in the SAME transaction (NFR-02) before committing once.
"""
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.enums import NotificationType
from app.models.notification_preference import NotificationPreference
from app.models.teacher import Teacher
from app.services import audit_service


def get_effective_preferences(
    db: Session, *, teacher_id: UUID
) -> dict[NotificationType, bool]:
    """Effective enabled/disabled for every type, defaulting missing rows to True."""
    overrides = {
        row.notification_type: row.enabled
        for row in db.query(NotificationPreference).filter(
            NotificationPreference.teacher_id == teacher_id
        )
    }
    return {ntype: overrides.get(ntype, True) for ntype in NotificationType}


def disabled_types(db: Session, *, teacher_id: UUID) -> set[NotificationType]:
    """Types the teacher has explicitly turned off (used to filter reads)."""
    return {
        row.notification_type
        for row in db.query(NotificationPreference).filter(
            NotificationPreference.teacher_id == teacher_id,
            NotificationPreference.enabled.is_(False),
        )
    }


def set_preference(
    db: Session,
    *,
    teacher: Teacher,
    notification_type: NotificationType,
    enabled: bool,
    ip_address: Optional[str] = None,
) -> NotificationPreference:
    """Upsert one preference and audit the change in the same transaction.

    Returns the persisted row. The preference write and its audit entry are
    flushed together and committed once so NFR-02 holds even on partial failure.
    """
    pref = (
        db.query(NotificationPreference)
        .filter(
            NotificationPreference.teacher_id == teacher.id,
            NotificationPreference.notification_type == notification_type,
        )
        .first()
    )
    if pref is None:
        pref = NotificationPreference(
            teacher_id=teacher.id,
            notification_type=notification_type,
            enabled=enabled,
        )
        db.add(pref)
    else:
        pref.enabled = enabled

    audit_service.log_action(
        db,
        action="notification_preference.updated",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        details={
            "notification_type": notification_type.value,
            "enabled": enabled,
        },
        ip_address=ip_address,
        commit=False,
    )

    db.commit()
    db.refresh(pref)
    return pref
