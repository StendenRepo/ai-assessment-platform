"""Assessment finalization and API serializers."""
from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.assessment import Assessment
from app.models.audit_event import AuditEvent
from app.models.enums import AssessmentStatus
from app.models.evidence_match import EvidenceMatch
from app.models.teacher import Teacher
from app.services import audit_service
from app.services.assessment_draft_core import (
    DRAFT_VERSION,
    _compute_overall_score,
    _load_draft,
    _overlap_alerts_for_student,
    _score_to_grade,
    _now,
)

def finalize_assessment(
    db: Session,
    *,
    assessment: Assessment,
    teacher: Teacher,
    teacher_notes: Optional[str] = None,
) -> dict[str, Any]:
    """Lock the assessment and persist the final snapshot."""
    if assessment.status == AssessmentStatus.final:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Assessment is already finalized",
        )

    draft = _load_draft(assessment)
    if not draft["criteria"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot finalize without assessment criteria — generate suggestions first",
        )

    defs = draft["criteria_defs"]
    missing = [
        d["name"]
        for d in defs
        if (draft["criteria"].get(d["key"], {}).get("effective") or {}).get("score") is None
    ]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Complete all criterion scores before finalizing: {', '.join(missing)}",
        )
    overall = _compute_overall_score(draft["criteria"], defs)
    grade = (draft.get("overall_grade") or {}).get("effective")
    if not grade and overall is not None:
        grade = _score_to_grade(overall)

    now = _now()
    final_payload = {
        "version": DRAFT_VERSION,
        "finalized_at": now.isoformat(),
        "finalized_by": str(teacher.id),
        "teacher_notes": teacher_notes,
        "overall_score": overall,
        "grade": grade,
        "summary": (draft.get("summary") or {}).get("effective"),
        "criteria": {},
        "transparency": {},
    }

    for d in defs:
        key = d["key"]
        entry = draft["criteria"].get(key, {})
        eff = entry.get("effective") or {}
        final_payload["criteria"][key] = {
            "name": d["name"],
            "score": eff.get("score"),
            "comment": eff.get("comment"),
        }
        final_payload["transparency"][key] = {
            "ai": entry.get("ai"),
            "teacher": entry.get("teacher"),
            "is_overridden": entry.get("is_overridden", False),
        }

    assessment.status = AssessmentStatus.final
    assessment.final_form_json = final_payload
    assessment.completed_at = now
    draft["locked"] = True
    assessment.draft_form_json = draft

    db.add(assessment)
    db.commit()
    db.refresh(assessment)

    audit_service.log_action(
        db,
        action="assessment.finalized",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        assessment_id=assessment.id,
        details={"grade": grade, "overall_score": overall},
    )
    return final_payload




def get_audit_trail(db: Session, assessment_id: UUID) -> list[AuditEvent]:
    return (
        db.query(AuditEvent)
        .filter(AuditEvent.assessment_id == assessment_id)
        .order_by(AuditEvent.timestamp.desc())
        .limit(50)
        .all()
    )


def count_evidence_matches(db: Session, assessment_id: UUID) -> int:
    return (
        db.query(EvidenceMatch)
        .filter(EvidenceMatch.assessment_id == assessment_id)
        .count()
    )


def build_draft_out(assessment: Assessment, db: Session) -> dict[str, Any]:
    """Serialize draft for API responses."""
    draft = _load_draft(assessment)
    if assessment.status == AssessmentStatus.final and assessment.final_form_json:
        draft["locked"] = True

    defs = draft["criteria_defs"]
    criteria_out = []
    for d in defs:
        key = d["key"]
        entry = draft["criteria"].get(key, {})
        criteria_out.append(
            {
                "key": key,
                "definition": d,
                "ai": entry.get("ai"),
                "teacher": entry.get("teacher"),
                "effective": entry.get("effective"),
                "is_overridden": bool(entry.get("is_overridden")),
            }
        )

    overall = _compute_overall_score(draft["criteria"], defs)
    locked = assessment.status == AssessmentStatus.final or draft.get("locked")
    has_ai = any(c.get("ai") for c in draft["criteria"].values())
    missing_scores = [
        d["name"]
        for d in defs
        if (draft["criteria"].get(d["key"], {}).get("effective") or {}).get("score") is None
    ]
    finalize_blocked_reason = None
    if has_ai and missing_scores:
        finalize_blocked_reason = (
            f"Complete scores for: {', '.join(missing_scores)}"
        )
    overlap_alerts = _overlap_alerts_for_student(db, assessment.student_id)

    return {
        "assessment_id": str(assessment.id),
        "status": assessment.status.value,
        "locked": locked,
        "version": draft.get("version", DRAFT_VERSION),
        "generated_at": draft.get("generated_at"),
        "criteria": criteria_out,
        "summary": draft.get("summary") or {},
        "overall_grade": draft.get("overall_grade") or {},
        "overall_score": overall,
        "evidence_match_count": count_evidence_matches(db, assessment.id),
        "overlap_alerts": overlap_alerts,
        "finalize_blocked_reason": finalize_blocked_reason,
        "can_edit": not locked,
        "can_chat": not locked and has_ai,
        "can_finalize": not locked and has_ai and not missing_scores,
    }


def build_final_out(assessment: Assessment, db: Session) -> dict[str, Any]:
    if assessment.status != AssessmentStatus.final or not assessment.final_form_json:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment has not been finalized",
        )
    form = assessment.final_form_json
    draft_view = build_draft_out(assessment, db)
    audit = get_audit_trail(db, assessment.id)

    return {
        "assessment_id": str(assessment.id),
        "status": assessment.status.value,
        "finalized_at": assessment.completed_at,
        "form": form,
        "criteria": draft_view["criteria"],
        "summary": form.get("summary"),
        "overall_grade": form.get("grade"),
        "overall_score": form.get("overall_score"),
        "audit_summary": [
            {
                "action": e.action,
                "source": e.source.value if e.source else None,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "details": e.details_json,
            }
            for e in audit
        ],
    }
