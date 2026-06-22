"""Shared dependencies and query helpers for module endpoints."""
from __future__ import annotations

from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.services.module_group_service import DEFAULT_GROUP_NAME, get_or_create_default_group
from app.models.evidence import Evidence
from app.models.module import Module
from app.models.project import Project
from app.models.student import Student, student_projects
from app.models.teacher import Teacher


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
    if not project_ids:
        return {}
    rows = db.execute(
        student_projects.select().where(student_projects.c.project_id.in_(project_ids))
    ).all()
    return {row.student_id: row.project_id for row in rows}


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
    return get_or_create_default_group(db, module)


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
