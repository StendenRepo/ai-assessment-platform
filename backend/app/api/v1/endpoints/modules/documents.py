"""Module API routes — documents."""
from .router import router
from .shared import *  # noqa: F403

# ---------------------------------------------------------------------------
# Rubric upload
# ---------------------------------------------------------------------------


@router.post("/{module_id}/rubric", response_model=ModuleOut)
def upload_rubric(
    module_id: str,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module_before = _get_visible_module_or_404(db, module_id, current_teacher)
    previous_rubric = (
        db.query(FileRecord).filter(FileRecord.id == module_before.rubric_file_id).first()
        if module_before.rubric_file_id
        else None
    )

    module = ModuleService.upload_rubric(
        module_id,
        file,
        current_teacher.id,
        db,
        is_admin=current_teacher.is_admin,
    )

    current_rubric = (
        db.query(FileRecord).filter(FileRecord.id == module.rubric_file_id).first()
        if module.rubric_file_id
        else None
    )
    is_replace = previous_rubric is not None
    audit_service.log_action(
        db,
        action="rubric.replaced" if is_replace else "rubric.uploaded",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "module_id": str(module.id),
            "module_name": module.name,
            "rubric_name": current_rubric.file_name if current_rubric else (file.filename or "rubric"),
            "previous_rubric_name": previous_rubric.file_name if previous_rubric else None,
            "operation": "replace" if is_replace else "upload",
            "where": "Module > Rubric",
            "route": "/api/v1/modules/{module_id}/rubric",
        },
        ip_address=request.client.host if request.client else None,
    )

    project_count, student_count = _module_project_counts(db, module.id)
    return _module_to_out(module, project_count, student_count, db)


@router.delete("/{module_id}/rubric", status_code=status.HTTP_204_NO_CONTENT)
def delete_rubric(
    module_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module_before = _get_visible_module_or_404(db, module_id, current_teacher)
    previous_rubric = (
        db.query(FileRecord).filter(FileRecord.id == module_before.rubric_file_id).first()
        if module_before.rubric_file_id
        else None
    )

    ModuleService.delete_rubric(
        module_id,
        current_teacher.id,
        db,
        is_admin=current_teacher.is_admin,
    )

    audit_service.log_action(
        db,
        action="rubric.deleted",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "module_id": str(module_before.id),
            "module_name": module_before.name,
            "rubric_name": previous_rubric.file_name if previous_rubric else None,
            "operation": "delete",
            "where": "Module > Rubric",
            "route": "/api/v1/modules/{module_id}/rubric",
        },
        ip_address=request.client.host if request.client else None,
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Module book upload
# ---------------------------------------------------------------------------


@router.post("/{module_id}/module-book", response_model=ModuleOut)
def upload_module_book(
    module_id: str,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module_before = _get_visible_module_or_404(db, module_id, current_teacher)
    previous_module_book = (
        db.query(FileRecord).filter(FileRecord.id == module_before.module_book_id).first()
        if module_before.module_book_id
        else None
    )

    module = ModuleService.upload_module_book(
        module_id,
        file,
        current_teacher.id,
        db,
        is_admin=current_teacher.is_admin,
    )

    current_module_book = (
        db.query(FileRecord).filter(FileRecord.id == module.module_book_id).first()
        if module.module_book_id
        else None
    )
    is_replace = previous_module_book is not None
    audit_service.log_action(
        db,
        action="module_book.replaced" if is_replace else "module_book.uploaded",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "module_id": str(module.id),
            "module_name": module.name,
            "module_book_name": (
                current_module_book.file_name
                if current_module_book
                else (file.filename or "module-book")
            ),
            "previous_module_book_name": (
                previous_module_book.file_name if previous_module_book else None
            ),
            "operation": "replace" if is_replace else "upload",
            "where": "Module > Module Book",
            "route": "/api/v1/modules/{module_id}/module-book",
        },
        ip_address=request.client.host if request.client else None,
    )

    project_count, student_count = _module_project_counts(db, module.id)
    return _module_to_out(module, project_count, student_count, db)


@router.delete("/{module_id}/module-book", status_code=status.HTTP_204_NO_CONTENT)
def delete_module_book(
    module_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module_before = _get_visible_module_or_404(db, module_id, current_teacher)
    previous_module_book = (
        db.query(FileRecord).filter(FileRecord.id == module_before.module_book_id).first()
        if module_before.module_book_id
        else None
    )

    ModuleService.delete_module_book(
        module_id,
        current_teacher.id,
        db,
        is_admin=current_teacher.is_admin,
    )

    audit_service.log_action(
        db,
        action="module_book.deleted",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "module_id": str(module_before.id),
            "module_name": module_before.name,
            "module_book_name": (
                previous_module_book.file_name if previous_module_book else None
            ),
            "operation": "delete",
            "where": "Module > Module Book",
            "route": "/api/v1/modules/{module_id}/module-book",
        },
        ip_address=request.client.host if request.client else None,
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Serve module documents (rubric / module book) for in-app viewing (FR-03)
# ---------------------------------------------------------------------------


def _serve_module_document(
    db: Session,
    *,
    module: Module,
    file_id,
    base_dir,
    kind: str,
    missing_detail: str,
    request: Request,
    teacher: Teacher,
) -> FileResponse:
    """Return the stored module document inline, logging a 'document.viewed'
    audit entry. Visibility has already been enforced by the caller via
    ``_get_visible_module_or_404``."""
    if not file_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=missing_detail)

    record = db.query(FileRecord).filter(FileRecord.id == file_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=missing_detail)

    full_path = _module_file_path(base_dir, module.id, record.path)
    if not full_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found on disk",
        )

    media_type, _ = mimetypes.guess_type(record.file_name or record.path)

    audit_service.log_action(
        db,
        action="document.viewed",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        details={
            "kind": kind,
            "module_id": str(module.id),
            "file_id": str(record.id),
            "file_name": record.file_name,
        },
        ip_address=request.client.host if request.client else None,
    )

    return FileResponse(
        path=str(full_path),
        media_type=media_type or "application/octet-stream",
        filename=record.file_name,
        content_disposition_type="inline",
    )


