"""Workspace chat: short by default, full context only when needed."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

CHAT_NUM_PREDICT = int(os.getenv("OLLAMA_CHAT_NUM_PREDICT", "140"))
CHAT_NUM_PREDICT_DETAIL = int(os.getenv("OLLAMA_CHAT_NUM_PREDICT_DETAIL", "400"))

CASUAL_EXACT = re.compile(
    r"^(?:"
    r"hey|hi|hello|hiya|yo|sup|thanks|thank you|thx|ok|okay|cheers|good morning|good afternoon"
    r")(?:[!.,?\s]+)?$",
    re.IGNORECASE,
)

DETAIL_PHRASES = (
    "explain",
    "elaborate",
    "more detail",
    "in depth",
    "tell me more",
    "expand on",
    "go deeper",
    "walk me through",
    "break down",
    "why did",
    "how did",
    "describe in",
)

ASSESSMENT_HINTS = (
    "evidence",
    "grade",
    "rubric",
    "criterion",
    "overlap",
    "contribute",
    "contribution",
    "oral",
    "assess",
    "score",
    "draft",
    "weak",
    "strong",
    "gap",
    "file",
    "upload",
    "documentation",
    "similar",
    "plagiar",
    "quote",
    "match",
    "suggest",
    "student",
    "work",
    "project",
    "technical",
    "writing",
    "?",
)


@dataclass
class ChatPlan:
    system: str
    user: str
    num_predict: int
    static_reply: str | None = None


def is_casual_message(message: str) -> bool:
    text = message.strip()
    if not text:
        return True
    lower = text.lower()
    if CASUAL_EXACT.match(text):
        return True
    if _has_assessment_intent(lower):
        return False
    words = lower.split()
    if len(words) <= 3 and "?" not in text:
        return True
    if len(text) <= 18 and "?" not in text:
        return True
    return False


def wants_detail(message: str) -> bool:
    lower = message.lower()
    return any(phrase in lower for phrase in DETAIL_PHRASES)


def _has_assessment_intent(lower: str) -> bool:
    return any(hint in lower for hint in ASSESSMENT_HINTS)


def _casual_static_reply(student_name: str, message: str) -> str:
    lower = message.strip().lower()
    if lower.startswith(("thanks", "thank you", "thx", "cheers")):
        return "You're welcome."
    if lower.startswith(("ok", "okay")):
        return "Got it."
    return f"Hi — ask about {student_name}'s evidence when you're ready."


def prepare_chat(teacher_message: str, ctx: dict) -> ChatPlan:
    student = ctx.get("student", "this student")
    msg = teacher_message.strip()

    if is_casual_message(msg):
        return ChatPlan(
            system="",
            user="",
            num_predict=0,
            static_reply=_casual_static_reply(student, msg),
        )

    detail = wants_detail(msg)
    if detail:
        system = (
            "You assist a lecturer reviewing one student's assessment. "
            "The teacher asked for detail — you may use several short paragraphs or bullets. "
            "Stay evidence-based using the context. Use markdown sparingly."
        )
        num_predict = CHAT_NUM_PREDICT_DETAIL
        payload = ctx
    else:
        system = (
            "You assist a lecturer reviewing one student's assessment. "
            "Default: **very concise** — at most 2 short sentences, OR up to 3 brief bullet points. "
            "No preamble, no recap of the question, no listing all criteria. "
            "Cite only the most relevant evidence. "
            "If the teacher wants more, they will ask — do not volunteer long analysis."
        )
        num_predict = CHAT_NUM_PREDICT
        payload = _slim_context(ctx)
    user = (
        f"Teacher message:\n{msg}\n\n"
        "Assessment context:\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )
    return ChatPlan(system=system, user=user, num_predict=num_predict)


def _slim_context(ctx: dict) -> dict:
    return {
        "student": ctx.get("student"),
        "criteria": (ctx.get("criteria") or [])[:6],
        "analysis_summary": (ctx.get("analysis_summary") or [])[:3],
        "evidence_matches": (ctx.get("evidence_matches") or [])[:3],
        "overlaps": (ctx.get("overlaps") or [])[:2],
    }
