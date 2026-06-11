"""Assessment draft workflow: AI suggestions, teacher overrides, chat refine, finalize.

Implements G2-146 (overrule), G2-147 (chat refine), G2-150 (finalize).
"""
from __future__ import annotations

import copy
import json
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.assessment import Assessment
from app.models.audit_event import AuditEvent
from app.models.chat_message import ChatMessage
from app.models.enums import AssessmentStatus, AuditSource
from app.models.evidence import Evidence
from app.models.evidence_match import EvidenceMatch
from app.models.file_record import FileRecord
from app.models.module import Module
from app.models.project import Project
from app.models.recording import Recording
from app.models.student import Student
from app.models.teacher import Teacher
from app.services import audit_service
from app.services.evidence_matcher import match_criterion_to_evidence, persist_matches
from app.services import ollama_client
from app.services.overlap_service import OverlapService, parse_signal_detail

DRAFT_VERSION = 1

DEFAULT_CRITERIA: list[dict[str, Any]] = [
    {
        "key": "crit-1",
        "name": "Code Quality",
        "description": "Readable, maintainable and well-structured code",
        "max_score": 10,
        "category": "Technical",
    },
    {
        "key": "crit-2",
        "name": "Documentation",
        "description": "Completeness and clarity of technical documentation",
        "max_score": 10,
        "category": "Communication",
    },
    {
        "key": "crit-3",
        "name": "Collaboration",
        "description": "Contribution to teamwork and communication",
        "max_score": 10,
        "category": "Process",
    },
    {
        "key": "crit-4",
        "name": "Testing",
        "description": "Unit tests, integration tests and test coverage",
        "max_score": 10,
        "category": "Technical",
    },
    {
        "key": "crit-5",
        "name": "Presentation",
        "description": "Oral presentation and communication skills",
        "max_score": 10,
        "category": "Communication",
    },
]

_ASSESSMENT_SYSTEM_PROMPT = """You are an expert university assessor assistant operating on-premises.
You ONLY analyse uploaded student evidence and rubric criteria — never invent facts.
Return valid JSON only. Ground every score and comment in the evidence provided.
When evidence is weak or missing, say so explicitly and score conservatively.
Do not modify or rewrite student evidence text — only assess it."""


class AssessmentLockedError(ValueError):
    """Raised when mutating a finalized assessment."""


def _now() -> datetime:
    return datetime.utcnow()


def _assert_editable(assessment: Assessment) -> None:
    if assessment.status == AssessmentStatus.final:
        raise AssessmentLockedError("Assessment is finalized and locked from changes")


def _empty_draft() -> dict[str, Any]:
    return {
        "version": DRAFT_VERSION,
        "criteria_defs": copy.deepcopy(DEFAULT_CRITERIA),
        "criteria": {},
        "summary": {"ai": None, "teacher": None, "effective": None},
        "overall_grade": {"ai": None, "teacher": None, "effective": None},
        "locked": False,
        "generated_at": None,
    }


def _load_draft(assessment: Assessment) -> dict[str, Any]:
    raw = assessment.draft_form_json
    if not raw or not isinstance(raw, dict):
        return _empty_draft()
    draft = copy.deepcopy(raw)
    draft.setdefault("version", DRAFT_VERSION)
    draft.setdefault("criteria_defs", copy.deepcopy(DEFAULT_CRITERIA))
    draft.setdefault("criteria", {})
    draft.setdefault("summary", {"ai": None, "teacher": None, "effective": None})
    draft.setdefault("overall_grade", {"ai": None, "teacher": None, "effective": None})
    draft.setdefault("locked", assessment.status == AssessmentStatus.final)
    return draft


def _save_draft(db: Session, assessment: Assessment, draft: dict[str, Any]) -> None:
    assessment.draft_form_json = draft
    db.add(assessment)
    db.commit()
    db.refresh(assessment)


