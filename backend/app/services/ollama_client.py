"""Shared on-premise LLM client (Ollama) with primary/backup model fallback."""
from __future__ import annotations

import json
import re
from typing import Any, Optional

import httpx

from app.config import settings

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


def generate(
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.2,
) -> Optional[str]:
    """Single-turn text generation. Returns None if all models fail."""
    for model in (settings.OLLAMA_MODEL, settings.OLLAMA_MODEL_BACKUP):
        if not model:
            continue
        try:
            payload: dict[str, Any] = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": settings.OLLAMA_NUM_PREDICT,
                    "num_ctx": settings.OLLAMA_NUM_CTX,
                },
            }
            if system:
                payload["system"] = system
            with httpx.Client(timeout=settings.OLLAMA_TIMEOUT_SECONDS) as client:
                response = client.post(
                    f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate",
                    json=payload,
                )
                response.raise_for_status()
                text = (response.json().get("response") or "").strip()
                if text:
                    return text
        except Exception:
            continue
    return None


def chat(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.3,
) -> Optional[str]:
    """Multi-turn chat completion. Each message: {role, content}."""
    for model in (settings.OLLAMA_MODEL, settings.OLLAMA_MODEL_BACKUP):
        if not model:
            continue
        try:
            with httpx.Client(timeout=settings.OLLAMA_TIMEOUT_SECONDS) as client:
                response = client.post(
                    f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat",
                    json={
                        "model": model,
                        "messages": messages,
                        "stream": False,
                        "options": {
                            "temperature": temperature,
                            "num_predict": settings.OLLAMA_NUM_PREDICT,
                            "num_ctx": settings.OLLAMA_NUM_CTX,
                        },
                    },
                )
                response.raise_for_status()
                message = response.json().get("message") or {}
                text = (message.get("content") or "").strip()
                if text:
                    return text
        except Exception:
            continue
    return None


def parse_json_response(text: str) -> Optional[dict]:
    """Extract a JSON object from raw LLM output (handles fenced blocks)."""
    if not text:
        return None
    stripped = text.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    match = _JSON_BLOCK_RE.search(stripped)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None
