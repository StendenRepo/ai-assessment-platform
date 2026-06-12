from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher, get_db
from app.models.enums import EmbeddingStatus
from app.models.student import Student
from app.models.teacher import Teacher
from app.schemas.evidence import EvidenceOut
from app.services import audit_service
from app.services.evidence_service import EvidenceService, run_vision_background

router = APIRouter()


@router.get(
    "/{student_id}",
    summary="Get a single student by student number",
)
def get_student(
    student_id: str,
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Student not found"
        )
    return {
        "id": student.student_number,
        "name": student.name,
        "student_number": student.student_number,
        "status": student.status.value if student.status else "active",
        "consent_given": bool(student.consent_given),
    }


@router.post(
    "/{student_id}/evidence",
    response_model=EvidenceOut,
    status_code=201,
    summary="Upload a file as student evidence",
)
def upload_evidence(
    student_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    student = db.get(Student, student_id)
    subject_label = f"student {student.name}" if student and student.name else "this student"
    evidence = EvidenceService.upload_file(student_id, file, db)
    audit_service.log_action(
        db,
        action="evidence.uploaded",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "evidence_id": str(evidence.id),
            "student_id": student_id,
            "file_name": evidence.file_name,
            "file_type": evidence.file_type.value if evidence.file_type else None,
            "source_type": evidence.source_type.value if evidence.source_type else None,
            "embedding_status": (
                evidence.embedding_status.value if evidence.embedding_status else None
            ),
        },
        ip_address=request.client.host if request.client else None,
    )
    if evidence.embedding_status == EmbeddingStatus.processing:
        background_tasks.add_task(
            run_vision_background,
            str(evidence.id),
            str(current_teacher.id),
            subject_label,
        )
    return evidence


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
    return EvidenceService.list_for_student(student_id, db)
