"""Excel template builders for module imports and rubrics."""
from __future__ import annotations

import io
from datetime import date


def student_import_filename() -> str:
    today = date.today().strftime("%Y-%m-%d")
    return f"student_import_template_{today}.xlsx"


def rubric_template_filename() -> str:
    today = date.today().strftime("%Y-%m-%d")
    return f"rubric_template_{today}.xlsx"


def build_student_import_template() -> io.BytesIO:
    try:
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError as exc:
        raise RuntimeError("openpyxl is not installed on the server.") from exc

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Students"

    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    center = Alignment(horizontal="center", vertical="center")
    left = Alignment(horizontal="left", vertical="center")

    headers = ["Name", "Student Number"]
    col_widths = [30, 18]

    for col_idx, (header, width) in enumerate(zip(headers, col_widths), start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.row_dimensions[1].height = 22

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
    return buf


def build_rubric_template() -> io.BytesIO:
    try:
        import openpyxl
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter
    except ImportError as exc:
        raise RuntimeError("openpyxl is not installed on the server.") from exc

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Rubric"

    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)

    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left = Alignment(horizontal="left", vertical="top", wrap_text=True)

    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    ws.merge_cells("A1:F1")
    title_cell = ws["A1"]
    title_cell.value = "Scoring Rubric Template"
    title_cell.font = Font(bold=True, size=14, color="FFFFFF")
    title_cell.fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    title_cell.alignment = center
    ws.row_dimensions[1].height = 25

    ws.merge_cells("A2:F2")
    instr_cell = ws["A2"]
    instr_cell.value = (
        "Fill in your assessment criteria and define proficiency levels. "
        "You can add more criteria rows as needed."
    )
    instr_cell.font = Font(italic=True, size=9, color="64748B")
    instr_cell.alignment = left
    ws.row_dimensions[2].height = 18

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

    example_data = [
        [
            "Content Accuracy",
            "All facts accurate and well-researched",
            "Most facts accurate",
            "Some inaccuracies present",
            "Multiple errors",
            4,
        ],
        [
            "Organization",
            "Clear structure with logical flow",
            "Generally well-organized",
            "Somewhat disorganized",
            "Confusing structure",
            4,
        ],
        [
            "Clarity",
            "Very clear and easy to understand",
            "Mostly clear communication",
            "Some unclear sections",
            "Difficult to understand",
            3,
        ],
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

    ws.row_dimensions[17].height = 2

    ws.merge_cells("A18:F18")
    summary_header = ws["A18"]
    summary_header.value = "Scoring Summary"
    summary_header.font = Font(bold=True, size=11, color="FFFFFF")
    summary_header.fill = PatternFill(start_color="64748B", end_color="64748B", fill_type="solid")
    summary_header.alignment = center
    summary_header.border = thin_border
    ws.row_dimensions[18].height = 18

    ws.merge_cells("A19:E19")
    total_label = ws["A19"]
    total_label.value = "Total Points Possible"
    total_label.font = Font(bold=True, size=10)
    total_label.alignment = Alignment(horizontal="right", vertical="center")
    total_label.border = thin_border

    total_cell = ws["F19"]
    total_cell.value = "=SUM(F4:F15)"
    total_cell.font = Font(bold=True, size=10, color="FFFFFF")
    total_cell.fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    total_cell.alignment = center
    total_cell.border = thin_border
    ws.row_dimensions[19].height = 18

    ws.freeze_panes = "A4"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
