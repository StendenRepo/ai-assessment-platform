"""Module API routes — export."""
from .router import router
from .shared import *  # noqa: F403

from app.services import module_export_service as export_service


@router.get(
    "/{module_id}/export/grades",
    summary="Export student grades as Excel",
    response_class=StreamingResponse,
)
def export_grades_excel(
    module_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    """Return an .xlsx file with one row per student: name, student number,
    group, assessment status and final grade."""
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    grade_rows, _, _ = export_service.collect_grade_rows(db, module)

    try:
        buf = export_service.build_grades_workbook(module, grade_rows)
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="openpyxl is not installed on the server.",
        )

    audit_service.log_action(
        db,
        action="grades.exported",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "module_id": str(module.id),
            "module_name": module.name,
            "student_count": len(grade_rows),
        },
        ip_address=request.client.host if request.client else None,
    )

    filename = export_service.grades_export_filename(module)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{module_id}/export/archive",
    summary="Export a complete module archive (rubric, module book, evidence, assessments, grades)",
    response_class=StreamingResponse,
)
def export_module_archive(
    module_id: str,
    request: Request,
    format: str = "zip",
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    grade_rows, _, _ = export_service.collect_grade_rows(db, module)

    buf, filename, media_type = export_service.build_module_archive(db, module, format)

    audit_service.log_action(
        db,
        action="module.archive_exported",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "module_id": str(module.id),
            "module_name": module.name,
            "student_count": len(grade_rows),
            "format": format,
        },
        ip_address=request.client.host if request.client else None,
    )

    return StreamingResponse(
        buf,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
