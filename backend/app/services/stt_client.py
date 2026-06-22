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


def transcribe(
    audio_bytes: bytes,
    filename: str = "recording.webm",
    language: str | None = None,
) -> TranscriptionResult:
    """Send audio to the STT service and return the full text plus segments.

    ``language`` is an optional ISO code ("en", "nl", …); None lets the STT
    service auto-detect. The opening segment(s) hold the oral consent statement,
    which the teacher reviews before confirming consent.
    """
    response = httpx.post(
        f"{settings.STT_URL}/transcribe",
        files={"file": (filename, audio_bytes, "application/octet-stream")},
        data={"language": language} if language else None,
        timeout=settings.STT_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()
    return {
        "text": data.get("text", ""),
        "segments": data.get("segments", []),
    }


def transcribe_chunk(audio_bytes: bytes, language: str | None = None) -> dict:
    """Low-latency transcription of one short WAV chunk for live subtitles (FR-06).

    Separate from transcribe(): hits the STT /transcribe-chunk endpoint (small
    model) with a short timeout so a slow chunk is dropped rather than stalling
    the transient live caption. The result is never persisted and is never the
    official transcript. Raises on any HTTP/transport error; callers treat the
    live path as best-effort and ignore failures.
    """
    response = httpx.post(
        f"{settings.STT_URL}/transcribe-chunk",
        files={"file": ("chunk.wav", audio_bytes, "application/octet-stream")},
        data={"language": language} if language else None,
        timeout=settings.STT_CHUNK_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()
    return {"text": data.get("text", "")}
