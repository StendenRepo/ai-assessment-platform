import json
import os
from collections.abc import Iterator
from typing import Optional

import httpx

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "90"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "320"))
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "2048"))


def get_config() -> dict:
    return {
        "base_url": OLLAMA_BASE_URL,
        "model": OLLAMA_MODEL,
    }


def is_available() -> bool:
    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(f"{OLLAMA_BASE_URL}/api/tags")
            return r.status_code == 200
    except (httpx.HTTPError, OSError):
        return False


def model_is_pulled() -> bool:
    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if r.status_code != 200:
                return False
            names = [m.get("name", "") for m in r.json().get("models", [])]
            prefix = OLLAMA_MODEL.split(":")[0]
            return any(n == OLLAMA_MODEL or n.startswith(f"{prefix}:") for n in names)
    except (httpx.HTTPError, OSError):
        return False


def chat(system: str, user: str, *, num_predict: int | None = None) -> Optional[str]:
    """Call local Ollama chat API. Returns None if unavailable or on error."""
    if not is_available():
        return None

    payload = {
        "model": OLLAMA_MODEL,
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
    if not is_available():
        return

    payload = {
        "model": OLLAMA_MODEL,
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
