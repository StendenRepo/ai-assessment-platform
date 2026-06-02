from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai import ollama_client
from app.api.deps import get_current_teacher, get_db
from app.models.audit_event import AuditEvent
from app.models.enums import AuditSource, FileType, SourceType
from app.models.evidence import Evidence
from app.models.module import Module
from app.models.project import Project
from app.models.student import Student
from app.models.teacher import Teacher

router = APIRouter(tags=["Platform"])


def _parse_day(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


# --- Audit & system ---


@router.get("/audit")
def get_audit(
    action: str | None = None,
    teacher: str | None = None,
    q: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    limit = min(max(limit, 1), 500)
    from_day = _parse_day(from_date)
    to_day = _parse_day(to_date)

    rows = db.query(AuditEvent).order_by(AuditEvent.timestamp.desc()).limit(2000).all()
    teacher_ids = {row.teacher_id for row in rows if row.teacher_id is not None}
    teacher_map = {
        t.id: t
        for t in db.query(Teacher)
        .filter(Teacher.id.in_(list(teacher_ids)))
        .all()
    }

    def to_event(row: AuditEvent) -> dict:
        details = row.details_json or {}
        who = teacher_map.get(row.teacher_id)
        teacher_name = who.name if who else None
        return {
            "id": str(row.id),
            "timestamp": row.timestamp.astimezone(timezone.utc).isoformat(),
            "action": row.action,
            "module_id": details.get("module_id"),
            "project_id": details.get("project_id"),
            "student_id": details.get("student_id"),
            "teacher": teacher_name,
            "detail": details,
            "source": (row.source.value if row.source else None),
        }

    items = [to_event(row) for row in rows]

    if not current_teacher.is_admin:
        items = [e for e in items if e.get("teacher") == current_teacher.name]
    if action:
        items = [e for e in items if e.get("action") == action]
    if teacher:
        needle = teacher.strip().lower()
        items = [e for e in items if (e.get("teacher") or "").lower() == needle]
    if q:
        needle = q.strip().lower()
        if needle:
            items = [
                e
                for e in items
                if needle
                in " ".join(
                    [
                        e.get("action") or "",
                        e.get("teacher") or "",
                        e.get("module_id") or "",
                        e.get("project_id") or "",
                        e.get("student_id") or "",
                        str(e.get("detail") or ""),
                    ]
                ).lower()
            ]
    if from_day:
        items = [e for e in items if date.fromisoformat(e["timestamp"][:10]) >= from_day]
    if to_day:
        items = [e for e in items if date.fromisoformat(e["timestamp"][:10]) <= to_day]

    filtered_count = len(items)
    shown = items[:limit]
    actions = sorted({e.get("action") for e in shown if e.get("action")})
    teachers = sorted({e.get("teacher") for e in shown if e.get("teacher")})

    return {
        "events": shown,
        "total": len(rows),
        "count": filtered_count,
        "shown": len(shown),
        "actions": actions,
        "teachers": teachers,
    }


@router.get("/llm-status")
def llm_status():
    up = ollama_client.is_available()
    ready = ollama_client.model_is_pulled() if up else False
    return {
        **ollama_client.get_config(),
        "ollama_reachable": up,
        "model_ready": ready,
        "ready": up and ready,
    }


@router.post("/seed-demo")
def reseed_demo(
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = Module(
        teacher_id=current_teacher.id,
        name="Applied AI 2026",
        academic_year="2025-2026",
    )
    db.add(module)
    db.flush()

    project_1 = Project(module_id=module.id, name="Group 1", group_name="Group 1")
    project_2 = Project(module_id=module.id, name="Group 2", group_name="Group 2")
    db.add_all([project_1, project_2])
    db.flush()

    fixtures_dir = Path(__file__).resolve().parents[3] / "ai" / "fixtures"
    uploads_dir = Path(__file__).resolve().parents[4] / "data" / "uploads" / "evidence"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    demo_rows = [
        (project_1, "Lisa Anderson", "S2034567", "student_a.txt"),
        (project_1, "Thomas Johnson", "S2034789", "student_b.txt"),
        (project_2, "Maya Patel", "S2035012", "student_c.txt"),
    ]

    for group, name, student_number, fixture_name in demo_rows:
        student = Student(project_id=group.id, name=name, student_number=student_number)
        db.add(student)
        db.flush()

        fixture_path = fixtures_dir / fixture_name
        if fixture_path.exists():
            raw = fixture_path.read_bytes()
            out_name = f"{uuid.uuid4().hex[:12]}-{fixture_name}"
            out_path = uploads_dir / out_name
            out_path.write_bytes(raw)
            db.add(
                Evidence(
                    student_id=student.id,
                    file_name=fixture_name,
                    file_type=FileType.other,
                    file_path=str(out_path),
                    source_type=SourceType.upload,
                )
            )

    db.add(
        AuditEvent(
            teacher_id=current_teacher.id,
            action="seed_demo",
            details_json={"module_id": str(module.id), "project_count": 2, "student_count": 3},
            source=AuditSource.system,
            timestamp=datetime.utcnow(),
        )
    )
    db.commit()

    return {"ok": True, "modules": [str(module.id)]}
