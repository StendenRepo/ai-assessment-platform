import uuid as _uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.models.enums import EmbeddingStatus, SourceType
from app.models.evidence import Evidence
from app.models.evidence_match import EvidenceMatch
from app.models.overlap_signal import OverlapSignal
from app.models.student import Student
from app.services.text_extraction import (
    EVIDENCE_EXTENSIONS,
    extract_document_text_strict,
    read_stored_evidence_text,
    resolve_evidence_file_type,
)


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

# Re-export for API / tests that import SUPPORTED_EXTENSIONS from here.
SUPPORTED_EXTENSIONS = EVIDENCE_EXTENSIONS


def _resolve_file_type(filename: str):
    try:
        return resolve_evidence_file_type(filename)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


class EvidenceService:
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

        filename = file.filename or ""
        file_type = _resolve_file_type(filename)

        raw = file.file.read()
        try:
            content = extract_document_text_strict(raw, filename)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

        upload_dir = EVIDENCE_UPLOAD_DIR / str(student_id)
        upload_dir.mkdir(parents=True, exist_ok=True)

        unique_name = f"{_uuid.uuid4().hex}_{filename}"
        file_path = upload_dir / unique_name
        file_path.write_text(content, encoding="utf-8")

        relative_path = str(file_path.relative_to(EVIDENCE_UPLOAD_DIR))

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

    @staticmethod
    def list_for_student(student_id: str, db: Session) -> list[Evidence]:
        student = db.get(Student, student_id)
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

    @staticmethod
    def delete(evidence_id: str, db: Session) -> None:
        evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
        if not evidence:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evidence not found",
            )

        eid = evidence.id
        db.query(OverlapSignal).filter(
            or_(
                OverlapSignal.evidence_a_id == eid,
                OverlapSignal.evidence_b_id == eid,
            )
        ).delete(synchronize_session=False)
        db.query(EvidenceMatch).filter(EvidenceMatch.evidence_id == eid).delete(
            synchronize_session=False
        )

        full_path = EVIDENCE_UPLOAD_DIR / evidence.file_path

        try:
            if full_path.exists():
                full_path.unlink()
        except OSError:
            pass

        db.delete(evidence)
        db.commit()

    @staticmethod
    def read_content(evidence_id: str, db: Session) -> tuple[Evidence, str]:
        evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
        if not evidence:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evidence not found",
            )
        if not (EVIDENCE_UPLOAD_DIR / evidence.file_path).exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evidence file not found on disk",
            )
        content = read_stored_evidence_text(evidence, EVIDENCE_UPLOAD_DIR)
        return evidence, content
