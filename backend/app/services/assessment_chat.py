"""Assessment discuss/refine chat workflow."""
from __future__ import annotations

import copy
import uuid
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.assessment import Assessment
from app.models.audit_event import AuditEvent
from app.models.chat_message import ChatMessage
from app.models.enums import AuditSource
from app.models.teacher import Teacher
from app.services import audit_service, ollama_client
from app.services.assessment_draft_core import (
    _CHAT_DISCUSS_SYSTEM_PROMPT,
    _CHAT_PROPOSE_SYSTEM_PROMPT,
    _apply_proposed_changes,
    _assert_editable,
    _assert_has_suggestions,
    _build_assessment_context,
    _build_proposed_changes,
    _changes_to_out,
    _compute_overall_score,
    _context_block,
    _criteria_catalog_for_prompt,
    _effective_value,
    _get_proposal_message,
    _history_for_llm,
    _infer_updates_from_conversation,
    _load_draft,
    _now,
    _proposal_summary_text,
    _reject_pending_proposals,
    _save_draft,
    _score_to_grade,
    _unrefined_history_for_llm,
    _unrefined_chat_messages,
)
from app.lib.llm_json import parse_json_response

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

    raw = ollama_client.chat(chat_messages, temperature=0.35, **ollama_client.assessment_llm_options())
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
    """Generate a refinement proposal from unrefined chat messages — does not mutate draft."""
    _assert_editable(assessment)
    draft = _load_draft(assessment)
    _assert_has_suggestions(draft)
    history = list_chat_messages(db, assessment.id)
    fresh_messages = _unrefined_chat_messages(history)

    refine_history = _unrefined_history_for_llm(history)
    if not any(row["role"] == "user" for row in refine_history):
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
                + "\n\nBased only on the new conversation below, propose criterion updates grounded in evidence. "
                  "Do not re-propose changes that were already applied in previous refinements. "
                  "If the latest lecturer instruction mentions only one criterion, update only that criterion."
            ),
        },
        {
            "role": "assistant",
            "content": "Ready to propose updates from the discussion.",
        },
    ]
    chat_messages.extend(refine_history)

    raw = ollama_client.chat(
        chat_messages,
        temperature=0.2,
        format_json=True,
        **ollama_client.assessment_llm_options(),
    )
    parsed = parse_json_response(raw or "")

    updates: list[dict[str, Any]] = []
    summary_update: Optional[str] = None
    parsed_reply: Optional[str] = None
    if parsed:
        parsed_reply = str(parsed.get("reply") or "").strip() or None
        updates = parsed.get("updates") or []
        summary_update = parsed.get("summary")

    # Deterministic teacher score commands (e.g. "change documentation to 10")
    # take precedence over the model's proposal, which can be noisy or ignore
    # the latest instruction.
    inferred = _infer_updates_from_conversation(fresh_messages, draft, ctx)
    if inferred:
        proposed, _ = _build_proposed_changes(draft, inferred, ctx)
        updates = inferred
    else:
        proposed, _ = _build_proposed_changes(draft, updates, ctx)

    if not proposed and not updates:
        convo_excerpt = "\n".join(
            f"{m['role']}: {m['content']}" for m in refine_history[-10:]
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
            **ollama_client.assessment_llm_options(),
        )
        retry_parsed = parse_json_response(retry_raw or "")
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
