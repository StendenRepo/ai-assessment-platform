import os
import uuid as _uuid
from pathlib import Path

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

# ---------------------------------------------------------------------------
# Supported file types — extend this dict when new user stories are added.
# Key   : lowercase file extension (with dot)
# Value : FileType enum value
# ---------------------------------------------------------------------------
SUPPORTED_EXTENSIONS: dict[str, FileType] = {
    ".md": FileType.markdown,
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
        # 1. Validate student_id is a proper UUID, then verify student exists
        _parse_uuid(student_id, "student_id")
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found",
            )

        # 2. Resolve & validate file type
        filename = file.filename or ""
        file_type = _resolve_file_type(filename)

        # 3. Read content
        raw = file.file.read()
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="File is not valid UTF-8 text",
            )

        # 4. Persist to disk
        upload_dir = Path(settings.UPLOAD_DIR) / "evidence" / str(student_id)
        upload_dir.mkdir(parents=True, exist_ok=True)

        unique_name = f"{_uuid.uuid4().hex}_{filename}"
        file_path = upload_dir / unique_name
        file_path.write_text(content, encoding="utf-8")

        # 5. Create DB record
        evidence = Evidence(
            student_id=student_id,
            file_name=filename,
            file_type=file_type,
            file_path=str(file_path),
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
        if not os.path.exists(evidence.file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evidence file not found on disk",
            )
        content = Path(evidence.file_path).read_text(encoding="utf-8")
        return evidence, content
