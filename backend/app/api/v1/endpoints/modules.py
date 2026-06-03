from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher, get_db
from app.models.module import Module
from app.models.teacher import Teacher
from app.schemas.module import ModuleCreate, ModuleResponse
from app.services.audit_service import log_action

router = APIRouter()


@router.post("", response_model=ModuleResponse, status_code=status.HTTP_201_CREATED)
def create_module(
    payload: ModuleCreate,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = Module(
        name=payload.name,
        code=payload.code,
        academic_year=payload.academic_year,
        teacher_id=current_teacher.id,
    )
    db.add(module)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A module with this code already exists",
        )

    log_action(
        db,
        action="module_created",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={"name": module.name, "code": module.code, "module_id": str(module.id)},
        commit=False,
    )
    db.commit()
    db.refresh(module)
    return module


@router.get("", response_model=List[ModuleResponse])
def list_modules(
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    return db.query(Module).order_by(Module.created_at.desc()).all()
