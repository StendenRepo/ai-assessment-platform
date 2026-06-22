"""AI suggestion generation and teacher overrides."""
from __future__ import annotations

import copy
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.assessment import Assessment
from app.models.teacher import Teacher
from app.models.enums import AuditSource
from app.models.evidence import Evidence
from app.services import audit_service
from app.services.evidence_matcher import match_criterion_to_evidence, persist_matches
from app.services.assessment_draft_core import (
    _assert_editable,
    _compute_overall_score,
    _effective_value,
    _get_module_for_student,
    _load_draft,
    _llm_assess_criterion,
    _llm_summary,
    _now,
    _recording_context,
    _rubric_text,
    _persist_draft,
    _score_to_grade,
    _build_evidence_refs,
)

def generate_suggestions(
    db: Session,
    *,
    assessment: Assessment,
    teacher: Teacher,
) -> dict[str, Any]:
    """Run grounded AI analysis and populate draft_form_json."""
    _assert_editable(assessment)

    module = _get_module_for_student(db, assessment.student_id)
    rubric = _rubric_text(db, module)
    recording_text = _recording_context(db, assessment.id)

    evidence_rows = (
        db.query(Evidence)
        .filter(Evidence.student_id == assessment.student_id)
        .order_by(Evidence.uploaded_at.desc())
        .all()
    )

    draft = _load_draft(assessment)
    defs = draft["criteria_defs"]
    now = _now()
    criteria_results: list[dict] = []

    for d in defs:
        key = d["key"]
        matches = match_criterion_to_evidence(key, d["name"], d["description"], evidence_rows)
        persist_matches(db, assessment_id=assessment.id, criterion_key=key, matches=matches)

        suggestion = _llm_assess_criterion(d, matches, rubric, recording_text)
        if suggestion.get("missing_gaps"):
            suggestion["comment"] = (
                f"{suggestion['comment']} Gap: {suggestion['missing_gaps']}"
            )

        ai_value = {
            "score": suggestion["score"],
            "comment": suggestion["comment"],
            "generated_at": now.isoformat(),
            "confidence": suggestion.get("confidence"),
            "evidence_refs": _build_evidence_refs(matches),
        }

        existing = draft["criteria"].get(key, {})
        overridden = bool(existing.get("is_overridden"))

        entry = {
            "ai": ai_value,
            "teacher": existing.get("teacher"),
            "is_overridden": overridden,
            "effective": _effective_value(ai_value, existing.get("teacher"), overridden),
        }
        draft["criteria"][key] = entry
        criteria_results.append({"key": key, **suggestion})

    summary_text = _llm_summary(criteria_results, defs)
    draft["summary"]["ai"] = summary_text
    if not draft["summary"].get("teacher"):
        draft["summary"]["effective"] = summary_text

    overall = _compute_overall_score(draft["criteria"], defs)
    if overall is not None:
        grade = _score_to_grade(overall)
        draft["overall_grade"]["ai"] = grade
        if not draft["overall_grade"].get("teacher"):
            draft["overall_grade"]["effective"] = grade

    draft["generated_at"] = now.isoformat()
    draft["locked"] = False

    _persist_draft(db, assessment, draft)

    audit_service.log_action(
        db,
        action="assessment.suggestions_generated",
        source=AuditSource.ai,
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        assessment_id=assessment.id,
        details={
            "criteria_count": len(defs),
            "evidence_count": len(evidence_rows),
            "overall_score": overall,
        },
        commit=False,
    )
    db.commit()
    return draft


def apply_overrides(
    db: Session,
    *,
    assessment: Assessment,
    teacher: Teacher,
    overrides: list[dict],
    summary: Optional[str] = None,
    overall_grade: Optional[str] = None,
) -> dict[str, Any]:
    """Apply teacher overrides; AI values are retained for audit."""
    _assert_editable(assessment)
    draft = _load_draft(assessment)
    defs_by_key = {d["key"]: d for d in draft["criteria_defs"]}
    now = _now()

    for item in overrides:
        key = item["criterion_key"]
        if key not in defs_by_key:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown criterion: {key}",
            )
        max_score = float(defs_by_key[key]["max_score"])
        score = item.get("score")
        if score is not None and (score < 0 or score > max_score):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Score for {key} must be between 0 and {max_score}",
            )

        entry = draft["criteria"].setdefault(key, {"ai": None, "teacher": None})
        eff = entry.get("effective") or {}
        new_score = score if score is not None else eff.get("score")
        new_comment = (
            item.get("comment") if item.get("comment") is not None else eff.get("comment")
        )
        if new_score == eff.get("score") and new_comment == eff.get("comment"):
            continue

        ai_snapshot = copy.deepcopy(entry.get("ai"))
        teacher_value = {
            "score": new_score,
            "comment": new_comment,
            "overridden_at": now.isoformat(),
        }
        entry["teacher"] = teacher_value
        entry["is_overridden"] = True
        entry["effective"] = {
            "score": teacher_value.get("score"),
            "comment": teacher_value.get("comment"),
        }
        if ai_snapshot:
            entry["ai"] = ai_snapshot

        audit_service.log_action(
            db,
            action="assessment.suggestion_overridden",
            teacher_id=teacher.id,
            teacher_name=teacher.name,
            assessment_id=assessment.id,
            details={
                "criterion_key": key,
                "ai": ai_snapshot,
                "teacher": teacher_value,
            },
            commit=False,
        )

    if summary is not None:
        summary_eff = (draft.get("summary") or {}).get("effective")
        if summary != summary_eff:
            audit_service.log_action(
                db,
                action="assessment.suggestion_overridden",
                teacher_id=teacher.id,
                teacher_name=teacher.name,
                assessment_id=assessment.id,
                details={
                    "field": "summary",
                    "ai": (draft.get("summary") or {}).get("ai"),
                    "teacher": summary,
                },
                commit=False,
            )
            draft["summary"]["teacher"] = summary
            draft["summary"]["effective"] = summary
    if overall_grade is not None:
        grade_eff = (draft.get("overall_grade") or {}).get("effective")
        if overall_grade != grade_eff:
            audit_service.log_action(
                db,
                action="assessment.suggestion_overridden",
                teacher_id=teacher.id,
                teacher_name=teacher.name,
                assessment_id=assessment.id,
                details={
                    "field": "overall_grade",
                    "ai": (draft.get("overall_grade") or {}).get("ai"),
                    "teacher": overall_grade,
                },
                commit=False,
            )
            draft["overall_grade"]["teacher"] = overall_grade
            draft["overall_grade"]["effective"] = overall_grade

    _persist_draft(db, assessment, draft)
    db.commit()
    return draft


def revert_criterion(
    db: Session,
    *,
    assessment: Assessment,
    teacher: Teacher,
    criterion_key: str,
) -> dict[str, Any]:
    _assert_editable(assessment)
    draft = _load_draft(assessment)
    entry = draft["criteria"].get(criterion_key)
    if not entry:
        raise HTTPException(status_code=404, detail="Criterion not found in draft")

    ai_value = entry.get("ai")
    entry["teacher"] = None
    entry["is_overridden"] = False
    entry["effective"] = _effective_value(ai_value, None, False)

    _persist_draft(db, assessment, draft)
    audit_service.log_action(
        db,
        action="assessment.override_reverted",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        assessment_id=assessment.id,
        details={"criterion_key": criterion_key},
        commit=False,
    )
    db.commit()
    return draft
