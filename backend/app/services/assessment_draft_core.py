"""Shared assessment draft helpers, constants, and context builders."""
from __future__ import annotations

import copy
import json
import logging
import re
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.assessment import Assessment
from app.models.chat_message import ChatMessage
from app.models.enums import AssessmentStatus
from app.models.evidence import Evidence
from app.models.file_record import FileRecord
from app.models.module import Module
from app.models.recording import Recording
from app.models.student import Student
from app.services.evidence_matcher import match_criterion_to_evidence, persist_matches
from app.lib.llm_json import parse_json_response
from app.services import ollama_client
from app.services.overlap.service import OverlapService, parse_signal_detail

logger = logging.getLogger(__name__)

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
- Be clear, helpful, and concise.
- Format replies for on-screen reading: short paragraphs, simple "-" bullet lists, and **bold** for criterion names or scores.
- Avoid markdown headings (###), numbered outlines, and code fences unless quoting a short excerpt."""

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


def _persist_draft(db: Session, assessment: Assessment, draft: dict[str, Any]) -> None:
    """Stage draft JSON on the assessment; does not commit."""
    assessment.draft_form_json = draft
    db.add(assessment)
    db.flush()
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


def _scoring_band_guide(max_score: float) -> str:
    bands = [
        (0.90, "fully and clearly demonstrated, no significant gaps"),
        (0.70, "mostly demonstrated with minor gaps"),
        (0.50, "partially demonstrated, notable gaps"),
        (0.30, "weakly addressed, largely insufficient"),
        (0.0, "absent, not addressed, or no evidence"),
    ]
    lines = []
    prev_low = None
    for frac, label in bands:
        low = round(frac * max_score, 1)
        high = max_score if prev_low is None else round(prev_low - 0.1, 1)
        prev_low = low
        lines.append(f"- {low:g}-{high:g}: {label}")
    return "\n".join(lines)


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

def _unrefined_history_for_llm(messages: list[ChatMessage]) -> list[dict[str, str]]:
    """Return chat messages after the latest applied refinement.

    Normal chat can use full history, but refine should only consider new
    lecturer instructions that have not already been applied.
    """
    latest_applied_index = -1

    for index, msg in enumerate(messages):
        meta = msg.metadata_json or {}
        if meta.get("type") == "proposal" and meta.get("status") == "applied":
            latest_applied_index = index

    fresh_messages = messages[latest_applied_index + 1 :]

    rows: list[dict[str, str]] = []
    for msg in fresh_messages:
        meta = msg.metadata_json or {}
        if meta.get("type") == "proposal":
            continue

        role = "assistant" if msg.role == "assistant" else "user"
        rows.append({"role": role, "content": msg.content})

    return rows

def _unrefined_chat_messages(messages: list[ChatMessage]) -> list[ChatMessage]:
    latest_applied_index = -1

    for index, msg in enumerate(messages):
        meta = msg.metadata_json or {}
        if meta.get("type") == "proposal" and meta.get("status") == "applied":
            latest_applied_index = index

    return [
        msg
        for msg in messages[latest_applied_index + 1 :]
        if (msg.metadata_json or {}).get("type") != "proposal"
    ]


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
    """Extract agreed score changes from chat history when the LLM returns empty updates."""
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
            rf"(?:set|change|make|update|put|give)?\s*{name_re}.{{0,80}}?\b(?:to|at|as)\s*(\d+(?:\.\d+)?)\b",
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
        if new_score < 0 or new_score > 10:
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
            "score": round(max_score * 0.15, 1),
            "comment": (
                f"No grounded evidence found for {criterion['name']}. "
                f"{note} Manual review recommended."
            ),
            "confidence": 0.2,
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
            "specific, e.g. “Raise Testing to 8 and cite the supporting evidence file.”"
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
    max_score = float(criterion["max_score"])
    evidence_block = json.dumps(_build_evidence_refs(matches), indent=2)
    has_evidence = any((m.quote or "").strip() for m in matches)
    scoring_guide = _scoring_band_guide(max_score)
    prompt = f"""Assess ONE rubric criterion for a student submission.

Criterion: {criterion['name']}
Description: {criterion['description']}
Max score: {max_score:g}

Score ONLY on how strongly the retrieved evidence demonstrates this criterion.
Scoring bands (out of {max_score:g}):
{scoring_guide}
Rules:
- If no evidence is present or the evidence does not address this criterion, score in the lowest band — never award a middle score to "play it safe".
- Reserve the top band for evidence that clearly and fully demonstrates the criterion.
- Quote the evidence that justifies the score; do not assume facts that are not in the evidence.

Rubric context (excerpt):
{rubric_excerpt[:1500] or 'No rubric text uploaded.'}

Interview / recording context:
{recording_text[:1500] or 'No recording transcripts.'}

Retrieved evidence chunks (READ ONLY — do not rewrite):
{evidence_block}

Evidence present: {"yes" if has_evidence else "no"}

Return JSON:
{{
  "score": <number 0-{max_score:g}>,
  "comment": "<2-4 sentences citing specific evidence file names and quotes>",
  "confidence": <0.0-1.0>,
  "missing_gaps": "<optional note if evidence is thin>"
}}"""
    for attempt in range(2):
        raw = ollama_client.generate(
            prompt,
            system=_ASSESSMENT_SYSTEM_PROMPT,
            **ollama_client.assessment_llm_options(),
            **ollama_client.assessment_sampling(),
        )
        parsed = parse_json_response(raw or "")
        if parsed and parsed.get("score") is not None:
            return {
                "score": max(0.0, min(max_score, float(parsed["score"]))),
                "comment": str(parsed.get("comment") or ""),
                "confidence": float(parsed.get("confidence") or 0.7),
                "missing_gaps": parsed.get("missing_gaps"),
            }
        if raw is None:
            break
        logger.warning(
            "assessment scoring: unparseable JSON for criterion '%s' on attempt %d/2; %s",
            criterion.get("name"),
            attempt + 1,
            "retrying" if attempt == 0 else "falling back to heuristic",
        )
    return _heuristic_suggestion(criterion, matches, max_score)


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
    raw = ollama_client.generate(
        prompt,
        system=_ASSESSMENT_SYSTEM_PROMPT,
        **ollama_client.assessment_llm_options(),
        **ollama_client.assessment_sampling(),
    )
    parsed = parse_json_response(raw or "")
    if parsed and parsed.get("summary"):
        return str(parsed["summary"])
    if lines:
        return (
            "AI draft summary based on uploaded evidence. "
            + " ".join(line.split("—", 1)[-1].strip() for line in lines[:3])
        )
    return "AI analysis pending — generate suggestions after uploading evidence."
