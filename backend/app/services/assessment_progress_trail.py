"""Build the four-stage assessment progress trail for export PDFs."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.assessment import Assessment
from app.models.audit_event import AuditEvent
from app.models.chat_message import ChatMessage
from app.models.enums import AssessmentStatus
from app.models.evidence import Evidence
from app.models.evidence_match import EvidenceMatch
from app.models.generation_run import GenerationRun
from app.models.student import Student
from app.services.assessment_draft_core import (
    _get_module_for_student,
    _load_draft,
)
from app.services.overlap.service import OverlapService, parse_signal_detail


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _build_submission_stage(
    evidence_rows: list[Evidence],
) -> dict[str, Any]:
    files = []
    timestamps: list[datetime] = []
    for ev in evidence_rows:
        uploaded = ev.uploaded_at
        if uploaded:
            timestamps.append(uploaded)
        files.append(
            {
                "id": str(ev.id),
                "file_name": ev.file_name,
                "file_type": ev.file_type.value if ev.file_type else "other",
                "source_type": ev.source_type.value if ev.source_type else "upload",
                "uploaded_at": _iso(uploaded),
                "file_path": ev.file_path,
            }
        )

    completed = len(files) > 0
    return {
        "key": "submission",
        "label": "Submission",
        "status": "completed" if completed else "pending",
        "timestamp": _iso(min(timestamps)) if timestamps else None,
        "source": "student",
        "summary": (
            f"{len(files)} document{'s' if len(files) != 1 else ''} submitted"
            if completed
            else "No submitted documents yet"
        ),
        "content": {"files": files},
    }


def _overlap_ai_items(db: Session, student_id: str, module_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    signals = OverlapService.get_signals_for_student(db, module_id, student_id)
    for signal in signals:
        detail = parse_signal_detail(signal.snippet)
        explanation = detail.get("ai_explanation") or detail.get("metrics_summary")
        passage = detail.get("passage_a") or (signal.snippet or "")[:400]
        items.append(
            {
                "type": "overlap_detection",
                "timestamp": _iso(signal.detected_at),
                "source": "ai",
                "summary": (
                    f"{detail.get('integrity_type', 'overlap')} "
                    f"({signal.overlap_type.value if signal.overlap_type else 'textual'}) "
                    f"— confidence {float(signal.confidence or 0):.0%}"
                ),
                "payload": {
                    "signal_id": str(signal.id),
                    "overlap_type": signal.overlap_type.value if signal.overlap_type else "textual",
                    "integrity_type": detail.get("integrity_type"),
                    "confidence": float(signal.confidence or 0),
                    "status": detail.get("status"),
                    "ai_explanation": explanation,
                    "passage": passage,
                    "detection_method": detail.get("detection_method"),
                },
            }
        )
    return items


def _evidence_match_ai_item(
    db: Session, assessment: Assessment, draft_generated_at: Optional[datetime]
) -> Optional[dict[str, Any]]:
    matches = (
        db.query(EvidenceMatch)
        .filter(EvidenceMatch.assessment_id == assessment.id)
        .all()
    )
    if not matches:
        return None

    run_ts: Optional[datetime] = None
    run = (
        db.query(GenerationRun)
        .filter(GenerationRun.assessment_id == assessment.id)
        .order_by(GenerationRun.created_at.desc())
        .first()
    )
    if run and run.created_at:
        run_ts = run.created_at

    ts = run_ts or draft_generated_at
    criteria_keys = sorted({m.criterion_key for m in matches})
    match_rows = []
    for m in matches:
        match_rows.append(
            {
                "criterion_key": m.criterion_key,
                "confidence_score": m.confidence_score,
                "supporting_quote": m.supporting_quote,
                "rationale": m.rationale,
                "missing_note": m.missing_note,
                "evidence_id": str(m.evidence_id) if m.evidence_id else None,
            }
        )

    return {
        "type": "evidence_match",
        "timestamp": _iso(ts),
        "source": "ai",
        "summary": f"{len(matches)} evidence match(es) across {len(criteria_keys)} criteria",
        "payload": {"criteria_keys": criteria_keys, "matches": match_rows},
    }


def _draft_ai_item(draft: dict[str, Any]) -> Optional[dict[str, Any]]:
    generated_at = _parse_dt(draft.get("generated_at"))
    has_ai = any((draft.get("criteria") or {}).get(k, {}).get("ai") for k in (draft.get("criteria") or {}))
    if not has_ai and not generated_at:
        return None

    criteria_out = []
    defs_by_key = {d["key"]: d for d in draft.get("criteria_defs") or []}
    for key, entry in (draft.get("criteria") or {}).items():
        ai = entry.get("ai")
        if not ai:
            continue
        defn = defs_by_key.get(key, {})
        criteria_out.append(
            {
                "key": key,
                "name": defn.get("name", key),
                "score": ai.get("score"),
                "comment": ai.get("comment"),
                "confidence": ai.get("confidence"),
                "evidence_refs": ai.get("evidence_refs") or [],
            }
        )

    summary = (draft.get("summary") or {}).get("ai")
    grade = (draft.get("overall_grade") or {}).get("ai")

    return {
        "type": "assessment_draft",
        "timestamp": _iso(generated_at),
        "source": "ai",
        "summary": (
            f"AI draft: grade {grade or '—'}, {len(criteria_out)} criteria scored"
            if criteria_out
            else "AI assessment draft generated"
        ),
        "payload": {
            "overall_grade": grade,
            "summary": summary,
            "criteria": criteria_out,
        },
    }


def _questions_ai_item(cache: Any) -> Optional[dict[str, Any]]:
    if not cache or not isinstance(cache, dict):
        return None
    questions = cache.get("questions") or []
    if not questions:
        return None
    total_q = sum(len(q.get("questions") or []) for q in questions)
    return {
        "type": "assessment_questions",
        "timestamp": cache.get("generated_at"),
        "source": "ai",
        "summary": f"{total_q} suggested question(s) for {len(questions)} criteria",
        "payload": {"questions": questions},
    }


def _chat_ai_item(messages: list[ChatMessage]) -> Optional[dict[str, Any]]:
    if not messages:
        return None
    serialized = []
    for m in messages:
        serialized.append(
            {
                "role": m.role,
                "content": m.content,
                "timestamp": _iso(m.timestamp),
                "metadata": m.metadata_json,
            }
        )
    first_ts = messages[0].timestamp
    last_ts = messages[-1].timestamp
    return {
        "type": "assessment_chat",
        "timestamp": _iso(first_ts),
        "source": "ai",
        "summary": (
            f"{len(messages)} chat message(s) "
            f"({first_ts.strftime('%d %b %H:%M') if first_ts else '—'}"
            f" – {last_ts.strftime('%d %b %H:%M') if last_ts else '—'})"
        ),
        "payload": {
            "messages": serialized,
            "message_count": len(messages),
            "first_timestamp": _iso(first_ts),
            "last_timestamp": _iso(last_ts),
        },
    }


def _collect_ai_items(
    db: Session,
    *,
    assessment: Optional[Assessment],
    student_id: str,
    module_id: Optional[str],
) -> list[dict[str, Any]]:
    if assessment is None:
        return []

    draft = _load_draft(assessment)
    draft_ts = _parse_dt(draft.get("generated_at"))
    items: list[dict[str, Any]] = []

    if module_id:
        items.extend(_overlap_ai_items(db, student_id, module_id))

    match_item = _evidence_match_ai_item(db, assessment, draft_ts)
    if match_item:
        items.append(match_item)

    draft_item = _draft_ai_item(draft)
    if draft_item:
        items.append(draft_item)

    q_item = _questions_ai_item(assessment.questions_cache_json)
    if q_item:
        items.append(q_item)

    chat_messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.assessment_id == assessment.id)
        .order_by(ChatMessage.timestamp.asc())
        .all()
    )
    chat_item = _chat_ai_item(chat_messages)
    if chat_item:
        items.append(chat_item)

    def sort_key(item: dict[str, Any]) -> datetime:
        parsed = _parse_dt(item.get("timestamp"))
        return parsed or datetime.min.replace(tzinfo=timezone.utc)

    items.sort(key=sort_key)
    return items


def _build_ai_stage(ai_items: list[dict[str, Any]]) -> dict[str, Any]:
    completed = len(ai_items) > 0
    timestamps = [_parse_dt(i.get("timestamp")) for i in ai_items]
    timestamps = [t for t in timestamps if t is not None]
    stage_ts = min(timestamps) if timestamps else None

    summaries = {
        "overlap_detection": "Overlap detections",
        "evidence_match": "Evidence matching",
        "assessment_draft": "Assessment draft",
        "assessment_questions": "Suggested questions",
        "assessment_chat": "Assessment chat",
    }
    attachment_map = {
        "overlap_detection": "detail/overlap.pdf",
        "evidence_match": "detail/evidence-matches.pdf",
        "assessment_draft": "detail/assessment-draft.pdf",
        "assessment_questions": "detail/suggested-questions.pdf",
        "assessment_chat": "detail/ai-chat.pdf",
    }
    subsections = []
    for item in ai_items:
        subsections.append(
            {
                "type": item["type"],
                "label": summaries.get(item["type"], item["type"]),
                "summary": item.get("summary", ""),
                "timestamp": item.get("timestamp"),
                "attachment": attachment_map.get(item["type"]),
            }
        )

    return {
        "key": "ai_suggestion",
        "label": "AI suggestion",
        "status": "completed" if completed else "pending",
        "timestamp": _iso(stage_ts),
        "source": "ai",
        "summary": (
            f"{len(ai_items)} AI output(s) recorded"
            if completed
            else "Waiting for AI analysis"
        ),
        "content": {"ai_items": ai_items, "subsections": subsections},
    }


def _build_teacher_stage(
    db: Session,
    assessment: Optional[Assessment],
) -> dict[str, Any]:
    if assessment is None:
        return {
            "key": "teacher_decision",
            "label": "Teacher decision",
            "status": "pending",
            "timestamp": None,
            "source": "teacher",
            "summary": "Awaiting teacher review",
            "content": {"decisions": [], "accepted_without_changes": False},
        }

    draft = _load_draft(assessment)
    overrides = []
    override_times: list[datetime] = []

    defs_by_key = {d["key"]: d for d in draft.get("criteria_defs") or []}
    for key, entry in (draft.get("criteria") or {}).items():
        teacher = entry.get("teacher")
        ai = entry.get("ai")
        if not teacher and not entry.get("is_overridden"):
            continue
        if teacher:
            ot = _parse_dt(teacher.get("overridden_at"))
            if ot:
                override_times.append(ot)
            overrides.append(
                {
                    "criterion_key": key,
                    "criterion_name": defs_by_key.get(key, {}).get("name", key),
                    "ai_score": (ai or {}).get("score"),
                    "ai_comment": (ai or {}).get("comment"),
                    "teacher_score": teacher.get("score"),
                    "teacher_comment": teacher.get("comment"),
                    "overridden_at": teacher.get("overridden_at"),
                }
            )

    audit_events = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.assessment_id == assessment.id,
            AuditEvent.action.in_(
                [
                    "assessment.suggestion_overridden",
                    "assessment.chat_refine",
                    "assessment.override_reverted",
                    "assessment.finalized",
                ]
            ),
        )
        .order_by(AuditEvent.timestamp.asc())
        .all()
    )
    audit_rows = [
        {
            "action": e.action,
            "timestamp": _iso(e.timestamp),
            "source": e.source.value if e.source else None,
            "details": e.details_json,
        }
        for e in audit_events
    ]

    finalized = assessment.status == AssessmentStatus.final
    accepted_without_changes = finalized and len(overrides) == 0

    completed = bool(overrides or audit_events or finalized)
    stage_ts: Optional[datetime] = None
    if override_times:
        stage_ts = max(override_times)
    elif finalized and assessment.completed_at:
        stage_ts = assessment.completed_at
    elif audit_events:
        stage_ts = audit_events[-1].timestamp

    if accepted_without_changes:
        summary = "Teacher accepted AI suggestions without modification"
    elif overrides:
        summary = f"Teacher reviewed and updated {len(overrides)} criterion(s)"
    elif completed:
        summary = "Teacher review recorded"
    else:
        summary = "Awaiting teacher review"

    return {
        "key": "teacher_decision",
        "label": "Teacher decision",
        "status": "completed" if completed else "pending",
        "timestamp": _iso(stage_ts),
        "source": "teacher",
        "summary": summary,
        "content": {
            "decisions": overrides,
            "accepted_without_changes": accepted_without_changes,
            "audit_events": audit_rows,
            "attachment": "detail/teacher-decisions.pdf" if len(overrides) > 3 else None,
        },
    }


def _build_final_stage(assessment: Optional[Assessment]) -> dict[str, Any]:
    if assessment is None or assessment.status != AssessmentStatus.final:
        return {
            "key": "final_form",
            "label": "Final form",
            "status": "pending",
            "timestamp": None,
            "source": None,
            "summary": "Assessment not yet finalized",
            "content": {},
        }

    form = assessment.final_form_json or {}
    criteria = form.get("criteria") or {}
    criteria_rows = []
    if isinstance(criteria, dict):
        for key, val in criteria.items():
            if isinstance(val, dict):
                criteria_rows.append(
                    {
                        "key": key,
                        "name": val.get("name", key),
                        "score": val.get("score"),
                        "comment": val.get("comment"),
                    }
                )

    ts = assessment.completed_at or _parse_dt(form.get("finalized_at"))
    return {
        "key": "final_form",
        "label": "Final form",
        "status": "completed",
        "timestamp": _iso(ts),
        "source": "teacher",
        "summary": f"Final grade: {form.get('grade') or '—'}",
        "content": {
            "grade": form.get("grade"),
            "overall_score": form.get("overall_score"),
            "summary": form.get("summary"),
            "teacher_notes": form.get("teacher_notes"),
            "criteria": criteria_rows,
            "finalized_at": form.get("finalized_at"),
        },
    }


def build_progress_trail(
    db: Session,
    *,
    student: Student,
    assessment: Optional[Assessment] = None,
    module_name: Optional[str] = None,
) -> dict[str, Any]:
    """Assemble the four ordered progress-trail stages for PDF export."""
    module = _get_module_for_student(db, student.student_number)
    module_id = str(module.id) if module else None
    if not module_name and module:
        module_name = module.name or ""

    evidence_rows = (
        db.query(Evidence)
        .filter(Evidence.student_id == student.student_number)
        .order_by(Evidence.uploaded_at.asc())
        .all()
    )

    ai_items = _collect_ai_items(
        db,
        assessment=assessment,
        student_id=student.student_number,
        module_id=module_id,
    )

    stages = [
        _build_submission_stage(evidence_rows),
        _build_ai_stage(ai_items),
        _build_teacher_stage(db, assessment),
        _build_final_stage(assessment),
    ]

    return {
        "assessment_id": str(assessment.id) if assessment else None,
        "student_name": student.name,
        "student_number": student.student_number,
        "module_name": module_name or "",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "stages": stages,
        "evidence_files": stages[0]["content"].get("files", []),
        "ai_items": ai_items,
    }
