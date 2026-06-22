"""Central audit-trail writer.

Every recording-related action must be logged with a timestamp and the acting
teacher's name (FR-06 full audit trail requirement). This helper is the single
place that writes AuditEvent rows so the format stays consistent.
"""
from typing import Optional
from uuid import UUID

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent
from app.models.enums import AuditSource


def log_action(
    db: Session,
    *,
    action: str,
    source: AuditSource = AuditSource.teacher,
    teacher_id: Optional[UUID] = None,
    teacher_name: Optional[str] = None,
    assessment_id: Optional[UUID] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
    commit: bool = True,
) -> AuditEvent:
    """Record an audit event.

    The teacher name is denormalised into details_json so the trail stays
    readable even if the teacher record is later renamed or removed.
    """
    payload = dict(details or {})
    if teacher_name is not None:
        payload.setdefault("teacher_name", teacher_name)

    event = AuditEvent(
        assessment_id=assessment_id,
        teacher_id=teacher_id,
        action=action,
        details_json=payload or None,
        source=source,
        ip_address=ip_address,
    )
    db.add(event)
    if commit:
        db.commit()
    else:
        db.flush()
    return event


def list_events(
    db: Session,
    *,
    limit: int = 100,
    offset: int = 0,
    teacher_id: Optional[UUID] = None,
    assessment_id: Optional[UUID] = None,
    action_contains: Optional[str] = None,
) -> list[AuditEvent]:
    query = db.query(AuditEvent)

    if teacher_id is not None:
        query = query.filter(AuditEvent.teacher_id == teacher_id)
    if assessment_id is not None:
        query = query.filter(AuditEvent.assessment_id == assessment_id)
    if action_contains:
        query = query.filter(AuditEvent.action.ilike(f"%{action_contains}%"))

    return (
        query.order_by(desc(AuditEvent.timestamp), desc(AuditEvent.id))
        .offset(max(0, offset))
        .limit(max(1, min(limit, 500)))
        .all()
    )
