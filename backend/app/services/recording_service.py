"""Recording storage and transcription orchestration (G2-136, G2-140, G2-141).

Audio is stored on-premise under RECORDING_DIR, registered as a FileRecord with
a GDPR deletion date, linked to the assessment, then transcribed by the STT
container. Every action is written to the audit trail.
"""
import hashlib
import logging
import os
import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.models.assessment import Assessment
from app.models.enums import AuditSource, TranscriptionStatus
from app.models.file_record import FileRecord
from app.models.teacher import Teacher
from app.services import audit_service, stt_client

logger = logging.getLogger("recording")


def _ext_for(content_type: str | None, filename: str | None) -> str:
    if filename and "." in filename:
        return os.path.splitext(filename)[1]
    mapping = {
        "audio/webm": ".webm",
        "audio/ogg": ".ogg",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
    }
    return mapping.get(content_type or "", ".webm")


def save_recording(
    db: Session,
    *,
    assessment: Assessment,
    teacher: Teacher,
    audio_bytes: bytes,
    content_type: str | None = None,
    filename: str | None = None,
    ip_address: str | None = None,
) -> FileRecord:
    """Persist an uploaded recording and attach it to the assessment.

    Does not transcribe — call transcribe_recording afterwards (or as a
    background task) so the upload response stays fast.
    """
    os.makedirs(settings.RECORDING_DIR, exist_ok=True)

    ext = _ext_for(content_type, filename)
    stored_name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.abspath(os.path.join(settings.RECORDING_DIR, stored_name))
    with open(path, "wb") as fh:
        fh.write(audio_bytes)
    logger.info(
        "recording saved: %s (%d bytes) for assessment %s",
        path,
        len(audio_bytes),
        assessment.id,
    )

    sha256 = hashlib.sha256(audio_bytes).hexdigest()
    delete_after = datetime.utcnow() + timedelta(
        days=settings.RECORDING_RETENTION_DAYS
    )

    record = FileRecord(
        path=path,
        file_type=content_type or "audio",
        size_bytes=len(audio_bytes),
        hash=sha256,
        delete_after=delete_after,
    )
    db.add(record)
    db.flush()  # populate record.id

    assessment.recording_file_id = record.id
    assessment.transcription_status = TranscriptionStatus.pending
    db.flush()

    audit_service.log_action(
        db,
        action="recording.uploaded",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        assessment_id=assessment.id,
        details={
            "file_id": str(record.id),
            "size_bytes": record.size_bytes,
            "sha256": sha256,
            "delete_after": delete_after.isoformat(),
        },
        ip_address=ip_address,
        commit=False,
    )
    db.commit()
    db.refresh(record)
    return record


def transcribe_recording(
    db: Session,
    *,
    assessment: Assessment,
    teacher: Teacher,
) -> Assessment:
    """Transcribe the assessment's recording via the STT container.

    Stores the full transcript on the assessment and records the result in the
    audit trail. The opening segment carries the oral consent statement, which
    the teacher confirms separately (assessment_service.set_consent).
    """
    record = db.query(FileRecord).filter(FileRecord.id == assessment.recording_file_id).first()
    if record is None:
        raise ValueError("Assessment has no recording to transcribe")

    assessment.transcription_status = TranscriptionStatus.processing
    db.commit()

    try:
        with open(record.path, "rb") as fh:
            audio_bytes = fh.read()
        result = stt_client.transcribe(audio_bytes, filename=os.path.basename(record.path))
    except Exception as exc:  # noqa: BLE001 - we want to persist the failure state
        assessment.transcription_status = TranscriptionStatus.failed
        audit_service.log_action(
            db,
            action="recording.transcription_failed",
            source=AuditSource.system,
            teacher_id=teacher.id,
            teacher_name=teacher.name,
            assessment_id=assessment.id,
            details={"error": str(exc)},
            commit=False,
        )
        db.commit()
        raise

    assessment.transcript_text = result["text"]
    assessment.transcription_status = TranscriptionStatus.completed

    audit_service.log_action(
        db,
        action="recording.transcribed",
        source=AuditSource.ai,
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        assessment_id=assessment.id,
        details={"segment_count": len(result["segments"])},
        commit=False,
    )
    db.commit()
    db.refresh(assessment)
    return assessment
