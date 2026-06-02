import json
import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
OLLAMA_MODEL_BACKUP = os.getenv("OLLAMA_MODEL_BACKUP", "qwen2.5:3b")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "90"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "320"))
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "2048"))

_tags_cache: ContextVar[dict | None] = ContextVar("ollama_tags_cache", default=None)


def get_config() -> dict:
    return {
        "base_url": OLLAMA_BASE_URL,
        "model": OLLAMA_MODEL,
        "backup_model": OLLAMA_MODEL_BACKUP,
        "active_model": _resolve_model_name(),
    }


def _models_to_try() -> list[str]:
    candidates = [OLLAMA_MODEL, OLLAMA_MODEL_BACKUP]
    seen: set[str] = set()
    out: list[str] = []
    for model in candidates:
        normalized = (model or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _resolve_model_name() -> str | None:
    data = _tags_payload()
    if not data:
        return None
    names = [m.get("name", "") for m in data.get("models", [])]
    for preferred in _models_to_try():
        if preferred in names:
            return preferred
        prefix = preferred.split(":")[0]
        alternate = next((n for n in names if n.startswith(f"{prefix}:")), None)
        if alternate:
            return alternate
    return None


@contextmanager
def analysis_session():
    """Cache /api/tags lookups for the duration of one analysis run."""
    token = _tags_cache.set({})
    try:
        yield
    finally:
        _tags_cache.reset(token)


def _tags_payload() -> dict | None:
    cached = _tags_cache.get()
    if cached is not None:
        if "payload" in cached:
            return cached["payload"]
        try:
            with httpx.Client(timeout=5.0) as client:
                r = client.get(f"{OLLAMA_BASE_URL}/api/tags")
                if r.status_code != 200:
                    cached["payload"] = None
                else:
                    cached["payload"] = r.json()
        except (httpx.HTTPError, OSError):
            cached["payload"] = None
        return cached["payload"]

    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if r.status_code != 200:
                return None
            return r.json()
    except (httpx.HTTPError, OSError):
        return None


def is_available() -> bool:
    return _tags_payload() is not None


def model_is_pulled() -> bool:
    return _resolve_model_name() is not None


def chat(system: str, user: str, *, num_predict: int | None = None) -> Optional[str]:
    """Call local Ollama chat API. Returns None if unavailable or on error."""
    selected_model = _resolve_model_name()
    if not selected_model:
        return None

    payload = {
        "model": selected_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": num_predict if num_predict is not None else OLLAMA_NUM_PREDICT,
            "num_ctx": OLLAMA_NUM_CTX,
            "num_thread": int(os.getenv("OLLAMA_NUM_THREAD", "6")),
        },
    }

    try:
        with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
            r = client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
            r.raise_for_status()
            content = r.json().get("message", {}).get("content", "").strip()
            return content or None
    except (httpx.HTTPError, OSError, ValueError):
        return None


def chat_stream(system: str, user: str, *, num_predict: int | None = None) -> Iterator[str]:
    """Yield assistant text chunks from Ollama streaming API."""
    selected_model = _resolve_model_name()
    if not selected_model:
        return

    payload = {
        "model": selected_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": True,
        "options": {
            "temperature": 0.2,
            "num_predict": num_predict if num_predict is not None else OLLAMA_NUM_PREDICT,
            "num_ctx": OLLAMA_NUM_CTX,
            "num_thread": int(os.getenv("OLLAMA_NUM_THREAD", "6")),
        },
    }

    try:
        with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
            with client.stream("POST", f"{OLLAMA_BASE_URL}/api/chat", json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content
                    if chunk.get("done"):
                        break
    except (httpx.HTTPError, OSError, ValueError, json.JSONDecodeError):
        return
