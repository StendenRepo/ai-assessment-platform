from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher, get_db
from app.config import settings
from app.models.assessment import Assessment
from app.models.evidence import Evidence
from app.models.enums import ProjectStatus
from app.models.file_record import FileRecord
from app.models.module import Module
from app.models.project import Project
from app.models.student import Student
from app.models.teacher import Teacher
from app.schemas.module import ModuleCreate, ModuleGroupCreate, ModuleOut, RubricFileOut, StudentGroupUpdate
from app.schemas.overlap import OverlapAnalysisOut, OverlapSignalOut, OverlapWarningOut
from app.schemas.project import (
    ImportRowError,
    ProjectOut,
    StudentCreate,
    StudentImportResult,
    StudentOut,
)
from app.services.module_service import ModuleService
from app.services.overlap_service import OverlapService
from app.services.student_import import ImportParseError, parse_student_file

router = APIRouter()

_DUPLICATE_DETAIL = "A student with that student number already exists in this module"
_DEFAULT_GROUP_NAME = "Individual Students"


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


def _rubric_file_out(record: Optional[FileRecord]) -> Optional[RubricFileOut]:
    if not record:
        return None
    return RubricFileOut(
        id=str(record.id),
        file_name=record.file_name,
        file_type=record.file_type,
        size_bytes=record.size_bytes,
        uploaded_at=record.uploaded_at,
    )


def _module_to_out(m: Module, project_count: int, student_count: int, db: Session) -> ModuleOut:
    rubric = None
    if m.rubric_file_id:
        rubric = db.query(FileRecord).filter(FileRecord.id == m.rubric_file_id).first()
    module_book = None
    if m.module_book_id:
        module_book = db.query(FileRecord).filter(FileRecord.id == m.module_book_id).first()
    return ModuleOut(
        id=str(m.id),
        name=m.name,
        academic_year=m.academic_year,
        deadline=m.deadline,
        status=m.status.value if m.status else "active",
        created_at=m.created_at,
        project_count=project_count,
        student_count=student_count,
        rubric_file=_rubric_file_out(rubric),
        module_book_file=_rubric_file_out(module_book),
    )


def _visible_modules_query(db: Session, teacher: Teacher):
    if teacher.is_admin:
        return db.query(Module)
    return db.query(Module).filter(Module.teacher_id == teacher.id)


def _get_visible_module_or_404(db: Session, module_id: str, teacher: Teacher) -> Module:
    module = _visible_modules_query(db, teacher).filter(Module.id == module_id).first()
    if not module:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")
    return module


def _module_project_ids(db: Session, module_id: str) -> list[str]:
    return [
        str(p.id)
        for p in db.query(Project).filter(Project.module_id == module_id).all()
    ]


def _module_project_counts(db: Session, module_id: str) -> tuple[int, int]:
    projects = db.query(Project).filter(Project.module_id == module_id).all()
    project_count = len(projects)
    student_count = 0
    for project in projects:
        student_count += db.query(Student).filter(Student.project_id == project.id).count()
    return project_count, student_count


def _signal_to_out(signal, student_names: dict, evidence_names: dict) -> OverlapSignalOut:
    return OverlapSignalOut(
        id=str(signal.id),
        student_a_id=str(signal.student_a_id),
        student_a_name=student_names.get(signal.student_a_id, "Unknown student"),
        student_b_id=str(signal.student_b_id),
        student_b_name=student_names.get(signal.student_b_id, "Unknown student"),
        evidence_a_id=str(signal.evidence_a_id),
        evidence_a_name=evidence_names.get(signal.evidence_a_id, "Unknown evidence"),
        evidence_b_id=str(signal.evidence_b_id),
        evidence_b_name=evidence_names.get(signal.evidence_b_id, "Unknown evidence"),
        overlap_type=signal.overlap_type.value if signal.overlap_type else "textual",
        confidence=round(float(signal.confidence or 0.0), 2),
        snippet=signal.snippet,
        detected_at=signal.detected_at,
    )


