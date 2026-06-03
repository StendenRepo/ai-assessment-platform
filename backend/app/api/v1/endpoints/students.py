from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher, get_db
from app.models.student import Student
from app.models.teacher import Teacher
from app.schemas.evidence import EvidenceOut
from app.services.evidence_service import EvidenceService, _parse_uuid

router = APIRouter()


@router.get(
    "/{student_id}",
    summary="Get a single student by ID",
)
def get_student(
    student_id: str,
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    """Return basic info for a single student."""
    _parse_uuid(student_id, "student_id")
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Student not found"
        )
    return {
        "id": str(student.id),
        "name": student.name,
        "student_number": student.student_number,
        "status": student.status.value if student.status else "active",
        "consent_given": bool(student.consent_given),
        "project_id": str(student.project_id),
    }


@router.post(
    "/{student_id}/evidence",
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
    return EvidenceService.upload_file(student_id, file, db)


@router.get(
    "/{student_id}/evidence",
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
