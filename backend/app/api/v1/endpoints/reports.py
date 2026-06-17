"""Reports overview endpoint.

Returns a list of recent export events from the audit log:
- ``grades.exported``          — Excel grade export
- ``module.archive_exported``  — Group Overview archive
- ``student.dossier_exported`` — Individual student dossier

Teachers see only their own exports; admins see all.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher, get_db
from app.models.audit_event import AuditEvent
from app.models.teacher import Teacher

router = APIRouter()

_REPORT_ACTIONS = {
    "grades.exported",
    "module.archive_exported",
    "student.dossier_exported",
}

_ACTION_LABELS = {
    "grades.exported": "Grade Export (Excel)",
    "module.archive_exported": "Group Overview Archive",
    "student.dossier_exported": "Individual Student Dossier",
}


def _event_to_out(event: AuditEvent) -> dict:
    details = event.details_json or {}
    return {
        "id": event.id,
        "action": event.action,
        "label": _ACTION_LABELS.get(event.action, event.action),
        "timestamp": event.timestamp.isoformat() if event.timestamp else None,
        "teacher_name": details.get("teacher_name"),
        # report-specific detail fields
        "module_id": details.get("module_id"),
        "module_name": details.get("module_name"),
        "student_name": details.get("student_name"),
        "student_id": details.get("student_id"),
        "format": details.get("format", "zip"),
        "student_count": details.get("student_count"),
        "evidence_count": details.get("evidence_count"),
    }


@router.get("", summary="List recent report exports")
def list_reports(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    """Return recent export events.

    - Regular teachers see only their own exports.
    - Admins see exports from all teachers.
    """
    query = db.query(AuditEvent).filter(AuditEvent.action.in_(_REPORT_ACTIONS))

    if not current_teacher.is_admin:
        query = query.filter(AuditEvent.teacher_id == current_teacher.id)

    events = (
        query.order_by(desc(AuditEvent.timestamp), desc(AuditEvent.id))
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [_event_to_out(e) for e in events]
