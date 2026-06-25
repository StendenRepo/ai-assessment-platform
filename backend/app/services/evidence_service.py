import base64
import hashlib
import hmac
import io
import logging
import mimetypes
import uuid as _uuid
from datetime import datetime
from pathlib import Path

from docx import Document as DocxDocument
from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.config import settings
from app.models.enums import EmbeddingStatus, FileType, NotificationType, SourceType
from app.models.evidence import Evidence
from app.models.evidence_match import EvidenceMatch
from app.models.overlap_signal import OverlapSignal
from app.models.project import Project
from app.models.student import Student
from app.services import notification_service
from app.services.text_extraction import extract_document_text_strict


logger = logging.getLogger(__name__)


def _purge_generation_runs_for_student(db: Session, student_id: str) -> None:
    from app.models.assessment import Assessment
    from app.models.evidence_match import EvidenceMatch
    from app.models.generation_run import GenerationRun
    from app.models.notification import Notification

    run_ids = [
        rid
        for (rid,) in db.query(GenerationRun.id)
        .join(Assessment, GenerationRun.assessment_id == Assessment.id)
        .filter(Assessment.student_id == student_id)
        .all()
    ]
    if not run_ids:
        return
    db.query(Notification).filter(
        Notification.generation_run_id.in_(run_ids)
    ).delete(synchronize_session=False)
    db.query(EvidenceMatch).filter(
        EvidenceMatch.run_id.in_(run_ids)
    ).delete(synchronize_session=False)
    db.query(GenerationRun).filter(
        GenerationRun.id.in_(run_ids)
    ).delete(synchronize_session=False)


def _parse_uuid(value: str, label: str = "id") -> _uuid.UUID:
    """Parse *value* as a UUID, raising HTTP 422 if it is not valid."""
    try:
        return _uuid.UUID(str(value))
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid {label}: '{value}' is not a valid UUID",
        )


def _teacher_can_access_evidence(evidence: Evidence, teacher) -> bool:
    """Return True if *teacher* may read this evidence file.

    Admins can access everything. Otherwise the evidence must resolve to a
    module owned by the teacher — either directly through its project, or
    through any project the linked student belongs to. Mirrors the
    teacher → module → group → student/project ownership chain used elsewhere.
    """
    if getattr(teacher, "is_admin", False):
        return True
    if evidence.project and evidence.project.module:
        if evidence.project.module.teacher_id == teacher.id:
            return True
    if evidence.student:
        for project in evidence.student.projects:
            if project.module and project.module.teacher_id == teacher.id:
                return True
    return False


def _evidence_upload_dir() -> Path:
    return Path(settings.UPLOAD_DIR) / "evidence"


EVIDENCE_UPLOAD_DIR = Path(settings.UPLOAD_DIR) / "evidence"


def _evidence_text_dir() -> Path:
    return Path(settings.UPLOAD_DIR) / "evidence_text"


def _full_path_for(relative_path: str) -> Path:
    return _evidence_upload_dir() / relative_path


def _text_path_for(file_path: Path) -> Path:
    evidence_root = _evidence_upload_dir()
    try:
        relative_path = file_path.relative_to(evidence_root)
    except ValueError:
        relative_path = Path(file_path.name)
    return _evidence_text_dir() / relative_path.parent / f"{relative_path.name}.txt"


def _should_store_text_sidecar(file_type: FileType) -> bool:
    return file_type == FileType.image


def _image_placeholder_text(filename: str) -> str:
    return f"[Image evidence uploaded: {filename}]"


def _is_image_placeholder_text(text: str) -> bool:
    value = (text or "").strip()
    return value.startswith("[Image evidence uploaded:") and value.endswith("]")


