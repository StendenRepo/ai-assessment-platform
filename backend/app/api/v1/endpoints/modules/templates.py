"""Module API routes — templates."""
from .router import router
from .shared import *  # noqa: F403

from app.services import module_templates as template_service


@router.get(
    "/template/students",
    summary="Download student import template",
    response_class=StreamingResponse,
)
def download_student_template(
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    try:
        buf = template_service.build_student_import_template()
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="openpyxl is not installed on the server.",
        )

    audit_service.log_action(
        db,
        action="template.downloaded",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={"template_type": "student_import"},
        ip_address=None,
    )

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{template_service.student_import_filename()}"'
        },
    )


@router.get(
    "/template/rubric",
    summary="Download rubric scoring template",
    response_class=StreamingResponse,
)
def download_rubric_template(
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    try:
        buf = template_service.build_rubric_template()
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="openpyxl is not installed on the server.",
        )

    audit_service.log_action(
        db,
        action="template.downloaded",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={"template_type": "rubric"},
        ip_address=None,
    )

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{template_service.rubric_template_filename()}"'
        },
    )