def _effective_value(ai: dict | None, teacher: dict | None, overridden: bool) -> dict | None:
    if overridden and teacher:
        return {
            "score": teacher.get("score"),
            "comment": teacher.get("comment"),
        }
    if ai:
        return {"score": ai.get("score"), "comment": ai.get("comment")}
    if teacher:
        return {"score": teacher.get("score"), "comment": teacher.get("comment")}
    return None


def _compute_overall_score(criteria: dict, defs: list[dict]) -> Optional[float]:
    scores = []
    for d in defs:
        key = d["key"]
        entry = criteria.get(key) or {}
        eff = entry.get("effective") or {}
        score = eff.get("score")
        if score is not None:
            scores.append(float(score))
    if not scores:
        return None
    return round(sum(scores) / len(scores), 2)


def _score_to_grade(avg: float, max_score: float = 10) -> str:
    pct = (avg / max_score) * 100 if max_score else 0
    if pct >= 90:
        return "A"
    if pct >= 85:
        return "A-"
    if pct >= 80:
        return "B+"
    if pct >= 75:
        return "B"
    if pct >= 70:
        return "B-"
    if pct >= 65:
        return "C+"
    if pct >= 60:
        return "C"
    if pct >= 55:
        return "C-"
    if pct >= 50:
        return "D"
    return "F"


def _get_module_for_student(db: Session, student_id: str) -> Optional[Module]:
    student = db.get(Student, student_id)
    if not student or not student.projects:
        return None
    project = student.projects[0]
    return db.get(Module, project.module_id)


def _rubric_text(db: Session, module: Optional[Module]) -> str:
    if not module or not module.rubric_file_id:
        return ""
    record = db.get(FileRecord, module.rubric_file_id)
    return (record.extracted_text or "") if record else ""


def _recording_context(db: Session, assessment_id: UUID) -> str:
    recordings = (
        db.query(Recording)
        .filter(Recording.assessment_id == assessment_id, Recording.deleted_at.is_(None))
        .order_by(Recording.sequence_number)
        .all()
    )
    parts = []
    for rec in recordings:
        if rec.transcript_text:
            parts.append(f"[{rec.display_name}]: {rec.transcript_text[:2000]}")
    return "\n\n".join(parts)


def _heuristic_suggestion(
    criterion: dict,
    matches: list,
    max_score: float,
) -> dict[str, Any]:
    """Deterministic fallback when the LLM is unavailable."""
    if not matches or (matches[0].missing_note and not matches[0].quote):
        note = matches[0].missing_note if matches else "No evidence available."
        return {
            "score": round(max_score * 0.4, 1),
            "comment": (
                f"Insufficient grounded evidence for {criterion['name']}. "
                f"{note} Manual review recommended."
            ),
            "confidence": 0.35,
        }

    best = matches[0]
    confidence = best.confidence or 0.5
    score = round(min(max_score, max(0, confidence * max_score * 1.15)), 1)
    quote_preview = (best.quote or "")[:200]
    comment = (
        f"Evidence in [[{best.file_name}]] supports {criterion['name'].lower()}: "
        f'"{quote_preview}..." '
        f"(retrieval confidence {confidence:.0%})."
    )
    if best.missing_note:
        comment += f" Note: {best.missing_note}"
    return {"score": score, "comment": comment, "confidence": confidence}


def _overlap_alerts_for_student(db: Session, student_id: str) -> list[dict[str, Any]]:
    """Overlap signals involving this student (for assessment review warnings)."""
    module = _get_module_for_student(db, student_id)
    if not module:
        return []
    signals = OverlapService.get_signals_for_student(db, str(module.id), student_id)
    alerts: list[dict[str, Any]] = []
    for signal in signals[:8]:
        detail = parse_signal_detail(signal.snippet)
        row_status = detail.get("status")
        if not row_status:
            row_status = "confirmed" if (signal.confidence or 0) >= 0.55 else "possible"
        other_id = (
            signal.student_b_id
            if signal.student_a_id == student_id
            else signal.student_a_id
        )
        alerts.append(
            {
                "signal_id": str(signal.id),
                "status": row_status,
                "confidence": float(signal.confidence or 0),
                "other_student_id": other_id,
                "overlap_type": signal.overlap_type.value if signal.overlap_type else "textual",
                "snippet": (detail.get("passage_a") or signal.snippet or "")[:300],
            }
        )
    return alerts


