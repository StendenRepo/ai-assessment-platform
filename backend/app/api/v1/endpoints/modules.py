import json
import uuid
from io import BytesIO
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai import ollama_client
from app.ai.assessment_chat import prepare_chat
from app.ai.orchestrator import run_analysis
from app.api.deps import get_current_teacher, get_db
from app.database import SessionLocal
from app.models.assessment import Assessment
from app.models.audit_event import AuditEvent
from app.models.chat_message import ChatMessage
from app.models.evidence import Evidence
from app.models.enums import AssessmentStatus, AuditSource, FileType, ProjectStatus, SourceType
from app.models.file_record import FileRecord
from app.models.module import Module
from app.models.overlap_signal import OverlapSignal
from app.models.project import Project
from app.models.student import Student
from app.models.teacher import Teacher
from app.ingestion.files import extract_text_from_bytes, parse_rubric_lines
from app.schemas.module import ModuleCreate, ModuleGroupCreate, ModuleOut, StudentGroupUpdate
from app.schemas.project import (
    ImportRowError,
    ProjectOut,
    StudentCreate,
    StudentImportResult,
    StudentOut,
)
from app.services.dev_ui_bridge import analysis_to_insights
from app.services.student_import import ImportParseError, parse_student_file

router = APIRouter()

_DUPLICATE_DETAIL = "A student with that student number already exists in this module"
_DEFAULT_GROUP_NAME = "Individual Students"
_DEFAULT_ANALYSIS_CRITERIA = [
    "Individual contribution",
    "Technical implementation",
    "Reflection and documentation",
]
_UPLOADS_ROOT = Path(__file__).resolve().parents[4] / "data" / "uploads"
_EVIDENCE_UPLOADS = _UPLOADS_ROOT / "evidence"
_RUBRIC_UPLOADS = _UPLOADS_ROOT / "rubrics"


def _storage_file_type(filename: str) -> FileType:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return FileType.pdf
    if ext == ".docx":
        return FileType.docx
    if ext in {".xlsx", ".xls"}:
        return FileType.xlsx
    if ext == ".pptx":
        return FileType.pptx
    if ext in {".md", ".markdown"}:
        return FileType.markdown
    if ext in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        return FileType.image
    if ext == ".zip":
        return FileType.zip
    return FileType.other


