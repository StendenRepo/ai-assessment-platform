import io
import uuid as _uuid
from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader
from fastapi import HTTPException, UploadFile, status
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


EVIDENCE_UPLOAD_DIR: Path = Path(settings.UPLOAD_DIR) / "evidence"

# ---------------------------------------------------------------------------
# Supported file types — extend this dict when new user stories are added.
# Key   : lowercase file extension (with dot)
# Value : FileType enum value
# ---------------------------------------------------------------------------
SUPPORTED_EXTENSIONS: dict[str, FileType] = {
    ".md": FileType.markdown,
    ".docx": FileType.docx,
    ".pdf": FileType.pdf,
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

    # Fallback for any future types not yet handled
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"Text extraction not implemented for file type '{file_type}'",
    )


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
        upload_dir = EVIDENCE_UPLOAD_DIR / str(student_id)
        upload_dir.mkdir(parents=True, exist_ok=True)

        unique_name = f"{_uuid.uuid4().hex}_{filename}"
        file_path = upload_dir / unique_name
        file_path.write_text(content, encoding="utf-8")

        # Store path relative to EVIDENCE_UPLOAD_DIR so the record stays
        # portable when the base upload directory changes.
        relative_path = str(file_path.relative_to(EVIDENCE_UPLOAD_DIR))

        # Create DB record — status starts as processing, then set to completed
        # once the file is safely written to disk.
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
        full_path = EVIDENCE_UPLOAD_DIR / evidence.file_path

        # Remove file from disk (ignore if already gone)
        try:
            if full_path.exists():
                full_path.unlink()
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
        full_path = EVIDENCE_UPLOAD_DIR / evidence.file_path
        if not full_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evidence file not found on disk",
            )
        content = full_path.read_text(encoding="utf-8")
        return evidence, content