def _student_storage_key(student_id: str) -> str:
    # Deterministic pseudonymization to avoid exposing raw student numbers in paths.
    digest = hmac.new(
        settings.EVIDENCE_PATH_SALT.encode("utf-8"),
        str(student_id).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"s_{digest[:24]}"


def _project_storage_key(project_id: str) -> str:
    digest = hmac.new(
        settings.EVIDENCE_PATH_SALT.encode("utf-8"),
        str(project_id).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"p_{digest[:24]}"

# ---------------------------------------------------------------------------
# Supported file types — extend this dict when new user stories are added.
# Key   : lowercase file extension (with dot)
# Value : FileType enum value
# ---------------------------------------------------------------------------
SUPPORTED_EXTENSIONS: dict[str, FileType] = {
    ".md": FileType.markdown,
    ".txt": FileType.other,
    ".docx": FileType.docx,
    ".pdf": FileType.pdf,
    ".xlsx": FileType.xlsx,
    ".csv": FileType.other,
    ".png": FileType.image,
    ".jpg": FileType.image,
    ".jpeg": FileType.image,
}


def _resolve_file_type(filename: str) -> FileType:
    """Return the FileType for *filename*, or raise 422 if unsupported."""
    ext = Path(filename).suffix.lower()
    file_type = SUPPORTED_EXTENSIONS.get(ext)
    if file_type is None:
        allowed = ", ".join(SUPPORTED_EXTENSIONS.keys())
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type '{ext}'. Allowed: {allowed}",
        )
    return file_type


def _extract_text(raw: bytes, file_type: FileType, filename: str) -> str:
    """Extract plain-text content from *raw* bytes based on *file_type*."""
    if file_type == FileType.markdown:
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Markdown file is not valid UTF-8 text",
            )

    if file_type == FileType.docx:
        try:
            doc = DocxDocument(io.BytesIO(raw))
            return "\n".join(
                paragraph.text for paragraph in doc.paragraphs
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Could not parse '{filename}' as a valid Word document (.docx)",
            )

    if file_type == FileType.pdf:
        try:
            reader = PdfReader(io.BytesIO(raw))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n\n".join(pages)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Could not parse '{filename}' as a valid PDF",
            )

    if file_type in (FileType.xlsx, FileType.other):
        try:
            return extract_document_text_strict(raw, filename)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

    if file_type == FileType.image:
        return _extract_image_text(raw, filename)

    # Fallback for any future types not yet handled
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"Text extraction not implemented for file type '{file_type}'",
    )


def _extract_image_text(raw: bytes, filename: str) -> str:
    """Validate an image and describe it using the Ollama vision model."""
    _validate_image(raw, filename)

    text = _extract_image_text_with_vision(raw, filename)
    return text.strip() or _image_placeholder_text(filename)


def _validate_image(raw: bytes, filename: str) -> None:
    """Ensure uploaded bytes are a valid image payload."""
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
        image.close()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not parse '{filename}' as a valid image",
        )

def _extract_image_text_with_vision(raw: bytes, filename: str) -> str:
    """Describe an image using the configured Ollama vision model.

    Returns empty string if the model is unavailable or fails so the caller
    can fall back to the default placeholder text.
    """
    model = settings.VISION_MODEL
    if not model:
        return ""

    try:
        import httpx

        b64 = base64.b64encode(raw).decode("ascii")
        prompt = (
            "You are an assistant that extracts and describes the content of images "
            "submitted as student evidence. "
            "Describe what you see in detail: any visible text, diagrams, screenshots, "
            "code, or other content. Be thorough but concise. "
            "If the image contains text, transcribe it exactly."
        )
        with httpx.Client(timeout=settings.VISION_TIMEOUT_SECONDS) as client:
            response = client.post(
                f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "images": [b64],
                    "stream": False,
                },
            )
            response.raise_for_status()
            text = (response.json().get("response") or "").strip()
            return text
    except Exception as exc:
        logger.warning(
            "Vision extraction failed for '%s' using model '%s': %s",
            filename,
            model,
            exc,
        )
        return ""