def _save_uploaded_file(upload: UploadFile, raw: bytes, folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    safe_name = upload.filename or "upload.bin"
    out_name = f"{uuid.uuid4().hex[:12]}-{safe_name}"
    out_path = folder / out_name
    out_path.write_bytes(raw)
    return out_path


def _assessment_status(latest: Optional[Assessment]) -> str:
    if latest is None:
        return "not-started"
    if latest.status.value == "final":
        return "completed"
    return "in-progress"


def _student_to_out(s: Student, assessment_status: str = "not-started") -> StudentOut:
    return StudentOut(
        id=str(s.id),
        project_id=str(s.project_id),
        name=s.name,
        student_number=s.student_number,
        status=s.status.value if s.status else "active",
        consent_given=bool(s.consent_given),
        assessment_status=assessment_status,
    )


def _group_to_out(p: Project, student_count: int, file_count: int = 0) -> ProjectOut:
    return ProjectOut(
        id=str(p.id),
        name=p.name,
        group_name=p.group_name,
        module_id=str(p.module_id),
        status=p.status.value if p.status else "active",
        created_at=p.created_at,
        student_count=student_count,
        file_count=file_count,
    )


def _module_to_out(
    m: Module,
    project_count: int,
    student_count: int,
    *,
    criteria: list[dict] | None = None,
    projects: list[ProjectOut] | None = None,
) -> ModuleOut:
    return ModuleOut(
        id=str(m.id),
        name=m.name,
        academic_year=m.academic_year,
        status=m.status.value if m.status else "active",
        created_at=m.created_at,
        project_count=project_count,
        student_count=student_count,
        has_rubric=bool(m.rubric_file_id),
        has_module_guide=bool(m.module_book_id),
        criteria=criteria or [],
        criteria_count=len(criteria or []),
        projects=projects or [],
    )


def _owned_modules_query(db: Session, teacher: Teacher):
    return db.query(Module).filter(Module.teacher_id == teacher.id)


def _get_owned_module_or_404(db: Session, module_id: str, teacher: Teacher) -> Module:
    module = _owned_modules_query(db, teacher).filter(Module.id == module_id).first()
    if not module:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")
    return module


def _module_project_ids(db: Session, module_id: str) -> list[str]:
    return [str(p.id) for p in db.query(Project).filter(Project.module_id == module_id).all()]


def _module_project_counts(db: Session, module_id: str) -> tuple[int, int]:
    projects = db.query(Project).filter(Project.module_id == module_id).all()
    project_count = len(projects)
    student_count = 0
    for project in projects:
        student_count += db.query(Student).filter(Student.project_id == project.id).count()
    return project_count, student_count


def _module_projects_out(db: Session, module: Module) -> list[ProjectOut]:
    projects = (
        db.query(Project)
        .filter(Project.module_id == module.id)
        .order_by(Project.created_at.desc())
        .all()
    )
    if not projects:
        return []
    project_ids = [p.id for p in projects]
    counts = {
        pid: db.query(Student).filter(Student.project_id == pid).count() for pid in project_ids
    }
    return [_group_to_out(p, counts.get(p.id, 0)) for p in projects]


def _module_criteria_rows(db: Session, module: Module) -> list[dict]:
    candidate_ids = [module.rubric_file_id, module.module_book_id]
    for file_id in candidate_ids:
        if not file_id:
            continue
        record = db.query(FileRecord).filter(FileRecord.id == file_id).first()
        if not record:
            continue
        file_path = Path(record.path)
        if not file_path.exists():
            continue
        raw = file_path.read_bytes()
        text = extract_text_from_bytes(file_path.name, raw)
        criteria = parse_rubric_lines(text)
        if criteria:
            return criteria
    return [
        {"id": f"c{i + 1}", "title": title, "description": title}
        for i, title in enumerate(_DEFAULT_ANALYSIS_CRITERIA)
    ]


def _get_or_create_default_group(db: Session, module: Module) -> Project:
    default_group = (
        db.query(Project)
        .filter(Project.module_id == module.id, Project.name == _DEFAULT_GROUP_NAME)
        .first()
    )
    if default_group:
        return default_group

    default_group = Project(
        module_id=module.id,
        name=_DEFAULT_GROUP_NAME,
        group_name=_DEFAULT_GROUP_NAME,
        status=ProjectStatus.active,
    )
    db.add(default_group)
    db.flush()
    return default_group


def _resolve_group_for_module(
    db: Session,
    module: Module,
    project_id: Optional[str],
) -> Project:
    if project_id:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project or project.module_id != module.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
        return project
    return _get_or_create_default_group(db, module)


def _student_duplicate_query(db: Session, project_ids: list[str], student_number: str):
    return (
        db.query(Student)
        .filter(Student.project_id.in_(project_ids), Student.student_number == student_number)
        .first()
    )


# ---------------------------------------------------------------------------
# Modules
# ---------------------------------------------------------------------------


@router.get("", response_model=List[ModuleOut])
def list_modules(
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    modules = _owned_modules_query(db, current_teacher).order_by(Module.created_at.desc()).all()
    result = []
    for module in modules:
        project_count, student_count = _module_project_counts(db, module.id)
        result.append(_module_to_out(module, project_count, student_count))
    return result


@router.post("", response_model=ModuleOut, status_code=status.HTTP_201_CREATED)
def create_module(
    payload: ModuleCreate,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = Module(
        teacher_id=current_teacher.id,
        name=payload.name,
        academic_year=payload.academic_year,
    )
    db.add(module)
    db.commit()
    db.refresh(module)
    return _module_to_out(module, 0, 0)


@router.get("/{module_id}", response_model=ModuleOut)
def get_module(
    module_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_owned_module_or_404(db, module_id, current_teacher)
    project_count, student_count = _module_project_counts(db, module.id)
    return _module_to_out(
        module,
        project_count,
        student_count,
        criteria=_module_criteria_rows(db, module),
        projects=_module_projects_out(db, module),
    )


# ---------------------------------------------------------------------------
# Groups inside a module
# ---------------------------------------------------------------------------


@router.get("/{module_id}/groups", response_model=List[ProjectOut])
def list_module_groups(
    module_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_owned_module_or_404(db, module_id, current_teacher)
    projects = (
        db.query(Project)
        .filter(Project.module_id == module.id)
        .order_by(Project.created_at.desc())
        .all()
    )
    if not projects:
        return []
    project_ids = [p.id for p in projects]
    students = db.query(Student).filter(Student.project_id.in_(project_ids)).all()
    student_ids_by_project: dict = {}
    for s in students:
        student_ids_by_project.setdefault(s.project_id, []).append(s.id)
    all_student_ids = [s.id for s in students]
    file_counts: dict = {}
    if all_student_ids:
        for row in (
            db.query(Evidence.student_id, func.count(Evidence.id))
            .filter(Evidence.student_id.in_(all_student_ids))
            .group_by(Evidence.student_id)
            .all()
        ):
            sid, cnt = row
            project_id = next((s.project_id for s in students if s.id == sid), None)
            if project_id is not None:
                file_counts[project_id] = file_counts.get(project_id, 0) + cnt
    return [
        _group_to_out(
            project,
            len(student_ids_by_project.get(project.id, [])),
            file_counts.get(project.id, 0),
        )
        for project in projects
    ]


@router.post("/{module_id}/groups", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_module_group(
    module_id: str,
    payload: ModuleGroupCreate,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_owned_module_or_404(db, module_id, current_teacher)
    project = Project(
        module_id=module.id,
        name=payload.name,
        group_name=payload.group_name or payload.name,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return _group_to_out(project, 0)


@router.get("/{module_id}/projects/{project_id}")
def get_module_group(
    module_id: str,
    project_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_owned_module_or_404(db, module_id, current_teacher)
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.module_id == module.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    students = db.query(Student).filter(Student.project_id == project.id).order_by(Student.name).all()
    student_payload: list[dict] = []
    for student in students:
        files = db.query(Evidence).filter(Evidence.student_id == student.id).order_by(Evidence.uploaded_at.desc()).all()
        assessment = (
            db.query(Assessment)
            .filter(Assessment.student_id == student.id, Assessment.teacher_id == module.teacher_id)
            .order_by(Assessment.created_at.desc())
            .first()
        )
        has_analysis = bool((assessment.draft_form_json if assessment else None) or {})
        student_payload.append(
            {
                "id": str(student.id),
                "name": student.name,
                "student_number": student.student_number,
                "phase": "prepare" if has_analysis else "ingest",
                "has_analysis": has_analysis,
                "evidence_count": len(files),
                "evidence": [
                    {
                        "id": str(ev.id),
                        "filename": ev.file_name,
                        "uploaded_at": ev.uploaded_at.isoformat() if ev.uploaded_at else None,
                    }
                    for ev in files
                ],
            }
        )

    group_phase = "prepare" if any(s["has_analysis"] for s in student_payload) else "ingest"
    return {
        "id": str(project.id),
        "module_id": str(module.id),
        "name": project.name,
        "phase": group_phase,
        "students": student_payload,
    }


@router.post("/{module_id}/rubric")
async def upload_module_rubric(
    module_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_owned_module_or_404(db, module_id, current_teacher)
    raw = await file.read()
    out_path = _save_uploaded_file(file, raw, _RUBRIC_UPLOADS)
    record = FileRecord(path=str(out_path), file_type="rubric", size_bytes=len(raw))
    db.add(record)
    db.flush()
    module.rubric_file_id = record.id
    db.commit()
    return {
        "ok": True,
        "file": file.filename,
        "criteria": parse_rubric_lines(extract_text_from_bytes(file.filename or "rubric.txt", raw)),
    }


@router.post("/{module_id}/module-guide")
async def upload_module_guide(
    module_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_owned_module_or_404(db, module_id, current_teacher)
    raw = await file.read()
    out_path = _save_uploaded_file(file, raw, _RUBRIC_UPLOADS)
    record = FileRecord(path=str(out_path), file_type="module_guide", size_bytes=len(raw))
    db.add(record)
    db.flush()
    module.module_book_id = record.id
    db.commit()
    return {"ok": True, "file": file.filename}


@router.delete("/{module_id}/rubric")
def remove_module_rubric(
    module_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_owned_module_or_404(db, module_id, current_teacher)
    module.rubric_file_id = None
    db.commit()
    return {"ok": True}


@router.delete("/{module_id}/module-guide")
def remove_module_guide(
    module_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_owned_module_or_404(db, module_id, current_teacher)
    module.module_book_id = None
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Students within a module
# ---------------------------------------------------------------------------


@router.get("/{module_id}/students", response_model=List[StudentOut])
def list_module_students(
    module_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_owned_module_or_404(db, module_id, current_teacher)
    project_ids = _module_project_ids(db, module.id)
    if not project_ids:
        return []
    students = db.query(Student).filter(Student.project_id.in_(project_ids)).order_by(Student.name).all()
    latest_assessment: dict = {}
    if students:
        for a in db.query(Assessment).filter(Assessment.student_id.in_([s.id for s in students])).all():
            existing = latest_assessment.get(a.student_id)
            if existing is None or a.created_at > existing.created_at:
                latest_assessment[a.student_id] = a
    return [_student_to_out(s, _assessment_status(latest_assessment.get(s.id))) for s in students]


@router.post("/{module_id}/students", response_model=StudentOut, status_code=status.HTTP_201_CREATED)
def add_module_student(
    module_id: str,
    payload: StudentCreate,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_owned_module_or_404(db, module_id, current_teacher)
    project = _resolve_group_for_module(db, module, payload.project_id)

    duplicate = _student_duplicate_query(db, _module_project_ids(db, module.id), payload.student_number)
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_DUPLICATE_DETAIL)

    student = Student(
        project_id=project.id,
        name=payload.name,
        student_number=payload.student_number,
    )
    db.add(student)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_DUPLICATE_DETAIL)
    db.refresh(student)
    return _student_to_out(student)


@router.post("/{module_id}/projects/{project_id}/students")
def add_group_student(
    module_id: str,
    project_id: str,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_owned_module_or_404(db, module_id, current_teacher)
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.module_id == module.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    name = str(payload.get("name") or "").strip()
    student_number = str(payload.get("student_number") or "").strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Student name is required")
    if not student_number:
        student_number = f"AUTO-{uuid.uuid4().hex[:8]}"

    duplicate = (
        db.query(Student)
        .join(Project, Student.project_id == Project.id)
        .filter(Project.module_id == module.id, Student.student_number == student_number)
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_DUPLICATE_DETAIL)

    student = Student(project_id=project.id, name=name, student_number=student_number)
    db.add(student)
    db.commit()
    db.refresh(student)
    return {
        "id": str(student.id),
        "name": student.name,
        "student_number": student.student_number,
    }


@router.delete("/{module_id}/projects/{project_id}/students/{student_id}")
def remove_group_student(
    module_id: str,
    project_id: str,
    student_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_owned_module_or_404(db, module_id, current_teacher)
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.module_id == module.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    student = db.query(Student).filter(Student.id == student_id, Student.project_id == project.id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    evidence_ids = [ev.id for ev in db.query(Evidence).filter(Evidence.student_id == student.id).all()]
    if evidence_ids:
        db.query(OverlapSignal).filter(
            (OverlapSignal.evidence_a_id.in_(evidence_ids)) | (OverlapSignal.evidence_b_id.in_(evidence_ids))
        ).delete(synchronize_session=False)
    db.query(OverlapSignal).filter(
        (OverlapSignal.student_a_id == student.id) | (OverlapSignal.student_b_id == student.id)
    ).delete(synchronize_session=False)
    db.query(Evidence).filter(Evidence.student_id == student.id).delete(synchronize_session=False)
    assessment_ids = [
        aid
        for (aid,) in db.query(Assessment.id).filter(Assessment.student_id == student.id).all()
    ]
    if assessment_ids:
        db.query(ChatMessage).filter(ChatMessage.assessment_id.in_(assessment_ids)).delete(synchronize_session=False)
    db.query(Assessment).filter(Assessment.student_id == student.id).delete(synchronize_session=False)
    db.delete(student)
    db.commit()
    return {"ok": True}


@router.post("/{module_id}/projects/{project_id}/students/{student_id}/evidence")
async def upload_student_evidence(
    module_id: str,
    project_id: str,
    student_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_owned_module_or_404(db, module_id, current_teacher)
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.module_id == module.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    student = db.query(Student).filter(Student.id == student_id, Student.project_id == project.id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    raw = await file.read()
    out_path = _save_uploaded_file(file, raw, _EVIDENCE_UPLOADS)
    evidence = Evidence(
        student_id=student.id,
        file_name=file.filename or "evidence.bin",
        file_type=_storage_file_type(file.filename or ""),
        file_path=str(out_path),
        source_type=SourceType.upload,
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return {
        "id": str(evidence.id),
        "filename": evidence.file_name,
        "uploaded_at": evidence.uploaded_at.isoformat() if evidence.uploaded_at else None,
    }


@router.delete("/{module_id}/projects/{project_id}/students/{student_id}/evidence/{evidence_id}")
def remove_student_evidence(
    module_id: str,
    project_id: str,
    student_id: str,
    evidence_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_owned_module_or_404(db, module_id, current_teacher)
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.module_id == module.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    student = db.query(Student).filter(Student.id == student_id, Student.project_id == project.id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    evidence = (
        db.query(Evidence)
        .filter(Evidence.id == evidence_id, Evidence.student_id == student.id)
        .first()
    )
    if not evidence:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")

    db.query(OverlapSignal).filter(
        (OverlapSignal.evidence_a_id == evidence.id) | (OverlapSignal.evidence_b_id == evidence.id)
    ).delete(synchronize_session=False)
    db.delete(evidence)
    db.commit()
    return {"ok": True}


@router.patch("/{module_id}/students/{student_id}", response_model=StudentOut)
def move_student_to_group(
    module_id: str,
    student_id: str,
    payload: StudentGroupUpdate,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_owned_module_or_404(db, module_id, current_teacher)
    project_ids = _module_project_ids(db, module.id)
    student = (
        db.query(Student)
        .filter(Student.id == student_id, Student.project_id.in_(project_ids))
        .first()
    )
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found in this module")
    target = (
        db.query(Project)
        .filter(Project.id == payload.project_id, Project.module_id == module.id)
        .first()
    )
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found in this module")
    student.project_id = target.id
    db.commit()
    db.refresh(student)
    return _student_to_out(student)


@router.post("/{module_id}/students/import", response_model=StudentImportResult)
async def import_module_students(
    module_id: str,
    file: UploadFile = File(...),
    project_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_owned_module_or_404(db, module_id, current_teacher)
    project = _resolve_group_for_module(db, module, project_id)

    contents = await file.read()
    try:
        rows = parse_student_file(file.filename, contents)
    except ImportParseError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    existing_numbers = {
        number
        for (number,) in db.query(Student.student_number).filter(
            Student.project_id.in_(_module_project_ids(db, module.id))
        )
        if number
    }

    seen: set[str] = set()
    errors: List[ImportRowError] = []
    to_add: List[Student] = []

    for row in rows:
        name = row.name.strip()
        number = row.student_number.strip()

        if not name:
            errors.append(ImportRowError(row=row.row_number, student_number=number or None, message="Missing name"))
            continue
        if not number:
            errors.append(ImportRowError(row=row.row_number, message="Missing student number"))
            continue
        if number in seen:
            errors.append(
                ImportRowError(row=row.row_number, student_number=number, message="Duplicate student number in file")
            )
            continue
        if number in existing_numbers:
            errors.append(
                ImportRowError(
                    row=row.row_number,
                    student_number=number,
                    message="Student number already exists in this module",
                )
            )
            continue

        seen.add(number)
        to_add.append(Student(project_id=project.id, name=name, student_number=number))

    for student in to_add:
        db.add(student)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Import conflicted with a concurrent change. Please try again.",
        )

    return StudentImportResult(
        imported_count=len(to_add),
        error_count=len(errors),
        total_rows=len(rows),
        errors=errors,
        students=[_student_to_out(s) for s in to_add],
    )


# ---------------------------------------------------------------------------
# Modules/Projects AI analysis (SQL-backed)
# ---------------------------------------------------------------------------


def _analysis_for_student(result: dict, student_name: str) -> dict:
    return {
        "disclaimer": result.get("disclaimer"),
        "processing": result.get("processing"),
        "llm": result.get("llm"),
        "evidence_matches": [
            m for m in result.get("evidence_matches", []) if m.get("student") == student_name
        ],
        "overlaps": [
            o
            for o in result.get("overlaps", [])
            if student_name in (o.get("student_a"), o.get("student_b"))
        ],
        "draft_suggestions": [
            d for d in result.get("draft_suggestions", []) if d.get("student") == student_name
        ],
        "questions": [
            q for q in result.get("questions", []) if q.get("student") == student_name
        ],
    }


def _analysis_details(module_id: str, project_id: str, **kwargs) -> dict:
    details = {"module_id": module_id, "project_id": project_id}
    details.update(kwargs)
    return details


def _record_analysis_event(
    db: Session,
    *,
    module_id: str,
    project_id: str,
    teacher_id,
    action: str,
    detail: dict,
) -> None:
    db.add(
        AuditEvent(
            teacher_id=teacher_id,
            action=action,
            details_json=_analysis_details(module_id, project_id, **detail),
            source=AuditSource.ai,
        )
    )
    db.commit()


def _module_criteria(db: Session, module: Module) -> list[str]:
    criteria = _module_criteria_rows(db, module)
    titles = [c.get("title", "").strip() for c in criteria if c.get("title")]
    return titles or list(_DEFAULT_ANALYSIS_CRITERIA)


def _student_evidence_text(student: Student) -> tuple[str, str]:
    parts: list[str] = []
    src = "no evidence"
    for evidence in student.evidence:
        path = Path(evidence.file_path)
        if not path.exists():
            continue
        try:
            extracted = extract_text_from_bytes(evidence.file_name, path.read_bytes())
        except Exception:
            continue
        if extracted.strip():
            parts.append(extracted)
            src = evidence.file_name
    if not parts:
        return src, "(no evidence uploaded)"
    return src, "\n\n".join(parts)


def _persist_student_analysis(
    db: Session,
    *,
    module: Module,
    project: Project,
    student: Student,
    result: dict,
) -> None:
    analysis = _analysis_for_student(result, student.name)
    insights = analysis_to_insights(analysis, str(student.id), student.name)
    draft_rows = [
        {
            "criterion": d["criterion"],
            "suggestion": d["suggestion"],
            "suggestion_strength": d["suggestion_strength"],
            "teacher_score": None,
            "teacher_comment": "",
        }
        for d in analysis.get("draft_suggestions", [])
    ]

    assessment = (
        db.query(Assessment)
        .filter(
            Assessment.student_id == student.id,
            Assessment.teacher_id == module.teacher_id,
        )
        .order_by(Assessment.created_at.desc())
        .first()
    )
    if not assessment or assessment.status == AssessmentStatus.final:
        assessment = Assessment(
            student_id=student.id,
            teacher_id=module.teacher_id,
            status=AssessmentStatus.draft,
        )
        db.add(assessment)

    assessment.draft_form_json = {
        "module_id": str(module.id),
        "project_id": str(project.id),
        "student_id": str(student.id),
        "analysis": analysis,
        "insights": insights,
        "draft_form": draft_rows,
        "processing": result.get("processing"),
        "llm": result.get("llm"),
    }


def _run_project_analysis_task(module_id: str, project_id: str) -> None:
    db = SessionLocal()
    try:
        module = db.query(Module).filter(Module.id == module_id).first()
        project = (
            db.query(Project)
            .filter(Project.id == project_id, Project.module_id == module_id)
            .first()
        )
        if not module or not project:
            _record_analysis_event(
                db,
                module_id=module_id,
                project_id=project_id,
                teacher_id=None,
                action="analysis_failed",
                detail={"status": "failed", "error": "Project not found", "progress": 100},
            )
            return

        students = (
            db.query(Student)
            .filter(Student.project_id == project.id)
            .order_by(Student.name)
            .all()
        )
        if not students:
            _record_analysis_event(
                db,
                module_id=module_id,
                project_id=project_id,
                teacher_id=module.teacher_id,
                action="analysis_failed",
                detail={"status": "failed", "error": "No students in group", "progress": 100},
            )
            return

        criteria = _module_criteria(db, module)
        students_payload: dict[str, dict] = {}
        for s in students:
            src, text = _student_evidence_text(s)
            students_payload[s.name] = {
                "student_id": str(s.id),
                "source_file": src,
                "text": text,
            }

        def on_progress(step: str, progress: int) -> None:
            _record_analysis_event(
                db,
                module_id=module_id,
                project_id=project_id,
                teacher_id=module.teacher_id,
                action="analysis_progress",
                detail={"status": "running", "step": step, "progress": progress},
            )

        result = run_analysis(criteria, students_payload, on_progress=on_progress)
        for student in students:
            _persist_student_analysis(
                db,
                module=module,
                project=project,
                student=student,
                result=result,
            )
        db.commit()

        _record_analysis_event(
            db,
            module_id=module_id,
            project_id=project_id,
            teacher_id=module.teacher_id,
            action="analysis_completed",
            detail={
                "status": "completed",
                "step": "Completed",
                "progress": 100,
                "processing": result.get("processing", ""),
            },
        )
    except Exception as exc:
        db.rollback()
        _record_analysis_event(
            db,
            module_id=module_id,
            project_id=project_id,
            teacher_id=None,
            action="analysis_failed",
            detail={"status": "failed", "error": str(exc), "progress": 100},
        )
    finally:
        db.close()


def _latest_analysis_status(
    db: Session,
    *,
    module_id: str,
    project_id: str,
    teacher_id,
) -> dict:
    rows = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.teacher_id == teacher_id,
            AuditEvent.action.in_(
                ["analysis_started", "analysis_progress", "analysis_completed", "analysis_failed"]
            ),
        )
        .order_by(AuditEvent.timestamp.desc())
        .limit(200)
        .all()
    )
    for row in rows:
        details = row.details_json or {}
        if details.get("module_id") != module_id or details.get("project_id") != project_id:
            continue
        action = row.action
        if action == "analysis_completed":
            status_text = "completed"
        elif action == "analysis_failed":
            status_text = "failed"
        else:
            status_text = "running"
        return {
            "status": status_text,
            "module_id": module_id,
            "project_id": project_id,
            "step": details.get("step", "Queued"),
            "progress": details.get("progress", 0),
            "error": details.get("error"),
            "processing": details.get("processing"),
            "updated_at": row.timestamp.astimezone(timezone.utc).isoformat(),
        }
    return {
        "status": "idle",
        "module_id": module_id,
        "project_id": project_id,
        "step": "Not started",
        "progress": 0,
        "error": None,
        "processing": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/{module_id}/projects/{project_id}/ensure")
def ensure_group(
    module_id: str,
    project_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_owned_module_or_404(db, module_id, current_teacher)
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.module_id == module.id)
        .first()
    )
    if not project:
        raise HTTPException(404, "Group not found")
    students = db.query(Student).filter(Student.project_id == project.id).order_by(Student.name).all()
    return {
        "module_id": module_id,
        "project_id": project_id,
        "students": [{"id": str(s.id), "name": s.name} for s in students],
    }


@router.post("/{module_id}/projects/{project_id}/analyze")
def analyze_group(
    module_id: str,
    project_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_owned_module_or_404(db, module_id, current_teacher)
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.module_id == module.id)
        .first()
    )
    if not project:
        raise HTTPException(404, "Group not found")
    if not db.query(Student).filter(Student.project_id == project.id).first():
        raise HTTPException(400, "No students in group")

    current = _latest_analysis_status(
        db,
        module_id=module_id,
        project_id=project_id,
        teacher_id=current_teacher.id,
    )
    if current["status"] == "running":
        raise HTTPException(409, "Analysis already running")

    _record_analysis_event(
        db,
        module_id=module_id,
        project_id=project_id,
        teacher_id=current_teacher.id,
        action="analysis_started",
        detail={"status": "running", "step": "Queued", "progress": 1},
    )
    background_tasks.add_task(_run_project_analysis_task, module_id, project_id)
    return {"status": "started", "module_id": module_id, "project_id": project_id}


@router.get("/{module_id}/projects/{project_id}/analyze/status")
def analyze_group_status(
    module_id: str,
    project_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_owned_module_or_404(db, module_id, current_teacher)
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.module_id == module.id)
        .first()
    )
    if not project:
        raise HTTPException(404, "Group not found")
    return _latest_analysis_status(
        db,
        module_id=module_id,
        project_id=project_id,
        teacher_id=current_teacher.id,
    )


@router.get("/{module_id}/projects/{project_id}/students/{student_id}/ai-insights")
def student_ai_insights(
    module_id: str,
    project_id: str,
    student_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_owned_module_or_404(db, module_id, current_teacher)
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.module_id == module.id)
        .first()
    )
    if not project:
        raise HTTPException(404, "Group not found")
    student = (
        db.query(Student)
        .filter(Student.id == student_id, Student.project_id == project.id)
        .first()
    )
    if not student:
        raise HTTPException(404, "Student not found")

    assessment = (
        db.query(Assessment)
        .filter(
            Assessment.student_id == student.id,
            Assessment.teacher_id == current_teacher.id,
        )
        .order_by(Assessment.created_at.desc())
        .first()
    )
    payload = (assessment.draft_form_json if assessment else None) or {}
    analysis = payload.get("analysis") or {}
    insights = payload.get("insights")
    if insights is None:
        insights = analysis_to_insights(analysis, student_id, student.name)

    return {
        "student_id": student_id,
        "insights": insights,
        "processing": payload.get("processing") or analysis.get("processing"),
        "llm": payload.get("llm") or analysis.get("llm"),
    }


def _student_assessment(
    db: Session,
    *,
    student: Student,
    teacher_id,
) -> Assessment:
    assessment = (
        db.query(Assessment)
        .filter(Assessment.student_id == student.id, Assessment.teacher_id == teacher_id)
        .order_by(Assessment.created_at.desc())
        .first()
    )
    if assessment and assessment.status != AssessmentStatus.final:
        return assessment
    assessment = Assessment(
        student_id=student.id,
        teacher_id=teacher_id,
        status=AssessmentStatus.draft,
    )
    db.add(assessment)
    db.flush()
    return assessment


def _owned_group_student_or_404(
    db: Session,
    *,
    module_id: str,
    project_id: str,
    student_id: str,
    teacher: Teacher,
) -> tuple[Module, Project, Student]:
    module = _get_owned_module_or_404(db, module_id, teacher)
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.module_id == module.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    student = (
        db.query(Student)
        .filter(Student.id == student_id, Student.project_id == project.id)
        .first()
    )
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    return module, project, student


@router.patch("/{module_id}/projects/{project_id}/students/{student_id}/draft")
def update_student_draft(
    module_id: str,
    project_id: str,
    student_id: str,
    payload: list[dict] = Body(...),
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module, project, student = _owned_group_student_or_404(
        db,
        module_id=module_id,
        project_id=project_id,
        student_id=student_id,
        teacher=current_teacher,
    )
    assessment = _student_assessment(db, student=student, teacher_id=current_teacher.id)
    base = dict((assessment.draft_form_json or {}))
    base.update(
        {
            "module_id": str(module.id),
            "project_id": str(project.id),
            "student_id": str(student.id),
            "draft_form": payload,
        }
    )
    assessment.draft_form_json = base
    db.commit()
    return {"ok": True}


@router.get("/{module_id}/projects/{project_id}/students/{student_id}/chat")
def student_chat_history(
    module_id: str,
    project_id: str,
    student_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    _, _, student = _owned_group_student_or_404(
        db,
        module_id=module_id,
        project_id=project_id,
        student_id=student_id,
        teacher=current_teacher,
    )
    assessment = _student_assessment(db, student=student, teacher_id=current_teacher.id)
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.assessment_id == assessment.id)
        .order_by(ChatMessage.timestamp.asc())
        .all()
    )
    paired: list[dict] = []
    pending_user: dict | None = None
    for row in rows:
        if row.role == "teacher":
            if pending_user:
                paired.append(
                    {
                        "id": pending_user["id"],
                        "user": pending_user["content"],
                        "assistant": "",
                    }
                )
            pending_user = {"id": str(row.id), "content": row.content}
        elif row.role == "assistant":
            if pending_user:
                paired.append(
                    {
                        "id": str(row.id),
                        "user": pending_user["content"],
                        "assistant": row.content,
                    }
                )
                pending_user = None
            else:
                paired.append({"id": str(row.id), "user": "", "assistant": row.content})
    if pending_user:
        paired.append({"id": pending_user["id"], "user": pending_user["content"], "assistant": ""})
    return paired


@router.post("/{module_id}/projects/{project_id}/students/{student_id}/chat/stream")
def student_chat_stream(
    module_id: str,
    project_id: str,
    student_id: str,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module, project, student = _owned_group_student_or_404(
        db,
        module_id=module_id,
        project_id=project_id,
        student_id=student_id,
        teacher=current_teacher,
    )
    message = str(payload.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message is required")

    assessment = _student_assessment(db, student=student, teacher_id=current_teacher.id)
    context_payload = (assessment.draft_form_json or {})
    ctx = {
        "student": student.name,
        "criteria": [c.get("title") for c in _module_criteria_rows(db, module) if c.get("title")],
        "analysis_summary": (context_payload.get("insights") or [])[:5],
        "evidence_matches": (context_payload.get("analysis") or {}).get("evidence_matches", []),
        "overlaps": (context_payload.get("analysis") or {}).get("overlaps", []),
    }
    plan = prepare_chat(message, ctx)

    user_msg = ChatMessage(assessment_id=assessment.id, role="teacher", content=message)
    db.add(user_msg)
    db.flush()

    def sse(event: str, data: dict) -> str:
        return f"event: {event}\\ndata: {json.dumps(data)}\\n\\n"

    def stream():
        chunks: list[str] = []
        if plan.static_reply is not None:
            chunks.append(plan.static_reply)
            yield sse("token", {"text": plan.static_reply})
        else:
            for token in ollama_client.chat_stream(plan.system, plan.user, num_predict=plan.num_predict):
                chunks.append(token)
                yield sse("token", {"text": token})

        assistant = "".join(chunks).strip() or "I could not generate a response for this request."
        ai_msg = ChatMessage(assessment_id=assessment.id, role="assistant", content=assistant)
        db.add(ai_msg)
        db.commit()

        yield sse(
            "done",
            {
                "id": str(ai_msg.id),
                "user": message,
                "assistant": assistant,
            },
        )

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/{module_id}/projects/{project_id}/students/{student_id}")
def get_student_workspace(
    module_id: str,
    project_id: str,
    student_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    _, _, student = _owned_group_student_or_404(
        db,
        module_id=module_id,
        project_id=project_id,
        student_id=student_id,
        teacher=current_teacher,
    )
    assessment = _student_assessment(db, student=student, teacher_id=current_teacher.id)
    payload = (assessment.draft_form_json or {})
    files = db.query(Evidence).filter(Evidence.student_id == student.id).order_by(Evidence.uploaded_at.desc()).all()
    return {
        "id": str(student.id),
        "name": student.name,
        "student_number": student.student_number,
        "consent_given": bool(student.consent_given),
        "draft_form": payload.get("draft_form") or [],
        "analysis": payload.get("analysis") or {},
        "insights": payload.get("insights") or [],
        "evidence": [
            {
                "id": str(ev.id),
                "filename": ev.file_name,
                "uploaded_at": ev.uploaded_at.isoformat() if ev.uploaded_at else None,
            }
            for ev in files
        ],
    }


@router.post("/{module_id}/projects/{project_id}/students/{student_id}/consent")
def record_student_consent(
    module_id: str,
    project_id: str,
    student_id: str,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    _, _, student = _owned_group_student_or_404(
        db,
        module_id=module_id,
        project_id=project_id,
        student_id=student_id,
        teacher=current_teacher,
    )
    student.consent_given = bool(payload.get("consent_given"))
    db.commit()
    return {"ok": True, "consent_given": bool(student.consent_given), "note": payload.get("note", "")}


@router.post("/{module_id}/projects/{project_id}/students/{student_id}/transcript")
async def upload_student_transcript(
    module_id: str,
    project_id: str,
    student_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    _, _, student = _owned_group_student_or_404(
        db,
        module_id=module_id,
        project_id=project_id,
        student_id=student_id,
        teacher=current_teacher,
    )
    raw = await file.read()
    text = extract_text_from_bytes(file.filename or "transcript.txt", raw)
    assessment = _student_assessment(db, student=student, teacher_id=current_teacher.id)
    assessment.transcript_text = text
    db.commit()
    return {"ok": True, "length": len(text)}


@router.post("/{module_id}/projects/{project_id}/students/{student_id}/chat")
def student_chat_once(
    module_id: str,
    project_id: str,
    student_id: str,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    _, _, student = _owned_group_student_or_404(
        db,
        module_id=module_id,
        project_id=project_id,
        student_id=student_id,
        teacher=current_teacher,
    )
    message = str(payload.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message is required")
    assessment = _student_assessment(db, student=student, teacher_id=current_teacher.id)
    context_payload = (assessment.draft_form_json or {})
    plan = prepare_chat(
        message,
        {
            "student": student.name,
            "criteria": [c.get("title") for c in _module_criteria_rows(db, _get_owned_module_or_404(db, module_id, current_teacher)) if c.get("title")],
            "analysis_summary": (context_payload.get("insights") or [])[:5],
            "evidence_matches": (context_payload.get("analysis") or {}).get("evidence_matches", []),
            "overlaps": (context_payload.get("analysis") or {}).get("overlaps", []),
        },
    )
    if plan.static_reply is not None:
        assistant = plan.static_reply
    else:
        assistant = ollama_client.chat(plan.system, plan.user, num_predict=plan.num_predict) or "I could not generate a response for this request."

    db.add(ChatMessage(assessment_id=assessment.id, role="teacher", content=message))
    row = ChatMessage(assessment_id=assessment.id, role="assistant", content=assistant)
    db.add(row)
    db.commit()
    return {"id": str(row.id), "user": message, "assistant": assistant}


@router.get("/{module_id}/projects/{project_id}/students/{student_id}/export/zip")
def export_student_zip(
    module_id: str,
    project_id: str,
    student_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    _, _, student = _owned_group_student_or_404(
        db,
        module_id=module_id,
        project_id=project_id,
        student_id=student_id,
        teacher=current_teacher,
    )
    payload = {
        "student_id": str(student.id),
        "name": student.name,
        "student_number": student.student_number,
    }
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("student.json", json.dumps(payload, indent=2))
    data = buffer.getvalue()
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="student-{student_id}.zip"'},
    )


@router.get("/{module_id}/projects/{project_id}/students/{student_id}/export/eml")
def export_student_eml(
    module_id: str,
    project_id: str,
    student_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    _, _, student = _owned_group_student_or_404(
        db,
        module_id=module_id,
        project_id=project_id,
        student_id=student_id,
        teacher=current_teacher,
    )
    eml = (
        "Subject: Student Assessment Export\n"
        "Content-Type: text/plain; charset=utf-8\n\n"
        f"Student: {student.name}\n"
        f"Student Number: {student.student_number}\n"
    )
    return Response(
        content=eml,
        media_type="message/rfc822",
        headers={"Content-Disposition": f'attachment; filename="student-{student_id}.eml"'},
    )
