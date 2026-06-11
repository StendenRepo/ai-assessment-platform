import io
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher, get_db
from app.config import settings
from app.models.assessment import Assessment
from app.models.evidence import Evidence
from app.models.enums import ProjectStatus, StudentStatus
from app.models.file_record import FileRecord
from app.models.module import Module
from app.models.project import Project
from app.models.student import Student, student_projects
from app.models.teacher import Teacher
from app.schemas.module import (
    ModuleCreate,
    ModuleGroupCreate,
    ModuleGroupUpdate,
    ModuleOut,
    RubricFileOut,
    StudentGroupUpdate,
)
from app.schemas.overlap import OverlapAnalysisOut, OverlapSignalOut, OverlapWarningOut
from app.schemas.project import (
    ImportRowError,
    ProjectOut,
    StudentCreate,
    StudentImportResult,
    StudentOut,
)
from app.services.module_service import ModuleService
from app.services.overlap_service import OverlapService, parse_signal_detail
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


def _assessment_grade(latest: Optional[Assessment]) -> Optional[str]:
    if latest is None:
        return None

    for payload in (latest.final_form_json, latest.draft_form_json):
        data = payload
        if isinstance(payload, str):
            try:
                data = json.loads(payload)
            except Exception:
                continue

        if isinstance(data, dict):
            raw_grade = data.get("grade")
            if raw_grade is None:
                continue
            grade = str(raw_grade).strip()
            if grade:
                return grade
    return None


def _student_to_out(
    s: Student,
    assessment_status: str = "not-started",
    grade: Optional[str] = None,
    project_id: Optional[str] = None,
) -> StudentOut:
    return StudentOut(
        id=s.student_number,
        name=s.name,
        student_number=s.student_number,
        status=s.status.value if s.status else "active",
        consent_given=bool(s.consent_given),
        assessment_status=assessment_status,
        grade=grade,
        project_id=project_id,
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
    student_count = sum(
        db.query(student_projects).filter(student_projects.c.project_id == p.id).count()
        for p in projects
    )
    return project_count, student_count


def _students_in_projects(db: Session, project_ids: list) -> List[Student]:
    if not project_ids:
        return []
    return (
        db.query(Student)
        .join(student_projects, Student.student_number == student_projects.c.student_id)
        .filter(student_projects.c.project_id.in_(project_ids))
        .all()
    )


def _build_student_project_map(db: Session, project_ids: list) -> dict:
    """Returns {student_id: project_id} for students in the given projects."""
    if not project_ids:
        return {}
    rows = db.execute(
        student_projects.select().where(student_projects.c.project_id.in_(project_ids))
    ).all()
    return {row.student_id: row.project_id for row in rows}


def _signal_to_out(signal, student_names: dict, evidence_names: dict) -> OverlapSignalOut:
    detail = parse_signal_detail(signal.snippet)
    confidence = round(float(signal.confidence or 0.0), 2)
    status = detail.get("status")
    if not status:
        status = "confirmed" if confidence >= 0.55 else "possible"
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
        confidence=confidence,
        snippet=signal.snippet if not detail else detail.get("passage_a") or signal.snippet,
        detected_at=signal.detected_at,
        status=status,
        scope=detail.get("scope"),
        passage_a=detail.get("passage_a"),
        passage_b=detail.get("passage_b"),
        group_a_id=detail.get("group_a_id"),
        group_b_id=detail.get("group_b_id"),
        group_a_name=detail.get("group_a_name"),
        group_b_name=detail.get("group_b_name"),
    )


def _module_signal_context(db: Session, module: Module):
    project_ids = [p.id for p in db.query(Project).filter(Project.module_id == module.id).all()]
    if not project_ids:
        return {}, {}

    students = _students_in_projects(db, project_ids)
    student_names = {s.student_number: s.name for s in students}
    student_ids = [s.student_number for s in students]
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


