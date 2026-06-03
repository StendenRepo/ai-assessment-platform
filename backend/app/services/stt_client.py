"""Client for the on-premise faster-whisper STT container.

Kept separate so it can be mocked in tests and swapped without touching the
recording orchestration logic. No audio ever leaves the local network.
"""
from typing import TypedDict

import httpx

from app.config import settings


class TranscriptionSegment(TypedDict):
    start: float
    end: float
    text: str


class TranscriptionResult(TypedDict):
    text: str
    segments: list[TranscriptionSegment]


def transcribe(audio_bytes: bytes, filename: str = "recording.webm") -> TranscriptionResult:
    """Send audio to the STT service and return the full text plus segments.

    The opening segment(s) hold the oral consent statement, which the teacher
    reviews before confirming consent.
    """
    response = httpx.post(
        f"{settings.STT_URL}/transcribe",
        files={"file": (filename, audio_bytes, "application/octet-stream")},
        timeout=settings.STT_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()
    return {
        "text": data.get("text", ""),
        "segments": data.get("segments", []),
    }
