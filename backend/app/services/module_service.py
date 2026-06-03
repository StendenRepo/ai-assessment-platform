import hashlib
import uuid as _uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models.file_record import FileRecord
from app.models.module import Module

RUBRIC_UPLOAD_DIR: Path = Path(settings.UPLOAD_DIR) / "rubrics"

ALLOWED_EXTENSIONS = {".pdf", ".xlsx"}


def _check_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Only PDF and Excel (.xlsx) files are allowed. Got '{ext}'.",
        )
    return ext


def _rubric_path(module_id: str, stored_name: str) -> Path:
    """Rebuild the absolute path on disk from the filename stored in the DB."""
    return RUBRIC_UPLOAD_DIR / str(module_id) / stored_name


def _get_module_or_404(module_id: str, teacher_id, db: Session) -> Module:
    module = (
        db.query(Module)
        .filter(Module.id == module_id, Module.teacher_id == teacher_id)
        .first()
    )
    if not module:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")
    return module


class ModuleService:
    @staticmethod
    def list_for_teacher(teacher_id, db: Session) -> list[Module]:
        return (
            db.query(Module)
            .filter(Module.teacher_id == teacher_id)
            .order_by(Module.created_at.desc())
            .all()
        )

    @staticmethod
    def get(module_id: str, teacher_id, db: Session) -> Module:
        return _get_module_or_404(module_id, teacher_id, db)

    @staticmethod
    def create(name: str, academic_year: str | None, teacher_id, db: Session) -> Module:
        module = Module(teacher_id=teacher_id, name=name, academic_year=academic_year)
        db.add(module)
        db.commit()
        db.refresh(module)
        return module

    @staticmethod
    def upload_rubric(module_id: str, file: UploadFile, teacher_id, db: Session) -> Module:
        module = _get_module_or_404(module_id, teacher_id, db)

        filename = file.filename or "rubric"
        _check_extension(filename)

        raw = file.file.read()
        file_hash = hashlib.sha256(raw).hexdigest()
        size = len(raw)

        upload_dir = RUBRIC_UPLOAD_DIR / str(module_id)
        upload_dir.mkdir(parents=True, exist_ok=True)

        unique_name = f"{_uuid.uuid4().hex}_{filename}"
        file_path = upload_dir / unique_name
        file_path.write_bytes(raw)

        # Hold reference to old record so we can delete it after the FK is updated
        old_record = None
        if module.rubric_file_id:
            old_record = db.query(FileRecord).filter(FileRecord.id == module.rubric_file_id).first()

        record = FileRecord(
            file_name=filename,
            path=unique_name,
            file_type=Path(filename).suffix.lstrip(".").lower(),
            size_bytes=size,
            hash=file_hash,
        )
        db.add(record)
        db.flush()

        # Update FK to new record first, then delete the old one
        module.rubric_file_id = record.id
        db.flush()

        if old_record:
            old_path = _rubric_path(module_id, old_record.path)
            if old_path.exists():
                old_path.unlink(missing_ok=True)
            db.delete(old_record)

        db.commit()
        db.refresh(module)
        return module

    @staticmethod
    def delete_rubric(module_id: str, teacher_id, db: Session) -> Module:
        module = _get_module_or_404(module_id, teacher_id, db)

        if not module.rubric_file_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="This module has no rubric attached.",
            )

        record = db.query(FileRecord).filter(FileRecord.id == module.rubric_file_id).first()
        if record:
            file_path = _rubric_path(module_id, record.path)
            if file_path.exists():
                file_path.unlink(missing_ok=True)
            db.delete(record)

        module.rubric_file_id = None
        db.commit()
        db.refresh(module)
        return module
