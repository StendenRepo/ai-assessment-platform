"""Module group lifecycle helpers."""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.enums import ProjectStatus
from app.models.evidence import Evidence
from app.models.module import Module
from app.models.project import Project
from app.models.student import Student, student_projects
from app.services.evidence_service import EvidenceService

DEFAULT_GROUP_NAME = "Individual Students"


def get_or_create_default_group(db: Session, module: Module) -> Project:
    default_group = (
        db.query(Project)
        .filter(Project.module_id == module.id, Project.name == DEFAULT_GROUP_NAME)
        .first()
    )
    if default_group:
        return default_group

    default_group = Project(
        module_id=module.id,
        name=DEFAULT_GROUP_NAME,
        group_name=DEFAULT_GROUP_NAME,
        status=ProjectStatus.active,
    )
    db.add(default_group)
    db.flush()
    return default_group


class ModuleGroupService:
    @staticmethod
    def delete_group(module: Module, group: Project, db: Session) -> None:
        """Delete a non-default group, move members to default, remove shared evidence. Does not commit."""
        if group.name == DEFAULT_GROUP_NAME:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Default group cannot be deleted",
            )

        default_group = get_or_create_default_group(db, module)

        evidence_items = db.query(Evidence).filter(Evidence.project_id == group.id).all()
        if evidence_items:
            EvidenceService._delete_evidence_rows(evidence_items, db)

        student_ids_in_group = [
            row.student_id
            for row in db.execute(
                student_projects.select().where(student_projects.c.project_id == group.id)
            ).all()
        ]
        if student_ids_in_group:
            db.execute(
                student_projects.delete().where(student_projects.c.project_id == group.id)
            )
            already_in_default = {
                row.student_id
                for row in db.execute(
                    student_projects.select().where(
                        student_projects.c.project_id == default_group.id
                    )
                ).all()
            }
            for sid in student_ids_in_group:
                if sid not in already_in_default:
                    db.execute(
                        student_projects.insert().values(
                            student_id=sid, project_id=default_group.id
                        )
                    )

            for student in (
                db.query(Student)
                .filter(Student.student_number.in_(student_ids_in_group))
                .all()
            ):
                student.github_repo_url = default_group.github_repo_url
                student.github_branch = default_group.github_branch

        db.delete(group)
        db.flush()

        for ev in evidence_items:
            EvidenceService._delete_evidence_artifacts(ev)
