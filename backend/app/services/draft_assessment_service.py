"""Assessment draft workflow: AI suggestions, teacher overrides, chat refine, finalize.

Implements G2-146 (overrule), G2-147 (chat refine), G2-150 (finalize).
"""
from __future__ import annotations

import copy
import json
import re
import uuid
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

_CHAT_DISCUSS_SYSTEM_PROMPT = """You are an expert university assessor advisor helping a lecturer discuss a student assessment.

You have the current AI draft scores, uploaded evidence, module rubric, module book, and interview transcripts.

Rules:
- Answer questions, explain reasoning, compare evidence to rubric expectations, and debate scores conversationally.
- Reference specific evidence file names when relevant.
- You may suggest what could change, but do NOT output JSON or claim scores have been changed.
- The lecturer will use a separate Refine action to commit changes to the form.
- Never invent evidence or rewrite student work.
- Be clear, helpful, and concise."""

_CHAT_PROPOSE_SYSTEM_PROMPT = """You are an expert university assessor assistant. Based on the lecturer conversation and assessment context, propose criterion updates grounded in uploaded evidence.

Rules:
- If the conversation agreed on new scores, you MUST include them in updates[] — never return an empty updates array when scores were discussed.
- Use criterion_key values exactly as provided in the criteria catalog (e.g. crit-1, crit-2).
- Only propose changes for criteria that are NOT teacher-overridden (is_overridden=false).
- Every updated comment should mention evidence when available; if evidence is thin, say so explicitly.
- Respond with a single JSON object only (no markdown fences).

Required JSON shape:
{
  "reply": "Brief summary of what you are proposing and why.",
  "updates": [
    {"criterion_key": "crit-1", "score": 0, "comment": "No code evidence in upload.pdf — score lowered per discussion."}
  ],
  "summary": null
}

Use null for summary if the overall summary should stay unchanged. Never copy placeholder text from these instructions."""


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


def _module_book_text(db: Session, module: Optional[Module]) -> str:
    if not module or not module.module_book_id:
        return ""
    record = db.get(FileRecord, module.module_book_id)
    return (record.extracted_text or "") if record else ""


def _build_current_analysis(draft: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for d in draft["criteria_defs"]:
        key = d["key"]
        entry = draft["criteria"].get(key, {})
        eff = entry.get("effective") or {}
        ai = entry.get("ai") or {}
        rows.append(
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
    return rows


def _build_assessment_context(
    db: Session,
    *,
    assessment: Assessment,
    draft: dict[str, Any],
    criterion_key: Optional[str] = None,
) -> dict[str, Any]:
    module = _get_module_for_student(db, assessment.student_id)
    evidence_rows = (
        db.query(Evidence)
        .filter(Evidence.student_id == assessment.student_id)
        .order_by(Evidence.uploaded_at.desc())
        .all()
    )
    focus_keys = [criterion_key] if criterion_key else None
    evidence_refs = _gather_evidence_for_chat(draft, evidence_rows, focus_keys=focus_keys)
    return {
        "module": module,
        "evidence_rows": evidence_rows,
        "evidence_index": {str(e.id): e.file_name for e in evidence_rows},
        "evidence_refs": evidence_refs,
        "rubric": _rubric_text(db, module),
        "module_book": _module_book_text(db, module),
        "recording_text": _recording_context(db, assessment.id),
        "current_analysis": _build_current_analysis(draft),
        "defs_by_key": {d["key"]: d for d in draft["criteria_defs"]},
    }


def _context_block(ctx: dict[str, Any], *, focus_criterion_key: Optional[str] = None) -> str:
    focus_note = ""
    if focus_criterion_key:
        name = ctx["defs_by_key"].get(focus_criterion_key, {}).get("name", focus_criterion_key)
        focus_note = f"\nFocus criterion for this message: {name} ({focus_criterion_key})\n"
    return (
        f"{focus_note}"
        f"Current analysis:\n{json.dumps(ctx['current_analysis'], indent=2)}\n\n"
        f"Rubric excerpt:\n{(ctx['rubric'] or 'No rubric uploaded.')[:2000]}\n\n"
        f"Module book excerpt:\n{(ctx['module_book'] or 'No module book uploaded.')[:2000]}\n\n"
        f"Recording transcripts:\n{(ctx['recording_text'] or 'No recordings.')[:2000]}\n\n"
        f"Evidence file index:\n{json.dumps(ctx['evidence_index'], indent=2)}\n\n"
        f"Evidence quotes (read-only):\n{json.dumps(ctx['evidence_refs'], indent=2)}"
    )


def _history_for_llm(messages: list[ChatMessage]) -> list[dict[str, str]]:
    """Build LLM history from stored messages, skipping pending proposals."""
    rows: list[dict[str, str]] = []
    for msg in messages:
        meta = msg.metadata_json or {}
        if meta.get("type") == "proposal":
            status = meta.get("status")
            if status == "applied":
                rows.append(
                    {
                        "role": "assistant",
                        "content": f"[Applied refinement] {msg.content}",
                    }
                )
            continue
        role = "assistant" if msg.role == "assistant" else "user"
        rows.append({"role": role, "content": msg.content})
    return rows


def _resolve_criterion_key(raw_key: str | None, defs_by_key: dict[str, dict]) -> Optional[str]:
    if not raw_key:
        return None
    if raw_key in defs_by_key:
        return raw_key
    lower = raw_key.strip().lower()
    for key, d in defs_by_key.items():
        if d["name"].lower() == lower or key.lower() == lower:
            return key
    for key, d in defs_by_key.items():
        if lower in d["name"].lower() or d["name"].lower() in lower:
            return key
    return None


def _assert_has_suggestions(draft: dict[str, Any]) -> None:
    if not draft["criteria"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Generate AI suggestions before using assessment chat",
        )


def _get_proposal_message(db: Session, assessment_id: UUID, proposal_id: UUID) -> ChatMessage:
    msg = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.assessment_id == assessment_id,
            ChatMessage.id == proposal_id,
        )
        .first()
    )
    if not msg or (msg.metadata_json or {}).get("type") != "proposal":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")
    return msg


