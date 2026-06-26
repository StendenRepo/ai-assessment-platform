"""LLM prompt templates and builders for integrity detection.

Keeps the (long) prompt text and the LLM-facing wording in one place, separate
from the detection control flow.
"""

from __future__ import annotations

from app.services.overlap.integrity.thresholds import (
    _MAX_AI_FLAGS,
    _MAX_CHUNK_CHARS,
    _MAX_DOC_COMPARE_CHARS,
    _MAX_PAIR_CHARS,
    _MAX_PAIR_FLAGS,
    AI_FLAG_MIN,
    STUDENT_AI_CONFIRMED_MIN,
    STUDENT_AI_FLAG_MIN,
)

_AI_DETECTION_SYSTEM = (
    "You are an expert detector of AI-generated student writing (ChatGPT, Claude, Gemini, etc.). "
    "Students in an Applied AI course may submit LLM-written portfolios. "
    "Be sceptical: polished, generic, uniform prose without personal project detail is likely AI. "
    "Respond with JSON only — no markdown outside the object."
)

_INTEGRITY_SYSTEM = (
    "You are an academic integrity analyst for a university Applied AI course. "
    "Detect AI-generated writing and student-to-student plagiarism including subtle "
    "paraphrasing. Respond with JSON only — no markdown outside the object."
)


def build_full_document_plagiarism_prompt(
    clean_a: str, clean_b: str, tfidf_hint: float
) -> str:
    return f"""You are an expert plagiarism analyst. Compare these two COMPLETE student submissions.

Pre-screen similarity: {tfidf_hint:.2f} (scale 0-1).

═══ SUBMISSION A ═══
{clean_a[:_MAX_DOC_COMPARE_CHARS]}

═══ SUBMISSION B ═══
{clean_b[:_MAX_DOC_COMPARE_CHARS]}

Find EVERY instance where one student likely copied or paraphrased the other.
Students use paraphrasing, synonym swaps, reordering — not just word-for-word copying.

Return JSON:
{{
  "plagiarism_detected": true or false,
  "overall_confidence": 0.0 to 1.0,
  "status": "confirmed" or "possible" or "none",
  "flags": [
    {{
      "order_in_a": 1,
      "text_a": "exact sentence(s) copied verbatim from submission A (min 6 words)",
      "text_b": "exact corresponding sentence(s) copied verbatim from submission B",
      "confidence": 0.0 to 1.0,
      "reason": "brief reason for teacher"
    }}
  ],
  "explanation": "one sentence summary"
}}

Rules:
- List ALL instances found (up to {_MAX_PAIR_FLAGS}), ordered by order_in_a (1 = earliest in submission A).
- text_a and text_b MUST be copied exactly from the submissions above — complete sentences only.
- Include paraphrased passages with the same ideas/structure.
- Do NOT flag content that appears in only one submission.
- Do NOT invent text. If unsure, omit the flag.
- Each flag needs confidence >= {STUDENT_AI_FLAG_MIN}.
"""


def build_full_document_ai_prompt(clean: str) -> str:
    return f"""Analyse this COMPLETE student submission for AI-generated writing.

SUBMISSION:
{clean[:_MAX_DOC_COMPARE_CHARS]}

Return JSON:
{{
  "ai_detected": true or false,
  "overall_confidence": 0.0 to 1.0,
  "status": "confirmed" or "possible" or "none",
  "flags": [
    {{
      "text": "exact sentence(s) from the submission that appear AI-written (min 4 words)",
      "confidence": 0.0 to 1.0,
      "reason": "brief reason for teacher"
    }}
  ],
  "explanation": "one sentence summary"
}}

Detection rules:
- Flag writing that reads like ChatGPT/Claude: polished, generic, no first-person project detail,
  formulaic transitions, list-like structure, hedging ("it is important to note"), uniform tone.
- A submission can be MOSTLY or ENTIRELY AI-written — set ai_detected=true if likely.
- Include up to {_MAX_AI_FLAGS} flagged passages with confidence >= {AI_FLAG_MIN}.
- Copy text exactly from the submission for each flag.
- If the submission appears authentically student-written with specific project detail, set ai_detected=false.
"""


def build_chunk_ai_prompt(chunk: str, idx: int, total: int) -> str:
    return f"""Analyse this student submission excerpt for AI-generated writing.

EXCERPT ({idx + 1}/{total}):
{chunk[:_MAX_CHUNK_CHARS]}

Return JSON:
{{
  "ai_detected": true or false,
  "overall_confidence": 0.0 to 1.0,
  "flags": [
    {{
      "text": "exact substring from excerpt that appears AI-written (min 4 words)",
      "confidence": 0.0 to 1.0,
      "reason": "brief reason shown to teacher"
    }}
  ]
}}

Rules:
- Flag passages that sound like ChatGPT/Claude: generic, polished, no personal project detail.
- Include flags with confidence >= {AI_FLAG_MIN}.
- If this excerpt is likely AI-written, set ai_detected=true even if you cannot quote a short substring.
"""


def build_excerpt_plagiarism_prompt(
    clean_a: str, clean_b: str, tfidf_score: float
) -> str:
    return f"""Statistical pre-screen similarity: {tfidf_score:.2f} (scale 0-1).

Compare these two student excerpts for plagiarism. Students rarely copy word-for-word —
look for paraphrasing, synonym swaps, sentence reordering, shared unusual phrasing,
identical structure with light edits, and idea-level copying.

EXCERPT A:
{clean_a[:_MAX_PAIR_CHARS]}

EXCERPT B:
{clean_b[:_MAX_PAIR_CHARS]}

Return JSON:
{{
  "plagiarism_detected": true or false,
  "overall_confidence": 0.0 to 1.0,
  "status": "confirmed" or "possible" or "none",
  "flags": [
    {{
      "text_a": "full sentence from excerpt A containing the overlap (copy verbatim)",
      "text_b": "full sentence from excerpt B containing the overlap (copy verbatim)",
      "confidence": 0.0 to 1.0,
      "reason": "brief reason (e.g. paraphrased same paragraph, light synonym edits)"
    }}
  ],
  "explanation": "one concise sentence for a teacher"
}}

Rules:
- confirmed: clear copying or paraphrasing with same ideas/structure (confidence >= {STUDENT_AI_CONFIRMED_MIN})
- possible: suspicious similarity but not definitive (confidence >= {STUDENT_AI_FLAG_MIN})
- none: independent original work — prefer this when uncertain
- Only include flags you are confident about (confidence >= {STUDENT_AI_FLAG_MIN}).
- text_a and text_b must each be complete sentences copied exactly from the excerpts (min 8 words).
- Do NOT flag content that is unique to one student.
- Detect subtle paraphrasing, not only identical text.
- Prefer fewer high-quality flags over many weak ones.
"""
