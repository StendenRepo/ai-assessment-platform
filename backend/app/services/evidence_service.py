import base64
import hashlib
import hmac
import io
import logging
import mimetypes
import uuid as _uuid
from pathlib import Path

from docx import Document as DocxDocument
from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.config import settings
from app.models.enums import EmbeddingStatus, FileType, SourceType
from app.models.evidence import Evidence
from app.models.student import Student


logger = logging.getLogger(__name__)


def _parse_uuid(value: str, label: str = "id") -> _uuid.UUID:
    """Parse *value* as a UUID, raising HTTP 422 if it is not valid."""
    try:
        return _uuid.UUID(str(value))
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid {label}: '{value}' is not a valid UUID",
        )


def _evidence_upload_dir() -> Path:
    return Path(settings.UPLOAD_DIR) / "evidence"


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

# ---------------------------------------------------------------------------
# Supported file types — extend this dict when new user stories are added.
# Key   : lowercase file extension (with dot)
# Value : FileType enum value
# ---------------------------------------------------------------------------
SUPPORTED_EXTENSIONS: dict[str, FileType] = {
    ".md": FileType.markdown,
    ".docx": FileType.docx,
    ".pdf": FileType.pdf,
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

    if file_type == FileType.image:
        return _extract_image_text(raw, filename)

    # Fallback for any future types not yet handled
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"Text extraction not implemented for file type '{file_type}'",
    )


def _extract_image_text(raw: bytes, filename: str) -> str:
    """Validate an image and describe it using the Ollama vision model.

    Falls back to a placeholder marker when the vision model is unavailable so
    the evidence record is never empty.
    """
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
        image.close()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not parse '{filename}' as a valid image",
        )

    text = _extract_image_text_with_vision(raw, filename)
    return text.strip() or _image_placeholder_text(filename)


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



class EvidenceService:
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
        student = db.get(Student, student_id)
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found",
            )

        # Resolve & validate file type
        filename = file.filename or ""
        file_type = _resolve_file_type(filename)

        # Read raw bytes and extract plain-text content per file type
        raw = file.file.read()
        content = _extract_text(raw, file_type, filename)

        # Persist to disk
        upload_dir = _evidence_upload_dir() / _student_storage_key(student_id)
        upload_dir.mkdir(parents=True, exist_ok=True)

        unique_name = f"{_uuid.uuid4().hex}_{filename}"
        file_path = upload_dir / unique_name
        file_path.write_bytes(raw)
        if _should_store_text_sidecar(file_type):
            text_path = _text_path_for(file_path)
            text_path.parent.mkdir(parents=True, exist_ok=True)
            text_path.write_text(content, encoding="utf-8")

        # Store path relative to the evidence upload root so the record stays
        # portable when the base upload directory changes.
        relative_path = str(file_path.relative_to(_evidence_upload_dir()))

        # The evidence is immediately usable once the raw file and extracted
        # text sidecar have been written, so mark it completed at upload time.
        evidence = Evidence(
            student_id=student_id,
            file_name=filename,
            file_type=file_type,
            file_path=relative_path,
            source_type=SourceType.upload,
            embedding_status=EmbeddingStatus.completed,
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
        evidence_list = (
            db.query(Evidence)
            .filter(Evidence.student_id == student_id)
            .order_by(Evidence.uploaded_at.desc())
            .all()
        )
        changed = False
        for evidence in evidence_list:
            changed = EvidenceService._mark_completed_if_ready(evidence, db) or changed
        if changed:
            db.commit()
        return evidence_list

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
        # Reconstruct full path from the stored relative path
        full_path = _full_path_for(evidence.file_path)
        text_path = _text_path_for(full_path)

        # Remove evidence artifacts from disk (ignore if already gone)
        try:
            if full_path.exists():
                full_path.unlink()
            if text_path.exists():
                text_path.unlink()
        except OSError:
            pass  # Log in production; don't block the DB delete

        db.delete(evidence)
        db.commit()

    # ------------------------------------------------------------------
    # Read the raw text content of a single evidence record
    # ------------------------------------------------------------------
    @staticmethod
    def read_content(evidence_id: str, db: Session) -> tuple[Evidence, str]:
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
    def get_raw_file(evidence_id: str, db: Session) -> tuple[Evidence, Path, str]:
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
            # Retry AI extraction when the sidecar still contains fallback text.
            if file_type == FileType.image and _is_image_placeholder_text(sidecar_text):
                refreshed = EvidenceService._extract_and_store_text(evidence, full_path)
                return refreshed
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
