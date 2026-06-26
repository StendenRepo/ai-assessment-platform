"""Render assessment progress trail as a single full-detail PDF."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session

from app.models.assessment import Assessment
from app.models.student import Student
from app.services.assessment_progress_trail import build_progress_trail

AI_ITEM_LABELS = {
    "overlap_detection": "Overlap detection",
    "evidence_match": "Evidence matching",
    "assessment_draft": "Assessment draft (AI)",
    "assessment_questions": "Suggested questions",
    "assessment_chat": "Assessment chat",
}


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(Path(__file__).resolve().parent.parent / "templates")),
        autoescape=select_autoescape(["html", "xml"]),
    )


def _format_dt(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    else:
        return str(value)
    return dt.strftime("%d %b %Y, %H:%M UTC")


def _prepare_trail_view(trail: dict[str, Any]) -> dict[str, Any]:
    view = dict(trail)
    view["exported_at_display"] = _format_dt(trail.get("exported_at"))
    stages = []
    for stage in trail.get("stages") or []:
        s = dict(stage)
        s["timestamp_display"] = _format_dt(stage.get("timestamp"))
        content = dict(stage.get("content") or {})

        if stage.get("key") == "submission":
            files = []
            for f in content.get("files") or []:
                fc = dict(f)
                fc["uploaded_at_display"] = _format_dt(f.get("uploaded_at"))
                files.append(fc)
            content["files"] = files

        if stage.get("key") == "ai_suggestion":
            ai_items = []
            for item in content.get("ai_items") or trail.get("ai_items") or []:
                ic = dict(item)
                ic["label"] = AI_ITEM_LABELS.get(item.get("type"), item.get("type", ""))
                ic["timestamp_display"] = _format_dt(item.get("timestamp"))
                if item.get("type") == "assessment_chat":
                    payload = dict(item.get("payload") or {})
                    messages = []
                    for msg in payload.get("messages") or []:
                        mc = dict(msg)
                        mc["timestamp_display"] = _format_dt(msg.get("timestamp"))
                        messages.append(mc)
                    payload["messages"] = messages
                    ic["payload"] = payload
                ai_items.append(ic)
            content["ai_items"] = ai_items

        if stage.get("key") == "teacher_decision":
            decisions = []
            for d in content.get("decisions") or []:
                dc = dict(d)
                dc["overridden_at_display"] = _format_dt(d.get("overridden_at"))
                decisions.append(dc)
            content["decisions"] = decisions
            audit_events = []
            for ev in content.get("audit_events") or []:
                ec = dict(ev)
                ec["timestamp_display"] = _format_dt(ev.get("timestamp"))
                audit_events.append(ec)
            content["audit_events"] = audit_events

        if stage.get("key") == "final_form":
            content["finalized_at_display"] = _format_dt(content.get("finalized_at"))

        s["content"] = content
        stages.append(s)
    view["stages"] = stages
    return view


def render_progress_trail_pdf(trail: dict[str, Any]) -> bytes:
    """Render one self-contained PDF with full trail detail."""
    from playwright.sync_api import sync_playwright

    env = _env()
    view = _prepare_trail_view(trail)
    html = env.get_template("progress_trail.html").render(trail=view)
    footer_template = (
        '<div style="font-size:8px;color:#64748b;width:100%;text-align:center;">'
        "Assessment progress trail — transparency record"
        "</div>"
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_content(html, wait_until="load")
            return page.pdf(
                format="A4",
                margin={
                    "top": "18mm",
                    "bottom": "22mm",
                    "left": "16mm",
                    "right": "16mm",
                },
                print_background=True,
                display_header_footer=True,
                header_template="<div></div>",
                footer_template=footer_template,
            )
        finally:
            browser.close()


def build_progress_trail_pdf(
    db: Session,
    *,
    student: Student,
    assessment: Optional[Assessment] = None,
    module_name: Optional[str] = None,
) -> bytes:
    trail = build_progress_trail(
        db,
        student=student,
        assessment=assessment,
        module_name=module_name,
    )
    return render_progress_trail_pdf(trail)