def _changes_to_out(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "criterion_key": c["criterion_key"],
            "criterion_name": c.get("criterion_name", c["criterion_key"]),
            "before_score": (c.get("before") or {}).get("score"),
            "after_score": (c.get("after") or {}).get("score"),
            "before_comment": (c.get("before") or {}).get("comment"),
            "after_comment": (c.get("after") or {}).get("comment"),
        }
        for c in changes
    ]


def _criteria_catalog_for_prompt(draft: dict[str, Any]) -> str:
    lines = []
    for d in draft["criteria_defs"]:
        key = d["key"]
        entry = draft["criteria"].get(key, {})
        eff = entry.get("effective") or {}
        lines.append(
            f"- {key}: {d['name']} "
            f"(effective score: {eff.get('score', '—')}/10, "
            f"overridden: {bool(entry.get('is_overridden'))})"
        )
    return "\n".join(lines)


def _infer_updates_from_conversation(
    history: list[ChatMessage],
    draft: dict[str, Any],
    ctx: dict[str, Any],
) -> list[dict[str, Any]]:
    """Fallback: extract agreed score changes from discuss messages when JSON updates are empty."""
    lines: list[str] = []
    for msg in history:
        meta = msg.metadata_json or {}
        if meta.get("type") == "proposal":
            continue
        if msg.content:
            lines.append(msg.content)
    blob = "\n".join(lines)
    if not blob.strip():
        return []

    updates: list[dict[str, Any]] = []
    defs_by_key = ctx["defs_by_key"]

    for key, d in defs_by_key.items():
        entry = draft["criteria"].get(key, {})
        if entry.get("is_overridden"):
            continue
        eff = entry.get("effective") or {}
        current_score = eff.get("score")
        name = d["name"]
        name_re = re.escape(name)
        new_score: Optional[float] = None

        patterns = (
            rf"{name_re}.{{0,240}}?(?:from|revised from)\s*(\d+(?:\.\d+)?)\s*/?\s*10?\s*(?:to|→|->)\s*(\d+(?:\.\d+)?)",
            rf"(?:from|revised from)\s*(\d+(?:\.\d+)?)\s*/?\s*10?\s*(?:to|→|->)\s*(\d+(?:\.\d+)?).{{0,160}}?{name_re}",
            rf"{name_re}.{{0,160}}?(?:to|at|of)\s*(\d+(?:\.\d+)?)\s*/\s*10",
            rf"{name_re}.{{0,160}}?score(?:\s+of|\s+is|\s+would be)?\s*(\d+(?:\.\d+)?)",
        )
        for pat in patterns:
            match = re.search(pat, blob, re.I | re.DOTALL)
            if not match:
                continue
            groups = match.groups()
            new_score = float(groups[1] if len(groups) == 2 else groups[0])
            break

        if new_score is None:
            continue
        if current_score is not None and float(new_score) == float(current_score):
            continue

        comment = eff.get("comment") or ""
        for line in reversed(lines):
            if name.lower() in line.lower() and len(line.strip()) > 20:
                comment = line.strip()[:600]
                break
        if not comment:
            comment = f"Score adjusted to {new_score}/10 based on the discussion with the lecturer."

        updates.append({"criterion_key": key, "score": new_score, "comment": comment})

    return updates


