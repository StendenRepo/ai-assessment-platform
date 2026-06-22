"""Student roster operations for a module."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.assessment import Assessment
from app.models.enums import StudentStatus
from app.models.module import Module
from app.models.project import Project
from app.models.student import Student, student_projects
from app.schemas.module import StudentGroupUpdate
from app.schemas.project import ImportRowError, StudentCreate
from app.services.module_group_service import get_or_create_default_group
from app.services.student_import import ParsedRow

_DUPLICATE_DETAIL = "A student with that student number already exists in this module"


def _module_project_ids(db: Session, module_id: str) -> list[str]:
    return [
        str(p.id)
        for p in db.query(Project).filter(Project.module_id == module_id).all()
    ]


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
    return get_or_create_default_group(db, module)


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


def _build_student_project_map(db: Session, project_ids: list) -> dict:
    if not project_ids:
        return {}
    rows = db.execute(
        student_projects.select().where(student_projects.c.project_id.in_(project_ids))
    ).all()
    return {row.student_id: row.project_id for row in rows}


@dataclass
class ListedStudent:
    student: Student
    latest_assessment: Assessment | None
    project_id: str | None


@dataclass
class MoveStudentResult:
    student: Student
    current_project_id: str | None
    audit_details: dict


@dataclass
class ImportStudentsResult:
    imported: list[Student]
    errors: list[ImportRowError]
    total_rows: int


class ModuleRosterService:
    @staticmethod
    def list_students(module: Module, db: Session) -> list[ListedStudent]:
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
            for assessment in db.query(Assessment).filter(
                Assessment.student_id.in_([s.student_number for s in students])
            ).all():
                existing = latest_assessment.get(assessment.student_id)
                if existing is None or assessment.created_at > existing.created_at:
                    latest_assessment[assessment.student_id] = assessment

        return [
            ListedStudent(
                student=s,
                latest_assessment=latest_assessment.get(s.student_number),
                project_id=str(student_project_map[s.student_number])
                if s.student_number in student_project_map
                else None,
            )
            for s in students
        ]

    @staticmethod
    def add_student(module: Module, payload: StudentCreate, db: Session) -> tuple[Student, Project]:
        project = _resolve_group_for_module(db, module, payload.project_id)

        if (
            payload.github_repo_url
            and project.github_repo_url
            and payload.github_repo_url != project.github_repo_url
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This group already has a GitHub repository. Use the group repository instead.",
            )

        if _student_duplicate_in_module(db, _module_project_ids(db, module.id), payload.student_number):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_DUPLICATE_DETAIL)

        student = db.query(Student).filter(Student.student_number == payload.student_number).first()
        if student is None:
            student = Student(name=payload.name, student_number=payload.student_number)
            db.add(student)
            db.flush()

        if payload.github_repo_url:
            student.github_repo_url = payload.github_repo_url
        elif project.github_repo_url:
            student.github_repo_url = project.github_repo_url

        if payload.github_branch:
            student.github_branch = payload.github_branch
        elif project.github_branch:
            student.github_branch = project.github_branch

        student.projects.append(project)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_DUPLICATE_DETAIL)
        db.refresh(student)
        return student, project

    @staticmethod
    def move_student(
        module: Module,
        student_id: str,
        payload: StudentGroupUpdate,
        db: Session,
    ) -> MoveStudentResult:
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
            and "github_repo_url" not in payload.model_fields_set
        ):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No student updates provided")

        original_name = student.name
        original_number = student.student_number
        old_github_repo_url = student.github_repo_url
        old_github_branch = student.github_branch
        current_group_row = db.execute(
            student_projects.select().where(
                student_projects.c.student_id == student.student_number,
                student_projects.c.project_id.in_(project_ids),
            )
        ).first()
        old_project_id = str(current_group_row.project_id) if current_group_row else None
        target = None

        if payload.project_id is not None:
            target = (
                db.query(Project)
                .filter(Project.id == payload.project_id, Project.module_id == module.id)
                .first()
            )
            if not target:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found in this module")

            db.execute(
                student_projects.delete().where(
                    student_projects.c.student_id == student.student_number,
                    student_projects.c.project_id.in_(project_ids),
                )
            )
            db.execute(
                student_projects.insert().values(student_id=student.student_number, project_id=target.id)
            )

            if target.github_repo_url is not None:
                requested_repo = payload.github_repo_url if "github_repo_url" in payload.model_fields_set else None
                if requested_repo is not None and requested_repo != target.github_repo_url:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="This group already has a GitHub repository. Use the group repository instead.",
                    )
                student.github_repo_url = target.github_repo_url
                if target.github_branch is not None:
                    student.github_branch = target.github_branch

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

        if "github_repo_url" in payload.model_fields_set:
            if target and target.github_repo_url is not None:
                student.github_repo_url = target.github_repo_url
            else:
                student.github_repo_url = payload.github_repo_url

        if "github_branch" in payload.model_fields_set:
            if target and target.github_branch is not None:
                student.github_branch = target.github_branch
            else:
                student.github_branch = payload.github_branch

        new_project_id = str(target.id) if target is not None else old_project_id
        old_group = (
            db.query(Project).filter(Project.id == old_project_id).first()
            if old_project_id
            else None
        )
        student_repo_removed = old_github_repo_url is not None and student.github_repo_url is None
        student_repo_added = old_github_repo_url is None and student.github_repo_url is not None

        audit_details = {
            "module_id": str(module.id),
            "module_name": module.name,
            "student_id": original_number,
            "student_name": original_name if original_name == student.name else f"{original_name} → {student.name}",
            "old_group_name": old_group.group_name or old_group.name if old_group else None,
            "new_group_name": target.group_name or target.name if target else None,
            "old_student_number": original_number,
            "new_student_number": student.student_number,
            "old_project_id": old_project_id,
            "new_project_id": new_project_id,
            "new_status": student.status.value if student.status else None,
            "old_github_repo_url": old_github_repo_url,
            "new_github_repo_url": student.github_repo_url,
            "repo_removed": student_repo_removed,
            "repo_added": student_repo_added,
            "old_github_branch": old_github_branch,
            "new_github_branch": student.github_branch,
            "branch_changed": old_github_branch != student.github_branch
            and not student_repo_removed
            and not student_repo_added,
        }

        db.commit()
        db.refresh(student)

        if payload.project_id is not None:
            current_project_id = str(target.id)
        else:
            row = db.execute(
                student_projects.select().where(
                    student_projects.c.student_id == student.student_number,
                    student_projects.c.project_id.in_(project_ids),
                )
            ).first()
            current_project_id = str(row.project_id) if row else None

        return MoveStudentResult(
            student=student,
            current_project_id=current_project_id,
            audit_details=audit_details,
        )

    @staticmethod
    def import_students(
        module: Module,
        project: Project,
        rows: list[ParsedRow],
        db: Session,
    ) -> ImportStudentsResult:
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
                errors.append(
                    ImportRowError(
                        row=row.row_number,
                        student_number=number,
                        message="Student number must contain digits only",
                    )
                )
                continue
            if number in seen:
                errors.append(
                    ImportRowError(
                        row=row.row_number,
                        student_number=number,
                        message="Duplicate student number in file",
                    )
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
            student = db.query(Student).filter(Student.student_number == number).first()
            if student is None:
                student = Student(name=name, student_number=number)
                db.add(student)
                db.flush()
            if project.github_repo_url:
                student.github_repo_url = project.github_repo_url
            if project.github_branch:
                student.github_branch = project.github_branch
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

        return ImportStudentsResult(imported=to_add, errors=errors, total_rows=len(rows))
