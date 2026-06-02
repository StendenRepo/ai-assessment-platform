"""G2-129 — overlap report for dossier export."""

from __future__ import annotations

import io
import json
import zipfile


def format_overlap_report_md(report: dict) -> str:
    lines = [
        "OVERLAP DETECTION REPORT",
        "=" * 40,
        f"Module: {report.get('module_id', '')}",
        f"Group: {report.get('group_id', '')}",
        f"Generated: {report.get('generated_at', '')}",
        "",
        "CONFIRMED OVERLAPS",
        "-" * 40,
    ]
    confirmed = report.get("confirmed") or []
    if not confirmed:
        lines.append("(none)")
    for o in confirmed:
        scope = o.get("scope", "within_group")
        scope_label = "Cross-group" if scope == "cross_group" else "Within group"
        lines.append(
            f"\n• {o['student_a_name']} ↔ {o['student_b_name']} — "
            f"{o['similarity_percent']}% ({scope_label})"
        )
        if scope == "cross_group":
            lines.append(
                f"  Groups: {o.get('group_a_name', o.get('group_a_id'))} / "
                f"{o.get('group_b_name', o.get('group_b_id'))}"
            )
        lines.append(f"  Files: {o['file_a']} | {o['file_b']}")

    lines.extend(["", "POSSIBLE OVERLAPS (borderline)", "-" * 40])
    possible = report.get("possible") or []
    if not possible:
        lines.append("(none)")
    for o in possible:
        lines.append(
            f"\n• {o['student_a_name']} ↔ {o['student_b_name']} — "
            f"{o['similarity_percent']}%"
        )
        lines.append(f"  Files: {o['file_a']} | {o['file_b']}")

    return "\n".join(lines) + "\n"


def build_overlap_dossier_zip(report: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("overlap_report.md", format_overlap_report_md(report))
        zf.writestr("overlap_report.json", json.dumps(report, indent=2))
        zf.writestr(
            "README.txt",
            "Overlap report for teacher review. Confirmed and possible matches are listed separately.\n",
        )
    buf.seek(0)
    return buf.read()
