import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher, get_db
from app.models.assessment import Assessment
from app.models.enums import EmbeddingStatus
from app.models.evidence import Evidence
from app.models.student import Student
from app.models.teacher import Teacher
from app.schemas.evidence import EvidenceOut
from app.services.evidence_service import EvidenceService, run_vision_background, _evidence_upload_dir

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
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    evidence = EvidenceService.upload_file(student_id, file, db)
    if evidence.embedding_status == EmbeddingStatus.processing:
        background_tasks.add_task(run_vision_background, str(evidence.id))
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


@router.get(
    "/{student_id}/export/dossier",
    summary="Export a student dossier as a read-only ZIP file",
    response_class=StreamingResponse,
)
def export_student_dossier(
    student_id: str,
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    """Return a ZIP archive containing:
    - All evidence files uploaded for the student (in an ``evidence/`` folder).
    - A ``dossier.json`` metadata file with student info and assessment summary.

    All entries are stored with read-only permissions (0o444).
    The export runs entirely on-premise — no external services are called.
    """
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Student not found"
        )

    # Fetch evidence records
    evidence_records: list[Evidence] = (
        db.query(Evidence)
        .filter(Evidence.student_id == student_id)
        .order_by(Evidence.uploaded_at.asc())
        .all()
    )

    # Fetch latest assessment (if any)
    latest_assessment: Assessment | None = (
        db.query(Assessment)
        .filter(Assessment.student_id == student_id)
        .order_by(Assessment.created_at.desc())
        .first()
    )

    # Build metadata dict
    assessment_meta = None
    if latest_assessment:
        grade = None
        for payload in (latest_assessment.final_form_json, latest_assessment.draft_form_json):
            data = payload
            if isinstance(payload, str):
                try:
                    data = json.loads(payload)
                except Exception:
                    continue
            if isinstance(data, dict):
                raw = data.get("grade")
                if raw is not None:
                    grade = str(raw).strip() or None
                    break
        assessment_meta = {
            "id": str(latest_assessment.id),
            "status": latest_assessment.status.value if latest_assessment.status else None,
            "grade": grade,
            "created_at": latest_assessment.created_at.isoformat() if latest_assessment.created_at else None,
            "completed_at": latest_assessment.completed_at.isoformat() if latest_assessment.completed_at else None,
        }

    evidence_meta = []
    for ev in evidence_records:
        evidence_meta.append({
            "id": str(ev.id),
            "file_name": ev.file_name,
            "file_type": ev.file_type.value if ev.file_type else None,
            "uploaded_at": ev.uploaded_at.isoformat() if ev.uploaded_at else None,
            "embedding_status": ev.embedding_status.value if ev.embedding_status else None,
        })

    metadata = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "student": {
            "student_number": student.student_number,
            "name": student.name,
            "status": student.status.value if student.status else "active",
        },
        "assessment": assessment_meta,
        "evidence": evidence_meta,
    }

    # Build ZIP in memory
    buf = io.BytesIO()
    upload_dir = _evidence_upload_dir()

    # ZIP_DEFLATED gives good compression; ZIP_STORED is also fine for already-compressed files
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Write metadata
        meta_info = zipfile.ZipInfo("dossier.json")
        meta_info.external_attr = 0o444 << 16  # read-only
        zf.writestr(meta_info, json.dumps(metadata, indent=2, ensure_ascii=False))

        # Write each evidence file
        for ev in evidence_records:
            full_path = upload_dir / ev.file_path
            if not full_path.exists():
                continue
            # Sanitise the original filename to avoid path traversal
            safe_name = Path(ev.file_name).name or f"{ev.id}"
            arcname = f"evidence/{safe_name}"

            # Deduplicate arcnames if two files share the same original name
            existing = {zi.filename for zi in zf.infolist()}
            stem = Path(safe_name).stem
            suffix = Path(safe_name).suffix
            counter = 1
            while arcname in existing:
                arcname = f"evidence/{stem}_{counter}{suffix}"
                counter += 1

            info = zipfile.ZipInfo(arcname)
            info.external_attr = 0o444 << 16  # read-only
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, full_path.read_bytes())

    buf.seek(0)

    safe_student = "".join(
        c if c.isalnum() or c in "_-" else "_" for c in student.name
    ).strip("_") or student.student_number
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"dossier_{safe_student}_{today}.zip"

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