def _create_ai_processing_complete_notification(
    db: Session,
    *,
    evidence: Evidence,
    teacher_id: str | None = None,
    subject_label: str | None = None,
) -> None:
    teacher_uuid = None
    if teacher_id:
        try:
            teacher_uuid = _uuid.UUID(str(teacher_id))
        except (ValueError, TypeError, AttributeError):
            teacher_uuid = None

    if teacher_uuid is None and evidence.project and evidence.project.module:
        teacher_uuid = evidence.project.module.teacher_id

    if teacher_uuid is None and evidence.student and evidence.student.projects:
        first_project = evidence.student.projects[0]
        if first_project and first_project.module:
            teacher_uuid = first_project.module.teacher_id

    if teacher_uuid is None:
        return

    if subject_label:
        subject = subject_label
    elif evidence.student and evidence.student.name:
        subject = f"student {evidence.student.name}"
    elif evidence.project and evidence.project.name:
        subject = f"project {evidence.project.name}"
    else:
        subject = "your upload"

    target_path = None
    if evidence.project and evidence.project.module_id:
        target_path = (
            f"/modules/{evidence.project.module_id}/groups/{evidence.project.id}"
        )
    elif evidence.student and evidence.student.projects:
        first_project = evidence.student.projects[0]
        if first_project and first_project.module_id:
            target_path = (
                f"/modules/{first_project.module_id}/groups/{first_project.id}"
                f"/students/{evidence.student.student_number}"
            )

    notification_service.create_notification(
        db,
        teacher_id=teacher_uuid,
        type=NotificationType.ai_processing_complete,
        message=f"AI finished processing '{evidence.file_name}' for {subject}.",
        target_path=target_path,
        commit=False,
    )


def _create_ai_processing_failed_notification(
    db: Session,
    *,
    evidence: Evidence,
    teacher_id: str | None = None,
    subject_label: str | None = None,
) -> None:
    teacher_uuid = None
    if teacher_id:
        try:
            teacher_uuid = _uuid.UUID(str(teacher_id))
        except (ValueError, TypeError, AttributeError):
            teacher_uuid = None

    if teacher_uuid is None and evidence.project and evidence.project.module:
        teacher_uuid = evidence.project.module.teacher_id

    if teacher_uuid is None and evidence.student and evidence.student.projects:
        first_project = evidence.student.projects[0]
        if first_project and first_project.module:
            teacher_uuid = first_project.module.teacher_id

    if teacher_uuid is None:
        return

    if subject_label:
        subject = subject_label
    elif evidence.student and evidence.student.name:
        subject = f"student {evidence.student.name}"
    elif evidence.project and evidence.project.name:
        subject = f"project {evidence.project.name}"
    else:
        subject = "your upload"

    target_path = None
    if evidence.project and evidence.project.module_id:
        target_path = (
            f"/modules/{evidence.project.module_id}/groups/{evidence.project.id}"
        )
    elif evidence.student and evidence.student.projects:
        first_project = evidence.student.projects[0]
        if first_project and first_project.module_id:
            target_path = (
                f"/modules/{first_project.module_id}/groups/{first_project.id}"
                f"/students/{evidence.student.student_number}"
            )

    notification_service.create_notification(
        db,
        teacher_id=teacher_uuid,
        type=NotificationType.ai_processing_failed,
        message=f"AI failed to process '{evidence.file_name}' for {subject}.",
        target_path=target_path,
        commit=False,
    )


