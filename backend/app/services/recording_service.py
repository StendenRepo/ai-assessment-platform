"""Recording storage and transcription orchestration (G2-136, G2-140, G2-141).

Audio is stored on-premise under RECORDING_DIR, registered as a FileRecord with
a GDPR deletion date, and attached to its own Recording row (an assessment may
have many recordings). Each recording is transcribed independently by the STT
container. Every action is written to the audit trail.
"""
import hashlib
import logging
import os
import uuid
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.core import crypto
from app.models.assessment import Assessment
from app.models.enums import AuditSource, TranscriptionStatus
from app.models.file_record import FileRecord
from app.models.recording import Recording
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


def append_recording(
    db: Session,
    *,
    assessment: Assessment,
    teacher: Teacher,
    audio_bytes: bytes,
    content_type: str | None = None,
    filename: str | None = None,
    ip_address: str | None = None,
) -> Recording:
    """Persist an uploaded recording as a new Recording row on the assessment.

    Assigns the next sequence number and a default display name. Does not
    transcribe — call transcribe_recording afterwards (or as a background task)
    so the upload response stays fast.
    """
    os.makedirs(settings.RECORDING_DIR, exist_ok=True)

    ext = _ext_for(content_type, filename)
    stored_name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.abspath(os.path.join(settings.RECORDING_DIR, stored_name))
    # Audio is encrypted at rest (G2-162); only ciphertext touches the volume.
    crypto.write_encrypted_file(path, audio_bytes)

    sha256 = hashlib.sha256(audio_bytes).hexdigest()
    delete_after = datetime.utcnow() + timedelta(days=settings.RECORDING_RETENTION_DAYS)

    record = FileRecord(
        path=path,
        file_type=content_type or "audio",
        size_bytes=len(audio_bytes),
        hash=sha256,
        delete_after=delete_after,
    )
    db.add(record)
    db.flush()  # populate record.id

    # Next sequence number for this assessment (count all rows, including
    # soft-deleted, so numbers never collide).
    max_seq = (
        db.query(func.max(Recording.sequence_number))
        .filter(Recording.assessment_id == assessment.id)
        .scalar()
    )
    seq = (max_seq or 0) + 1

    recording = Recording(
        assessment_id=assessment.id,
        file_id=record.id,
        display_name=f"Recording {seq}",
        sequence_number=seq,
        transcription_status=TranscriptionStatus.pending,
    )
    db.add(recording)
    db.flush()

    logger.info(
        "recording saved: %s (%d bytes) for assessment %s (seq %d)",
        path,
        len(audio_bytes),
        assessment.id,
        seq,
    )

    audit_service.log_action(
        db,
        action="recording.uploaded",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        assessment_id=assessment.id,
        details={
            "recording_id": str(recording.id),
            "file_id": str(record.id),
            "sequence_number": seq,
            "size_bytes": record.size_bytes,
            "sha256": sha256,
            "delete_after": delete_after.isoformat(),
        },
        ip_address=ip_address,
        commit=False,
    )
    db.commit()
    db.refresh(recording)
    return recording


def transcribe_recording(
    db: Session,
    *,
    recording: Recording,
    teacher: Teacher,
    language: str | None = None,
) -> Recording:
    """Transcribe a single recording via the STT container.

    ``language`` is an optional ISO code ("en", "nl", …); None auto-detects.
    Stores the transcript on the recording row and records the result in the
    audit trail.
    """
    record = (
        db.query(FileRecord).filter(FileRecord.id == recording.file_id).first()
    )
    if record is None:
        raise ValueError("Recording has no file to transcribe")

    recording.transcription_status = TranscriptionStatus.processing
    db.commit()

    try:
        audio_bytes = crypto.read_encrypted_file(record.path)
        result = stt_client.transcribe(
            audio_bytes, filename=os.path.basename(record.path), language=language
        )
    except Exception as exc:  # noqa: BLE001 - we want to persist the failure state
        recording.transcription_status = TranscriptionStatus.failed
        audit_service.log_action(
            db,
            action="recording.transcription_failed",
            source=AuditSource.system,
            teacher_id=teacher.id,
            teacher_name=teacher.name,
            assessment_id=recording.assessment_id,
            details={"recording_id": str(recording.id), "error": str(exc)},
            commit=False,
        )
        db.commit()
        raise

    recording.transcript_text = result["text"]
    recording.transcription_status = TranscriptionStatus.completed

    audit_service.log_action(
        db,
        action="recording.transcribed",
        source=AuditSource.ai,
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        assessment_id=recording.assessment_id,
        details={
            "recording_id": str(recording.id),
            "segment_count": len(result["segments"]),
        },
        commit=False,
    )
    db.commit()
    db.refresh(recording)
    return recording


