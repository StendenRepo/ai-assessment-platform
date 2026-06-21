"""Serialize and parse overlap signal snippet payloads."""

from __future__ import annotations

import json
from typing import Optional

from app.services.overlap.markers import dedupe_student_flag_dicts

_SNIPPET_JSON_PREFIX = "{"


def parse_signal_detail(snippet: Optional[str]) -> dict:
    if not snippet or not snippet.strip().startswith(_SNIPPET_JSON_PREFIX):
        return {}
    try:
        return json.loads(snippet)
    except json.JSONDecodeError:
        return {}


def encode_text_snippet(hit: dict) -> str:
    return json.dumps(
        {
            "scope": hit.get("scope"),
            "status": hit.get("status"),
            "passage_a": hit.get("passage_a"),
            "passage_b": hit.get("passage_b"),
            "file_a": hit.get("file_a"),
            "file_b": hit.get("file_b"),
            "group_a_id": hit.get("group_a_id"),
            "group_b_id": hit.get("group_b_id"),
            "group_a_name": hit.get("group_a_name"),
            "group_b_name": hit.get("group_b_name"),
            "ai_verified": hit.get("ai_verified"),
            "ai_explanation": hit.get("ai_explanation"),
            "ai_shared_excerpt": hit.get("ai_shared_excerpt"),
            "detection_method": hit.get("detection_method"),
            "integrity_type": hit.get("integrity_type"),
            "flags": dedupe_student_flag_dicts(hit.get("flags") or []),
            "ai_content_percent": hit.get("ai_content_percent"),
            "peak_ai_section_percent": hit.get("peak_ai_section_percent"),
            "student_match_count": hit.get("student_match_count"),
            "overlap_confidence_percent": hit.get("overlap_confidence_percent"),
            "detection_confidence_percent": hit.get("detection_confidence_percent"),
            "metrics_summary": hit.get("metrics_summary"),
        }
    )
