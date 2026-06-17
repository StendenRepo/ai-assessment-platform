import io
import json
import mimetypes
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher, get_db
from app.config import settings
from app.models.assessment import Assessment
from app.models.evidence import Evidence
from app.models.enums import AuditSource, ProjectStatus, StudentStatus
from app.models.file_record import FileRecord
from app.models.module import Module
from app.models.project import Project
from app.models.student import Student, student_projects
from app.models.teacher import Teacher
from app.schemas.module import (
    ModuleCreate,
    ModuleGroupCreate,
    ModuleGroupUpdate,
    ModuleOut,
    RubricFileOut,
    StudentGroupUpdate,
)
from app.schemas.overlap import OverlapAnalysisOut, OverlapSignalOut, OverlapWarningOut
from app.schemas.project import (
    ImportRowError,
    ProjectOut,
    StudentCreate,
    StudentImportResult,
    StudentOut,
)
from app.services import audit_service
from app.services.module_service import (
    MODULE_BOOK_UPLOAD_DIR,
    RUBRIC_UPLOAD_DIR,
    ModuleService,
    _module_file_path,
)
from app.services.overlap_service import OverlapService
from app.services.student_import import ImportParseError, parse_student_file

router = APIRouter()

_DUPLICATE_DETAIL = "A student with that student number already exists in this module"
_DEFAULT_GROUP_NAME = "Individual Students"


def _assessment_status(latest: Optional[Assessment]) -> str:
    if latest is None:
        return "not-started"
    if latest.status.value == "final":
        return "completed"
    return "in-progress"


def _assessment_grade(latest: Optional[Assessment]) -> Optional[str]:
    if latest is None:
        return None

    for payload in (latest.final_form_json, latest.draft_form_json):
        data = payload
        if isinstance(payload, str):
            try:
                data = json.loads(payload)
            except Exception:
                continue

        if isinstance(data, dict):
            raw_grade = data.get("grade")
            if raw_grade is None:
                continue
            grade = str(raw_grade).strip()
            if grade:
                return grade
    return None


def _student_to_out(
    s: Student,
    assessment_status: str = "not-started",
    grade: Optional[str] = None,
    project_id: Optional[str] = None,
) -> StudentOut:
    return StudentOut(
        id=s.student_number,
        name=s.name,
        student_number=s.student_number,
        github_repo_url=s.github_repo_url,
        github_branch=s.github_branch,
        status=s.status.value if s.status else "active",
        consent_given=bool(s.consent_given),
        assessment_status=assessment_status,
        grade=grade,
        project_id=project_id,
    )


def _group_to_out(p: Project, student_count: int, file_count: int = 0) -> ProjectOut:
    return ProjectOut(
        id=str(p.id),
        name=p.name,
        group_name=p.group_name,
        github_repo_url=p.github_repo_url,
        github_branch=p.github_branch,
        module_id=str(p.module_id),
        status=p.status.value if p.status else "active",
        created_at=p.created_at,
        student_count=student_count,
        file_count=file_count,
    )


def _rubric_file_out(record: Optional[FileRecord]) -> Optional[RubricFileOut]:
    if not record:
        return None
    return RubricFileOut(
        id=str(record.id),
        file_name=record.file_name,
        file_type=record.file_type,
        size_bytes=record.size_bytes,
        uploaded_at=record.uploaded_at,
    )


def _module_to_out(m: Module, project_count: int, student_count: int, db: Session) -> ModuleOut:
    rubric = None
    if m.rubric_file_id:
        rubric = db.query(FileRecord).filter(FileRecord.id == m.rubric_file_id).first()
    module_book = None
    if m.module_book_id:
        module_book = db.query(FileRecord).filter(FileRecord.id == m.module_book_id).first()
    return ModuleOut(
        id=str(m.id),
        name=m.name,
        academic_year=m.academic_year,
        deadline=m.deadline,
        status=m.status.value if m.status else "active",
        created_at=m.created_at,
        project_count=project_count,
        student_count=student_count,
        rubric_file=_rubric_file_out(rubric),
        module_book_file=_rubric_file_out(module_book),
    )


def _visible_modules_query(db: Session, teacher: Teacher):
    if teacher.is_admin:
        return db.query(Module)
    return db.query(Module).filter(Module.teacher_id == teacher.id)


def _get_visible_module_or_404(db: Session, module_id: str, teacher: Teacher) -> Module:
    module = _visible_modules_query(db, teacher).filter(Module.id == module_id).first()
    if not module:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")
    return module


def _module_project_ids(db: Session, module_id: str) -> list[str]:
    return [
        str(p.id)
        for p in db.query(Project).filter(Project.module_id == module_id).all()
    ]


