"""Persistence and query helpers for overlap signals."""

from __future__ import annotations

from typing import Iterable, List, Optional

from sqlalchemy.orm import Session

from app.models.overlap_signal import OverlapSignal
from app.models.project import Project
from app.models.student import Student, student_projects
from app.services.overlap_signal_codec import parse_signal_detail


def filter_signals(
    signals: Iterable[OverlapSignal],
    *,
    status: Optional[str],
    scope: Optional[str],
    group_id: Optional[str],
) -> List[OverlapSignal]:
    rows = list(signals)
    if not status and not scope and not group_id:
        return rows

    filtered: List[OverlapSignal] = []
    for signal in rows:
        detail = parse_signal_detail(signal.snippet)
        row_status = detail.get("status")
        if not row_status:
            row_status = "confirmed" if (signal.confidence or 0) >= 0.68 else "possible"
        row_scope = detail.get("scope") or "within_group"

        if status and row_status != status:
            continue
        if scope and row_scope != scope:
            continue
        if group_id:
            gid = str(group_id)
            if gid not in {detail.get("group_a_id"), detail.get("group_b_id")}:
                continue
        filtered.append(signal)
    return filtered


def clear_module_signals(db: Session, student_ids: List[object]) -> None:
    if not student_ids:
        return
    (
        db.query(OverlapSignal)
        .filter(
            OverlapSignal.student_a_id.in_(student_ids),
            OverlapSignal.student_b_id.in_(student_ids),
        )
        .delete(synchronize_session=False)
    )


def get_module_signals(
    db: Session,
    module_id: str,
    *,
    status: Optional[str] = None,
    scope: Optional[str] = None,
    group_id: Optional[str] = None,
) -> List[OverlapSignal]:
    signals = (
        db.query(OverlapSignal)
        .join(Student, OverlapSignal.student_a_id == Student.student_number)
        .join(student_projects, Student.student_number == student_projects.c.student_id)
        .join(Project, student_projects.c.project_id == Project.id)
        .filter(Project.module_id == module_id)
        .order_by(OverlapSignal.confidence.desc(), OverlapSignal.detected_at.desc())
        .all()
    )
    return filter_signals(signals, status=status, scope=scope, group_id=group_id)


def get_signal(db: Session, module_id: str, signal_id: str) -> Optional[OverlapSignal]:
    students = (
        db.query(Student)
        .join(student_projects, Student.student_number == student_projects.c.student_id)
        .join(Project, student_projects.c.project_id == Project.id)
        .filter(Project.module_id == module_id)
        .all()
    )
    if not students:
        return None
    student_ids = [s.student_number for s in students]
    return (
        db.query(OverlapSignal)
        .filter(
            OverlapSignal.id == signal_id,
            OverlapSignal.student_a_id.in_(student_ids),
            OverlapSignal.student_b_id.in_(student_ids),
        )
        .first()
    )