def run_vision_background(
    evidence_id: str,
    teacher_id: str | None = None,
    subject_label: str | None = None,
) -> None:
    """FastAPI background task: run vision AI on an image evidence record.

    Creates its own DB session so it executes outside the original request
    context.  On success the sidecar is replaced with the AI description and
    ``embedding_status`` is set to ``completed``.  On any failure the status
    is set to ``failed`` so the frontend can surface the error.
    """
    from app.database import SessionLocal  # imported here to avoid circular import at module level

    db = SessionLocal()
    try:
        evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
        if not evidence:
            return
        if evidence.embedding_status == EmbeddingStatus.completed:
            return

        full_path = _full_path_for(evidence.file_path)
        if not full_path.exists():
            evidence.embedding_status = EmbeddingStatus.failed
            _create_ai_processing_failed_notification(
                db,
                evidence=evidence,
                teacher_id=teacher_id,
                subject_label=subject_label,
            )
            db.add(evidence)
            db.commit()
            return

        raw = full_path.read_bytes()
        text = _extract_image_text_with_vision(raw, evidence.file_name)
        content = text.strip() or _image_placeholder_text(evidence.file_name)

        text_path = _text_path_for(full_path)
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text(content, encoding="utf-8")

        # Only mark completed when AI produced real text. Placeholder means the
        # vision call failed/unavailable and should be surfaced as failed.
        if _is_image_placeholder_text(content):
            evidence.embedding_status = EmbeddingStatus.failed
            logger.warning(
                "Vision returned no content for '%s'; keeping placeholder and marking failed",
                evidence.file_name,
            )
            _create_ai_processing_failed_notification(
                db,
                evidence=evidence,
                teacher_id=teacher_id,
                subject_label=subject_label,
            )
        else:
            evidence.embedding_status = EmbeddingStatus.completed
            _create_ai_processing_complete_notification(
                db,
                evidence=evidence,
                teacher_id=teacher_id,
                subject_label=subject_label,
            )
        db.add(evidence)
        db.commit()
    except Exception:
        logger.exception("Background vision task failed for evidence %s", evidence_id)
        try:
            ev = db.query(Evidence).filter(Evidence.id == evidence_id).first()
            if ev:
                ev.embedding_status = EmbeddingStatus.failed
                _create_ai_processing_failed_notification(
                    db,
                    evidence=ev,
                    teacher_id=teacher_id,
                    subject_label=subject_label,
                )
                db.add(ev)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


