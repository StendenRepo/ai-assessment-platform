"""On-premise speech-to-text service using faster-whisper.

A thin FastAPI wrapper around faster-whisper so the backend can transcribe
assessment recordings without any audio leaving the local network (GDPR).

It only transcribes — it never produces grades or grade-level judgements
(FR-06 constraint). The opening segment(s) carry the student's oral consent.
"""
import os
import tempfile

from faster_whisper import WhisperModel
from fastapi import FastAPI, File, Form, UploadFile

# tiny/base/small/medium/large-v3 — base is a reasonable CPU default on-prem.
MODEL_SIZE = os.getenv("WHISPER_MODEL", "base")
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
# Language is now chosen per request (see /transcribe). When the caller sends no
# language, faster-whisper auto-detects.

app = FastAPI(title="STT Service", version="0.1.0")

_model: WhisperModel | None = None


def get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
    return _model


@app.get("/health")
def health():
    return {"status": "healthy", "model": MODEL_SIZE}


@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: str | None = Form(default=None),
):
    suffix = os.path.splitext(file.filename or "")[1] or ".webm"
    audio_bytes = await file.read()

    # None -> faster-whisper auto-detects; "en", "nl", etc. force the language.
    requested_language = language or None

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        segments, info = get_model().transcribe(tmp_path, language=requested_language)
        out_segments = [
            {"start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip()}
            for s in segments
        ]
    finally:
        os.unlink(tmp_path)

    full_text = " ".join(s["text"] for s in out_segments).strip()
    return {
        "text": full_text,
        "language": info.language,
        "duration": round(info.duration, 3),
        "segments": out_segments,
    }