def _build_proposed_changes(
    draft: dict[str, Any],
    updates: list[dict[str, Any]],
    ctx: dict[str, Any],
) -> tuple[list[dict[str, Any]], Optional[str]]:
    """Translate LLM updates into before/after proposal rows without mutating draft."""
    defs_by_key = ctx["defs_by_key"]
    evidence_refs = ctx["evidence_refs"]
    proposed: list[dict[str, Any]] = []
    for upd in updates:
        key = _resolve_criterion_key(upd.get("criterion_key"), defs_by_key)
        if not key:
            continue
        entry = draft["criteria"].get(key)
        if not entry or entry.get("is_overridden"):
            continue
        ai = entry.get("ai") or {}
        eff = entry.get("effective") or {}
        before_score = eff.get("score")
        before_comment = eff.get("comment")
        criterion_refs = [r for r in evidence_refs if r.get("criterion_key") == key] or evidence_refs
        new_comment = str(upd["comment"]).strip() if upd.get("comment") else None
        new_score = float(upd["score"]) if upd.get("score") is not None else before_score
        if not new_comment and new_score != before_score:
            new_comment = (
                before_comment
                or f"Score adjusted to {new_score}/10 based on the discussion with the lecturer."
            )
        if new_comment:
            new_comment = _ground_comment_with_evidence(new_comment, criterion_refs)
        if new_score == before_score and (not new_comment or new_comment == before_comment):
            continue
        proposed.append(
            {
                "criterion_key": key,
                "criterion_name": defs_by_key.get(key, {}).get("name", key),
                "before": {"score": before_score, "comment": before_comment},
                "after": {"score": new_score, "comment": new_comment or before_comment},
            }
        )
    return proposed, None


def _apply_proposed_changes(
    db: Session,
    *,
    assessment: Assessment,
    draft: dict[str, Any],
    proposed: list[dict[str, Any]],
    summary_update: Optional[str],
    ctx: dict[str, Any],
) -> list[dict[str, Any]]:
    """Persist proposed criterion changes into draft."""
    now = _now()
    evidence_rows = ctx["evidence_rows"]
    defs_by_key = ctx["defs_by_key"]
    applied: list[dict[str, Any]] = []

    for change in proposed:
        key = change["criterion_key"]
        entry = draft["criteria"].get(key)
        if not entry or entry.get("is_overridden"):
            continue
        ai = copy.deepcopy(entry.get("ai") or {})
        after = change.get("after") or {}
        if after.get("score") is not None:
            ai["score"] = float(after["score"])
        if after.get("comment"):
            ai["comment"] = after["comment"]
        ai["generated_at"] = now.isoformat()
        ai["refined_via_chat"] = True
        d = defs_by_key.get(key)
        if d:
            matches = match_criterion_to_evidence(
                key, d["name"], d["description"], evidence_rows
            )
            ai["evidence_refs"] = _build_evidence_refs(matches)
            persist_matches(db, assessment_id=assessment.id, criterion_key=key, matches=matches)
        entry["ai"] = ai
        entry["effective"] = _effective_value(ai, entry.get("teacher"), False)
        applied.append(change)

    if summary_update and not draft["summary"].get("teacher"):
        draft["summary"]["ai"] = summary_update
        draft["summary"]["effective"] = summary_update

    overall = _compute_overall_score(draft["criteria"], draft["criteria_defs"])
    if overall is not None and not draft["overall_grade"].get("teacher"):
        grade = _score_to_grade(overall)
        draft["overall_grade"]["ai"] = grade
        draft["overall_grade"]["effective"] = grade

    return applied


