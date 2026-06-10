import io
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


def _full_path_for(relative_path: str) -> Path:
    return _evidence_upload_dir() / relative_path


def _text_path_for(file_path: Path) -> Path:
    return file_path.with_name(f"{file_path.name}.txt")

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
    """Validate an image upload and extract text when OCR is available.

    OCR is optional in the current stack. If an OCR engine is not installed or
    returns no text, keep the upload successful and persist a readable marker so
    the evidence record still has content for downstream consumers.
    """
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except UnidentifiedImageError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not parse '{filename}' as a valid image",
        )
    except OSError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not parse '{filename}' as a valid image",
        )

    text = ""
    try:
        import pytesseract

        text = pytesseract.image_to_string(image)
    except Exception:
        text = ""
    finally:
        image.close()

    text = text.strip()
    if text:
        return text

    return f"[Image evidence uploaded: {filename}]"


class EvidenceService:
    # ------------------------------------------------------------------
    # Upload a file as evidence for a student
    # ------------------------------------------------------------------
    @staticmethod
    def upload_file(
        student_id: str,
        file: UploadFile,
        db: Session,
    ) -> Evidence:
        # Validate student_id is a proper UUID, then verify student exists
        _parse_uuid(student_id, "student_id")
        student = db.query(Student).filter(Student.id == student_id).first()
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
        upload_dir = _evidence_upload_dir() / str(student_id)
        upload_dir.mkdir(parents=True, exist_ok=True)

        unique_name = f"{_uuid.uuid4().hex}_{filename}"
        file_path = upload_dir / unique_name
        file_path.write_bytes(raw)
        _text_path_for(file_path).write_text(content, encoding="utf-8")

        # Store path relative to the evidence upload root so the record stays
        # portable when the base upload directory changes.
        relative_path = str(file_path.relative_to(_evidence_upload_dir()))

        # Create DB record. The file is stored and its text extracted, but no
        # embedding step has run yet, so the status stays "pending" until the
        # AI pipeline processes it. (Was incorrectly "completed", which claimed
        # embedding had finished when nothing had embedded the file.)
        evidence = Evidence(
            student_id=student_id,
            file_name=filename,
            file_type=file_type,
            file_path=relative_path,
            source_type=SourceType.upload,
            embedding_status=EmbeddingStatus.pending,
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
        _parse_uuid(student_id, "student_id")
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found",
            )
        return (
            db.query(Evidence)
            .filter(Evidence.student_id == student_id)
            .order_by(Evidence.uploaded_at.desc())
            .all()
        )

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
        return evidence, content

    @staticmethod
    def _read_or_rebuild_text_content(evidence: Evidence) -> str:
        full_path = _full_path_for(evidence.file_path)
        text_path = _text_path_for(full_path)
        if text_path.exists():
            return text_path.read_text(encoding="utf-8")

        try:
            return full_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return EvidenceService._extract_and_store_text(evidence, full_path)

    @staticmethod
    def _extract_and_store_text(evidence: Evidence, full_path: Path) -> str:
        file_type = evidence.file_type or _resolve_file_type(evidence.file_name)
        raw = full_path.read_bytes()
        content = _extract_text(raw, file_type, evidence.file_name)
        _text_path_for(full_path).write_text(content, encoding="utf-8")
        return content
