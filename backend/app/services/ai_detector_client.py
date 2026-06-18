"""HTTP client for the on-premise AI text classifier microservice."""
from __future__ import annotations

from typing import Any, Optional

import httpx

from app.config import settings


def classify_text(text: str) -> Optional[dict[str, Any]]:
    """Return classifier JSON or None if the detector service is unavailable."""
    if not text or not text.strip():
        return None
    url = f"{settings.AI_DETECTOR_URL.rstrip('/')}/classify"
    try:
        with httpx.Client(timeout=settings.AI_DETECTOR_TIMEOUT_SECONDS) as client:
            response = client.post(url, json={"text": text})
            response.raise_for_status()
            payload = response.json()
            if not payload.get("available", True):
                return None
            return payload
    except Exception:
        return None