def _reject_pending_proposals(db: Session, assessment_id: UUID) -> None:
    pending = (
        db.query(ChatMessage)
        .filter(ChatMessage.assessment_id == assessment_id)
        .order_by(ChatMessage.timestamp.desc())
        .all()
    )
    for msg in pending:
        meta = msg.metadata_json or {}
        if meta.get("type") == "proposal" and meta.get("status") == "pending":
            meta = {**meta, "status": "superseded"}
            msg.metadata_json = meta
            db.add(msg)


def _proposal_summary_text(proposed: list[dict[str, Any]], reply: str) -> str:
    if reply and not _is_template_placeholder(reply):
        return reply
    if not proposed:
        return "No criterion changes proposed based on the conversation."
    parts = []
    for c in proposed:
        before = c.get("before") or {}
        after = c.get("after") or {}
        name = c.get("criterion_name", c["criterion_key"])
        parts.append(f"{name}: {before.get('score')} → {after.get('score')}/10")
    return "Proposed updates: " + "; ".join(parts) + "."


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


def _ground_comment_with_evidence(comment: str, evidence_refs: list[dict]) -> str:
    """Ensure chat comments cite an uploaded file when evidence exists."""
    if not comment or _comment_cites_evidence(comment, evidence_refs):
        return comment
    named_refs = [r for r in evidence_refs if r.get("file_name")]
    if not named_refs:
        return comment
    return f"{comment.rstrip()} (See evidence in {named_refs[0]['file_name']}.)"


def _is_template_placeholder(text: str) -> bool:
    """Detect when the model echoes JSON schema placeholders instead of real text."""
    if not text:
        return True
    stripped = text.strip()
    lower = stripped.lower()
    if lower.startswith("<") and lower.endswith(">"):
        return True
    known_placeholders = {
        "<conversational reply to teacher>",
        "<optional updated overall summary>",
        "<paragraph>",
        "<2-4 sentences citing specific evidence file names and quotes>",
    }
    return lower in known_placeholders


def _build_chat_reply(
    *,
    parsed_reply: str | None,
    applied_changes: list[dict[str, Any]],
    updates_requested: int,
    teacher_message: str,
    defs_by_key: dict[str, dict],
) -> str:
    if parsed_reply and not _is_template_placeholder(parsed_reply):
        return parsed_reply

    if applied_changes:
        summaries = []
        for change in applied_changes:
            key = change["criterion_key"]
            name = defs_by_key.get(key, {}).get("name", key)
            after = change.get("after") or {}
            score = after.get("score")
            summaries.append(f"{name} → {score}/10" if score is not None else name)
        return (
            "I've updated the assessment based on your feedback: "
            + ", ".join(summaries)
            + "."
        )

    if updates_requested:
        return (
            "I understood your request but could not apply the suggested criterion "
            "changes — they need to reference uploaded evidence files. Try being "
            "specific, e.g. “Raise Testing to 8 — see maximizing_synergies.pdf.”"
        )

    snippet = teacher_message.strip()[:120]
    return (
        f"I noted your feedback (“{snippet}”) but no criterion scores were changed. "
        "Name a specific criterion and evidence file if you want me to adjust a score."
    )


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


def chat_discuss(
    db: Session,
    *,
    assessment: Assessment,
    teacher: Teacher,
    message: str,
    criterion_key: Optional[str] = None,
) -> str:
    """Conversational discuss-only chat — never mutates the draft."""
    _assert_editable(assessment)
    draft = _load_draft(assessment)
    _assert_has_suggestions(draft)

    teacher_msg = ChatMessage(
        assessment_id=assessment.id,
        role="teacher",
        content=message.strip(),
        metadata_json={"type": "discuss", "criterion_key": criterion_key},
    )
    db.add(teacher_msg)
    db.flush()

    ctx = _build_assessment_context(
        db, assessment=assessment, draft=draft, criterion_key=criterion_key
    )
    history = list_chat_messages(db, assessment.id)

    chat_messages: list[dict[str, str]] = [
        {"role": "system", "content": _CHAT_DISCUSS_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": "Assessment context:\n" + _context_block(ctx, focus_criterion_key=criterion_key),
        },
        {
            "role": "assistant",
            "content": "I have reviewed the assessment context. What would you like to discuss?",
        },
    ]
    chat_messages.extend(_history_for_llm(history[:-1]))
    chat_messages.append({"role": "user", "content": message.strip()})

    raw = ollama_client.chat(chat_messages, temperature=0.35)
    reply = (raw or "").strip()
    if not reply:
        reply = (
            "I could not reach the on-premise model. "
            "Your message was saved — try again when Ollama is available."
        )

    assistant_msg = ChatMessage(
        assessment_id=assessment.id,
        role="assistant",
        content=reply,
        metadata_json={"type": "discuss"},
    )
    db.add(assistant_msg)
    db.commit()
    return reply