def _gather_evidence_for_chat(
    draft: dict[str, Any],
    evidence_rows: list[Evidence],
    focus_keys: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """Collect read-only evidence quotes to ground chat refinements."""
    seen: set[tuple[str, str]] = set()
    refs: list[dict[str, Any]] = []
    defs_by_key = {d["key"]: d for d in draft["criteria_defs"]}
    keys = focus_keys or [d["key"] for d in draft["criteria_defs"]]

    for key in keys:
        entry = draft["criteria"].get(key, {})
        ai = entry.get("ai") or {}
        for ref in ai.get("evidence_refs") or []:
            dedup = (ref.get("file_name") or "", (ref.get("quote") or "")[:120])
            if dedup in seen:
                continue
            seen.add(dedup)
            refs.append({**ref, "criterion_key": key})

        d = defs_by_key.get(key)
        if d and len(refs) < 12:
            matches = match_criterion_to_evidence(
                key, d["name"], d["description"], evidence_rows
            )
            for m in matches:
                dedup = (m.file_name, m.quote[:120])
                if dedup in seen:
                    continue
                seen.add(dedup)
                refs.append(
                    {
                        "evidence_id": str(m.evidence_id) if m.evidence_id else None,
                        "file_name": m.file_name,
                        "quote": m.quote,
                        "confidence": m.confidence,
                        "missing_note": m.missing_note,
                        "criterion_key": key,
                    }
                )
    return refs[:15]


def _comment_cites_evidence(comment: str, evidence_refs: list[dict]) -> bool:
    """Heuristic: chat comment should reference at least one evidence file name."""
    if not comment:
        return True
    named_refs = [r for r in evidence_refs if r.get("file_name")]
    if not named_refs:
        return True
    lower = comment.lower()
    return any(ref["file_name"].lower() in lower for ref in named_refs)


def _build_evidence_refs(matches: list) -> list[dict]:
    refs = []
    for m in matches:
        refs.append(
            {
                "evidence_id": str(m.evidence_id) if m.evidence_id else None,
                "file_name": m.file_name,
                "quote": m.quote,
                "confidence": m.confidence,
                "missing_note": m.missing_note,
            }
        )
    return refs


def _llm_assess_criterion(
    criterion: dict,
    matches: list,
    rubric_excerpt: str,
    recording_text: str,
) -> dict[str, Any]:
    evidence_block = json.dumps(_build_evidence_refs(matches), indent=2)
    prompt = f"""Assess ONE rubric criterion for a student submission.

Criterion: {criterion['name']}
Description: {criterion['description']}
Max score: {criterion['max_score']}

Rubric context (excerpt):
{rubric_excerpt[:1500] or 'No rubric text uploaded.'}

Interview / recording context:
{recording_text[:1500] or 'No recording transcripts.'}

Retrieved evidence chunks (READ ONLY — do not rewrite):
{evidence_block}

Return JSON:
{{
  "score": <number 0-{criterion['max_score']}>,
  "comment": "<2-4 sentences citing specific evidence file names and quotes>",
  "confidence": <0.0-1.0>,
  "missing_gaps": "<optional note if evidence is thin>"
}}"""
    raw = ollama_client.generate(prompt, system=_ASSESSMENT_SYSTEM_PROMPT, temperature=0.15)
    parsed = ollama_client.parse_json_response(raw or "")
    if parsed and parsed.get("score") is not None:
        return {
            "score": float(parsed["score"]),
            "comment": str(parsed.get("comment") or ""),
            "confidence": float(parsed.get("confidence") or 0.7),
            "missing_gaps": parsed.get("missing_gaps"),
        }
    return _heuristic_suggestion(criterion, matches, float(criterion["max_score"]))


def _llm_summary(criteria_results: list[dict], defs: list[dict]) -> str:
    lines = []
    for d in defs:
        res = next((r for r in criteria_results if r["key"] == d["key"]), None)
        if res:
            lines.append(f"- {d['name']}: {res.get('score')}/10 — {res.get('comment', '')[:120]}")
    prompt = f"""Write a concise 3-5 sentence assessment summary for the lecturer.
Base it ONLY on these criterion analyses (do not invent evidence):

{chr(10).join(lines)}

Return JSON: {{"summary": "<paragraph>"}}"""
    raw = ollama_client.generate(prompt, system=_ASSESSMENT_SYSTEM_PROMPT, temperature=0.2)
    parsed = ollama_client.parse_json_response(raw or "")
    if parsed and parsed.get("summary"):
        return str(parsed["summary"])
    if lines:
        return (
            "AI draft summary based on uploaded evidence. "
            + " ".join(line.split("—", 1)[-1].strip() for line in lines[:3])
        )
    return "AI analysis pending — generate suggestions after uploading evidence."


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

    _save_draft(db, assessment, draft)

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
    )
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
    """G2-146: teacher overrules AI suggestions; both values retained."""
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

    _save_draft(db, assessment, draft)
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

    _save_draft(db, assessment, draft)
    audit_service.log_action(
        db,
        action="assessment.override_reverted",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        assessment_id=assessment.id,
        details={"criterion_key": criterion_key},
    )
    return draft