class EvidenceService:
    @staticmethod
    def _delete_evidence_artifacts(evidence: Evidence) -> None:
        full_path = _full_path_for(evidence.file_path)
        text_path = _text_path_for(full_path)
        try:
            if full_path.exists():
                full_path.unlink()
            if text_path.exists():
                text_path.unlink()
        except OSError:
            pass

    @staticmethod
    def _purge_overlap_associations(evidence_id, db: Session) -> None:
        db.query(OverlapSignal).filter(
            or_(
                OverlapSignal.evidence_a_id == evidence_id,
                OverlapSignal.evidence_b_id == evidence_id,
            )
        ).delete(synchronize_session=False)
        db.query(EvidenceMatch).filter(
            EvidenceMatch.evidence_id == evidence_id
        ).delete(synchronize_session=False)

    @staticmethod
    def _delete_evidence_rows(evidence_items: list[Evidence], db: Session) -> None:
        for evidence in evidence_items:
            EvidenceService._purge_overlap_associations(evidence.id, db)
            db.delete(evidence)

    @staticmethod
    def _mark_completed_if_ready(evidence: Evidence, db: Session) -> bool:
        if evidence.embedding_status != EmbeddingStatus.pending:
            return False

        full_path = _full_path_for(evidence.file_path)
        if not full_path.exists():
            return False

        text_path = _text_path_for(full_path)
        if not text_path.exists():
            try:
                EvidenceService._extract_and_store_text(evidence, full_path)
            except HTTPException:
                return False

        evidence.embedding_status = EmbeddingStatus.completed
        db.add(evidence)
        return True

    # ------------------------------------------------------------------
    # Upload a file as evidence for a student
    # ------------------------------------------------------------------
    @staticmethod
    def upload_file(
        student_id: str,
        file: UploadFile,
        db: Session,
    ) -> Evidence:
        return EvidenceService._upload_file(
            student_id=student_id,
            project_id=None,
            file=file,
            db=db,
        )

    @staticmethod
    def upload_file_for_project(
        project_id: str,
        file: UploadFile,
        db: Session,
    ) -> Evidence:
        return EvidenceService._upload_file(
            student_id=None,
            project_id=project_id,
            file=file,
            db=db,
        )

    @staticmethod
    def _upload_file(
        *,
        student_id: str | None,
        project_id: str | None,
        file: UploadFile,
        db: Session,
    ) -> Evidence:
        if bool(student_id) == bool(project_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide exactly one evidence scope",
            )

        if student_id:
            student = db.get(Student, student_id)
            if not student:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Student not found",
                )
        else:
            project = db.get(Project, project_id)
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )

        filename = file.filename or ""
        file_type = _resolve_file_type(filename)
        raw = file.file.read()

        if file_type == FileType.image:
            _validate_image(raw, filename)
            initial_status = EmbeddingStatus.processing
            sidecar_content: str | None = _image_placeholder_text(filename)
        else:
            sidecar_content = _extract_text(raw, file_type, filename)
            initial_status = EmbeddingStatus.completed

        storage_key = (
            _student_storage_key(student_id)
            if student_id
            else _project_storage_key(project_id)
        )
        upload_dir = _evidence_upload_dir() / storage_key
        upload_dir.mkdir(parents=True, exist_ok=True)

        unique_name = f"{_uuid.uuid4().hex}_{filename}"
        file_path = upload_dir / unique_name
        file_path.write_bytes(raw)
        if _should_store_text_sidecar(file_type) and sidecar_content is not None:
            text_path = _text_path_for(file_path)
            text_path.parent.mkdir(parents=True, exist_ok=True)
            text_path.write_text(sidecar_content, encoding="utf-8")

        relative_path = str(file_path.relative_to(_evidence_upload_dir()))
        evidence = Evidence(
            student_id=student_id,
            project_id=project_id,
            file_name=filename,
            file_type=file_type,
            file_path=relative_path,
            source_type=SourceType.upload,
            embedding_status=initial_status,
        )
        db.add(evidence)
        db.commit()
        db.refresh(evidence)
        return evidence

    # ------------------------------------------------------------------
    # List all evidence for a student
    # ------------------------------------------------------------------
    @staticmethod
    def list_for_student(student_id: str, db: Session) -> list[Evidence]:
        student = db.get(Student, student_id)
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found",
            )
        project_ids = [project.id for project in student.projects]
        evidence_list = db.query(Evidence).filter(Evidence.student_id == student_id).all()
        if project_ids:
            evidence_list.extend(
                db.query(Evidence).filter(Evidence.project_id.in_(project_ids)).all()
            )
        evidence_list = sorted(
            {e.id: e for e in evidence_list}.values(),
            key=lambda evidence: evidence.uploaded_at or datetime.min,
            reverse=True,
        )
        changed = False
        for evidence in evidence_list:
            changed = EvidenceService._mark_completed_if_ready(evidence, db) or changed
        if changed:
            db.commit()
        return evidence_list

    @staticmethod
    def list_for_project(project_id: str, db: Session) -> list[Evidence]:
        project = db.get(Project, project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )
        evidence_list = (
            db.query(Evidence)
            .filter(Evidence.project_id == project_id)
            .order_by(Evidence.uploaded_at.desc())
            .all()
        )
        changed = False
        for evidence in evidence_list:
            changed = EvidenceService._mark_completed_if_ready(evidence, db) or changed
        if changed:
            db.commit()
        return evidence_list

    @staticmethod
    def delete_for_student(student_id: str, db: Session) -> None:
        evidence_items = db.query(Evidence).filter(Evidence.student_id == student_id).all()
        EvidenceService._delete_evidence_rows(evidence_items, db)
        db.commit()
        for evidence in evidence_items:
            EvidenceService._delete_evidence_artifacts(evidence)

    @staticmethod
    def delete_for_project(project_id: str, db: Session) -> None:
        evidence_items = db.query(Evidence).filter(Evidence.project_id == project_id).all()
        EvidenceService._delete_evidence_rows(evidence_items, db)
        db.commit()
        for evidence in evidence_items:
            EvidenceService._delete_evidence_artifacts(evidence)

    # ------------------------------------------------------------------
    # Delete an evidence record (DB + file on disk)
    # ------------------------------------------------------------------
    @staticmethod
    def delete(evidence_id: str, db: Session) -> None:
        evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
        if not evidence:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evidence not found",
            )
        EvidenceService._purge_overlap_associations(evidence.id, db)
        EvidenceService._delete_evidence_artifacts(evidence)
        _purge_generation_runs_for_student(db, evidence.student_id)
        db.delete(evidence)
        db.commit()

    # ------------------------------------------------------------------
    # Read the raw text content of a single evidence record
    # ------------------------------------------------------------------
    @staticmethod
    def read_content(evidence_id: str, db: Session, teacher=None) -> tuple[Evidence, str]:
        evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
        if not evidence:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evidence not found",
            )
        if teacher is not None and not _teacher_can_access_evidence(evidence, teacher):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evidence not found",
            )
        full_path = _full_path_for(evidence.file_path)
        if not full_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evidence file not found on disk",
            )
        content = EvidenceService._read_or_rebuild_text_content(evidence)
        if EvidenceService._mark_completed_if_ready(evidence, db):
            db.commit()
        return evidence, content

    @staticmethod
    def reprocess_content(evidence_id: str, db: Session) -> tuple[Evidence, str]:
        evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
        if not evidence:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evidence not found",
            )
        full_path = _full_path_for(evidence.file_path)
        if not full_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evidence file not found on disk",
            )

        content = EvidenceService._extract_and_store_text(evidence, full_path)
        evidence.embedding_status = EmbeddingStatus.completed
        db.add(evidence)
        db.commit()
        return evidence, content

    @staticmethod
    def get_raw_file(evidence_id: str, db: Session, teacher=None) -> tuple[Evidence, Path, str]:
        evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
        if not evidence:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evidence not found",
            )
        if teacher is not None and not _teacher_can_access_evidence(evidence, teacher):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evidence not found",
            )

        full_path = _full_path_for(evidence.file_path)
        if not full_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evidence file not found on disk",
            )

        media_type, _ = mimetypes.guess_type(evidence.file_name)
        if EvidenceService._mark_completed_if_ready(evidence, db):
            db.commit()
        return evidence, full_path, media_type or "application/octet-stream"

    @staticmethod
    def _read_or_rebuild_text_content(evidence: Evidence) -> str:
        full_path = _full_path_for(evidence.file_path)
        text_path = _text_path_for(full_path)
        file_type = evidence.file_type or _resolve_file_type(evidence.file_name)

        if _should_store_text_sidecar(file_type) and text_path.exists():
            sidecar_text = text_path.read_text(encoding="utf-8")
            # Never run vision synchronously in a read/preview request.
            # Return whatever sidecar exists so the UI stays responsive.
            if file_type == FileType.image and _is_image_placeholder_text(sidecar_text):
                return sidecar_text
            return sidecar_text

        if file_type == FileType.markdown:
            try:
                return full_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                return EvidenceService._extract_and_store_text(evidence, full_path)

        return EvidenceService._extract_and_store_text(evidence, full_path)

    @staticmethod
    def _extract_and_store_text(evidence: Evidence, full_path: Path) -> str:
        file_type = evidence.file_type or _resolve_file_type(evidence.file_name)
        raw = full_path.read_bytes()
        content = _extract_text(raw, file_type, evidence.file_name)
        if _should_store_text_sidecar(file_type):
            text_path = _text_path_for(full_path)
            text_path.parent.mkdir(parents=True, exist_ok=True)
            text_path.write_text(content, encoding="utf-8")
        return content
