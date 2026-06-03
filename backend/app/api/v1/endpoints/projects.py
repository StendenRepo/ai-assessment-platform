from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher, get_db
from app.models.project import Project
from app.models.student import Student
from app.models.teacher import Teacher
from app.schemas.project import ProjectCreate, ProjectResponse
from app.services.audit_service import log_action

router = APIRouter()


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    if payload.module_id:
        from app.models.module import Module
        if not db.query(Module).filter(Module.id == payload.module_id).first():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")

    project = Project(
        name=payload.name,
        course=payload.course,
        group_name=payload.group_name,
        deadline=payload.deadline,
        module_id=payload.module_id,
    )
    db.add(project)
    db.flush()

    for s in payload.students or []:
        if s.email or s.student_number:
            db.add(Student(
                project_id=project.id,
                email=s.email or None,
                student_number=s.student_number or None,
                name=s.email or s.student_number,
            ))

    log_action(
        db,
        action="project_created",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={"name": project.name, "project_id": str(project.id)},
        commit=False,
    )
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=List[ProjectResponse])
def list_projects(
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    return db.query(Project).order_by(Project.created_at.desc()).all()
