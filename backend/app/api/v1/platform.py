from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from app.ai.orchestrator import run_analysis
from app.ai import ollama_client
from app.audit import log_event, query_audit_log
from app.export.dossier import build_eml, build_student_dossier_zip
from app.ingestion.files import extract_text_from_bytes, parse_rubric_lines
from app.store import store

router = APIRouter(tags=["Platform"])


# --- Modules (FR-01) ---


class ModuleCreate(BaseModel):
    name: str
    academic_year: str


@router.get("/modules")
def list_modules():
    return [
        {
            "id": m.id,
            "name": m.name,
            "academic_year": m.academic_year,
            "criteria_count": len(m.criteria),
            "projects_count": len(m.projects),
            "created_at": m.created_at,
        }
        for m in store.modules.values()
    ]


@router.post("/modules")
def create_module(body: ModuleCreate):
    m = store.create_module(body.name, body.academic_year)
    log_event("module_created", module_id=m.id, detail={"name": body.name})
    return m


@router.get("/modules/{module_id}")
def get_module(module_id: str):
    m = store.modules.get(module_id)
    if not m:
        raise HTTPException(404, "Module not found")
    return {
        "id": m.id,
        "name": m.name,
        "academic_year": m.academic_year,
        "criteria": m.criteria,
        "has_rubric": bool(m.rubric_text),
        "has_module_guide": bool(m.module_guide_text),
        "rubric_text": m.rubric_text[:2000] if m.rubric_text else "",
        "module_guide_text": m.module_guide_text[:2000] if m.module_guide_text else "",
        "projects": [
            {
                "id": p.id,
                "name": p.name,
                "phase": p.phase,
                "students_count": len(p.students),
            }
            for p in m.projects
        ],
    }


@router.post("/modules/{module_id}/upload-rubric")
async def upload_rubric(module_id: str, file: UploadFile = File(...)):
    m = store.modules.get(module_id)
    if not m:
        raise HTTPException(404, "Module not found")
    raw = await file.read()
    text = extract_text_from_bytes(file.filename or "rubric.docx", raw)
    criteria = parse_rubric_lines(text)
    store.update_module_docs(module_id, rubric_text=text, criteria=criteria)
    log_event("rubric_uploaded", module_id=module_id, detail={"file": file.filename})
    return {"criteria": criteria, "chars": len(text)}


@router.post("/modules/{module_id}/upload-module-guide")
async def upload_module_guide(module_id: str, file: UploadFile = File(...)):
    m = store.modules.get(module_id)
    if not m:
        raise HTTPException(404, "Module not found")
    raw = await file.read()
    text = extract_text_from_bytes(file.filename or "guide.pdf", raw)
    store.update_module_docs(module_id, module_guide_text=text)
    log_event("module_guide_uploaded", module_id=module_id, detail={"file": file.filename})
    return {"chars": len(text)}


@router.delete("/modules/{module_id}/rubric")
def delete_rubric(module_id: str):
    m = store.clear_rubric(module_id)
    if not m:
        raise HTTPException(404, "Module not found")
    log_event("rubric_removed", module_id=module_id)
    return {"ok": True}


@router.delete("/modules/{module_id}/module-guide")
def delete_module_guide(module_id: str):
    m = store.clear_module_guide(module_id)
    if not m:
        raise HTTPException(404, "Module not found")
    log_event("module_guide_removed", module_id=module_id)
    return {"ok": True}


# --- Projects & students (FR-02) ---


class ProjectCreate(BaseModel):
    name: str


class StudentCreate(BaseModel):
    name: str
    student_number: str = ""


@router.post("/modules/{module_id}/projects")
def create_project(module_id: str, body: ProjectCreate):
    p = store.create_project(module_id, body.name)
    if not p:
        raise HTTPException(404, "Module not found")
    log_event("project_created", module_id=module_id, project_id=p.id)
    return p


