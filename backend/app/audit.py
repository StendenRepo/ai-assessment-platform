from __future__ import annotations

import json
from datetime import datetime, timezone

from app.store import store


def log_event(
    action: str,
    *,
    module_id: str | None = None,
    project_id: str | None = None,
    student_id: str | None = None,
    detail: dict | None = None,
    teacher: str | None = None,
) -> dict:
    entry = {
        "id": store._new_id(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "module_id": module_id,
        "project_id": project_id,
        "student_id": student_id,
        "teacher": teacher or store.current_teacher,
        "detail": detail or {},
    }
    store.audit_log.append(entry)
    store.save()
    return entry


def query_audit_log(
    *,
    action: str | None = None,
    teacher: str | None = None,
    q: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 100,
) -> dict:
    """Filter audit entries (newest first). Dates: YYYY-MM-DD (UTC, inclusive)."""
    limit = min(max(limit, 1), 500)
    events = list(reversed(store.audit_log))

    if action:
        events = [e for e in events if e.get("action") == action]
    if teacher:
        t = teacher.strip().lower()
        events = [e for e in events if (e.get("teacher") or "").lower() == t]
    if q:
        needle = q.strip().lower()
        if needle:

            def matches(entry: dict) -> bool:
                parts = [
                    entry.get("action", ""),
                    entry.get("teacher", ""),
                    entry.get("module_id", ""),
                    entry.get("project_id", ""),
                    entry.get("student_id", ""),
                ]
                try:
                    parts.append(json.dumps(entry.get("detail") or {}))
                except TypeError:
                    parts.append(str(entry.get("detail")))
                return needle in " ".join(parts).lower()

            events = [e for e in events if matches(e)]

    if from_date:
        events = [e for e in events if (e.get("timestamp") or "")[:10] >= from_date[:10]]
    if to_date:
        events = [e for e in events if (e.get("timestamp") or "")[:10] <= to_date[:10]]

    filtered_count = len(events)
    events = events[:limit]

    actions = sorted({e.get("action", "") for e in store.audit_log if e.get("action")})
    teachers = sorted({e.get("teacher") for e in store.audit_log if e.get("teacher")})

    return {
        "events": events,
        "total": len(store.audit_log),
        "count": filtered_count,
        "shown": len(events),
        "actions": actions,
        "teachers": teachers,
    }
