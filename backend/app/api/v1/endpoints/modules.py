from typing import List

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher, get_db
from app.models.file_record import FileRecord
from app.models.teacher import Teacher
from app.schemas.module import ModuleCreate, ModuleOut, RubricFileOut
from app.services.module_service import ModuleService

router = APIRouter()


def _rubric_file_out(record: FileRecord | None) -> RubricFileOut | None:
    if not record:
        return None
    return RubricFileOut(
        id=str(record.id),
        file_name=record.file_name,
        file_type=record.file_type,
        size_bytes=record.size_bytes,
        uploaded_at=record.uploaded_at,
    )


def _module_out(module, db: Session) -> ModuleOut:
    rubric = None
    if module.rubric_file_id:
        rubric = db.query(FileRecord).filter(FileRecord.id == module.rubric_file_id).first()
    return ModuleOut(
        id=str(module.id),
        name=module.name,
        academic_year=module.academic_year,
        status=module.status.value if module.status else "active",
        created_at=module.created_at,
        rubric_file=_rubric_file_out(rubric),
    )


@router.get("", response_model=List[ModuleOut])
def list_modules(
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    modules = ModuleService.list_for_teacher(teacher.id, db)
    return [_module_out(m, db) for m in modules]


@router.post("", response_model=ModuleOut, status_code=status.HTTP_201_CREATED)
def create_module(
    payload: ModuleCreate,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    module = ModuleService.create(payload.name, payload.academic_year, teacher.id, db)
    return _module_out(module, db)


@router.get("/{module_id}", response_model=ModuleOut)
def get_module(
    module_id: str,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    module = ModuleService.get(module_id, teacher.id, db)
    return _module_out(module, db)


@router.post("/{module_id}/rubric", response_model=ModuleOut)
def upload_rubric(
    module_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    module = ModuleService.upload_rubric(module_id, file, teacher.id, db)
    return _module_out(module, db)


@router.delete("/{module_id}/rubric", status_code=status.HTTP_204_NO_CONTENT)
def delete_rubric(
    module_id: str,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    ModuleService.delete_rubric(module_id, teacher.id, db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