@router.get("/modules/{module_id}/projects/{project_id}")
def get_project(module_id: str, project_id: str):
    p = store._find_project(module_id, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    return {
        "id": p.id,
        "name": p.name,
        "phase": p.phase,
        "students": [
            {
                "id": s.id,
                "name": s.name,
                "student_number": s.student_number,
                "evidence_count": len(s.evidence),
                "evidence": [
                    {"id": e.id, "filename": e.filename, "file_type": e.file_type, "uploaded_at": e.uploaded_at}
                    for e in s.evidence
                ],
                "has_analysis": s.analysis is not None,
                "phase": s.phase,
            }
            for s in p.students
        ],
    }


@router.post("/modules/{module_id}/projects/{project_id}/students")
def add_student(module_id: str, project_id: str, body: StudentCreate):
    s = store.add_student(module_id, project_id, body.name, body.student_number)
    if not s:
        raise HTTPException(404, "Project not found")
    log_event("student_added", module_id=module_id, project_id=project_id, student_id=s.id)
    return s


@router.delete("/modules/{module_id}/projects/{project_id}/students/{student_id}")
def delete_student(module_id: str, project_id: str, student_id: str):
    removed = store.remove_student(module_id, project_id, student_id)
    if not removed:
        raise HTTPException(404, "Student not found")
    log_event(
        "student_removed",
        module_id=module_id,
        project_id=project_id,
        student_id=student_id,
        detail={"name": removed.name},
    )
    return {"ok": True, "name": removed.name}


# --- Evidence ---


@router.post("/modules/{module_id}/projects/{project_id}/students/{student_id}/evidence")
async def upload_evidence(
    module_id: str,
    project_id: str,
    student_id: str,
    file: UploadFile = File(...),
):
    raw = await file.read()
    fname = file.filename or "evidence.txt"
    text = extract_text_from_bytes(fname, raw)
    suffix = fname.rsplit(".", 1)[-1].lower() if "." in fname else "txt"
    ev = store.add_evidence(module_id, project_id, student_id, fname, text, suffix)
    if not ev:
        raise HTTPException(404, "Student not found")
    log_event(
        "evidence_uploaded",
        module_id=module_id,
        project_id=project_id,
        student_id=student_id,
        detail={"file": fname, "chars": len(text)},
    )
    return {"id": ev.id, "filename": ev.filename, "preview": ev.content_preview, "chars": len(text)}


@router.delete(
    "/modules/{module_id}/projects/{project_id}/students/{student_id}/evidence/{evidence_id}"
)
def delete_evidence(
    module_id: str,
    project_id: str,
    student_id: str,
    evidence_id: str,
):
    removed = store.remove_evidence(module_id, project_id, student_id, evidence_id)
    if not removed:
        raise HTTPException(404, "Evidence not found")
    log_event(
        "evidence_removed",
        module_id=module_id,
        project_id=project_id,
        student_id=student_id,
        detail={"file": removed.filename, "evidence_id": evidence_id},
    )
    return {"ok": True, "filename": removed.filename}


# --- Analysis ---


def _apply_analysis_to_project(module_id: str, project_id: str, result: dict) -> None:
    project = store._find_project(module_id, project_id)
    if not project:
        return
    for s in project.students:
        s.analysis = result
        s.draft_form = [
            {
                "criterion": d["criterion"],
                "suggestion": d["suggestion"],
                "suggestion_strength": d["suggestion_strength"],
                "teacher_score": None,
                "teacher_comment": "",
            }
            for d in result.get("draft_suggestions", [])
            if d.get("student") == s.name
        ]
        s.phase = "prepare"
    project.phase = "prepare"
    store.save()


def _run_project_analysis_task(module_id: str, project_id: str) -> None:
    try:
        module = store.modules.get(module_id)
        project = store._find_project(module_id, project_id)
        if not module or not project:
            store.fail_analysis_job(module_id, project_id, "Project not found")
            return

        store.update_analysis_job(module_id, project_id, step="Loading student evidence", progress=5)

        criteria = store.criterion_titles(module)
        students_payload: dict[str, dict] = {}
        for s in project.students:
            text = store.get_student_evidence_text(s)
            src = s.evidence[0].filename if s.evidence else "no evidence"
            students_payload[s.name] = {
                "source_file": src,
                "text": text or "(no evidence uploaded)",
            }

        def on_progress(step: str, progress: int) -> None:
            store.update_analysis_job(module_id, project_id, step=step, progress=progress)

        result = run_analysis(criteria, students_payload, on_progress=on_progress)
        _apply_analysis_to_project(module_id, project_id, result)
        store.complete_analysis_job(
            module_id, project_id, processing=result.get("processing", "")
        )
        log_event(
            "analysis_completed",
            module_id=module_id,
            project_id=project_id,
            detail={"processing": result["processing"]},
        )
    except Exception as exc:
        store.fail_analysis_job(module_id, project_id, str(exc))


@router.post("/modules/{module_id}/projects/{project_id}/analyze")
def analyze_project(
    module_id: str,
    project_id: str,
    background_tasks: BackgroundTasks,
):
    module = store.modules.get(module_id)
    project = store._find_project(module_id, project_id)
    if not module or not project:
        raise HTTPException(404, "Not found")
    if not project.students:
        raise HTTPException(400, "No students in project")
    if not store.start_analysis_job(module_id, project_id):
        raise HTTPException(409, "Analysis already running for this project")

    background_tasks.add_task(_run_project_analysis_task, module_id, project_id)
    return {"status": "started"}


@router.get("/modules/{module_id}/projects/{project_id}/analyze/status")
def analyze_project_status(module_id: str, project_id: str):
    project = store._find_project(module_id, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return store.get_analysis_job(module_id, project_id)


@router.get("/modules/{module_id}/projects/{project_id}/students/{student_id}")
def get_student_workspace(module_id: str, project_id: str, student_id: str):
    s = store._find_student(module_id, project_id, student_id)
    if not s:
        raise HTTPException(404, "Student not found")
    return {
        "id": s.id,
        "name": s.name,
        "student_number": s.student_number,
        "phase": s.phase,
        "consent_given": s.consent_given,
        "transcript": s.transcript,
        "evidence": [
            {
                "id": e.id,
                "filename": e.filename,
                "preview": e.content_preview,
                "file_type": e.file_type,
            }
            for e in s.evidence
        ],
        "analysis": s.analysis,
        "draft_form": s.draft_form,
    }


class DraftUpdate(BaseModel):
    criterion: str
    suggestion: str = ""
    suggestion_strength: int | None = None
    teacher_score: float | None = None
    teacher_comment: str = ""


@router.patch("/modules/{module_id}/projects/{project_id}/students/{student_id}/draft")
def update_draft(
    module_id: str,
    project_id: str,
    student_id: str,
    body: list[DraftUpdate],
):
    s = store._find_student(module_id, project_id, student_id)
    if not s:
        raise HTTPException(404, "Student not found")
    s.draft_form = [b.model_dump() for b in body]
    s.phase = "grade"
    log_event("draft_updated", module_id=module_id, project_id=project_id, student_id=student_id)
    store.save()
    return {"draft_form": s.draft_form}


# --- Recording stub (FR-06) ---


class ConsentBody(BaseModel):
    consent_given: bool
    note: str = ""


@router.post("/modules/{module_id}/projects/{project_id}/students/{student_id}/consent")
def record_consent(module_id: str, project_id: str, student_id: str, body: ConsentBody):
    s = store._find_student(module_id, project_id, student_id)
    if not s:
        raise HTTPException(404, "Student not found")
    s.consent_given = body.consent_given
    s.recording_note = body.note
    s.phase = "conduct"
    log_event("consent_recorded", module_id=module_id, project_id=project_id, student_id=student_id, detail=body.model_dump())
    store.save()
    return {"consent_given": s.consent_given}


@router.post("/modules/{module_id}/projects/{project_id}/students/{student_id}/transcript")
async def upload_transcript(
    module_id: str,
    project_id: str,
    student_id: str,
    file: UploadFile = File(...),
):
    """Prototype: upload transcript .txt or audio metadata — full STT deferred to later sprint."""
    s = store._find_student(module_id, project_id, student_id)
    if not s:
        raise HTTPException(404, "Student not found")
    raw = await file.read()
    if (file.filename or "").lower().endswith((".txt", ".md")):
        s.transcript = raw.decode("utf-8", errors="replace")
    else:
        s.transcript = f"[Recording stored: {file.filename}, {len(raw)} bytes — local STT planned week 6+]"
    log_event("transcript_uploaded", module_id=module_id, project_id=project_id, student_id=student_id)
    store.save()
    return {"transcript_preview": s.transcript[:500]}


# --- Chat (FR-07 prototype) ---


class ChatMessage(BaseModel):
    message: str


def _chat_context(module_id: str, project_id: str, student_id: str, question: str) -> tuple[Any, Any, dict]:
    module = store.modules.get(module_id)
    s = store._find_student(module_id, project_id, student_id)
    if not s:
        raise HTTPException(404, "Student not found")
    analysis = s.analysis or {}
    ctx = {
        "student": s.name,
        "criteria": module.criteria if module else [],
        "analysis_summary": analysis.get("draft_suggestions", [])[:5],
        "evidence_matches": [
            m
            for m in (analysis.get("evidence_matches") or [])
            if m.get("student") == s.name
        ][:5],
        "overlaps": analysis.get("overlaps", [])[:3],
    }
    return module, s, ctx


@router.post("/modules/{module_id}/projects/{project_id}/students/{student_id}/chat")
def assessment_chat(
    module_id: str,
    project_id: str,
    student_id: str,
    body: ChatMessage,
):
    from app.ai.assessment_chat import prepare_chat
    from app.ai.ollama_client import chat

    _, _, ctx = _chat_context(module_id, project_id, student_id, body.message)
    plan = prepare_chat(body.message, ctx)
    if plan.static_reply:
        reply = plan.static_reply
    else:
        reply = chat(plan.system, plan.user, num_predict=plan.num_predict)
    entry = {
        "id": store._new_id(),
        "student_id": student_id,
        "user": body.message,
        "assistant": reply or "(LLM unavailable — check Ollama)",
    }
    store.chat_history.append(entry)
    store.save()
    log_event("chat_message", module_id=module_id, project_id=project_id, student_id=student_id)
    return entry


@router.post("/modules/{module_id}/projects/{project_id}/students/{student_id}/chat/stream")
def assessment_chat_stream(
    module_id: str,
    project_id: str,
    student_id: str,
    body: ChatMessage,
):
    from app.ai.assessment_chat import prepare_chat
    from app.ai.ollama_client import chat_stream

    _, _, ctx = _chat_context(module_id, project_id, student_id, body.message)
    plan = prepare_chat(body.message, ctx)

    def sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    def generate():
        parts: list[str] = []
        try:
            if plan.static_reply:
                yield sse("token", {"text": plan.static_reply})
                parts.append(plan.static_reply)
            else:
                for token in chat_stream(plan.system, plan.user, num_predict=plan.num_predict):
                    parts.append(token)
                    yield sse("token", {"text": token})
            assistant = "".join(parts).strip() or "(LLM unavailable — check Ollama)"
            entry = {
                "id": store._new_id(),
                "student_id": student_id,
                "user": body.message,
                "assistant": assistant,
            }
            store.chat_history.append(entry)
            store.save()
            log_event("chat_message", module_id=module_id, project_id=project_id, student_id=student_id)
            yield sse("done", entry)
        except Exception as exc:
            yield sse("error", {"message": str(exc)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/modules/{module_id}/projects/{project_id}/students/{student_id}/chat")
def chat_history(module_id: str, project_id: str, student_id: str):
    return [c for c in store.chat_history if c.get("student_id") == student_id][-20:]


# --- Export (FR-08) ---


@router.get("/modules/{module_id}/projects/{project_id}/students/{student_id}/export/zip")
def export_zip(module_id: str, project_id: str, student_id: str):
    module = store.modules.get(module_id)
    project = store._find_project(module_id, project_id)
    s = store._find_student(module_id, project_id, student_id)
    if not module or not project or not s:
        raise HTTPException(404, "Not found")
    data = build_student_dossier_zip(module, project.name, s)
    log_event("export_zip", module_id=module_id, project_id=project_id, student_id=student_id)
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="dossier_{s.id}.zip"'},
    )


@router.get("/modules/{module_id}/projects/{project_id}/students/{student_id}/export/eml")
def export_eml(module_id: str, project_id: str, student_id: str):
    module = store.modules.get(module_id)
    project = store._find_project(module_id, project_id)
    s = store._find_student(module_id, project_id, student_id)
    if not module or not project or not s:
        raise HTTPException(404, "Not found")
    eml = build_eml(module, project.name, s)
    return Response(content=eml, media_type="message/rfc822")


# --- Audit & system ---


@router.get("/audit")
def get_audit(
    action: str | None = None,
    teacher: str | None = None,
    q: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 100,
):
    return query_audit_log(
        action=action,
        teacher=teacher,
        q=q,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
    )


@router.get("/llm-status")
def llm_status():
    up = ollama_client.is_available()
    ready = ollama_client.model_is_pulled() if up else False
    return {
        **ollama_client.get_config(),
        "ollama_reachable": up,
        "model_ready": ready,
        "ready": up and ready,
    }


@router.post("/seed-demo")
def reseed_demo():
    store._seed_demo()
    return {"ok": True, "modules": list(store.modules.keys())}