def _student_duplicate_in_module(db: Session, project_ids: list[str], student_number: str) -> bool:
    if not project_ids:
        return False
    return (
        db.query(Student)
        .join(student_projects, Student.student_number == student_projects.c.student_id)
        .filter(
            student_projects.c.project_id.in_(project_ids),
            Student.student_number == student_number,
        )
        .first()
    ) is not None


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
    """Permanently delete a module and all its groups. Students who belong only
    to this module (and no other) are also deleted along with their evidence."""
    from pathlib import Path
    from app.services.module_service import RUBRIC_UPLOAD_DIR

    EVIDENCE_UPLOAD_DIR = Path(settings.UPLOAD_DIR) / "evidence"

    module = _get_visible_module_or_404(db, module_id, current_teacher)
    project_ids = _module_project_ids(db, module.id)

    # Collect student_ids enrolled in this module
    student_ids = [
        row.student_id
        for row in db.execute(
            student_projects.select().where(student_projects.c.project_id.in_(project_ids))
        ).all()
    ] if project_ids else []

    # Remove student_projects associations for this module's projects
    if project_ids:
        db.execute(
            student_projects.delete().where(
                student_projects.c.project_id.in_(project_ids)
            )
        )

    # Find students who are now orphaned (no remaining project associations)
    orphaned_ids = [
        sid for sid in student_ids
        if not db.execute(
            student_projects.select().where(student_projects.c.student_id == sid)
        ).first()
    ]

    # Delete evidence files on disk and DB records for orphaned students
    if orphaned_ids:
        evidence_records = db.query(Evidence).filter(Evidence.student_id.in_(orphaned_ids)).all()
        for ev in evidence_records:
            try:
                file_path = EVIDENCE_UPLOAD_DIR / ev.file_path
                if file_path.exists():
                    file_path.unlink()
            except OSError:
                pass
        db.query(Evidence).filter(Evidence.student_id.in_(orphaned_ids)).delete(
            synchronize_session=False
        )
        db.query(Student).filter(Student.student_number.in_(orphaned_ids)).delete(
            synchronize_session=False
        )

    # Delete rubric file on disk
    if module.rubric_file_id:
        rubric_record = db.query(FileRecord).filter(FileRecord.id == module.rubric_file_id).first()
        if rubric_record:
            try:
                rubric_path = RUBRIC_UPLOAD_DIR / str(module.id) / rubric_record.path
                if rubric_path.exists():
                    rubric_path.unlink()
                rubric_dir = RUBRIC_UPLOAD_DIR / str(module.id)
                if rubric_dir.exists() and not any(rubric_dir.iterdir()):
                    rubric_dir.rmdir()
            except OSError:
                pass

    db.query(Project).filter(Project.module_id == module.id).delete(synchronize_session=False)
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
    student_project_map = _build_student_project_map(db, project_ids)

    # Group student counts by project
    student_count_by_project: dict = {}
    for project_id in student_project_map.values():
        student_count_by_project[project_id] = student_count_by_project.get(project_id, 0) + 1

    # Count evidence files per project via student membership
    student_ids_by_project: dict = {}
    for sid, pid in student_project_map.items():
        student_ids_by_project.setdefault(pid, []).append(sid)

    all_student_ids = list(student_project_map.keys())
    file_counts: dict = {}
    if all_student_ids:
        for sid, cnt in db.query(Evidence.student_id, func.count(Evidence.id)).filter(
            Evidence.student_id.in_(all_student_ids)
        ).group_by(Evidence.student_id).all():
            pid = student_project_map.get(sid)
            if pid is not None:
                file_counts[pid] = file_counts.get(pid, 0) + cnt

    return [
        _group_to_out(
            project,
            student_count_by_project.get(project.id, 0),
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


@router.patch("/{module_id}/groups/{group_id}", response_model=ProjectOut)
def update_module_group(
    module_id: str,
    group_id: str,
    payload: ModuleGroupUpdate,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    group = (
        db.query(Project)
        .filter(Project.id == group_id, Project.module_id == module.id)
        .first()
    )
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    if payload.name is None and payload.group_name is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No group updates provided")

    if payload.name is not None:
        group.name = payload.name
    if payload.group_name is not None:
        group.group_name = payload.group_name

    db.commit()
    db.refresh(group)

    student_count = db.query(student_projects).filter(
        student_projects.c.project_id == group.id
    ).count()
    student_ids = [
        row.student_id
        for row in db.execute(
            student_projects.select().where(student_projects.c.project_id == group.id)
        ).all()
    ]
    file_count = 0
    if student_ids:
        file_count = (
            db.query(func.count(Evidence.id))
            .filter(Evidence.student_id.in_(student_ids))
            .scalar()
            or 0
        )
    return _group_to_out(group, student_count, file_count)


@router.delete("/{module_id}/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_module_group(
    module_id: str,
    group_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    group = (
        db.query(Project)
        .filter(Project.id == group_id, Project.module_id == module.id)
        .first()
    )
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    if group.name == _DEFAULT_GROUP_NAME:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Default group cannot be deleted",
        )

    default_group = _get_or_create_default_group(db, module)

    # Move all students from deleted group to default group
    student_ids_in_group = [
        row.student_id
        for row in db.execute(
            student_projects.select().where(student_projects.c.project_id == group.id)
        ).all()
    ]
    if student_ids_in_group:
        # Remove existing associations with the deleted group
        db.execute(
            student_projects.delete().where(
                student_projects.c.project_id == group.id
            )
        )
        # Add associations to the default group (skip if already there)
        already_in_default = {
            row.student_id
            for row in db.execute(
                student_projects.select().where(student_projects.c.project_id == default_group.id)
            ).all()
        }
        for sid in student_ids_in_group:
            if sid not in already_in_default:
                db.execute(
                    student_projects.insert().values(student_id=sid, project_id=default_group.id)
                )

    db.delete(group)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
    students = (
        db.query(Student)
        .join(student_projects, Student.student_number == student_projects.c.student_id)
        .filter(student_projects.c.project_id.in_(project_ids))
        .order_by(Student.name)
        .all()
    ) if project_ids else []

    student_project_map = _build_student_project_map(db, project_ids)

    latest_assessment: dict = {}
    if students:
        for a in db.query(Assessment).filter(
            Assessment.student_id.in_([s.student_number for s in students])
        ).all():
            existing = latest_assessment.get(a.student_id)
            if existing is None or a.created_at > existing.created_at:
                latest_assessment[a.student_id] = a
    return [
        _student_to_out(
            s,
            _assessment_status(latest_assessment.get(s.student_number)),
            _assessment_grade(latest_assessment.get(s.student_number)),
            project_id=str(student_project_map[s.student_number]) if s.student_number in student_project_map else None,
        )
        for s in students
    ]


@router.post("/{module_id}/students", response_model=StudentOut, status_code=status.HTTP_201_CREATED)
def add_module_student(
    module_id: str,
    payload: StudentCreate,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    project = _resolve_group_for_module(db, module, payload.project_id)

    if _student_duplicate_in_module(db, _module_project_ids(db, module.id), payload.student_number):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_DUPLICATE_DETAIL)

    # Reuse existing student record if one with this number already exists
    student = db.query(Student).filter(Student.student_number == payload.student_number).first()
    if student is None:
        student = Student(name=payload.name, student_number=payload.student_number)
        db.add(student)
        db.flush()

    student.projects.append(project)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_DUPLICATE_DETAIL)
    db.refresh(student)
    return _student_to_out(student, project_id=str(project.id))


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
        .join(student_projects, Student.student_number == student_projects.c.student_id)
        .filter(
            Student.student_number == student_id,
            student_projects.c.project_id.in_(project_ids),
        )
        .first()
    )
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found in this module")

    if (
        payload.project_id is None
        and payload.name is None
        and payload.student_number is None
        and payload.status is None
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No student updates provided")

    if payload.project_id is not None:
        target = (
            db.query(Project)
            .filter(Project.id == payload.project_id, Project.module_id == module.id)
            .first()
        )
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found in this module")

        # Move student from current group(s) in this module to the target group
        db.execute(
            student_projects.delete().where(
                student_projects.c.student_id == student.student_number,
                student_projects.c.project_id.in_(project_ids),
            )
        )
        db.execute(
            student_projects.insert().values(student_id=student.student_number, project_id=target.id)
        )

    if payload.name is not None:
        student.name = payload.name

    if payload.student_number is not None:
        if _student_duplicate_in_module(db, project_ids, payload.student_number):
            existing = (
                db.query(Student)
                .join(student_projects, Student.student_number == student_projects.c.student_id)
                .filter(
                    student_projects.c.project_id.in_(project_ids),
                    Student.student_number == payload.student_number,
                    Student.student_number != student.student_number,
                )
                .first()
            )
            if existing:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_DUPLICATE_DETAIL)
        student.student_number = payload.student_number

    if payload.status is not None:
        student.status = StudentStatus(payload.status)

    db.commit()
    db.refresh(student)
    # Resolve the student's current group within this module for the response
    current_project_id = None
    if payload.project_id is not None:
        current_project_id = str(target.id)
    else:
        row = db.execute(
            student_projects.select().where(
                student_projects.c.student_id == student.student_number,
                student_projects.c.project_id.in_(project_ids),
            )
        ).first()
        if row:
            current_project_id = str(row.project_id)
    return _student_to_out(student, project_id=current_project_id)


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

    module_project_ids = _module_project_ids(db, module.id)
    existing_numbers = {
        s.student_number
        for s in (
            db.query(Student)
            .join(student_projects, Student.student_number == student_projects.c.student_id)
            .filter(student_projects.c.project_id.in_(module_project_ids))
            .all()
        )
        if s.student_number
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
        if not number.isdigit():
            errors.append(ImportRowError(row=row.row_number, student_number=number, message="Student number must contain digits only"))
            continue
        if number in seen:
            errors.append(ImportRowError(row=row.row_number, student_number=number, message="Duplicate student number in file"))
            continue
        if number in existing_numbers:
            errors.append(ImportRowError(row=row.row_number, student_number=number, message="Student number already exists in this module"))
            continue

        seen.add(number)
        student = db.query(Student).filter(Student.student_number == number).first()
        if student is None:
            student = Student(name=name, student_number=number)
            db.add(student)
            db.flush()
        student.projects.append(project)
        to_add.append(student)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Import conflicted with a concurrent change. Please try again.",
        )

    for s in to_add:
        db.refresh(s)

    return StudentImportResult(
        imported_count=len(to_add),
        error_count=len(errors),
        total_rows=len(rows),
        errors=errors,
        students=[_student_to_out(s, project_id=str(project.id)) for s in to_add],
    )


# ---------------------------------------------------------------------------
# Overlap detection
# ---------------------------------------------------------------------------


@router.get("/{module_id}/overlap/signals", response_model=List[OverlapSignalOut])
def list_module_overlap_signals(
    module_id: str,
    status: Optional[str] = Query(None, description="confirmed or possible"),
    scope: Optional[str] = Query(None, description="within_group or cross_group"),
    group_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    signals = OverlapService.get_module_signals(
        db,
        str(module.id),
        status=status,
        scope=scope,
        group_id=group_id,
    )
    student_names, evidence_names = _module_signal_context(db, module)
    return [_signal_to_out(signal, student_names, evidence_names) for signal in signals]


@router.get("/{module_id}/overlap/signals/{signal_id}", response_model=OverlapSignalOut)
def get_module_overlap_signal(
    module_id: str,
    signal_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    signal = OverlapService.get_signal(db, str(module.id), signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Overlap signal not found")
    student_names, evidence_names = _module_signal_context(db, module)
    return _signal_to_out(signal, student_names, evidence_names)


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


# ---------------------------------------------------------------------------
# Excel grade export
# ---------------------------------------------------------------------------


@router.get(
    "/{module_id}/export/grades",
    summary="Export student grades as Excel",
    response_class=StreamingResponse,
)
def export_grades_excel(
    module_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    """Return an .xlsx file with one row per student: name, student number,
    group, assessment status and final grade."""
    try:
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="openpyxl is not installed on the server.",
        )

    module = _get_visible_module_or_404(db, module_id, current_teacher)

    projects = db.query(Project).filter(Project.module_id == module.id).all()
    project_name_by_id = {p.id: p.name for p in projects}
    project_ids = [p.id for p in projects]

    students = (
        db.query(Student)
        .join(student_projects, Student.student_number == student_projects.c.student_id)
        .filter(student_projects.c.project_id.in_(project_ids))
        .order_by(Student.name)
        .all()
    ) if project_ids else []

    # Build student -> project mapping for the group column
    student_project_map = _build_student_project_map(db, project_ids)

    latest_assessment: dict = {}
    if students:
        for a in db.query(Assessment).filter(
            Assessment.student_id.in_([s.student_number for s in students])
        ).all():
            existing = latest_assessment.get(a.student_id)
            if existing is None or a.created_at > existing.created_at:
                latest_assessment[a.student_id] = a

    # Build workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Grades"

    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    center = Alignment(horizontal="center", vertical="center")

    headers = ["#", "Student Name", "Student Number", "Group", "Assessment Status", "Grade"]
    col_widths = [5, 30, 18, 25, 22, 12]

    for col_idx, (header, width) in enumerate(zip(headers, col_widths), start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.row_dimensions[1].height = 22

    for row_idx, student in enumerate(students, start=2):
        assessment = latest_assessment.get(student.student_number)
        ast_status = _assessment_status(assessment)
        grade = _assessment_grade(assessment) or "—"
        group_pid = student_project_map.get(student.student_number)
        group_name = project_name_by_id.get(group_pid, "—") if group_pid else "—"

        row_data = [
            row_idx - 1,
            student.name,
            student.student_number or "—",
            group_name,
            ast_status.replace("-", " ").title(),
            grade,
        ]

        row_fill = PatternFill(
            start_color="F8FAFC" if row_idx % 2 == 0 else "FFFFFF",
            end_color="F8FAFC" if row_idx % 2 == 0 else "FFFFFF",
            fill_type="solid",
        )

        for col_idx, value in enumerate(row_data, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.fill = row_fill
            cell.alignment = Alignment(
                horizontal="center" if col_idx in (1, 3, 5, 6) else "left",
                vertical="center",
            )

        ws.row_dimensions[row_idx].height = 18

    ws.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    from datetime import date
    safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in module.name).strip("_")
    today = date.today().strftime("%Y-%m-%d")
    filename = f"{safe_name}_{today}.xlsx"

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
