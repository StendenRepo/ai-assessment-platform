"""Module grade and archive export helpers."""
from __future__ import annotations

import csv
import io
import json
import tarfile
import zipfile
from datetime import date
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.assessment import Assessment
from app.models.evidence import Evidence
from app.models.file_record import FileRecord
from app.models.module import Module
from app.models.project import Project
from app.models.student import Student, student_projects
from app.services.module_service import MODULE_BOOK_UPLOAD_DIR, RUBRIC_UPLOAD_DIR

EVIDENCE_UPLOAD_DIR = Path(settings.UPLOAD_DIR) / "evidence"


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


def _build_student_project_map(db: Session, project_ids: list) -> dict:
    """Returns {student_id: project_id} for students in the given projects."""
    if not project_ids:
        return {}
    rows = db.execute(
        student_projects.select().where(student_projects.c.project_id.in_(project_ids))
    ).all()
    return {row.student_id: row.project_id for row in rows}


def collect_grade_rows(
    db: Session,
    module: Module,
) -> tuple[list, dict, dict]:
    """Return (grade_rows, student_project_map, project_name_by_id).

    grade_rows is a list of dicts with keys:
        student_number, name, group_name, grade, assessment_status
    """
    projects = db.query(Project).filter(Project.module_id == module.id).all()
    project_ids = [p.id for p in projects]
    project_name_by_id = {p.id: (p.group_name or p.name) for p in projects}

    students = (
        db.query(Student)
        .join(student_projects, Student.student_number == student_projects.c.student_id)
        .filter(student_projects.c.project_id.in_(project_ids))
        .order_by(Student.name)
        .all()
    ) if project_ids else []

    student_project_map = _build_student_project_map(db, project_ids) if project_ids else {}

    latest_assessment: dict = {}
    if students:
        for a in db.query(Assessment).filter(
            Assessment.student_id.in_([s.student_number for s in students])
        ).all():
            existing = latest_assessment.get(a.student_id)
            if existing is None or a.created_at > existing.created_at:
                latest_assessment[a.student_id] = a

    rows = []
    for student in students:
        assessment = latest_assessment.get(student.student_number)
        grade = _assessment_grade(assessment) or "—"
        ast_status = _assessment_status(assessment)
        group_pid = student_project_map.get(student.student_number)
        group_name = project_name_by_id.get(group_pid, "—") if group_pid else "—"
        rows.append({
            "student_number": student.student_number or "—",
            "name": student.name,
            "group_name": group_name,
            "grade": grade,
            "assessment_status": ast_status,
        })

    return rows, student_project_map, project_name_by_id


def grades_export_filename(module: Module) -> str:
    safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in module.name).strip("_")
    today = date.today().strftime("%Y-%m-%d")
    return f"{safe_name}_{today}.xlsx"


def build_grades_workbook(module: Module, grade_rows: list) -> io.BytesIO:
    try:
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError as exc:
        raise RuntimeError("openpyxl is not installed on the server.") from exc

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Grades"

    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    center = Alignment(horizontal="center", vertical="center")

    headers = ["Student Number", "Student Name", "Module", "Group", "Grade"]
    col_widths = [18, 30, 28, 24, 12]

    for col_idx, (header, width) in enumerate(zip(headers, col_widths), start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.row_dimensions[1].height = 22

    for row_idx, row in enumerate(grade_rows, start=2):
        row_data = [
            row["student_number"],
            row["name"],
            module.name,
            row["group_name"],
            row["grade"],
        ]

        row_fill = PatternFill(
            start_color="F8FAFC" if row_idx % 2 == 0 else "FFFFFF",
            end_color="F8FAFC" if row_idx % 2 == 0 else "FFFFFF",
            fill_type="solid",
        )

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
    return buf


def _module_project_ids(db: Session, module_id: str) -> list[str]:
    return [
        str(p.id)
        for p in db.query(Project).filter(Project.module_id == module_id).all()
    ]


def _students_in_projects(db: Session, project_ids: list) -> list[Student]:
    if not project_ids:
        return []
    return (
        db.query(Student)
        .join(student_projects, Student.student_number == student_projects.c.student_id)
        .filter(student_projects.c.project_id.in_(project_ids))
        .all()
    )


def _safe_archive_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in "_-. " else "_" for c in name).strip()


