"""Shared on-premise LLM client (Ollama) with primary/backup model fallback."""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.config import settings
from app.lib.llm_json import parse_json_response

logger = logging.getLogger(__name__)


def default_models() -> tuple[str, ...]:
    return _dedupe_models(settings.OLLAMA_MODEL, settings.OLLAMA_MODEL_BACKUP)


def assessment_models() -> tuple[str, ...]:
    names = [
        settings.ASSESSMENT_OLLAMA_MODEL,
        settings.ASSESSMENT_OLLAMA_MODEL_BACKUP,
    ]
    if settings.ASSESSMENT_OLLAMA_FALLBACK_TO_GENERAL:
        names.extend([settings.OLLAMA_MODEL, settings.OLLAMA_MODEL_BACKUP])
    return _dedupe_models(*names)


def _dedupe_models(*names: str) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for name in names:
        if name and name not in seen:
            seen.add(name)
            ordered.append(name)
    return tuple(ordered)


def assessment_llm_options() -> dict[str, Any]:
    return {
        "models": assessment_models(),
        "timeout_seconds": settings.ASSESSMENT_OLLAMA_TIMEOUT_SECONDS,
    }


def assessment_sampling() -> dict[str, Any]:
    return {
        "temperature": settings.ASSESSMENT_OLLAMA_TEMPERATURE,
        "seed": settings.ASSESSMENT_OLLAMA_SEED,
    }


def generate(
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.2,
    models: tuple[str, ...] | None = None,
    timeout_seconds: float | None = None,
    seed: int | None = None,
) -> Optional[str]:
    """Single-turn text generation. Returns None if all models fail."""
    chain = models or default_models()
    timeout = (
        timeout_seconds
        if timeout_seconds is not None
        else settings.OLLAMA_TIMEOUT_SECONDS
    )
    for model in chain:
        try:
            options: dict[str, Any] = {
                "temperature": temperature,
                "num_predict": settings.OLLAMA_NUM_PREDICT,
                "num_ctx": settings.OLLAMA_NUM_CTX,
            }
            if seed is not None:
                options["seed"] = seed
            payload: dict[str, Any] = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": options,
            }
            if system:
                payload["system"] = system
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate",
                    json=payload,
                )
                response.raise_for_status()
                text = (response.json().get("response") or "").strip()
                if text:
                    return text
        except Exception as exc:
            logger.warning("ollama generate failed for model %s: %s", model, exc)
            continue
    logger.warning("ollama generate: all models failed (%s)", ", ".join(chain))
    return None


def chat(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.3,
    format_json: bool = False,
    models: tuple[str, ...] | None = None,
    timeout_seconds: float | None = None,
) -> Optional[str]:
    """Multi-turn chat completion. Each message: {role, content}."""
    chain = models or default_models()
    timeout = (
        timeout_seconds
        if timeout_seconds is not None
        else settings.OLLAMA_TIMEOUT_SECONDS
    )
    for model in chain:
        try:
            payload: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": settings.OLLAMA_NUM_PREDICT,
                    "num_ctx": settings.OLLAMA_NUM_CTX,
                },
            }
            if format_json:
                payload["format"] = "json"
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat",
                    json=payload,
                )
                response.raise_for_status()
                message = response.json().get("message") or {}
                text = (message.get("content") or "").strip()
                if text:
                    return text
        except Exception as exc:
            logger.warning("ollama chat failed for model %s: %s", model, exc)
            continue
    logger.warning("ollama chat: all models failed (%s)", ", ".join(chain))
    return None


__all__ = [
    "assessment_llm_options",
    "assessment_sampling",
    "assessment_models",
    "chat",
    "default_models",
    "generate",
    "parse_json_response",
]
