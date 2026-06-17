from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher, get_db
from app.models.module import Module
from app.models.enums import EmbeddingStatus
from app.models.project import Project
from app.models.student import Student, student_projects
from app.models.teacher import Teacher
from app.schemas.evidence import EvidenceOut
from app.schemas.project import (
    ImportRowError,
    ProjectOut,
    StudentCreate,
    StudentImportResult,
    StudentOut,
)
from app.services import audit_service
from app.services.evidence_service import EvidenceService, run_vision_background
from app.services.student_import import ImportParseError, parse_student_file

router = APIRouter()

_DUPLICATE_DETAIL = "A student with that student number already exists in this project"


def _student_to_out(s: Student, project_id: str = None) -> StudentOut:
    return StudentOut(
        id=s.student_number,
        name=s.name,
        student_number=s.student_number,
        github_repo_url=s.github_repo_url,
        github_branch=s.github_branch,
        status=s.status.value if s.status else "active",
        consent_given=bool(s.consent_given),
        project_id=project_id,
    )


def _project_to_out(p: Project, student_count: int) -> ProjectOut:
    return ProjectOut(
        id=str(p.id),
        name=p.name,
        group_name=p.group_name,
        github_repo_url=p.github_repo_url,
        github_branch=p.github_branch,
        module_id=str(p.module_id),
        status=p.status.value if p.status else "active",
        created_at=p.created_at,
        student_count=student_count,
    )


def _owned_projects_query(db: Session, teacher: Teacher):
    """Projects belonging to the given teacher (project -> module -> teacher)."""
    if teacher.is_admin:
        return db.query(Project)
    return (
        db.query(Project)
        .join(Module, Project.module_id == Module.id)
        .filter(Module.teacher_id == teacher.id)
    )


def _get_owned_project_or_404(db: Session, project_id: str, teacher: Teacher) -> Project:
    project = _owned_projects_query(db, teacher).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _student_count_for_project(db: Session, project_id) -> int:
    return (
        db.query(student_projects)
        .filter(student_projects.c.project_id == project_id)
        .count()
    )


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

@router.get("", response_model=List[ProjectOut])
def list_projects(
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    projects = _owned_projects_query(db, current_teacher).order_by(Project.created_at.desc()).all()
    return [_project_to_out(p, _student_count_for_project(db, p.id)) for p in projects]


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    project = _get_owned_project_or_404(db, project_id, current_teacher)
    return _project_to_out(project, _student_count_for_project(db, project.id))


@router.post(
    "/{project_id}/evidence",
    response_model=EvidenceOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload shared evidence for a project",
)
def upload_project_evidence(
    project_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    project = _get_owned_project_or_404(db, project_id, current_teacher)
    evidence = EvidenceService.upload_file_for_project(str(project.id), file, db)
    audit_service.log_action(
        db,
        action="evidence.uploaded",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "evidence_id": str(evidence.id),
            "project_id": str(project.id),
            "project_name": project.name,
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
            f"project {project.name}",
        )
    return evidence


@router.get(
    "/{project_id}/evidence",
    response_model=List[EvidenceOut],
    summary="List shared evidence for a project",
)
def list_project_evidence(
    project_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    project = _get_owned_project_or_404(db, project_id, current_teacher)
    return EvidenceService.list_for_project(str(project.id), db)


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------

@router.get("/{project_id}/students", response_model=List[StudentOut])
def list_project_students(
    project_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    project = _get_owned_project_or_404(db, project_id, current_teacher)
    students = (
        db.query(Student)
        .join(student_projects, Student.student_number == student_projects.c.student_id)
        .filter(student_projects.c.project_id == project.id)
        .order_by(Student.name)
        .all()
    )
    return [_student_to_out(s, project_id=str(project.id)) for s in students]


@router.post(
    "/{project_id}/students",
    response_model=StudentOut,
    status_code=status.HTTP_201_CREATED,
)
def add_project_student(
    project_id: str,
    payload: StudentCreate,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    project = _get_owned_project_or_404(db, project_id, current_teacher)

    if (
        payload.github_repo_url
        and project.github_repo_url
        and payload.github_repo_url != project.github_repo_url
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This group already has a GitHub repository. Use the group repository instead.",
        )

    # Check if this student is already linked to this project
    existing = db.query(Student).filter(Student.student_number == payload.student_number).first()
    if existing:
        already_in_project = (
            db.query(student_projects)
            .filter(
                student_projects.c.student_id == existing.student_number,
                student_projects.c.project_id == project.id,
            )
            .first()
        )
        if already_in_project:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_DUPLICATE_DETAIL)
        if payload.github_repo_url:
            existing.github_repo_url = payload.github_repo_url
        elif project.github_repo_url:
            existing.github_repo_url = project.github_repo_url
        if payload.github_branch:
            existing.github_branch = payload.github_branch
        elif project.github_branch:
            existing.github_branch = project.github_branch
        existing.projects.append(project)
        db.commit()
        db.refresh(existing)
        audit_service.log_action(
            db,
            action="student.created",
            teacher_id=current_teacher.id,
            teacher_name=current_teacher.name,
            details={
                "project_id": str(project.id),
                "project_name": project.name,
                "student_id": existing.student_number,
                "student_name": existing.name,
                "github_repo_url": existing.github_repo_url,
                "github_branch": existing.github_branch,
            },
        )
        return _student_to_out(existing, project_id=str(project.id))

    student = Student(
        name=payload.name,
        student_number=payload.student_number,
        github_repo_url=payload.github_repo_url or project.github_repo_url,
        github_branch=payload.github_branch or project.github_branch,
    )
    student.projects.append(project)
    db.add(student)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_DUPLICATE_DETAIL)
    db.refresh(student)
    audit_service.log_action(
        db,
        action="student.created",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "project_id": str(project.id),
            "project_name": project.name,
            "student_id": student.student_number,
            "student_name": student.name,
            "github_repo_url": student.github_repo_url,
            "github_branch": student.github_branch,
        },
    )
    return _student_to_out(student, project_id=str(project.id))


@router.post(
    "/{project_id}/students/import",
    response_model=StudentImportResult,
)
async def import_project_students(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    project = _get_owned_project_or_404(db, project_id, current_teacher)

    contents = await file.read()
    try:
        rows = parse_student_file(file.filename, contents)
    except ImportParseError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # Student numbers already linked to this project
    existing_in_project = {
        row.student_number
        for row in (
            db.query(Student.student_number)
            .join(student_projects, Student.student_number == student_projects.c.student_id)
            .filter(student_projects.c.project_id == project.id)
        )
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
        if number in existing_in_project:
            errors.append(ImportRowError(row=row.row_number, student_number=number, message="Student number already exists in this project"))
            continue

        seen.add(number)
        # Reuse an existing student record (same number, different project) or create new
        student = db.query(Student).filter(Student.student_number == number).first()
        if student is None:
            student = Student(name=name, student_number=number)
            db.add(student)
        if project.github_repo_url:
            student.github_repo_url = project.github_repo_url
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

    for student in to_add:
        db.refresh(student)

    audit_service.log_action(
        db,
        action="students.imported",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "project_id": str(project.id),
            "project_name": project.name,
            "imported_count": len(to_add),
            "error_count": len(errors),
            "total_rows": len(rows),
        },
    )

    return StudentImportResult(
        imported_count=len(to_add),
        error_count=len(errors),
        total_rows=len(rows),
        errors=errors,
        students=[_student_to_out(s, project_id=str(project.id)) for s in to_add],
    )