def chat_refine(
    db: Session,
    *,
    assessment: Assessment,
    teacher: Teacher,
    message: str,
) -> tuple[str, dict[str, Any]]:
    """G2-147: teacher chats to refine AI analysis only (not evidence)."""
    _assert_editable(assessment)
    draft = _load_draft(assessment)
    if not draft["criteria"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Generate AI suggestions before using chat refinement",
        )

    teacher_msg = ChatMessage(
        assessment_id=assessment.id,
        role="teacher",
        content=message.strip(),
    )
    db.add(teacher_msg)
    db.flush()

    history = (
        db.query(ChatMessage)
        .filter(ChatMessage.assessment_id == assessment.id)
        .order_by(ChatMessage.timestamp)
        .all()
    )

    evidence_rows = (
        db.query(Evidence)
        .filter(Evidence.student_id == assessment.student_id)
        .all()
    )
    evidence_index = {str(e.id): e.file_name for e in evidence_rows}
    evidence_refs = _gather_evidence_for_chat(draft, evidence_rows)
    defs_by_key = {d["key"]: d for d in draft["criteria_defs"]}

    current_analysis = []
    for d in draft["criteria_defs"]:
        key = d["key"]
        entry = draft["criteria"].get(key, {})
        eff = entry.get("effective") or {}
        ai = entry.get("ai") or {}
        current_analysis.append(
            {
                "criterion": d["name"],
                "key": key,
                "ai_score": ai.get("score"),
                "ai_comment": ai.get("comment"),
                "effective_score": eff.get("score"),
                "effective_comment": eff.get("comment"),
                "is_overridden": entry.get("is_overridden", False),
            }
        )

    chat_messages = [
        {
            "role": "system",
            "content": (
                _ASSESSMENT_SYSTEM_PROMPT
                + "\nThe teacher is refining YOUR analysis only. "
                "Never modify student evidence text. "
                "If a criterion is teacher-overridden (is_overridden=true), "
                "do not change its effective score/comment — only refine non-overridden criteria "
                "or provide advisory notes."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Current AI analysis JSON:\n{json.dumps(current_analysis, indent=2)}\n\n"
                f"Evidence file index (read-only): {json.dumps(evidence_index)}\n\n"
                "Retrieved evidence quotes (READ ONLY — do not rewrite or invent):\n"
                f"{json.dumps(evidence_refs, indent=2)}\n\n"
                "Respond with JSON:\n"
                "{\n"
                '  "reply": "<conversational reply to teacher>",\n'
                '  "updates": [\n'
                '    {"criterion_key": "crit-1", "score": 8, "comment": "..."}\n'
                "  ],\n"
                '  "summary": "<optional updated overall summary>"\n'
                "}\n"
                "Only include updates for criteria the teacher asked to change and that are NOT overridden. "
                "Every updated comment MUST cite specific evidence file names and stay consistent with the quotes above."
            ),
        },
    ]
    for msg in history[-12:]:
        role = "assistant" if msg.role == "assistant" else "user"
        chat_messages.append({"role": role, "content": msg.content})

    raw = ollama_client.chat(chat_messages, temperature=0.25)
    parsed = ollama_client.parse_json_response(raw or "")

    if not parsed:
        reply = (
            raw
            or "I could not reach the on-premise model. "
            "Your message was saved — try again when Ollama is available."
        )
        updates = []
        summary_update = None
    else:
        reply = str(parsed.get("reply") or "I've updated the analysis based on your feedback.")
        updates = parsed.get("updates") or []
        summary_update = parsed.get("summary")

    now = _now()
    applied_changes: list[dict[str, Any]] = []
    for upd in updates:
        key = upd.get("criterion_key")
        if not key:
            continue
        entry = draft["criteria"].get(key)
        if not entry or entry.get("is_overridden"):
            continue
        ai = copy.deepcopy(entry.get("ai") or {})
        prior_score = ai.get("score")
        prior_comment = ai.get("comment")
        criterion_refs = [r for r in evidence_refs if r.get("criterion_key") == key] or evidence_refs
        new_comment = str(upd["comment"]) if upd.get("comment") else None
        if new_comment and not _comment_cites_evidence(new_comment, criterion_refs):
            continue
        if upd.get("score") is not None:
            ai["score"] = float(upd["score"])
        if new_comment:
            ai["comment"] = new_comment
        ai["generated_at"] = now.isoformat()
        ai["refined_via_chat"] = True
        d = defs_by_key.get(key)
        if d:
            matches = match_criterion_to_evidence(
                key, d["name"], d["description"], evidence_rows
            )
            ai["evidence_refs"] = _build_evidence_refs(matches)
            persist_matches(
                db, assessment_id=assessment.id, criterion_key=key, matches=matches
            )
        entry["ai"] = ai
        entry["effective"] = _effective_value(ai, entry.get("teacher"), False)
        applied_changes.append(
            {
                "criterion_key": key,
                "before": {"score": prior_score, "comment": prior_comment},
                "after": {"score": ai.get("score"), "comment": ai.get("comment")},
            }
        )

    if summary_update and not draft["summary"].get("teacher"):
        draft["summary"]["ai"] = summary_update
        draft["summary"]["effective"] = summary_update

    overall = _compute_overall_score(draft["criteria"], draft["criteria_defs"])
    if overall is not None and not draft["overall_grade"].get("teacher"):
        grade = _score_to_grade(overall)
        draft["overall_grade"]["ai"] = grade
        draft["overall_grade"]["effective"] = grade

    assistant_msg = ChatMessage(
        assessment_id=assessment.id,
        role="assistant",
        content=reply,
    )
    db.add(assistant_msg)
    _save_draft(db, assessment, draft)

    audit_service.log_action(
        db,
        action="assessment.chat_refine",
        source=AuditSource.ai,
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        assessment_id=assessment.id,
        details={
            "teacher_message": message[:500],
            "updates_requested": len(updates),
            "updates_applied": len(applied_changes),
            "changes": applied_changes,
        },
    )
    return reply, draft


def finalize_assessment(
    db: Session,
    *,
    assessment: Assessment,
    teacher: Teacher,
    teacher_notes: Optional[str] = None,
) -> dict[str, Any]:
    """G2-150: lock form and persist final snapshot."""
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


def list_chat_messages(db: Session, assessment_id: UUID) -> list[ChatMessage]:
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.assessment_id == assessment_id)
        .order_by(ChatMessage.timestamp)
        .all()
    )


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
