import hashlib
import uuid as _uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models.file_record import FileRecord
from app.models.module import Module

RUBRIC_UPLOAD_DIR: Path = Path(settings.UPLOAD_DIR) / "rubrics"
MODULE_BOOK_UPLOAD_DIR: Path = Path(settings.UPLOAD_DIR) / "module_books"

RUBRIC_ALLOWED_EXTENSIONS = {".pdf", ".xlsx"}
RUBRIC_ALLOWED_LABEL = "PDF and Excel (.xlsx)"

# A module book is a course document, so accept document formats rather than
# spreadsheets. Note: the content is only stored and linked here; parsing and
# embedding it so the AI can use it is handled separately (see G2-105).
MODULE_BOOK_ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MODULE_BOOK_ALLOWED_LABEL = "PDF and Word (.docx)"


def _check_extension(filename: str, allowed: set[str], label: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Only {label} files are allowed. Got '{ext}'.",
        )
    return ext


def _module_file_path(base_dir: Path, module_id: str, stored_name: str) -> Path:
    """Rebuild the absolute path on disk from the filename stored in the DB."""
    return base_dir / str(module_id) / stored_name


def _get_module_or_404(module_id: str, teacher_id, db: Session, is_admin: bool = False) -> Module:
    query = db.query(Module).filter(Module.id == module_id)
    if not is_admin:
        query = query.filter(Module.teacher_id == teacher_id)
    module = query.first()
    if not module:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")
    return module


def _set_module_file(
    module: Module,
    file: UploadFile,
    *,
    base_dir: Path,
    allowed: set[str],
    label: str,
    fk_attr: str,
    default_name: str,
    db: Session,
) -> Module:
    """Store an uploaded file, link it to ``module`` via ``fk_attr`` and remove
    the file it replaces (if any). Shared by rubric and module book uploads."""
    filename = file.filename or default_name
    _check_extension(filename, allowed, label)

    raw = file.file.read()
    file_hash = hashlib.sha256(raw).hexdigest()
    size = len(raw)

    upload_dir = base_dir / str(module.id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    unique_name = f"{_uuid.uuid4().hex}_{filename}"
    (upload_dir / unique_name).write_bytes(raw)

    # Hold reference to the old record so we can delete it after the FK is updated.
    old_id = getattr(module, fk_attr)
    old_record = (
        db.query(FileRecord).filter(FileRecord.id == old_id).first() if old_id else None
    )

    record = FileRecord(
        file_name=filename,
        path=unique_name,
        file_type=Path(filename).suffix.lstrip(".").lower(),
        size_bytes=size,
        hash=file_hash,
    )
    db.add(record)
    db.flush()

    # Update FK to the new record first, then delete the old one.
    setattr(module, fk_attr, record.id)
    db.flush()

    if old_record:
        old_path = _module_file_path(base_dir, module.id, old_record.path)
        old_path.unlink(missing_ok=True)
        db.delete(old_record)

    db.commit()
    db.refresh(module)
    return module


def _clear_module_file(
    module: Module,
    *,
    base_dir: Path,
    fk_attr: str,
    missing_detail: str,
    db: Session,
) -> Module:
    """Detach and delete the file linked to ``module`` via ``fk_attr``."""
    file_id = getattr(module, fk_attr)
    if not file_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=missing_detail)

    record = db.query(FileRecord).filter(FileRecord.id == file_id).first()
    if record:
        _module_file_path(base_dir, module.id, record.path).unlink(missing_ok=True)
        db.delete(record)

    setattr(module, fk_attr, None)
    db.commit()
    db.refresh(module)
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
    def upload_rubric(
        module_id: str,
        file: UploadFile,
        teacher_id,
        db: Session,
        is_admin: bool = False,
    ) -> Module:
        module = _get_module_or_404(module_id, teacher_id, db, is_admin=is_admin)
        return _set_module_file(
            module,
            file,
            base_dir=RUBRIC_UPLOAD_DIR,
            allowed=RUBRIC_ALLOWED_EXTENSIONS,
            label=RUBRIC_ALLOWED_LABEL,
            fk_attr="rubric_file_id",
            default_name="rubric",
            db=db,
        )

    @staticmethod
    def delete_rubric(module_id: str, teacher_id, db: Session, is_admin: bool = False) -> Module:
        module = _get_module_or_404(module_id, teacher_id, db, is_admin=is_admin)
        return _clear_module_file(
            module,
            base_dir=RUBRIC_UPLOAD_DIR,
            fk_attr="rubric_file_id",
            missing_detail="This module has no rubric attached.",
            db=db,
        )

    @staticmethod
    def upload_module_book(
        module_id: str,
        file: UploadFile,
        teacher_id,
        db: Session,
        is_admin: bool = False,
    ) -> Module:
        module = _get_module_or_404(module_id, teacher_id, db, is_admin=is_admin)
        return _set_module_file(
            module,
            file,
            base_dir=MODULE_BOOK_UPLOAD_DIR,
            allowed=MODULE_BOOK_ALLOWED_EXTENSIONS,
            label=MODULE_BOOK_ALLOWED_LABEL,
            fk_attr="module_book_id",
            default_name="module-book",
            db=db,
        )

    @staticmethod
    def delete_module_book(
        module_id: str, teacher_id, db: Session, is_admin: bool = False
    ) -> Module:
        module = _get_module_or_404(module_id, teacher_id, db, is_admin=is_admin)
        return _clear_module_file(
            module,
            base_dir=MODULE_BOOK_UPLOAD_DIR,
            fk_attr="module_book_id",
            missing_detail="This module has no module book attached.",
            db=db,
        )
