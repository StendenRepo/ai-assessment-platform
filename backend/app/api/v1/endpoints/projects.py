from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher, get_db
from app.models.project import Project
from app.models.student import Student
from app.models.teacher import Teacher
from app.schemas.project import ProjectOut, StudentCreate, StudentOut

router = APIRouter()


def _student_to_out(s: Student) -> StudentOut:
    return StudentOut(
        id=str(s.id),
        project_id=str(s.project_id),
        name=s.name,
        student_number=s.student_number,
        status=s.status.value if s.status else "active",
        consent_given=bool(s.consent_given),
    )


def _project_to_out(p: Project, student_count: int) -> ProjectOut:
    return ProjectOut(
        id=str(p.id),
        name=p.name,
        group_name=p.group_name,
        module_id=str(p.module_id),
        status=p.status.value if p.status else "active",
        created_at=p.created_at,
        student_count=student_count,
    )


def _get_project_or_404(db: Session, project_id: str) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

@router.get("/projects", response_model=List[ProjectOut])
def list_projects(
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    result = []
    for p in projects:
        count = db.query(Student).filter(Student.project_id == p.id).count()
        result.append(_project_to_out(p, count))
    return result


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    project = _get_project_or_404(db, project_id)
    count = db.query(Student).filter(Student.project_id == project.id).count()
    return _project_to_out(project, count)


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------

@router.get("/projects/{project_id}/students", response_model=List[StudentOut])
def list_project_students(
    project_id: str,
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    _get_project_or_404(db, project_id)
    students = (
        db.query(Student)
        .filter(Student.project_id == project_id)
        .order_by(Student.name)
        .all()
    )
    return [_student_to_out(s) for s in students]


@router.post(
    "/projects/{project_id}/students",
    response_model=StudentOut,
    status_code=status.HTTP_201_CREATED,
)
def add_project_student(
    project_id: str,
    payload: StudentCreate,
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    project = _get_project_or_404(db, project_id)

    duplicate = (
        db.query(Student)
        .filter(
            Student.project_id == project.id,
            Student.student_number == payload.student_number,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A student with that student number already exists in this project",
        )

    student = Student(
        project_id=project.id,
        name=payload.name,
        student_number=payload.student_number,
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return _student_to_out(student)
