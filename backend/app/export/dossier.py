from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone
from email.message import EmailMessage

from app.store import Module, Student


def build_student_dossier_zip(
    module: Module,
    project_id: str,
    project_name: str,
    student: Student,
) -> bytes:
    buf = io.BytesIO()
    analysis = student.analysis or {}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "README.txt",
            "AI Assessment dossier (prototype). Teacher has final authority.\n",
        )
        zf.writestr(
            "rubric_criteria.json",
            json.dumps(module.criteria, indent=2),
        )
        if module.rubric_text:
            zf.writestr("rubric_source.txt", module.rubric_text)
        if module.module_guide_text:
            zf.writestr("module_guide.txt", module.module_guide_text)
        for ev in student.evidence:
            content = getattr(ev, "_full_content", ev.content_preview)
            zf.writestr(f"evidence/{ev.filename}", content)
        zf.writestr(
            "analysis_results.json",
            json.dumps(analysis, indent=2),
        )
        zf.writestr(
            "draft_assessment.txt",
            _format_draft(student, analysis),
        )
        zf.writestr(
            "overlap_signals.json",
            json.dumps(analysis.get("overlaps", []), indent=2),
        )
        try:
            from app.services.overlap_service import collect_overlaps_for_export
            from app.export.overlap_report import format_overlap_report_md

            report = collect_overlaps_for_export(module.id, project_id)
            zf.writestr("overlap_report.md", format_overlap_report_md(report))
            zf.writestr("overlap_report.json", json.dumps(report, indent=2))
        except Exception:
            pass
    buf.seek(0)
    return buf.read()


def build_eml(
    module: Module,
    project_name: str,
    student: Student,
    teacher_email: str = "teacher@stenden.com",
) -> str:
    msg = EmailMessage()
    msg["Subject"] = f"Assessment dossier — {student.name} — {project_name}"
    msg["From"] = teacher_email
    msg["To"] = f"{student.name.lower().replace(' ', '.')}@student.stenden.com"
    msg.set_content(
        f"Attached assessment materials for {student.name} ({project_name}, {module.name}).\n"
        f"Generated {datetime.now(timezone.utc).isoformat()}.\n"
        "This is a prototype export for SharePoint archiving (Nike method).\n"
    )
    return msg.as_string()


def _format_draft(student: Student, analysis: dict) -> str:
    lines = [f"Draft assessment — {student.name}", "=" * 40, ""]
    for d in analysis.get("draft_suggestions", []):
        if d.get("student") not in (None, student.name):
            continue
        lines.append(f"## {d.get('criterion', '')}")
        lines.append(d.get("suggestion", ""))
        lines.append(f"(Suggestion strength: {d.get('suggestion_strength', 'n/a')}%)")
        lines.append("")
    lines.append("Questions for oral assessment:")
    for q in analysis.get("questions", []):
        if q.get("student") not in (None, student.name):
            continue
        lines.append(f"- {q.get('question', '')}")
    return "\n".join(lines)