def chat_propose_refine(
    db: Session,
    *,
    assessment: Assessment,
    teacher: Teacher,
) -> dict[str, Any]:
    """Generate a refinement proposal from the full conversation — does not mutate draft."""
    _assert_editable(assessment)
    draft = _load_draft(assessment)
    _assert_has_suggestions(draft)

    history = list_chat_messages(db, assessment.id)
    if not any(m.role == "teacher" for m in history):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Discuss the assessment before refining — send at least one message first",
        )

    _reject_pending_proposals(db, assessment.id)
    ctx = _build_assessment_context(db, assessment=assessment, draft=draft)
    catalog = _criteria_catalog_for_prompt(draft)

    chat_messages: list[dict[str, str]] = [
        {"role": "system", "content": _CHAT_PROPOSE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Assessment context:\n"
                + _context_block(ctx)
                + "\n\nAvailable criteria (use criterion_key exactly):\n"
                + catalog
                + "\n\nBased on the conversation below, propose criterion updates grounded in evidence. "
                "If the lecturer and assistant agreed on new scores, include every agreed change in updates[]."
            ),
        },
        {
            "role": "assistant",
            "content": "Ready to propose updates from the discussion.",
        },
    ]
    chat_messages.extend(_history_for_llm(history))

    raw = ollama_client.chat(chat_messages, temperature=0.2, format_json=True)
    parsed = ollama_client.parse_json_response(raw or "")

    updates: list[dict[str, Any]] = []
    summary_update: Optional[str] = None
    parsed_reply: Optional[str] = None
    if parsed:
        parsed_reply = str(parsed.get("reply") or "").strip() or None
        updates = parsed.get("updates") or []
        summary_update = parsed.get("summary")

    proposed, _ = _build_proposed_changes(draft, updates, ctx)

    if not proposed:
        inferred = _infer_updates_from_conversation(history, draft, ctx)
        if inferred:
            proposed, _ = _build_proposed_changes(draft, inferred, ctx)
            updates = inferred

    if not proposed and not updates:
        convo_excerpt = "\n".join(
            f"{m.role}: {m.content}"
            for m in history[-10:]
            if (m.metadata_json or {}).get("type") != "proposal"
        )
        retry_raw = ollama_client.chat(
            [
                {"role": "system", "content": _CHAT_PROPOSE_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Criteria catalog:\n{catalog}\n\n"
                        f"Conversation:\n{convo_excerpt}\n\n"
                        "Return JSON only. The conversation contains agreed score changes — "
                        "populate updates[] with every change. Do not return an empty updates array."
                    ),
                },
            ],
            temperature=0.15,
            format_json=True,
        )
        retry_parsed = ollama_client.parse_json_response(retry_raw or "")
        if retry_parsed:
            parsed_reply = str(retry_parsed.get("reply") or "").strip() or parsed_reply
            retry_updates = retry_parsed.get("updates") or []
            if retry_updates:
                updates = retry_updates
                summary_update = retry_parsed.get("summary") or summary_update
                proposed, _ = _build_proposed_changes(draft, updates, ctx)

    reply = _proposal_summary_text(proposed, parsed_reply or "")

    proposal_id = uuid.uuid4()
    proposal_msg = ChatMessage(
        id=proposal_id,
        assessment_id=assessment.id,
        role="assistant",
        content=reply,
        metadata_json={
            "type": "proposal",
            "status": "pending",
            "proposal_id": str(proposal_id),
            "proposed_changes": _changes_to_out(proposed),
            "summary_proposed": summary_update,
            "updates_requested": len(updates),
        },
    )
    db.add(proposal_msg)
    db.commit()

    return {
        "proposal_id": str(proposal_id),
        "message_id": str(proposal_id),
        "reply": reply,
        "proposed_changes": _changes_to_out(proposed),
        "summary_proposed": summary_update,
        "updates_requested": len(updates),
    }