def _module_project_counts(db: Session, module_id: str) -> tuple[int, int]:
    projects = db.query(Project).filter(Project.module_id == module_id).all()
    project_count = len(projects)
    student_count = sum(
        db.query(student_projects).filter(student_projects.c.project_id == p.id).count()
        for p in projects
    )
    return project_count, student_count


def _students_in_projects(db: Session, project_ids: list) -> List[Student]:
    if not project_ids:
        return []
    return (
        db.query(Student)
        .join(student_projects, Student.student_number == student_projects.c.student_id)
        .filter(student_projects.c.project_id.in_(project_ids))
        .all()
    )


def _build_student_project_map(db: Session, project_ids: list) -> dict:
    """Returns {student_id: project_id} for students in the given projects."""
    if not project_ids:
        return {}
    rows = db.execute(
        student_projects.select().where(student_projects.c.project_id.in_(project_ids))
    ).all()
    return {row.student_id: row.project_id for row in rows}


def _signal_to_out(signal, student_names: dict, evidence_names: dict) -> OverlapSignalOut:
    return OverlapSignalOut(
        id=str(signal.id),
        student_a_id=str(signal.student_a_id),
        student_a_name=student_names.get(signal.student_a_id, "Unknown student"),
        student_b_id=str(signal.student_b_id),
        student_b_name=student_names.get(signal.student_b_id, "Unknown student"),
        evidence_a_id=str(signal.evidence_a_id),
        evidence_a_name=evidence_names.get(signal.evidence_a_id, "Unknown evidence"),
        evidence_b_id=str(signal.evidence_b_id),
        evidence_b_name=evidence_names.get(signal.evidence_b_id, "Unknown evidence"),
        overlap_type=signal.overlap_type.value if signal.overlap_type else "textual",
        confidence=round(float(signal.confidence or 0.0), 2),
        snippet=signal.snippet,
        detected_at=signal.detected_at,
    )


def _module_signal_context(db: Session, module: Module):
    project_ids = [p.id for p in db.query(Project).filter(Project.module_id == module.id).all()]
    if not project_ids:
        return {}, {}

    students = _students_in_projects(db, project_ids)
    student_names = {s.student_number: s.name for s in students}
    student_ids = [s.student_number for s in students]
    evidence_names = {}
    if student_ids:
        for e in db.query(Evidence).filter(Evidence.student_id.in_(student_ids)).all():
            evidence_names[e.id] = e.file_name
    return student_names, evidence_names


def _get_or_create_default_group(db: Session, module: Module) -> Project:
    default_group = (
        db.query(Project)
        .filter(Project.module_id == module.id, Project.name == _DEFAULT_GROUP_NAME)
        .first()
    )
    if default_group:
        return default_group

    default_group = Project(
        module_id=module.id,
        name=_DEFAULT_GROUP_NAME,
        group_name=_DEFAULT_GROUP_NAME,
        status=ProjectStatus.active,
    )
    db.add(default_group)
    db.flush()
    return default_group


def _resolve_group_for_module(
    db: Session,
    module: Module,
    project_id: Optional[str],
) -> Project:
    if project_id:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project or project.module_id != module.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
        return project
    return _get_or_create_default_group(db, module)


def _student_duplicate_in_module(db: Session, project_ids: list[str], student_number: str) -> bool:
    if not project_ids:
        return False
    return (
        db.query(Student)
        .join(student_projects, Student.student_number == student_projects.c.student_id)
        .filter(
            student_projects.c.project_id.in_(project_ids),
            Student.student_number == student_number,
        )
        .first()
    ) is not None


