"""Rubric criteria endpoints — Stage 2 of the project creation flow.

# Two-stage project creation (read this first)

Creating a project is a TWO-stage process:

  Stage 1  POST /api/v1/projects                       -> project.status = "draft"
  Stage 2  POST /api/v1/projects/{id}/rubric/save      -> project.status = "ready"
           (the "Complete Setup" action)

Between the two stages the teacher can freely add/update/delete individual
criteria through the per-row endpoints below — that's what the "Save Draft"
button uses. The bulk-save endpoint is the ONLY place that flips
project.status to "ready"; every other endpoint here leaves the status
untouched.

# Audit trail (NFR-02)

Every write produces an audit_log entry in the SAME database transaction as
the write:

  - POST   /rubric              -> criterion_created
  - PATCH  /rubric/{id}          -> criterion_updated
  - DELETE /rubric/{id}          -> criterion_deleted
  - POST   /rubric/save          -> project_ready (single combined entry with
                                    criteria_count + total_points)

# Ownership

All endpoints require the calling teacher to own the parent project — i.e.
the project's module must belong to that teacher. A foreign project returns
404 (not 403) so we don't leak the existence of other teachers' projects.
"""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher, get_db
from app.models.module import Module
from app.models.project import Project
from app.models.rubric import RubricCriterion
from app.models.teacher import Teacher
from app.models.enums import ProjectStatus
from app.schemas.rubric import (
    RubricBulkSave,
    RubricCriterionCreate,
    RubricCriterionResponse,
    RubricCriterionUpdate,
)
from app.services.audit_service import log_action

router = APIRouter()


def _get_owned_project(
    project_id: UUID, db: Session, teacher: Teacher
) -> Project:
    """Fetch a project that belongs to the calling teacher.

    A project belongs to a teacher when its module belongs to that teacher.
    Projects with module_id=None are visible to any authenticated teacher
    for now (the multi-tenant scoping for module-less projects is tracked
    as a separate cleanup; flagged in code review).
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    if project.module_id is not None:
        module = (
            db.query(Module)
            .filter(Module.id == project.module_id)
            .first()
        )
        if module is None or module.teacher_id != teacher.id:
            # Same 404 — do not leak existence
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )
    return project


def _get_owned_criterion(
    project: Project, criterion_id: UUID, db: Session
) -> RubricCriterion:
    criterion = (
        db.query(RubricCriterion)
        .filter(
            RubricCriterion.id == criterion_id,
            RubricCriterion.project_id == project.id,
        )
        .first()
    )
    if not criterion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Criterion not found",
        )
    return criterion


@router.get(
    "/projects/{project_id}/rubric",
    response_model=List[RubricCriterionResponse],
)
def list_criteria(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    project = _get_owned_project(project_id, db, current_teacher)
    return (
        db.query(RubricCriterion)
        .filter(RubricCriterion.project_id == project.id)
        .order_by(RubricCriterion.category, RubricCriterion.position, RubricCriterion.created_at)
        .all()
    )


@router.post(
    "/projects/{project_id}/rubric",
    response_model=RubricCriterionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_criterion(
    project_id: UUID,
    payload: RubricCriterionCreate,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    project = _get_owned_project(project_id, db, current_teacher)
    criterion = RubricCriterion(
        project_id=project.id,
        category=payload.category,
        title=payload.title,
        description=payload.description,
        points=payload.points,
        position=payload.position,
    )
    db.add(criterion)
    db.flush()

    log_action(
        db,
        action="criterion_created",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "project_id": str(project.id),
            "criterion_id": str(criterion.id),
            "category": criterion.category,
            "title": criterion.title,
            "points": criterion.points,
        },
        commit=False,
    )
    db.commit()
    db.refresh(criterion)
    return criterion


@router.patch(
    "/projects/{project_id}/rubric/{criterion_id}",
    response_model=RubricCriterionResponse,
)
def update_criterion(
    project_id: UUID,
    criterion_id: UUID,
    payload: RubricCriterionUpdate,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    project = _get_owned_project(project_id, db, current_teacher)
    criterion = _get_owned_criterion(project, criterion_id, db)

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields supplied to update",
        )
    for field, value in changes.items():
        setattr(criterion, field, value)
    db.flush()

    log_action(
        db,
        action="criterion_updated",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "project_id": str(project.id),
            "criterion_id": str(criterion.id),
            "changed_fields": sorted(changes.keys()),
        },
        commit=False,
    )
    db.commit()
    db.refresh(criterion)
    return criterion


@router.delete(
    "/projects/{project_id}/rubric/{criterion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_criterion(
    project_id: UUID,
    criterion_id: UUID,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    project = _get_owned_project(project_id, db, current_teacher)
    criterion = _get_owned_criterion(project, criterion_id, db)

    snapshot = {
        "project_id": str(project.id),
        "criterion_id": str(criterion.id),
        "category": criterion.category,
        "title": criterion.title,
        "points": criterion.points,
    }
    db.delete(criterion)
    db.flush()

    log_action(
        db,
        action="criterion_deleted",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details=snapshot,
        commit=False,
    )
    db.commit()
    return None


@router.post(
    "/projects/{project_id}/rubric/save",
    response_model=List[RubricCriterionResponse],
)
def bulk_save_rubric(
    project_id: UUID,
    payload: RubricBulkSave,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    """Atomically replace the project's rubric AND mark the project ready.

    This is the "Complete Setup →" action. Either every row saves AND the
    status flip to "ready" lands, or nothing changes. At least one criterion
    is required.
    """
    project = _get_owned_project(project_id, db, current_teacher)

    if not payload.criteria:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot mark project ready with no criteria",
        )

    # Replace strategy: delete all existing rows for this project, then insert
    # the new list. Done inside a single transaction so a failure rolls back
    # the entire operation, including the status flip.
    db.query(RubricCriterion).filter(
        RubricCriterion.project_id == project.id
    ).delete(synchronize_session=False)

    saved: List[RubricCriterion] = []
    total_points = 0
    for idx, c in enumerate(payload.criteria):
        row = RubricCriterion(
            project_id=project.id,
            category=c.category,
            title=c.title,
            description=c.description,
            points=c.points,
            position=c.position if c.position else idx,
        )
        db.add(row)
        saved.append(row)
        total_points += c.points

    project.status = ProjectStatus.ready
    db.flush()

    log_action(
        db,
        action="project_ready",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "project_id": str(project.id),
            "criteria_count": len(saved),
            "total_points": total_points,
        },
        commit=False,
    )
    db.commit()
    for row in saved:
        db.refresh(row)
    return saved