def chat_apply_proposal(
    db: Session,
    *,
    assessment: Assessment,
    teacher: Teacher,
    proposal_id: UUID,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Accept a pending proposal and apply it to the draft."""
    _assert_editable(assessment)
    draft = _load_draft(assessment)
    msg = _get_proposal_message(db, assessment.id, proposal_id)
    meta = msg.metadata_json or {}
    if meta.get("status") != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Proposal is already {meta.get('status')}",
        )

    ctx = _build_assessment_context(db, assessment=assessment, draft=draft)
    proposed = []
    for row in meta.get("proposed_changes") or []:
        proposed.append(
            {
                "criterion_key": row["criterion_key"],
                "criterion_name": row.get("criterion_name", row["criterion_key"]),
                "before": {
                    "score": row.get("before_score"),
                    "comment": row.get("before_comment"),
                },
                "after": {
                    "score": row.get("after_score"),
                    "comment": row.get("after_comment"),
                },
            }
        )

    if not proposed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This proposal contains no applicable criterion changes",
        )

    applied = _apply_proposed_changes(
        db,
        assessment=assessment,
        draft=draft,
        proposed=proposed,
        summary_update=meta.get("summary_proposed"),
        ctx=ctx,
    )
    _save_draft(db, assessment, draft)

    meta = {**meta, "status": "applied", "applied_changes": _changes_to_out(applied)}
    msg.metadata_json = meta
    msg.content = f"Applied refinement: {msg.content}"
    db.add(msg)
    db.commit()

    audit_service.log_action(
        db,
        action="assessment.chat_refine",
        source=AuditSource.ai,
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        assessment_id=assessment.id,
        details={
            "proposal_id": str(proposal_id),
            "updates_applied": len(applied),
            "changes": applied,
        },
    )
    return draft, _changes_to_out(applied)


def chat_reject_proposal(
    db: Session,
    *,
    assessment: Assessment,
    teacher: Teacher,
    proposal_id: UUID,
) -> None:
    _assert_editable(assessment)
    msg = _get_proposal_message(db, assessment.id, proposal_id)
    meta = msg.metadata_json or {}
    if meta.get("status") != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Proposal is already {meta.get('status')}",
        )
    meta = {**meta, "status": "rejected"}
    msg.metadata_json = meta
    db.add(msg)
    db.commit()


def chat_undo_last_apply(
    db: Session,
    *,
    assessment: Assessment,
    teacher: Teacher,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Restore criterion AI values from the most recent applied chat refinement."""
    _assert_editable(assessment)
    event = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.assessment_id == assessment.id,
            AuditEvent.action == "assessment.chat_refine",
        )
        .order_by(AuditEvent.timestamp.desc())
        .first()
    )
    if not event or not event.details_json:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No applied refinement to undo",
        )

    draft = _load_draft(assessment)
    restored: list[dict[str, Any]] = []
    for change in event.details_json.get("changes") or []:
        key = change.get("criterion_key")
        if not key or key not in draft["criteria"]:
            continue
        entry = draft["criteria"][key]
        if entry.get("is_overridden"):
            continue
        before = change.get("before") or {}
        ai = copy.deepcopy(entry.get("ai") or {})
        if before.get("score") is not None:
            ai["score"] = before["score"]
        if before.get("comment") is not None:
            ai["comment"] = before["comment"]
        ai["generated_at"] = _now().isoformat()
        ai["refined_via_chat"] = False
        entry["ai"] = ai
        entry["effective"] = _effective_value(ai, entry.get("teacher"), False)
        restored.append(
            {
                "criterion_key": key,
                "criterion_name": change.get("criterion_name", key),
                "before_score": (change.get("after") or {}).get("score"),
                "after_score": before.get("score"),
            }
        )

    if not restored:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nothing to undo — overridden criteria were not changed",
        )

    overall = _compute_overall_score(draft["criteria"], draft["criteria_defs"])
    if overall is not None and not draft["overall_grade"].get("teacher"):
        draft["overall_grade"]["ai"] = _score_to_grade(overall)
        draft["overall_grade"]["effective"] = draft["overall_grade"]["ai"]

    _save_draft(db, assessment, draft)
    audit_service.log_action(
        db,
        action="assessment.chat_undo",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        assessment_id=assessment.id,
        details={"restored": restored},
    )
    return draft, restored


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


def serialize_chat_messages(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "timestamp": m.timestamp,
            "metadata": m.metadata_json,
        }
        for m in messages
    ]


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