# ---------------------------------------------------------------------------
# Modules
# ---------------------------------------------------------------------------


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
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="openpyxl is not installed on the server.",
        )

    # Build workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Students"

    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    center = Alignment(horizontal="center", vertical="center")
    left = Alignment(horizontal="left", vertical="center")

    # Columns: Name | Student Number
    headers = ["Name", "Student Number"]
    col_widths = [30, 18]

    for col_idx, (header, width) in enumerate(zip(headers, col_widths), start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.row_dimensions[1].height = 22

    # Add example rows
    example_rows = [
        ["Alice Smith", "1001"],
        ["Bob Johnson", "1002"],
        ["Charlie Brown", "1003"],
    ]

    for row_idx, row_data in enumerate(example_rows, start=2):
        row_fill = PatternFill(
            start_color="F8FAFC" if row_idx % 2 == 0 else "FFFFFF",
            end_color="F8FAFC" if row_idx % 2 == 0 else "FFFFFF",
            fill_type="solid",
        )
        
        for col_idx, value in enumerate(row_data, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.fill = row_fill
            cell.alignment = center if col_idx == 2 else left
        
        ws.row_dimensions[row_idx].height = 18

    # Add a few more empty rows for user input
    for row_idx in range(5, 25):
        row_fill = PatternFill(
            start_color="F8FAFC" if row_idx % 2 == 0 else "FFFFFF",
            end_color="F8FAFC" if row_idx % 2 == 0 else "FFFFFF",
            fill_type="solid",
        )
        for col_idx in range(1, 3):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.fill = row_fill
            cell.alignment = center if col_idx == 2 else left
        
        ws.row_dimensions[row_idx].height = 18

    ws.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    audit_service.log_action(
        db,
        action="template.downloaded",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "template_type": "student_import",
        },
        ip_address=None,
    )

    from datetime import date
    today = date.today().strftime("%Y-%m-%d")
    filename = f"student_import_template_{today}.xlsx"

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="openpyxl is not installed on the server.",
        )

    # Build workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Rubric"

    # Define styles
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left = Alignment(horizontal="left", vertical="top", wrap_text=True)
    
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    # Title
    ws.merge_cells('A1:F1')
    title_cell = ws['A1']
    title_cell.value = "Scoring Rubric Template"
    title_cell.font = Font(bold=True, size=14, color="FFFFFF")
    title_cell.fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    title_cell.alignment = center
    ws.row_dimensions[1].height = 25

    # Instructions
    ws.merge_cells('A2:F2')
    instr_cell = ws['A2']
    instr_cell.value = "Fill in your assessment criteria and define proficiency levels. You can add more criteria rows as needed."
    instr_cell.font = Font(italic=True, size=9, color="64748B")
    instr_cell.alignment = left
    ws.row_dimensions[2].height = 18

    # Column headers (row 3)
    headers = ["Criteria", "Excellent (4)", "Good (3)", "Fair (2)", "Poor (1)", "Max Points"]
    col_widths = [20, 15, 15, 15, 15, 12]

    for col_idx, (header, width) in enumerate(zip(headers, col_widths), start=1):
        cell = ws.cell(row=3, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center
        cell.border = thin_border
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.row_dimensions[3].height = 20

    # Example criteria rows
    example_data = [
        ["Content Accuracy", "All facts accurate and well-researched", "Most facts accurate", "Some inaccuracies present", "Multiple errors", 4],
        ["Organization", "Clear structure with logical flow", "Generally well-organized", "Somewhat disorganized", "Confusing structure", 4],
        ["Clarity", "Very clear and easy to understand", "Mostly clear communication", "Some unclear sections", "Difficult to understand", 3],
    ]

    for row_idx, row_data in enumerate(example_data, start=4):
        row_fill = PatternFill(
            start_color="F8FAFC" if row_idx % 2 == 0 else "FFFFFF",
            end_color="F8FAFC" if row_idx % 2 == 0 else "FFFFFF",
            fill_type="solid",
        )
        
        for col_idx, value in enumerate(row_data, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.fill = row_fill
            cell.alignment = center if col_idx > 1 else left
            cell.border = thin_border
        
        ws.row_dimensions[row_idx].height = 35

    # Add empty rows for user input (rows 7-15)
    for row_idx in range(7, 16):
        row_fill = PatternFill(
            start_color="F8FAFC" if row_idx % 2 == 0 else "FFFFFF",
            end_color="F8FAFC" if row_idx % 2 == 0 else "FFFFFF",
            fill_type="solid",
        )
        for col_idx in range(1, 7):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.fill = row_fill
            cell.alignment = center if col_idx > 1 else left
            cell.border = thin_border
        
        ws.row_dimensions[row_idx].height = 35

    # Summary section (row 17)
    ws.row_dimensions[17].height = 2  # Empty row

    ws.merge_cells('A18:F18')
    summary_header = ws['A18']
    summary_header.value = "Scoring Summary"
    summary_header.font = Font(bold=True, size=11, color="FFFFFF")
    summary_header.fill = PatternFill(start_color="64748B", end_color="64748B", fill_type="solid")
    summary_header.alignment = center
    summary_header.border = thin_border
    ws.row_dimensions[18].height = 18

    # Total points row
    ws.merge_cells('A19:E19')
    total_label = ws['A19']
    total_label.value = "Total Points Possible"
    total_label.font = Font(bold=True, size=10)
    total_label.alignment = Alignment(horizontal="right", vertical="center")
    total_label.border = thin_border
    
    total_cell = ws['F19']
    total_cell.value = "=SUM(F4:F15)"  # Sum of max points
    total_cell.font = Font(bold=True, size=10, color="FFFFFF")
    total_cell.fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    total_cell.alignment = center
    total_cell.border = thin_border
    ws.row_dimensions[19].height = 18

    # Freeze panes
    ws.freeze_panes = "A4"

    # Save to buffer
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    audit_service.log_action(
        db,
        action="template.downloaded",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "template_type": "rubric",
        },
        ip_address=None,
    )

    from datetime import date
    today = date.today().strftime("%Y-%m-%d")
    filename = f"rubric_template_{today}.xlsx"

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
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
    from pathlib import Path
    from app.services.module_service import RUBRIC_UPLOAD_DIR

    EVIDENCE_UPLOAD_DIR = Path(settings.UPLOAD_DIR) / "evidence"
    EVIDENCE_TEXT_DIR = Path(settings.UPLOAD_DIR) / "evidence_text"

    module = _get_visible_module_or_404(db, module_id, current_teacher)
    module_name = module.name  # Capture name before deletion
    project_ids = _module_project_ids(db, module.id)

    # Collect student_ids enrolled in this module
    student_ids = [
        row.student_id
        for row in db.execute(
            student_projects.select().where(student_projects.c.project_id.in_(project_ids))
        ).all()
    ] if project_ids else []

    # Remove student_projects associations for this module's projects
    if project_ids:
        db.execute(
            student_projects.delete().where(
                student_projects.c.project_id.in_(project_ids)
            )
        )

    # Find students who are now orphaned (no remaining project associations)
    orphaned_ids = [
        sid for sid in student_ids
        if not db.execute(
            student_projects.select().where(student_projects.c.student_id == sid)
        ).first()
    ]

    # Delete evidence files on disk and DB records for orphaned students and shared project evidence.
    evidence_records = (
        db.query(Evidence).filter(Evidence.student_id.in_(orphaned_ids)).all()
        if orphaned_ids
        else []
    )
    shared_evidence_records = (
        db.query(Evidence).filter(Evidence.project_id.in_(project_ids)).all()
        if project_ids
        else []
    )
    for ev in evidence_records + shared_evidence_records:
        try:
            file_path = EVIDENCE_UPLOAD_DIR / ev.file_path
            text_path = EVIDENCE_TEXT_DIR / f"{ev.file_path}.txt"
            if file_path.exists():
                file_path.unlink()
            if text_path.exists():
                text_path.unlink()
        except OSError:
            pass
    if orphaned_ids:
        db.query(Evidence).filter(Evidence.student_id.in_(orphaned_ids)).delete(
            synchronize_session=False
        )
        db.query(Student).filter(Student.student_number.in_(orphaned_ids)).delete(
            synchronize_session=False
        )
    if project_ids:
        db.query(Evidence).filter(Evidence.project_id.in_(project_ids)).delete(
            synchronize_session=False
        )

    # Delete rubric file on disk
    if module.rubric_file_id:
        rubric_record = db.query(FileRecord).filter(FileRecord.id == module.rubric_file_id).first()
        if rubric_record:
            try:
                rubric_path = RUBRIC_UPLOAD_DIR / str(module.id) / rubric_record.path
                if rubric_path.exists():
                    rubric_path.unlink()
                rubric_dir = RUBRIC_UPLOAD_DIR / str(module.id)
                if rubric_dir.exists() and not any(rubric_dir.iterdir()):
                    rubric_dir.rmdir()
            except OSError:
                pass

    deleted_module_id = str(module.id)
    db.query(Project).filter(Project.module_id == module.id).delete(synchronize_session=False)
    db.delete(module)

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


# ---------------------------------------------------------------------------
# Groups inside a module
# ---------------------------------------------------------------------------


@router.get("/{module_id}/groups", response_model=List[ProjectOut])
def list_module_groups(
    module_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    projects = (
        db.query(Project)
        .filter(Project.module_id == module.id)
        .order_by(Project.created_at.desc())
        .all()
    )
    if not projects:
        return []

    project_ids = [p.id for p in projects]
    student_project_map = _build_student_project_map(db, project_ids)

    # Group student counts by project
    student_count_by_project: dict = {}
    for project_id in student_project_map.values():
        student_count_by_project[project_id] = student_count_by_project.get(project_id, 0) + 1

    # Count evidence files per project via student membership and shared project evidence.
    student_ids_by_project: dict = {}
    for sid, pid in student_project_map.items():
        student_ids_by_project.setdefault(pid, []).append(sid)

    all_student_ids = list(student_project_map.keys())
    file_counts: dict = {}
    if all_student_ids:
        for sid, cnt in db.query(Evidence.student_id, func.count(Evidence.id)).filter(
            Evidence.student_id.in_(all_student_ids)
        ).group_by(Evidence.student_id).all():
            pid = student_project_map.get(sid)
            if pid is not None:
                file_counts[pid] = file_counts.get(pid, 0) + cnt

    for pid, cnt in db.query(Evidence.project_id, func.count(Evidence.id)).filter(
        Evidence.project_id.in_(project_ids)
    ).group_by(Evidence.project_id).all():
        file_counts[pid] = file_counts.get(pid, 0) + cnt

    return [
        _group_to_out(
            project,
            student_count_by_project.get(project.id, 0),
            file_counts.get(project.id, 0),
        )
        for project in projects
    ]


@router.post("/{module_id}/groups", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_module_group(
    module_id: str,
    payload: ModuleGroupCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    project = Project(
        module_id=module.id,
        name=payload.name,
        group_name=payload.group_name or payload.name,
        github_repo_url=payload.github_repo_url,
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    audit_service.log_action(
        db,
        action="group.created",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "module_id": str(module.id),
            "module_name": module.name,
            "group_id": str(project.id),
            "group_name": project.group_name or project.name,
            "project_name": project.name,
            "github_repo_url": project.github_repo_url,
            "github_branch": project.github_branch,
            "operation": "create",
            "where": f"Modules > {module.name} > Groups",
            "route": "/api/v1/modules/{module_id}/groups",
        },
        ip_address=request.client.host if request.client else None,
    )

    return _group_to_out(project, 0)


@router.patch("/{module_id}/groups/{group_id}", response_model=ProjectOut)
def update_module_group(
    module_id: str,
    group_id: str,
    payload: ModuleGroupUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    group = (
        db.query(Project)
        .filter(Project.id == group_id, Project.module_id == module.id)
        .first()
    )
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    updates = payload.model_fields_set
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No group updates provided")

    old_name = group.name
    old_group_name = group.group_name
    old_github_repo_url = group.github_repo_url
    old_github_branch = group.github_branch

    if payload.name is not None:
        group.name = payload.name
    if payload.group_name is not None:
        group.group_name = payload.group_name
    if "github_repo_url" in updates:
        group.github_repo_url = payload.github_repo_url

        # Keep student-level repo references in sync whenever a group repo changes.
        student_ids = [
            row.student_id
            for row in db.execute(
                student_projects.select().where(student_projects.c.project_id == group.id)
            ).all()
        ]
        if student_ids:
            for student in db.query(Student).filter(Student.student_number.in_(student_ids)).all():
                student.github_repo_url = payload.github_repo_url

    if "github_branch" in updates:
        group.github_branch = payload.github_branch

        # Sync branch to all students in this group.
        student_ids = [
            row.student_id
            for row in db.execute(
                student_projects.select().where(student_projects.c.project_id == group.id)
            ).all()
        ]
        if student_ids:
            for student in db.query(Student).filter(Student.student_number.in_(student_ids)).all():
                student.github_branch = payload.github_branch

    repo_removed = old_github_repo_url is not None and group.github_repo_url is None
    repo_added = old_github_repo_url is None and group.github_repo_url is not None
    audit_service.log_action(
        db,
        action="group.updated",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "module_id": str(module.id),
            "group_id": str(group.id),
            "old_name": old_name,
            "new_name": group.name,
            "old_group_name": old_group_name,
            "new_group_name": group.group_name,
            "old_github_repo_url": old_github_repo_url,
            "new_github_repo_url": group.github_repo_url,
            "repo_removed": repo_removed,
            "repo_added": repo_added,
            "old_github_branch": old_github_branch,
            "new_github_branch": group.github_branch,
            "branch_changed": old_github_branch != group.github_branch and not repo_removed and not repo_added,
        },
        ip_address=request.client.host if request.client else None,
        commit=False,
    )

    db.commit()
    db.refresh(group)

    student_count = db.query(student_projects).filter(
        student_projects.c.project_id == group.id
    ).count()
    student_ids = [
        row.student_id
        for row in db.execute(
            student_projects.select().where(student_projects.c.project_id == group.id)
        ).all()
    ]
    file_count = 0
    if student_ids:
        file_count = (
            db.query(func.count(Evidence.id))
            .filter(Evidence.student_id.in_(student_ids))
            .scalar()
            or 0
        )
    return _group_to_out(group, student_count, file_count)


@router.delete("/{module_id}/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_module_group(
    module_id: str,
    group_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    from pathlib import Path

    EVIDENCE_UPLOAD_DIR = Path(settings.UPLOAD_DIR) / "evidence"
    EVIDENCE_TEXT_DIR = Path(settings.UPLOAD_DIR) / "evidence_text"

    module = _get_visible_module_or_404(db, module_id, current_teacher)
    group = (
        db.query(Project)
        .filter(Project.id == group_id, Project.module_id == module.id)
        .first()
    )
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    group_name = group.group_name or group.name  # Capture before deletion

    if group.name == _DEFAULT_GROUP_NAME:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Default group cannot be deleted",
        )

    default_group = _get_or_create_default_group(db, module)

    project_evidence_records = db.query(Evidence).filter(Evidence.project_id == group.id).all()
    for ev in project_evidence_records:
        try:
            file_path = EVIDENCE_UPLOAD_DIR / ev.file_path
            text_path = EVIDENCE_TEXT_DIR / f"{ev.file_path}.txt"
            if file_path.exists():
                file_path.unlink()
            if text_path.exists():
                text_path.unlink()
        except OSError:
            pass
    if project_evidence_records:
        db.query(Evidence).filter(Evidence.project_id == group.id).delete(
            synchronize_session=False
        )

    # Move all students from deleted group to default group
    student_ids_in_group = [
        row.student_id
        for row in db.execute(
            student_projects.select().where(student_projects.c.project_id == group.id)
        ).all()
    ]
    if student_ids_in_group:
        # Remove existing associations with the deleted group
        db.execute(
            student_projects.delete().where(
                student_projects.c.project_id == group.id
            )
        )
        # Add associations to the default group (skip if already there)
        already_in_default = {
            row.student_id
            for row in db.execute(
                student_projects.select().where(student_projects.c.project_id == default_group.id)
            ).all()
        }
        for sid in student_ids_in_group:
            if sid not in already_in_default:
                db.execute(
                    student_projects.insert().values(student_id=sid, project_id=default_group.id)
                )

        # Preserve group-level repo consistency after moving members.
        for student in db.query(Student).filter(Student.student_number.in_(student_ids_in_group)).all():
            student.github_repo_url = default_group.github_repo_url
            student.github_branch = default_group.github_branch

    db.delete(group)
    db.commit()

    audit_service.log_action(
        db,
        action="group.deleted",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "module_id": str(module.id),
            "module_name": module.name,
            "group_id": str(group.id),
            "group_name": group_name,
            "github_repo_url": group.github_repo_url,
            "github_branch": group.github_branch,
            "operation": "delete",
            "where": f"Modules > {module.name} > Groups",
            "route": "/api/v1/modules/{module_id}/groups/{group_id}",
        },
        ip_address=request.client.host if request.client else None,
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Students within a module
# ---------------------------------------------------------------------------


@router.get("/{module_id}/students", response_model=List[StudentOut])
def list_module_students(
    module_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    project_ids = _module_project_ids(db, module.id)
    students = (
        db.query(Student)
        .join(student_projects, Student.student_number == student_projects.c.student_id)
        .filter(student_projects.c.project_id.in_(project_ids))
        .order_by(Student.name)
        .all()
    ) if project_ids else []

    student_project_map = _build_student_project_map(db, project_ids)

    latest_assessment: dict = {}
    if students:
        for a in db.query(Assessment).filter(
            Assessment.student_id.in_([s.student_number for s in students])
        ).all():
            existing = latest_assessment.get(a.student_id)
            if existing is None or a.created_at > existing.created_at:
                latest_assessment[a.student_id] = a
    return [
        _student_to_out(
            s,
            _assessment_status(latest_assessment.get(s.student_number)),
            _assessment_grade(latest_assessment.get(s.student_number)),
            project_id=str(student_project_map[s.student_number]) if s.student_number in student_project_map else None,
        )
        for s in students
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
    project = _resolve_group_for_module(db, module, payload.project_id)

    if (
        payload.github_repo_url
        and project.github_repo_url
        and payload.github_repo_url != project.github_repo_url
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This group already has a GitHub repository. Use the group repository instead.",
        )

    if _student_duplicate_in_module(db, _module_project_ids(db, module.id), payload.student_number):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_DUPLICATE_DETAIL)

    # Reuse existing student record if one with this number already exists
    student = db.query(Student).filter(Student.student_number == payload.student_number).first()
    if student is None:
        student = Student(name=payload.name, student_number=payload.student_number)
        db.add(student)
        db.flush()

    if payload.github_repo_url:
        student.github_repo_url = payload.github_repo_url
    elif project.github_repo_url:
        student.github_repo_url = project.github_repo_url

    if payload.github_branch:
        student.github_branch = payload.github_branch
    elif project.github_branch:
        student.github_branch = project.github_branch

    student.projects.append(project)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_DUPLICATE_DETAIL)
    db.refresh(student)

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
    project_ids = _module_project_ids(db, module.id)

    student = (
        db.query(Student)
        .join(student_projects, Student.student_number == student_projects.c.student_id)
        .filter(
            Student.student_number == student_id,
            student_projects.c.project_id.in_(project_ids),
        )
        .first()
    )
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found in this module")

    if (
        payload.project_id is None
        and payload.name is None
        and payload.student_number is None
        and payload.status is None
        and "github_repo_url" not in payload.model_fields_set
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No student updates provided")

    original_name = student.name
    original_number = student.student_number
    old_github_repo_url = student.github_repo_url
    old_github_branch = student.github_branch
    current_group_row = db.execute(
        student_projects.select().where(
            student_projects.c.student_id == student.student_number,
            student_projects.c.project_id.in_(project_ids),
        )
    ).first()
    old_project_id = str(current_group_row.project_id) if current_group_row else None
    target = None

    if payload.project_id is not None:
        target = (
            db.query(Project)
            .filter(Project.id == payload.project_id, Project.module_id == module.id)
            .first()
        )
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found in this module")

        # Move student from current group(s) in this module to the target group
        db.execute(
            student_projects.delete().where(
                student_projects.c.student_id == student.student_number,
                student_projects.c.project_id.in_(project_ids),
            )
        )
        db.execute(
            student_projects.insert().values(student_id=student.student_number, project_id=target.id)
        )

        if target.github_repo_url is not None:
            requested_repo = payload.github_repo_url if "github_repo_url" in payload.model_fields_set else None
            if requested_repo is not None and requested_repo != target.github_repo_url:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This group already has a GitHub repository. Use the group repository instead.",
                )
            student.github_repo_url = target.github_repo_url
            if target.github_branch is not None:
                student.github_branch = target.github_branch

    if payload.name is not None:
        student.name = payload.name

    if payload.student_number is not None:
        if _student_duplicate_in_module(db, project_ids, payload.student_number):
            existing = (
                db.query(Student)
                .join(student_projects, Student.student_number == student_projects.c.student_id)
                .filter(
                    student_projects.c.project_id.in_(project_ids),
                    Student.student_number == payload.student_number,
                    Student.student_number != student.student_number,
                )

                .first()
            )
            if existing:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_DUPLICATE_DETAIL)
        student.student_number = payload.student_number

    if payload.status is not None:
        student.status = StudentStatus(payload.status)

    if "github_repo_url" in payload.model_fields_set:
        if target and target.github_repo_url is not None:
            student.github_repo_url = target.github_repo_url
        else:
            student.github_repo_url = payload.github_repo_url

    if "github_branch" in payload.model_fields_set:
        if target and target.github_branch is not None:
            student.github_branch = target.github_branch
        else:
            student.github_branch = payload.github_branch

    new_project_id = str(target.id) if target is not None else old_project_id
    old_group = (
        db.query(Project).filter(Project.id == old_project_id).first()
        if old_project_id
        else None
    )
    student_repo_removed = old_github_repo_url is not None and student.github_repo_url is None
    student_repo_added = old_github_repo_url is None and student.github_repo_url is not None
    audit_service.log_action(
        db,
        action="student.updated",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "module_id": str(module.id),
            "module_name": module.name,
            "student_id": original_number,
            "student_name": original_name if original_name == student.name else f"{original_name} → {student.name}",
            "old_group_name": old_group.group_name or old_group.name if old_group else None,
            "new_group_name": target.group_name or target.name if target else None,
            "old_student_number": original_number,
            "new_student_number": student.student_number,
            "old_project_id": old_project_id,
            "new_project_id": new_project_id,
            "new_status": student.status.value if student.status else None,
            "old_github_repo_url": old_github_repo_url,
            "new_github_repo_url": student.github_repo_url,
            "repo_removed": student_repo_removed,
            "repo_added": student_repo_added,
            "old_github_branch": old_github_branch,
            "new_github_branch": student.github_branch,
            "branch_changed": old_github_branch != student.github_branch and not student_repo_removed and not student_repo_added,
        },
        ip_address=request.client.host if request.client else None,
        commit=False,
    )

    db.commit()
    db.refresh(student)
    # Resolve the student's current group within this module for the response
    current_project_id = None
    if payload.project_id is not None:
        current_project_id = str(target.id)
    else:
        row = db.execute(
            student_projects.select().where(
                student_projects.c.student_id == student.student_number,
                student_projects.c.project_id.in_(project_ids),
            )
        ).first()
        if row:
            current_project_id = str(row.project_id)
    return _student_to_out(student, project_id=current_project_id)


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

    module_project_ids = _module_project_ids(db, module.id)
    existing_numbers = {
        s.student_number
        for s in (
            db.query(Student)
            .join(student_projects, Student.student_number == student_projects.c.student_id)
            .filter(student_projects.c.project_id.in_(module_project_ids))
            .all()
        )
        if s.student_number
    }

    seen: set[str] = set()
    errors: List[ImportRowError] = []
    to_add: List[Student] = []

    for row in rows:
        name = row.name.strip()
        number = row.student_number.strip()

        if not name:
            errors.append(ImportRowError(row=row.row_number, student_number=number or None, message="Missing name"))
            continue
        if not number:
            errors.append(ImportRowError(row=row.row_number, message="Missing student number"))
            continue
        if not number.isdigit():
            errors.append(ImportRowError(row=row.row_number, student_number=number, message="Student number must contain digits only"))
            continue
        if number in seen:
            errors.append(ImportRowError(row=row.row_number, student_number=number, message="Duplicate student number in file"))
            continue
        if number in existing_numbers:
            errors.append(ImportRowError(row=row.row_number, student_number=number, message="Student number already exists in this module"))
            continue

        seen.add(number)
        student = db.query(Student).filter(Student.student_number == number).first()
        if student is None:
            student = Student(name=name, student_number=number)
            db.add(student)
            db.flush()
        if project.github_repo_url:
            student.github_repo_url = project.github_repo_url
        if project.github_branch:
            student.github_branch = project.github_branch
        student.projects.append(project)
        to_add.append(student)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Import conflicted with a concurrent change. Please try again.",
        )

    for s in to_add:
        db.refresh(s)

    return StudentImportResult(
        imported_count=len(to_add),
        error_count=len(errors),
        total_rows=len(rows),
        errors=errors,
        students=[_student_to_out(s, project_id=str(project.id)) for s in to_add],
    )


# ---------------------------------------------------------------------------
# Overlap detection
# ---------------------------------------------------------------------------


@router.get("/{module_id}/overlap/signals", response_model=List[OverlapSignalOut])
def list_module_overlap_signals(
    module_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    signals = OverlapService.get_module_signals(db, str(module.id))
    student_names, evidence_names = _module_signal_context(db, module)
    return [_signal_to_out(signal, student_names, evidence_names) for signal in signals]


@router.post("/{module_id}/overlap/analyze", response_model=OverlapAnalysisOut)
def analyze_module_overlap(
    module_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    generated = OverlapService.analyze_module_overlap(db, str(module.id))
    warning_data = OverlapService.build_warning(generated)
    student_names, evidence_names = _module_signal_context(db, module)

    audit_service.log_action(
        db,
        action="overlap.analyzed",
        source=AuditSource.ai,
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "module_id": str(module.id),
            "signal_count": len(generated),
            "high_risk_count": warning_data.get("high_risk_count", 0),
            "has_overlap": warning_data.get("has_overlap", False),
        },
        ip_address=request.client.host if request.client else None,
    )

    return OverlapAnalysisOut(
        module_id=str(module.id),
        generated_count=len(generated),
        warning=OverlapWarningOut(**warning_data),
        signals=[_signal_to_out(signal, student_names, evidence_names) for signal in generated],
    )


@router.get("/{module_id}/overlap/warning", response_model=OverlapWarningOut)
def get_module_overlap_warning(
    module_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    signals = OverlapService.get_module_signals(db, str(module.id))
    warning_data = OverlapService.build_warning(signals)
    return OverlapWarningOut(**warning_data)


# ---------------------------------------------------------------------------
# Excel grade export
# ---------------------------------------------------------------------------


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
    try:
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="openpyxl is not installed on the server.",
        )

    module = _get_visible_module_or_404(db, module_id, current_teacher)

    projects = db.query(Project).filter(Project.module_id == module.id).all()
    project_ids = [p.id for p in projects]
    project_name_by_id = {p.id: p.name for p in projects}

    students = (
        db.query(Student)
        .join(student_projects, Student.student_number == student_projects.c.student_id)
        .filter(student_projects.c.project_id.in_(project_ids))
        .order_by(Student.name)
        .all()
    ) if project_ids else []

    student_project_map = _build_student_project_map(db, project_ids)

    latest_assessment: dict = {}
    if students:
        for a in db.query(Assessment).filter(
            Assessment.student_id.in_([s.student_number for s in students])
        ).all():
            existing = latest_assessment.get(a.student_id)
            if existing is None or a.created_at > existing.created_at:
                latest_assessment[a.student_id] = a

    # Build workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Grades"

    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    center = Alignment(horizontal="center", vertical="center")

    # Columns: Student Number | Student Name | Module | Group | Grade
    headers = ["Student Number", "Student Name", "Module", "Group", "Grade"]
    col_widths = [18, 30, 28, 24, 12]

    for col_idx, (header, width) in enumerate(zip(headers, col_widths), start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.row_dimensions[1].height = 22

    for row_idx, student in enumerate(students, start=2):
        assessment = latest_assessment.get(student.student_number)
        grade = _assessment_grade(assessment) or "—"
        group_pid = student_project_map.get(student.student_number)
        group_name = project_name_by_id.get(group_pid, "—") if group_pid else "—"

        row_data = [
            student.student_number or "—",
            student.name,
            module.name,
            group_name,
            grade,
        ]

        row_fill = PatternFill(
            start_color="F8FAFC" if row_idx % 2 == 0 else "FFFFFF",
            end_color="F8FAFC" if row_idx % 2 == 0 else "FFFFFF",
            fill_type="solid",
        )

        # Centered: Student Number (1), Grade (5) — left-aligned: Name (2), Module (3), Group (4)
        for col_idx, value in enumerate(row_data, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.fill = row_fill
            cell.alignment = Alignment(
                horizontal="center" if col_idx in (1, 5) else "left",
                vertical="center",
            )

        ws.row_dimensions[row_idx].height = 18

    ws.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    audit_service.log_action(
        db,
        action="grades.exported",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "module_id": str(module.id),
            "module_name": module.name,
            "student_count": len(students),
        },
        ip_address=request.client.host if request.client else None,
    )

    from datetime import date
    safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in module.name).strip("_")
    today = date.today().strftime("%Y-%m-%d")
    filename = f"{safe_name}_{today}.xlsx"

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
