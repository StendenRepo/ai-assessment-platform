from typing import List

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher, get_db
from app.models.teacher import Teacher
from app.schemas.evidence import EvidenceOut
from app.services.evidence_service import SUPPORTED_EXTENSIONS, EvidenceService

router = APIRouter()


@router.get(
    "/evidence/supported-types",
    summary="List supported upload file types",
)
def get_supported_types():
    """Return the file extensions that are currently accepted for evidence upload."""
    return {"supported_extensions": list(SUPPORTED_EXTENSIONS.keys())}


@router.post(
    "/students/{student_id}/evidence",
    response_model=EvidenceOut,
    status_code=201,
    summary="Upload a file as student evidence",
)
def upload_evidence(
    student_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    """
    Upload a file as evidence for a student.

    - Supported extensions are returned by `GET /evidence/supported-types`.
    - File is stored on disk and linked to the student in the database.
    - Returns the created evidence record.
    """
    evidence = EvidenceService.upload_file(student_id, file, db)
    return evidence


@router.get(
    "/students/{student_id}/evidence",
    response_model=List[EvidenceOut],
    summary="List all evidence for a student",
)
def list_evidence(
    student_id: str,
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    """Return all evidence records linked to the given student."""
    return EvidenceService.list_for_student(student_id, db)


@router.get(
    "/evidence/{evidence_id}/content",
    summary="Read the text content of an evidence file",
)
def get_evidence_content(
    evidence_id: str,
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    """
    Return the raw text content of an evidence file.

    Response shape: `{ "id": "...", "file_name": "...", "content": "..." }`
    """
    evidence, content = EvidenceService.read_content(evidence_id, db)
    return {
        "id": str(evidence.id),
        "file_name": evidence.file_name,
        "content": content,
    }