def _module_signal_context(db: Session, module: Module):
    project_ids = [p.id for p in db.query(Project).filter(Project.module_id == module.id).all()]
    if not project_ids:
        return {}, {}

    students = db.query(Student).filter(Student.project_id.in_(project_ids)).all()
    student_names = {s.id: s.name for s in students}
    student_ids = [s.id for s in students]
    evidence_names = {}
    if student_ids:
        for e in db.query(Evidence).filter(Evidence.student_id.in_(student_ids)).all():
            evidence_names[e.id] = e.file_name
    return student_names, evidence_names


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
    modules = _visible_modules_query(db, current_teacher).order_by(Module.created_at.desc()).all()
    result = []
    for module in modules:
        project_count, student_count = _module_project_counts(db, module.id)
        result.append(_module_to_out(module, project_count, student_count, db))
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
        deadline=payload.deadline,
    )
    db.add(module)
    db.commit()
    db.refresh(module)
    return _module_to_out(module, 0, 0, db)


@router.get("/{module_id}", response_model=ModuleOut)
def get_module(
    module_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    project_count, student_count = _module_project_counts(db, module.id)
    return _module_to_out(module, project_count, student_count, db)


@router.patch("/{module_id}", response_model=ModuleOut, summary="Rename a module")
def rename_module(
    module_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    """Update the name (and optionally academic_year) of a module."""
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    new_name = payload.get("name", "").strip()
    if not new_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="name must not be empty",
        )
    module.name = new_name
    if "academic_year" in payload:
        module.academic_year = payload["academic_year"]
    db.commit()
    db.refresh(module)
    project_count, student_count = _module_project_counts(db, module.id)
    return _module_to_out(module, project_count, student_count, db)


@router.delete("/{module_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a module")
def delete_module(
    module_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    """Permanently delete a module and all its groups, students, evidence records
    and the associated files on disk (evidence uploads + rubric)."""
    from pathlib import Path
    from app.services.module_service import RUBRIC_UPLOAD_DIR

    # Evidence files are stored relative to <UPLOAD_DIR>/evidence/
    EVIDENCE_UPLOAD_DIR = Path(settings.UPLOAD_DIR) / "evidence"

    module = _get_visible_module_or_404(db, module_id, current_teacher)

    # Collect and delete evidence files on disk ──────────────────────────
    project_ids = _module_project_ids(db, module.id)
    if project_ids:
        students = db.query(Student).filter(Student.project_id.in_(project_ids)).all()
        student_ids = [s.id for s in students]
        if student_ids:
            evidence_records = (
                db.query(Evidence).filter(Evidence.student_id.in_(student_ids)).all()
            )
            for ev in evidence_records:
                try:
                    file_path = EVIDENCE_UPLOAD_DIR / ev.file_path
                    if file_path.exists():
                        file_path.unlink()
                except OSError:
                    pass  # Log in production; don't block the delete

    # Delete rubric file on disk ─────────────────────────────────────────
    if module.rubric_file_id:
        rubric_record = (
            db.query(FileRecord).filter(FileRecord.id == module.rubric_file_id).first()
        )
        if rubric_record:
            try:
                rubric_path = RUBRIC_UPLOAD_DIR / str(module.id) / rubric_record.path
                if rubric_path.exists():
                    rubric_path.unlink()
                # Remove the now-empty module rubric directory if possible
                rubric_dir = RUBRIC_UPLOAD_DIR / str(module.id)
                if rubric_dir.exists() and not any(rubric_dir.iterdir()):
                    rubric_dir.rmdir()
            except OSError:
                pass

    # Delete DB records explicitly (no ORM cascade configured) ──────────
    # Delete in leaf-to-root order to respect FK constraints.
    if project_ids:
        students = db.query(Student).filter(Student.project_id.in_(project_ids)).all()
        student_ids = [s.id for s in students]
        if student_ids:
            db.query(Evidence).filter(Evidence.student_id.in_(student_ids)).delete(
                synchronize_session=False
            )
        db.query(Student).filter(Student.project_id.in_(project_ids)).delete(
            synchronize_session=False
        )
    db.query(Project).filter(Project.module_id == module.id).delete(
        synchronize_session=False
    )
    db.delete(module)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Rubric upload
# ---------------------------------------------------------------------------


@router.post("/{module_id}/rubric", response_model=ModuleOut)
def upload_rubric(
    module_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = ModuleService.upload_rubric(
        module_id,
        file,
        current_teacher.id,
        db,
        is_admin=current_teacher.is_admin,
    )
    project_count, student_count = _module_project_counts(db, module.id)
    return _module_to_out(module, project_count, student_count, db)


@router.delete("/{module_id}/rubric", status_code=status.HTTP_204_NO_CONTENT)
def delete_rubric(
    module_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    ModuleService.delete_rubric(
        module_id,
        current_teacher.id,
        db,
        is_admin=current_teacher.is_admin,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Module book upload
# ---------------------------------------------------------------------------


@router.post("/{module_id}/module-book", response_model=ModuleOut)
def upload_module_book(
    module_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = ModuleService.upload_module_book(
        module_id,
        file,
        current_teacher.id,
        db,
        is_admin=current_teacher.is_admin,
    )
    project_count, student_count = _module_project_counts(db, module.id)
    return _module_to_out(module, project_count, student_count, db)


@router.delete("/{module_id}/module-book", status_code=status.HTTP_204_NO_CONTENT)
def delete_module_book(
    module_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    ModuleService.delete_module_book(
        module_id,
        current_teacher.id,
        db,
        is_admin=current_teacher.is_admin,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Groups inside a module
# ---------------------------------------------------------------------------


@router.get("/{module_id}/groups", response_model=List[ProjectOut])
def list_module_groups(
    module_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
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
        for row in db.query(Evidence.student_id, func.count(Evidence.id)).filter(
            Evidence.student_id.in_(all_student_ids)
        ).group_by(Evidence.student_id).all():
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
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    project = Project(
        module_id=module.id,
        name=payload.name,
        group_name=payload.group_name or payload.name,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return _group_to_out(project, 0)


# ---------------------------------------------------------------------------
# Students within a module
# ---------------------------------------------------------------------------


@router.get("/{module_id}/students", response_model=List[StudentOut])
def list_module_students(
    module_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    project_ids = _module_project_ids(db, module.id)
    if not project_ids:
        return []
    students = (
        db.query(Student)
        .filter(Student.project_id.in_(project_ids))
        .order_by(Student.name)
        .all()
    )
    latest_assessment: dict = {}
    if students:
        for a in db.query(Assessment).filter(
            Assessment.student_id.in_([s.id for s in students])
        ).all():
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
    module = _get_visible_module_or_404(db, module_id, current_teacher)
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


@router.patch("/{module_id}/students/{student_id}", response_model=StudentOut)
def move_student_to_group(
    module_id: str,
    student_id: str,
    payload: StudentGroupUpdate,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
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
    module = _get_visible_module_or_404(db, module_id, current_teacher)
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
            errors.append(
                ImportRowError(row=row.row_number, student_number=number or None, message="Missing name")
            )
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
                ImportRowError(row=row.row_number, student_number=number, message="Student number already exists in this module")
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
# Overlap detection
# ---------------------------------------------------------------------------


@router.get("/{module_id}/overlap/signals", response_model=List[OverlapSignalOut])
def list_module_overlap_signals(
    module_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    signals = OverlapService.get_module_signals(db, str(module.id))
    student_names, evidence_names = _module_signal_context(db, module)
    return [_signal_to_out(signal, student_names, evidence_names) for signal in signals]


@router.post("/{module_id}/overlap/analyze", response_model=OverlapAnalysisOut)
def analyze_module_overlap(
    module_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    generated = OverlapService.analyze_module_overlap(db, str(module.id))
    warning_data = OverlapService.build_warning(generated)
    student_names, evidence_names = _module_signal_context(db, module)

    return OverlapAnalysisOut(
        module_id=str(module.id),
        generated_count=len(generated),
        warning=OverlapWarningOut(**warning_data),
        signals=[_signal_to_out(signal, student_names, evidence_names) for signal in generated],
    )


@router.get("/{module_id}/overlap/warning", response_model=OverlapWarningOut)
def get_module_overlap_warning(
    module_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    signals = OverlapService.get_module_signals(db, str(module.id))
    warning_data = OverlapService.build_warning(signals)
    return OverlapWarningOut(**warning_data)
