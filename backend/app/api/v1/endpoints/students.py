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
    - A ``dossier.txt`` summary file with student info and assessment details.

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

    # Resolve grade from latest assessment
    grade: str | None = None
    if latest_assessment:
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

    # Build human-readable plain-text summary
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = [
        "=" * 60,
        "STUDENT DOSSIER",
        "=" * 60,
        f"Exported at : {now_str}",
        "",
        "STUDENT",
        "-" * 30,
        f"Name           : {student.name}",
        f"Student number : {student.student_number}",
        f"Status         : {student.status.value if student.status else 'active'}",
        "",
        "ASSESSMENT",
        "-" * 30,
    ]
    if latest_assessment:
        ast_status = latest_assessment.status.value if latest_assessment.status else "—"
        created = latest_assessment.created_at.strftime("%Y-%m-%d") if latest_assessment.created_at else "—"
        completed = latest_assessment.completed_at.strftime("%Y-%m-%d") if latest_assessment.completed_at else "—"
        lines += [
            f"Status         : {ast_status}",
            f"Grade          : {grade or '—'}",
            f"Created        : {created}",
            f"Completed      : {completed}",
        ]
    else:
        lines.append("No assessment found.")

    lines += [
        "",
        "EVIDENCE FILES",
        "-" * 30,
    ]
    if evidence_records:
        for i, ev in enumerate(evidence_records, start=1):
            uploaded = ev.uploaded_at.strftime("%Y-%m-%d") if ev.uploaded_at else "—"
            file_type = ev.file_type.value if ev.file_type else "—"
            lines.append(f"{i:>2}. {ev.file_name}  [{file_type}]  uploaded {uploaded}")
    else:
        lines.append("No evidence files uploaded.")

    lines += ["", "=" * 60]
    summary_text = "\n".join(lines) + "\n"

    # Build ZIP in memory
    buf = io.BytesIO()
    upload_dir = _evidence_upload_dir()

    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Write human-readable summary
        meta_info = zipfile.ZipInfo("dossier.txt")
        meta_info.external_attr = 0o444 << 16  # read-only
        zf.writestr(meta_info, summary_text.encode("utf-8"))

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