def rename_recording(
    db: Session,
    *,
    recording: Recording,
    teacher: Teacher,
    new_name: str,
    ip_address: str | None = None,
) -> Recording:
    """Rename a recording (G2: editable display name)."""
    old_name = recording.display_name
    recording.display_name = new_name
    audit_service.log_action(
        db,
        action="recording.renamed",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        assessment_id=recording.assessment_id,
        details={
            "recording_id": str(recording.id),
            "old_name": old_name,
            "new_name": new_name,
        },
        ip_address=ip_address,
        commit=False,
    )
    db.commit()
    db.refresh(recording)
    return recording


class ExtensionNotAllowed(Exception):
    """Raised when an expiry extension would exceed the GDPR cap."""


def extend_expiry(
    db: Session,
    *,
    recording: Recording,
    teacher: Teacher,
    reason: str,
    extra_days: int,
    ip_address: str | None = None,
) -> Recording:
    """Extend a recording's deletion date within the GDPR cap (G2-141).

    Cap: at most RECORDING_MAX_EXTENSIONS extensions per recording, each adding
    at most RECORDING_MAX_EXTENSION_DAYS days, and a non-empty reason is required.
    """
    if not reason or not reason.strip():
        raise ExtensionNotAllowed("A reason is required to extend expiry")
    if extra_days < 1 or extra_days > settings.RECORDING_MAX_EXTENSION_DAYS:
        raise ExtensionNotAllowed(
            f"Extension must be between 1 and {settings.RECORDING_MAX_EXTENSION_DAYS} days"
        )

    record = db.query(FileRecord).filter(FileRecord.id == recording.file_id).first()
    if record is None:
        raise ExtensionNotAllowed("Recording has no file to extend")
    if record.extension_count >= settings.RECORDING_MAX_EXTENSIONS:
        raise ExtensionNotAllowed(
            f"Expiry can be extended at most {settings.RECORDING_MAX_EXTENSIONS} times"
        )

    old_delete_after = record.delete_after or datetime.utcnow()
    new_delete_after = old_delete_after + timedelta(days=extra_days)
    record.delete_after = new_delete_after
    record.extension_count += 1
    # Extending revives a recording that was already flagged for deletion.
    record.flagged_for_deletion = False

    audit_service.log_action(
        db,
        action="recording.expiry_extended",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        assessment_id=recording.assessment_id,
        details={
            "recording_id": str(recording.id),
            "file_id": str(record.id),
            "old_delete_after": old_delete_after.isoformat(),
            "new_delete_after": new_delete_after.isoformat(),
            "extra_days": extra_days,
            "reason": reason,
            "extension_count": record.extension_count,
        },
        ip_address=ip_address,
        commit=False,
    )
    db.commit()
    db.refresh(recording)
    return recording


def _soft_delete_recording(
    db: Session,
    recording: Recording,
    *,
    action: str,
    source: AuditSource = AuditSource.teacher,
    teacher: Teacher | None = None,
    reason: str | None = None,
    ip_address: str | None = None,
) -> None:
    """Shared removal path: unlink the audio file, mark deleted, keep the row.

    Used by BOTH the manual DELETE endpoint and the retention auto-purge so the
    removal + audit logic lives in exactly one place. The row and its file_record
    are retained for the audit trail; only the audio bytes on disk are removed.
    """
    now = datetime.utcnow()
    record = db.query(FileRecord).filter(FileRecord.id == recording.file_id).first()

    file_removed = False
    if record is not None:
        if record.path and os.path.exists(record.path):
            try:
                os.remove(record.path)
                file_removed = True
            except OSError as exc:  # noqa: BLE001 - keep going, but log
                logger.warning("could not remove recording file %s: %s", record.path, exc)
        record.deleted_at = now

    recording.deleted_at = now

    details = {
        "recording_id": str(recording.id),
        "file_id": str(record.id) if record else None,
        "file_removed": file_removed,
    }
    if reason is not None:
        details["reason"] = reason

    audit_service.log_action(
        db,
        action=action,
        source=source,
        teacher_id=teacher.id if teacher else None,
        teacher_name=teacher.name if teacher else None,
        assessment_id=recording.assessment_id,
        details=details,
        ip_address=ip_address,
        commit=False,
    )
    db.commit()


def delete_recording(
    db: Session,
    *,
    recording: Recording,
    teacher: Teacher,
    ip_address: str | None = None,
) -> None:
    """Manual soft-delete (teacher action). Shares the removal path with auto-purge."""
    _soft_delete_recording(
        db,
        recording,
        action="recording.deleted",
        source=AuditSource.teacher,
        teacher=teacher,
        ip_address=ip_address,
    )


def auto_delete_recording(db: Session, recording: Recording) -> None:
    """System purge of an expired recording (retention, G2-141).

    Same removal path as the manual delete, but attributed to the system and
    audited as ``recording.auto_deleted``.
    """
    _soft_delete_recording(
        db,
        recording,
        action="recording.auto_deleted",
        source=AuditSource.system,
        reason="retention expired, no action taken",
    )
