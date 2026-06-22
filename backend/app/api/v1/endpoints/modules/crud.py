"""Module API routes — crud."""
from .router import router
from .shared import *  # noqa: F403

@router.get("", response_model=List[ModuleOut])
def list_modules(
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    modules = _visible_modules_query(db, current_teacher).order_by(Module.created_at.desc()).all()
    result = []
    for module in modules:
        project_count, student_count = _module_project_counts(db, module.id)
        result.append(_module_to_out(module, project_count, student_count, db))
    return result

@router.post("", response_model=ModuleOut, status_code=status.HTTP_201_CREATED)
def create_module(
    payload: ModuleCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = Module(
        teacher_id=current_teacher.id,
        name=payload.name,
        academic_year=payload.academic_year,
        deadline=payload.deadline,
    )
    db.add(module)
    db.commit()
    db.refresh(module)

    audit_service.log_action(
        db,
        action="module.created",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "module_id": str(module.id),
            "module_name": module.name,
            "academic_year": module.academic_year,
            "operation": "create",
            "where": "Modules",
            "route": "/api/v1/modules",
        },
        ip_address=request.client.host if request.client else None,
    )

    return _module_to_out(module, 0, 0, db)


@router.get("/{module_id}", response_model=ModuleOut)
def get_module(
    module_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    project_count, student_count = _module_project_counts(db, module.id)
    return _module_to_out(module, project_count, student_count, db)


@router.patch("/{module_id}", response_model=ModuleOut, summary="Rename a module")
def rename_module(
    module_id: str,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    """Update the name (and optionally academic_year) of a module."""
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    new_name = payload.get("name", "").strip()
    if not new_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="name must not be empty",
        )
    old_name = module.name
    old_academic_year = module.academic_year
    module.name = new_name
    if "academic_year" in payload:
        module.academic_year = payload["academic_year"]

    audit_service.log_action(
        db,
        action="module.updated",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "module_id": str(module.id),
            "old_name": old_name,
            "new_name": module.name,
            "old_academic_year": old_academic_year,
            "new_academic_year": module.academic_year,
        },
        ip_address=request.client.host if request.client else None,
        commit=False,
    )
    db.commit()
    db.refresh(module)
    project_count, student_count = _module_project_counts(db, module.id)
    return _module_to_out(module, project_count, student_count, db)


@router.delete("/{module_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a module")
def delete_module(
    module_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    """Permanently delete a module and all its groups. Students who belong only
    to this module (and no other) are also deleted along with their evidence."""
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    module_name = module.name
    deleted_module_id = str(module.id)

    ModuleService.delete_module(module, db)

    audit_service.log_action(
        db,
        action="module.deleted",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "module_id": deleted_module_id,
            "module_name": module_name,
            "operation": "delete",
            "where": "Modules",
            "route": "/api/v1/modules/{module_id}",
        },
        ip_address=request.client.host if request.client else None,
        commit=False,
    )

    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
