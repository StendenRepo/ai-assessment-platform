"""G2-122 – G2-129 overlap detection, review, and dossier export."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.export.overlap_report import build_overlap_dossier_zip
from app.schemas.overlap import (
    OverlapDetail,
    OverlapDetectResponse,
    OverlapListResponse,
    OverlapSummary,
)
from app.services.dev_ui_bridge import ensure_dev_context, ensure_dev_module
from app.services.overlap_service import (
    collect_overlaps_for_export,
    get_overlap,
    list_confirmed_overlaps,
    list_group_overlaps,
    list_possible_overlaps,
    run_cross_group_scan,
    run_full_overlap_scan,
    run_group_overlap_scan,
)
from app.store import store

router = APIRouter(prefix="/projects", tags=["Overlaps"])


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


@router.post(
    "/{project_id}/groups/{group_id}/overlaps/detect",
    response_model=OverlapDetectResponse,
)
def detect_group_overlaps_endpoint(project_id: str, group_id: str):
    """G2-122: within-group scan."""
    ensure_dev_context(store, project_id, group_id)
    project = store._find_project(project_id, group_id)
    if not project:
        raise HTTPException(404, "Group not found")
    if len(project.students) < 2:
        raise HTTPException(400, "At least two students required")

    items = run_group_overlap_scan(project_id, group_id)
    c = _counts(items)
    return OverlapDetectResponse(
        module_id=project_id,
        group_id=group_id,
        scanned_students=len(project.students),
        confirmed_count=c["confirmed"],
        possible_count=c["possible"],
        within_group_count=c["within"],
        items=[_summary(o) for o in items],
    )


@router.post("/{project_id}/overlaps/detect-all", response_model=OverlapDetectResponse)
def detect_all_overlaps(project_id: str, group_id: str | None = None):
    """G2-122 + G2-123: within-group (all or one) and cross-group."""
    ensure_dev_module(store, project_id)
    result = run_full_overlap_scan(project_id, group_id=group_id)
    items = result["within_group"] + result["cross_group"]
    module = store.modules[project_id]
    students = sum(len(p.students) for p in module.projects)
    return OverlapDetectResponse(
        module_id=project_id,
        group_id=group_id,
        scanned_students=students,
        confirmed_count=result["confirmed_count"],
        possible_count=result["possible_count"],
        within_group_count=len(result["within_group"]),
        cross_group_count=len(result["cross_group"]),
        items=[_summary(o) for o in items],
    )


@router.post("/{project_id}/overlaps/cross-group/detect")
def detect_cross_group(project_id: str):
    """G2-123: cross-group only."""
    ensure_dev_module(store, project_id)
    items = run_cross_group_scan(project_id)
    c = _counts(items)
    return OverlapDetectResponse(
        module_id=project_id,
        confirmed_count=c["confirmed"],
        possible_count=c["possible"],
        cross_group_count=c["cross"],
        items=[_summary(o) for o in items],
    )


@router.get("/{project_id}/groups/{group_id}/overlaps", response_model=OverlapListResponse)
def list_overlaps(
    project_id: str,
    group_id: str,
    status: str | None = Query(None, pattern="^(confirmed|possible)$"),
    scope: str | None = Query(None, pattern="^(within_group|cross_group)$"),
    sort: str = Query("similarity", pattern="^(similarity|detected_at)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    include_cross: bool = Query(True),
):
    """G2-126 list + G2-124 sort/filter."""
    ensure_dev_context(store, project_id, group_id)
    within = list_group_overlaps(
        project_id, group_id, status=status, scope=scope or "within_group", sort=sort, order=order
    )
    cross = (
        store.get_cross_group_overlaps(project_id)
        if include_cross
        else []
    )
    if status:
        cross = [o for o in cross if o.get("status") == status]
    if scope == "cross_group":
        items = cross
    elif scope == "within_group":
        items = within
    else:
        items = within + cross
        if sort == "similarity":
            items.sort(key=lambda x: x.get("similarity", 0), reverse=order == "desc")
    c = _counts(items)
    return OverlapListResponse(
        module_id=project_id,
        group_id=group_id,
        confirmed_count=c["confirmed"],
        possible_count=c["possible"],
        within_group_count=c["within"],
        cross_group_count=c["cross"],
        items=[_summary(o) for o in items],
    )


@router.get(
    "/{project_id}/groups/{group_id}/overlaps/confirmed",
    response_model=OverlapListResponse,
)
def list_confirmed(project_id: str, group_id: str, sort: str = "similarity", order: str = "desc"):
    """G2-127: confirmed overlaps only."""
    ensure_dev_context(store, project_id, group_id)
    items = list_confirmed_overlaps(project_id, group_id, sort=sort, order=order)
    cross = [o for o in store.get_cross_group_overlaps(project_id) if o.get("status") == "confirmed"]
    items = items + cross
    items.sort(key=lambda x: x.get("similarity", 0), reverse=order == "desc")
    c = _counts(items)
    return OverlapListResponse(
        module_id=project_id,
        group_id=group_id,
        confirmed_count=c["confirmed"],
        possible_count=0,
        within_group_count=c["within"],
        cross_group_count=c["cross"],
        items=[_summary(o) for o in items],
    )


@router.get(
    "/{project_id}/groups/{group_id}/overlaps/possible",
    response_model=OverlapListResponse,
)
def list_possible(project_id: str, group_id: str, sort: str = "similarity", order: str = "desc"):
    """G2-127: borderline overlaps only — separate from confirmed."""
    ensure_dev_context(store, project_id, group_id)
    items = list_possible_overlaps(project_id, group_id, sort=sort, order=order)
    cross = [o for o in store.get_cross_group_overlaps(project_id) if o.get("status") == "possible"]
    items = items + cross
    items.sort(key=lambda x: x.get("similarity", 0), reverse=order == "desc")
    c = _counts(items)
    return OverlapListResponse(
        module_id=project_id,
        group_id=group_id,
        confirmed_count=0,
        possible_count=c["possible"],
        within_group_count=c["within"],
        cross_group_count=c["cross"],
        items=[_summary(o) for o in items],
    )


@router.get(
    "/{project_id}/groups/{group_id}/overlaps/{overlap_id}",
    response_model=OverlapDetail,
)
def get_overlap_detail(project_id: str, group_id: str, overlap_id: str):
    """G2-125: side-by-side passages."""
    ensure_dev_context(store, project_id, group_id)
    row = get_overlap(project_id, group_id, overlap_id)
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
        group_id=row.get("group_id", group_id),
        group_a_id=row.get("group_a_id"),
        group_b_id=row.get("group_b_id"),
        group_a_name=row.get("group_a_name"),
        group_b_name=row.get("group_b_name"),
        passage_a=row["passage_a"],
        passage_b=row["passage_b"],
        evidence_a_id=row["evidence_a_id"],
        evidence_b_id=row["evidence_b_id"],
    )


@router.get("/{project_id}/groups/{group_id}/overlaps/export/zip")
def export_overlap_dossier(project_id: str, group_id: str):
    """G2-129: dossier ZIP with overlap report."""
    ensure_dev_context(store, project_id, group_id)
    report = collect_overlaps_for_export(project_id, group_id)
    data = build_overlap_dossier_zip(report)
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="overlap-report-{group_id}.zip"'
        },
    )