def _module_document_content(
    db: Session, *, file_id, missing_detail: str
) -> dict:
    """Return the extracted plain text for a module document (used to preview
    .docx module books, which browsers can't render inline)."""
    if not file_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=missing_detail)
    record = db.query(FileRecord).filter(FileRecord.id == file_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=missing_detail)
    return {
        "id": str(record.id),
        "file_name": record.file_name,
        "content": record.extracted_text or "",
    }


@router.get("/{module_id}/rubric/file", summary="View or download the module rubric")
def get_rubric_file(
    module_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    return _serve_module_document(
        db,
        module=module,
        file_id=module.rubric_file_id,
        base_dir=RUBRIC_UPLOAD_DIR,
        kind="rubric",
        missing_detail="This module has no rubric attached.",
        request=request,
        teacher=current_teacher,
    )


@router.get("/{module_id}/rubric/content", summary="Extracted text of the module rubric")
def get_rubric_content(
    module_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    return _module_document_content(
        db,
        file_id=module.rubric_file_id,
        missing_detail="This module has no rubric attached.",
    )


@router.get("/{module_id}/module-book/file", summary="View or download the module book")
def get_module_book_file(
    module_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    return _serve_module_document(
        db,
        module=module,
        file_id=module.module_book_id,
        base_dir=MODULE_BOOK_UPLOAD_DIR,
        kind="module_book",
        missing_detail="This module has no module book attached.",
        request=request,
        teacher=current_teacher,
    )


@router.get(
    "/{module_id}/module-book/content",
    summary="Extracted text of the module book",
)
def get_module_book_content(
    module_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    return _module_document_content(
        db,
        file_id=module.module_book_id,
        missing_detail="This module has no module book attached.",
    )

