"""Tests for the STT service, focused on the live-subtitle chunk endpoint (FR-06).

faster-whisper is heavy (downloads model weights), so it is stubbed before the
app is imported. These tests assert the contract of /transcribe-chunk — text
only, using the SEPARATE small chunk model — without loading a real model.
"""
import io
import os
import struct
import sys
import types
import wave

# ── stub faster_whisper BEFORE importing the app ─────────────────────────────--
_recorded = {"chunk_model_built": 0, "batch_model_built": 0}


class _StubWhisperModel:
    def __init__(self, size, device=None, compute_type=None):
        # Track which model size was instantiated so we can prove the chunk
        # endpoint uses its own (small) model, separate from the batch model.
        if size == os.getenv("WHISPER_CHUNK_MODEL", "tiny"):
            _recorded["chunk_model_built"] += 1
        else:
            _recorded["batch_model_built"] += 1

    def transcribe(self, path, language=None, **kwargs):
        _recorded["last_kwargs"] = {"language": language, **kwargs}
        seg = types.SimpleNamespace(start=0.0, end=1.0, text="  hello world  ")
        info = types.SimpleNamespace(language="en", duration=1.0)
        return [seg], info


_fake = types.ModuleType("faster_whisper")
_fake.WhisperModel = _StubWhisperModel
sys.modules.setdefault("faster_whisper", _fake)

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient  # noqa: E402
import app as stt_app  # noqa: E402

client = TestClient(stt_app.app)


def _silent_wav_bytes(seconds: float = 1.0, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<" + "h" * int(rate * seconds), *([0] * int(rate * seconds))))
    return buf.getvalue()


def test_transcribe_chunk_returns_text_only():
    resp = client.post(
        "/transcribe-chunk",
        files={"file": ("chunk.wav", _silent_wav_bytes(), "audio/wav")},
    )
    assert resp.status_code == 200
    # text only (stripped), no segments/language/duration keys.
    assert resp.json() == {"text": "hello world"}


def test_transcribe_chunk_disables_vad():
    client.post(
        "/transcribe-chunk",
        files={"file": ("chunk.wav", _silent_wav_bytes(), "audio/wav")},
    )
    assert stt_app._chunk_model is not None
    assert _recorded["last_kwargs"]["vad_filter"] is False


def test_transcribe_chunk_uses_separate_chunk_model(monkeypatch):
    # The batch model must never be built/used by the chunk endpoint.
    def _boom():
        raise AssertionError("chunk endpoint must not use the batch model")

    monkeypatch.setattr(stt_app, "get_model", _boom)
    resp = client.post(
        "/transcribe-chunk",
        files={"file": ("chunk.wav", _silent_wav_bytes(), "audio/wav")},
    )
    assert resp.status_code == 200
    assert _recorded["chunk_model_built"] >= 1


def test_transcribe_chunk_accepts_language():
    resp = client.post(
        "/transcribe-chunk",
        files={"file": ("chunk.wav", _silent_wav_bytes(), "audio/wav")},
        data={"language": "nl"},
    )
    assert resp.status_code == 200
    assert _recorded["last_kwargs"]["language"] == "nl"
