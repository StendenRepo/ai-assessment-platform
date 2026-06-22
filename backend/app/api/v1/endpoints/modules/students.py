"""Module API routes — students."""
from .router import router
from .shared import *  # noqa: F403
from app.services.module_roster_service import ModuleRosterService


@router.get("/{module_id}/students", response_model=List[StudentOut])
def list_module_students(
    module_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    listed = ModuleRosterService.list_students(module, db)
    return [
        _student_to_out(
            item.student,
            _assessment_status(item.latest_assessment),
            _assessment_grade(item.latest_assessment),
            project_id=item.project_id,
        )
        for item in listed
    ]


@router.post("/{module_id}/students", response_model=StudentOut, status_code=status.HTTP_201_CREATED)
def add_module_student(
    module_id: str,
    payload: StudentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    student, project = ModuleRosterService.add_student(module, payload, db)

    audit_service.log_action(
        db,
        action="student.created",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "module_id": str(module.id),
            "module_name": module.name,
            "student_id": student.student_number,
            "student_name": student.name,
            "group_id": str(project.id),
            "group_name": project.group_name or project.name,
            "github_repo_url": student.github_repo_url,
            "github_branch": student.github_branch,
            "operation": "create",
            "where": f"Modules > {module.name} > Students",
            "route": "/api/v1/modules/{module_id}/students",
        },
        ip_address=request.client.host if request.client else None,
    )

    return _student_to_out(student, project_id=str(project.id))


@router.patch("/{module_id}/students/{student_id}", response_model=StudentOut)
def move_student_to_group(
    module_id: str,
    student_id: str,
    payload: StudentGroupUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    result = ModuleRosterService.move_student(module, student_id, payload, db)

    audit_service.log_action(
        db,
        action="student.updated",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details=result.audit_details,
        ip_address=request.client.host if request.client else None,
        commit=False,
    )

    return _student_to_out(result.student, project_id=result.current_project_id)


@router.post("/{module_id}/students/import", response_model=StudentImportResult)
async def import_module_students(
    module_id: str,
    file: UploadFile = File(...),
    project_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    project = _resolve_group_for_module(db, module, project_id)

    contents = await file.read()
    try:
        rows = parse_student_file(file.filename, contents)
    except ImportParseError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    result = ModuleRosterService.import_students(module, project, rows, db)

    return StudentImportResult(
        imported_count=len(result.imported),
        error_count=len(result.errors),
        total_rows=result.total_rows,
        errors=result.errors,
        students=[_student_to_out(s, project_id=str(project.id)) for s in result.imported],
    )
