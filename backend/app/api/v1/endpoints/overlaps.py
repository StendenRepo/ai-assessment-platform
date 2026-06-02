"""G2-122 – G2-129 overlap detection, review, and dossier export (SQL-backed)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.ai.chunker import chunk_text
from app.ai.overlap_detector import EvidenceChunk, detect_cross_group_overlaps, detect_group_overlaps
from app.api.deps import get_current_teacher, get_db
from app.export.overlap_report import build_overlap_dossier_zip
from app.ingestion.files import extract_text_from_bytes
from app.models.evidence import Evidence
from app.models.module import Module
from app.models.project import Project
from app.models.student import Student
from app.models.teacher import Teacher
from app.schemas.overlap import (
    OverlapDetail,
    OverlapDetectResponse,
    OverlapListResponse,
    OverlapSummary,
)

router = APIRouter(prefix="/modules", tags=["Overlaps"])


def _summary(o: dict) -> OverlapSummary:
    return OverlapSummary(
        id=o["id"],
        status=o["status"],
        scope=o.get("scope", "within_group"),
        student_a_id=o["student_a_id"],
        student_a_name=o["student_a_name"],
        student_b_id=o["student_b_id"],
        student_b_name=o["student_b_name"],
        file_a=o["file_a"],
        file_b=o["file_b"],
        similarity=o["similarity"],
        similarity_percent=o["similarity_percent"],
        detected_at=o.get("detected_at"),
        group_id=o.get("group_id"),
        group_a_id=o.get("group_a_id"),
        group_b_id=o.get("group_b_id"),
        group_a_name=o.get("group_a_name"),
        group_b_name=o.get("group_b_name"),
    )


def _counts(items: list[dict]) -> dict:
    return {
        "confirmed": sum(1 for o in items if o.get("status") == "confirmed"),
        "possible": sum(1 for o in items if o.get("status") == "possible"),
        "within": sum(1 for o in items if o.get("scope") == "within_group"),
        "cross": sum(1 for o in items if o.get("scope") == "cross_group"),
    }


def _owned_module_or_404(db: Session, module_id: str, teacher: Teacher) -> Module:
    module = (
        db.query(Module)
        .filter(Module.id == module_id, Module.teacher_id == teacher.id)
        .first()
    )
    if not module:
        raise HTTPException(404, "Module not found")
    return module


def _project_or_404(db: Session, module: Module, project_id: str) -> Project:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.module_id == module.id)
        .first()
    )
    if not project:
        raise HTTPException(404, "Group not found")
    return project


def _evidence_text(evidence: Evidence) -> str:
    path = Path(evidence.file_path)
    if not path.exists():
        return ""
    try:
        return extract_text_from_bytes(evidence.file_name, path.read_bytes())
    except Exception:
        return ""


def _chunks_for_project(db: Session, project: Project) -> list[EvidenceChunk]:
    students = db.query(Student).filter(Student.project_id == project.id).all()
    if not students:
        return []

    chunks: list[EvidenceChunk] = []
    for student in students:
        files = db.query(Evidence).filter(Evidence.student_id == student.id).all()
        for evidence in files:
            text = _evidence_text(evidence)
            for index, part in enumerate(chunk_text(text)):
                chunks.append(
                    EvidenceChunk(
                        student_id=str(student.id),
                        student_name=student.name,
                        evidence_id=str(evidence.id),
                        file_name=evidence.file_name,
                        chunk_index=index,
                        text=part,
                        group_id=str(project.id),
                        group_name=project.name,
                    )
                )
    return chunks


def _stable_overlap_id(item: dict) -> str:
    raw = "|".join(
        [
            item.get("scope", ""),
            item.get("student_a_id", ""),
            item.get("student_b_id", ""),
            item.get("evidence_a_id", ""),
            item.get("evidence_b_id", ""),
            str(item.get("group_a_id", "")),
            str(item.get("group_b_id", "")),
            str(item.get("similarity", "")),
        ]
    )
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _stamp(items: list[dict], *, module_id: str, project_id: str | None = None) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    for item in items:
        item["id"] = _stable_overlap_id(item)
        item["detected_at"] = now
        item["module_id"] = module_id
        if project_id:
            item.setdefault("group_id", project_id)
    return items


def _within_overlaps(db: Session, module: Module, project: Project) -> list[dict]:
    chunks = _chunks_for_project(db, project)
    items = detect_group_overlaps(chunks, scope="within_group")
    return _stamp(items, module_id=str(module.id), project_id=str(project.id))


def _cross_overlaps(db: Session, module: Module) -> list[dict]:
    projects = db.query(Project).filter(Project.module_id == module.id).all()
    all_cross: list[dict] = []
    for project_a, project_b in combinations(projects, 2):
        chunks_a = _chunks_for_project(db, project_a)
        chunks_b = _chunks_for_project(db, project_b)
        all_cross.extend(detect_cross_group_overlaps(chunks_a, chunks_b))
    all_cross.sort(key=lambda x: x.get("similarity", 0), reverse=True)
    return _stamp(all_cross, module_id=str(module.id))


def _filter_sort(items: list[dict], *, status: str | None, sort: str, order: str) -> list[dict]:
    rows = list(items)
    if status:
        rows = [o for o in rows if o.get("status") == status]
    reverse = order == "desc"
    if sort == "similarity":
        rows.sort(key=lambda x: x.get("similarity", 0), reverse=reverse)
    elif sort == "detected_at":
        rows.sort(key=lambda x: x.get("detected_at", ""), reverse=reverse)
    return rows


@router.post(
    "/{module_id}/projects/{project_id}/overlaps/detect",
    response_model=OverlapDetectResponse,
)
def detect_group_overlaps_endpoint(
    module_id: str,
    project_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    """G2-122: within-group scan."""
    module = _owned_module_or_404(db, module_id, current_teacher)
    project = _project_or_404(db, module, project_id)
    students = db.query(Student).filter(Student.project_id == project.id).all()
    if len(students) < 2:
        raise HTTPException(400, "At least two students required")

    items = _within_overlaps(db, module, project)
    c = _counts(items)
    return OverlapDetectResponse(
        module_id=module_id,
        group_id=project_id,
        scanned_students=len(students),
        confirmed_count=c["confirmed"],
        possible_count=c["possible"],
        within_group_count=c["within"],
        items=[_summary(o) for o in items],
    )


@router.post("/{module_id}/overlaps/detect-all", response_model=OverlapDetectResponse)
def detect_all_overlaps(
    module_id: str,
    project_id: str | None = None,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    """G2-122 + G2-123: within-group (all or one) and cross-group."""
    module = _owned_module_or_404(db, module_id, current_teacher)
    projects = db.query(Project).filter(Project.module_id == module.id).all()

    within: list[dict] = []
    if project_id:
        project = _project_or_404(db, module, project_id)
        within.extend(_within_overlaps(db, module, project))
    else:
        for project in projects:
            within.extend(_within_overlaps(db, module, project))

    cross = _cross_overlaps(db, module)
    items = within + cross
    students = (
        db.query(Student)
        .join(Project, Student.project_id == Project.id)
        .filter(Project.module_id == module.id)
        .count()
    )
    counts = _counts(items)

    return OverlapDetectResponse(
        module_id=module_id,
        group_id=project_id,
        scanned_students=students,
        confirmed_count=counts["confirmed"],
        possible_count=counts["possible"],
        within_group_count=len(within),
        cross_group_count=len(cross),
        items=[_summary(o) for o in items],
    )


@router.post("/{module_id}/overlaps/cross-group/detect")
def detect_cross_group(
    module_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    """G2-123: cross-group only."""
    module = _owned_module_or_404(db, module_id, current_teacher)
    items = _cross_overlaps(db, module)
    c = _counts(items)
    return OverlapDetectResponse(
        module_id=module_id,
        confirmed_count=c["confirmed"],
        possible_count=c["possible"],
        cross_group_count=c["cross"],
        items=[_summary(o) for o in items],
    )


@router.get("/{module_id}/projects/{project_id}/overlaps", response_model=OverlapListResponse)
def list_overlaps(
    module_id: str,
    project_id: str,
    status: str | None = Query(None, pattern="^(confirmed|possible)$"),
    scope: str | None = Query(None, pattern="^(within_group|cross_group)$"),
    sort: str = Query("similarity", pattern="^(similarity|detected_at)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    include_cross: bool = Query(True),
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    """G2-126 list + G2-124 sort/filter."""
    module = _owned_module_or_404(db, module_id, current_teacher)
    project = _project_or_404(db, module, project_id)

    within = _within_overlaps(db, module, project)
    cross = _cross_overlaps(db, module) if include_cross else []

    if scope == "cross_group":
        items = _filter_sort(cross, status=status, sort=sort, order=order)
    elif scope == "within_group":
        items = _filter_sort(within, status=status, sort=sort, order=order)
    else:
        items = _filter_sort(within + cross, status=status, sort=sort, order=order)

    c = _counts(items)
    return OverlapListResponse(
        module_id=module_id,
        group_id=project_id,
        confirmed_count=c["confirmed"],
        possible_count=c["possible"],
        within_group_count=c["within"],
        cross_group_count=c["cross"],
        items=[_summary(o) for o in items],
    )


@router.get(
    "/{module_id}/projects/{project_id}/overlaps/confirmed",
    response_model=OverlapListResponse,
)
def list_confirmed(
    module_id: str,
    project_id: str,
    sort: str = "similarity",
    order: str = "desc",
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    """G2-127: confirmed overlaps only."""
    module = _owned_module_or_404(db, module_id, current_teacher)
    project = _project_or_404(db, module, project_id)

    within = _within_overlaps(db, module, project)
    cross = _cross_overlaps(db, module)
    items = _filter_sort(within + cross, status="confirmed", sort=sort, order=order)

    c = _counts(items)
    return OverlapListResponse(
        module_id=module_id,
        group_id=project_id,
        confirmed_count=c["confirmed"],
        possible_count=0,
        within_group_count=c["within"],
        cross_group_count=c["cross"],
        items=[_summary(o) for o in items],
    )


@router.get(
    "/{module_id}/projects/{project_id}/overlaps/possible",
    response_model=OverlapListResponse,
)
def list_possible(
    module_id: str,
    project_id: str,
    sort: str = "similarity",
    order: str = "desc",
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    """G2-127: borderline overlaps only — separate from confirmed."""
    module = _owned_module_or_404(db, module_id, current_teacher)
    project = _project_or_404(db, module, project_id)

    within = _within_overlaps(db, module, project)
    cross = _cross_overlaps(db, module)
    items = _filter_sort(within + cross, status="possible", sort=sort, order=order)

    c = _counts(items)
    return OverlapListResponse(
        module_id=module_id,
        group_id=project_id,
        confirmed_count=0,
        possible_count=c["possible"],
        within_group_count=c["within"],
        cross_group_count=c["cross"],
        items=[_summary(o) for o in items],
    )


@router.get(
    "/{module_id}/projects/{project_id}/overlaps/{overlap_id}",
    response_model=OverlapDetail,
)
def get_overlap_detail(
    module_id: str,
    project_id: str,
    overlap_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    """G2-125: side-by-side passages."""
    module = _owned_module_or_404(db, module_id, current_teacher)
    project = _project_or_404(db, module, project_id)
    rows = _within_overlaps(db, module, project) + _cross_overlaps(db, module)

    row = next((o for o in rows if o.get("id") == overlap_id), None)
    if not row:
        raise HTTPException(404, "Overlap not found")

    return OverlapDetail(
        id=row["id"],
        status=row["status"],
        scope=row.get("scope", "within_group"),
        student_a_id=row["student_a_id"],
        student_a_name=row["student_a_name"],
        student_b_id=row["student_b_id"],
        student_b_name=row["student_b_name"],
        file_a=row["file_a"],
        file_b=row["file_b"],
        similarity=row["similarity"],
        similarity_percent=row["similarity_percent"],
        detected_at=row.get("detected_at"),
        group_id=row.get("group_id", project_id),
        group_a_id=row.get("group_a_id"),
        group_b_id=row.get("group_b_id"),
        group_a_name=row.get("group_a_name"),
        group_b_name=row.get("group_b_name"),
        passage_a=row["passage_a"],
        passage_b=row["passage_b"],
        evidence_a_id=row["evidence_a_id"],
        evidence_b_id=row["evidence_b_id"],
    )


@router.get("/{module_id}/projects/{project_id}/overlaps/export/zip")
def export_overlap_dossier(
    module_id: str,
    project_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    """G2-129: dossier ZIP with overlap report."""
    module = _owned_module_or_404(db, module_id, current_teacher)
    project = _project_or_404(db, module, project_id)

    within = _within_overlaps(db, module, project)
    cross = _cross_overlaps(db, module)
    report = {
        "module_id": module_id,
        "group_id": project_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "within_group": within,
        "cross_group": cross,
        "confirmed": [o for o in within + cross if o.get("status") == "confirmed"],
        "possible": [o for o in within + cross if o.get("status") == "possible"],
    }

    data = build_overlap_dossier_zip(report)
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="overlap-report-{project_id}.zip"'},
    )
