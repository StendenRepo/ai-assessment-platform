"""Dev UI–shaped routes over the POC platform store + AI pipeline."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.api.v1.platform import _run_project_analysis_task
from app.services.dev_ui_bridge import analysis_to_insights, ensure_dev_context
from app.store import store

router = APIRouter(prefix="/projects", tags=["Dev platform"])


@router.post("/{project_id}/groups/{group_id}/ensure")
def ensure_group(project_id: str, group_id: str):
    ensure_dev_context(store, project_id, group_id)
    project = store._find_project(project_id, group_id)
    if not project:
        raise HTTPException(500, "Failed to prepare group context")
    return {
        "module_id": project_id,
        "project_id": group_id,
        "students": [{"id": s.id, "name": s.name} for s in project.students],
    }


@router.post("/{project_id}/groups/{group_id}/analyze")
def analyze_group(project_id: str, group_id: str, background_tasks: BackgroundTasks):
    ensure_dev_context(store, project_id, group_id)
    module = store.modules.get(project_id)
    project = store._find_project(project_id, group_id)
    if not module or not project:
        raise HTTPException(404, "Group not found")
    if not project.students:
        raise HTTPException(400, "No students in group")
    if not store.start_analysis_job(project_id, group_id):
        raise HTTPException(409, "Analysis already running")
    background_tasks.add_task(_run_project_analysis_task, project_id, group_id)
    return {"status": "started", "module_id": project_id, "project_id": group_id}


@router.get("/{project_id}/groups/{group_id}/analyze/status")
def analyze_group_status(project_id: str, group_id: str):
    project = store._find_project(project_id, group_id)
    if not project:
        raise HTTPException(404, "Group not found")
    return store.get_analysis_job(project_id, group_id)


@router.get("/{project_id}/groups/{group_id}/students/{student_id}/ai-insights")
def student_ai_insights(project_id: str, group_id: str, student_id: str):
    ensure_dev_context(store, project_id, group_id)
    student = store._find_student(project_id, group_id, student_id)
    if not student:
        raise HTTPException(404, "Student not found")
    insights = analysis_to_insights(student.analysis, student_id, student.name)
    return {
        "student_id": student_id,
        "insights": insights,
        "processing": (student.analysis or {}).get("processing"),
        "llm": (student.analysis or {}).get("llm"),
    }