def build_module_archive(
    db: Session,
    module: Module,
    format: str,
) -> tuple[io.BytesIO, str, str]:
    """Return (buffer, filename, media_type) for a module archive export."""
    grade_rows, student_project_map, project_name_by_id = collect_grade_rows(db, module)

    project_ids = _module_project_ids(db, module.id)
    students = _students_in_projects(db, project_ids) if project_ids else []

    latest_assessment: dict = {}
    if students:
        for a in db.query(Assessment).filter(
            Assessment.student_id.in_([s.student_number for s in students])
        ).all():
            existing = latest_assessment.get(a.student_id)
            if existing is None or a.created_at > existing.created_at:
                latest_assessment[a.student_id] = a

    evidence_by_student: dict = {}
    if students:
        for ev in db.query(Evidence).filter(
            Evidence.student_id.in_([s.student_number for s in students])
        ).order_by(Evidence.uploaded_at.asc()).all():
            evidence_by_student.setdefault(ev.student_id, []).append(ev)

    today_str = date.today().strftime("%Y-%m-%d")
    buf = io.BytesIO()

    def _build_content() -> list[tuple[str, bytes]]:
        entries: list[tuple[str, bytes]] = []

        if module.rubric_file_id:
            rubric_rec = db.query(FileRecord).filter(FileRecord.id == module.rubric_file_id).first()
            if rubric_rec:
                rubric_path = RUBRIC_UPLOAD_DIR / str(module.id) / rubric_rec.path
                if rubric_path.exists():
                    entries.append((
                        f"rubric/{rubric_rec.file_name or rubric_rec.path}",
                        rubric_path.read_bytes(),
                    ))

        if module.module_book_id:
            book_rec = db.query(FileRecord).filter(FileRecord.id == module.module_book_id).first()
            if book_rec:
                book_path = MODULE_BOOK_UPLOAD_DIR / str(module.id) / book_rec.path
                if book_path.exists():
                    entries.append((
                        f"module_book/{book_rec.file_name or book_rec.path}",
                        book_path.read_bytes(),
                    ))

        for student in students:
            safe_name = _safe_archive_name(student.name) or student.student_number
            group_pid = student_project_map.get(student.student_number)
            raw_group = project_name_by_id.get(group_pid, "Unknown_Group") if group_pid else "Unknown_Group"
            safe_group = _safe_archive_name(raw_group) or "Unknown_Group"
            folder = f"groups/{safe_group}/students/{safe_name}_{student.student_number}"
            seen_ev: set[str] = set()
            for ev in evidence_by_student.get(student.student_number, []):
                full_path = EVIDENCE_UPLOAD_DIR / ev.file_path
                if not full_path.exists():
                    continue
                ev_safe = Path(ev.file_name).name or str(ev.id)
                arcname = f"{folder}/evidence/{ev_safe}"
                stem = Path(ev_safe).stem
                suffix = Path(ev_safe).suffix
                counter = 1
                while arcname in seen_ev:
                    arcname = f"{folder}/evidence/{stem}_{counter}{suffix}"
                    counter += 1
                seen_ev.add(arcname)
                entries.append((arcname, full_path.read_bytes()))

            assessment = latest_assessment.get(student.student_number)
            if assessment:
                form_data = assessment.final_form_json or assessment.draft_form_json
                if form_data:
                    if isinstance(form_data, str):
                        try:
                            form_data = json.loads(form_data)
                        except Exception:
                            pass
                    ast_lines = [
                        "=" * 60,
                        "ASSESSMENT SUMMARY",
                        "=" * 60,
                        f"Student        : {student.name}",
                        f"Student number : {student.student_number}",
                        f"Module         : {module.name}",
                        f"Status         : {assessment.status.value if assessment.status else '—'}",
                    ]
                    if assessment.created_at:
                        ast_lines.append(f"Created        : {assessment.created_at.strftime('%Y-%m-%d')}")
                    if assessment.completed_at:
                        ast_lines.append(f"Completed      : {assessment.completed_at.strftime('%Y-%m-%d')}")
                    ast_lines.append("")

                    if isinstance(form_data, dict):
                        grade = form_data.get("grade")
                        if grade is not None:
                            ast_lines.append(f"Grade          : {grade}")
                            ast_lines.append("")

                        feedback = form_data.get("feedback") or form_data.get("general_feedback")
                        if feedback:
                            ast_lines += ["FEEDBACK", "-" * 30, str(feedback), ""]

                        criteria = form_data.get("criteria") or form_data.get("scores") or form_data.get("rubric_scores")
                        if isinstance(criteria, dict):
                            ast_lines += ["CRITERIA SCORES", "-" * 30]
                            for key, val in criteria.items():
                                ast_lines.append(f"  {key}: {val}")
                            ast_lines.append("")
                        elif isinstance(criteria, list):
                            ast_lines += ["CRITERIA SCORES", "-" * 30]
                            for item in criteria:
                                if isinstance(item, dict):
                                    name_key = item.get("name") or item.get("criterion") or item.get("label", "")
                                    score_key = item.get("score") or item.get("value") or item.get("points", "")
                                    fb_key = item.get("feedback") or item.get("comment", "")
                                    line = f"  {name_key}: {score_key}"
                                    if fb_key:
                                        line += f" — {fb_key}"
                                    ast_lines.append(line)
                                else:
                                    ast_lines.append(f"  {item}")
                            ast_lines.append("")

                        shown = {"grade", "feedback", "general_feedback", "criteria", "scores", "rubric_scores"}
                        extras = {k: v for k, v in form_data.items() if k not in shown and v not in (None, "", [], {})}
                        if extras:
                            ast_lines += ["ADDITIONAL FIELDS", "-" * 30]
                            for k, v in extras.items():
                                ast_lines.append(f"  {k}: {v}")
                            ast_lines.append("")

                    ast_lines.append("=" * 60)
                    form_bytes = ("\n".join(ast_lines) + "\n").encode("utf-8")
                    entries.append((f"{folder}/assessment.txt", form_bytes))

        grades_buf = io.StringIO()
        writer = csv.writer(grades_buf, delimiter=";")
        writer.writerow(["Student Number", "Student Name", "Module", "Group", "Grade"])
        for row in grade_rows:
            writer.writerow([
                row["student_number"],
                row["name"],
                module.name,
                row["group_name"],
                row["grade"],
            ])
        entries.append(("grades.csv", grades_buf.getvalue().encode("utf-8-sig")))

        readme_lines = [
            "=" * 60,
            f"MODULE ARCHIVE: {module.name}",
            "=" * 60,
            f"Exported : {today_str}",
            f"Module   : {module.name}",
            f"Year     : {module.academic_year or '—'}",
            f"Students : {len(grade_rows)}",
            "",
            "CONTENTS",
            "-" * 30,
            "rubric/          — Original rubric file",
            "module_book/     — Original module book",
            "groups/          — Per-group folders, each containing per-student subfolders",
            "  <group>/students/<student>/evidence/  — Evidence files",
            "  <group>/students/<student>/assessment.json  — Assessment form",
            "grades.csv       — Grade list for all students",
            "",
            "=" * 60,
        ]
        entries.append(("README.txt", "\n".join(readme_lines).encode("utf-8")))
        return entries

    entries = _build_content()
    safe_module = _safe_archive_name(module.name) or str(module.id)

    if format == "tar":
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            for arcname, data in entries:
                ti = tarfile.TarInfo(name=arcname)
                ti.size = len(data)
                ti.mode = 0o444
                tf.addfile(ti, io.BytesIO(data))
        buf.seek(0)
        filename = f"archive_{safe_module}_{today_str}.tar.gz"
        media_type = "application/gzip"
    else:
        with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for arcname, data in entries:
                info = zipfile.ZipInfo(arcname)
                info.external_attr = 0o444 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(info, data)
        buf.seek(0)
        filename = f"archive_{safe_module}_{today_str}.zip"
        media_type = "application/zip"

    return buf, filename, media_type
