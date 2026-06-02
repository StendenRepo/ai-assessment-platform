"""Overlap detection and storage for groups and modules."""

from __future__ import annotations

from datetime import datetime, timezone

from app.ai.overlap_detector import (
    EvidenceChunk,
    detect_cross_group_overlaps,
    detect_group_overlaps,
)
from app.ai.chunker import chunk_text
from app.store import PlatformStore, store


def _chunks_for_group(
    platform: PlatformStore, module_id: str, group_id: str
) -> list[EvidenceChunk]:
    project = platform._find_project(module_id, group_id)
    if not project:
        return []
    chunks: list[EvidenceChunk] = []
    for student in project.students:
        for ev in student.evidence:
            text = platform._evidence_content.get(ev.id) or ev.content_preview or ""
            for i, part in enumerate(chunk_text(text)):
                chunks.append(
                    EvidenceChunk(
                        student_id=student.id,
                        student_name=student.name,
                        evidence_id=ev.id,
                        file_name=ev.filename,
                        chunk_index=i,
                        text=part,
                        group_id=group_id,
                        group_name=project.name,
                    )
                )
    return chunks


def _stamp(records: list[dict], module_id: str, group_id: str | None = None) -> list[dict]:
    detected_at = datetime.now(timezone.utc).isoformat()
    for o in records:
        o["detected_at"] = detected_at
        o["module_id"] = module_id
        if group_id:
            o["group_id"] = group_id
    return records


def run_group_overlap_scan(
    module_id: str,
    group_id: str,
    *,
    platform: PlatformStore | None = None,
) -> list[dict]:
    """G2-122: within-group scan."""
    platform = platform or store
    chunks = _chunks_for_group(platform, module_id, group_id)
    overlaps = _stamp(
        detect_group_overlaps(chunks, scope="within_group"),
        module_id,
        group_id,
    )
    platform.set_group_overlaps(module_id, group_id, overlaps)
    return overlaps


def run_cross_group_scan(
    module_id: str,
    *,
    platform: PlatformStore | None = None,
) -> list[dict]:
    """G2-123: compare evidence across every pair of groups in the module."""
    platform = platform or store
    module = platform.modules.get(module_id)
    if not module or len(module.projects) < 2:
        return []

    all_cross: list[dict] = []
    projects = module.projects
    for i in range(len(projects)):
        for j in range(i + 1, len(projects)):
            ga, gb = projects[i], projects[j]
            chunks_a = _chunks_for_group(platform, module_id, ga.id)
            chunks_b = _chunks_for_group(platform, module_id, gb.id)
            hits = detect_cross_group_overlaps(chunks_a, chunks_b)
            all_cross.extend(_stamp(hits, module_id))

    all_cross.sort(key=lambda x: x.get("similarity", 0), reverse=True)
    platform.set_cross_group_overlaps(module_id, all_cross)
    return all_cross


def run_full_overlap_scan(
    module_id: str,
    group_id: str | None = None,
    *,
    platform: PlatformStore | None = None,
) -> dict:
    """Run within-group (one or all groups) plus cross-group for the module."""
    platform = platform or store
    module = platform.modules.get(module_id)
    if not module:
        return {"within_group": [], "cross_group": []}

    within: list[dict] = []
    if group_id:
        p = platform._find_project(module_id, group_id)
        if p:
            within.extend(run_group_overlap_scan(module_id, group_id, platform=platform))
    else:
        for project in module.projects:
            within.extend(
                run_group_overlap_scan(module_id, project.id, platform=platform)
            )

    cross = run_cross_group_scan(module_id, platform=platform)
    return {
        "within_group": within,
        "cross_group": cross,
        "confirmed_count": sum(
            1 for o in within + cross if o.get("status") == "confirmed"
        ),
        "possible_count": sum(
            1 for o in within + cross if o.get("status") == "possible"
        ),
    }


def list_group_overlaps(
    module_id: str,
    group_id: str,
    *,
    status: str | None = None,
    scope: str | None = None,
    sort: str = "similarity",
    order: str = "desc",
    platform: PlatformStore | None = None,
) -> list[dict]:
    platform = platform or store
    items = list(platform.get_group_overlaps(module_id, group_id))
    if scope:
        items = [o for o in items if o.get("scope") == scope]
    return _filter_sort(items, status=status, sort=sort, order=order)


def list_module_overlaps(
    module_id: str,
    *,
    status: str | None = None,
    scope: str | None = None,
    sort: str = "similarity",
    order: str = "desc",
    platform: PlatformStore | None = None,
) -> list[dict]:
    """All overlaps for a project/module (within all groups + cross-group)."""
    platform = platform or store
    module = platform.modules.get(module_id)
    if not module:
        return []
    items: list[dict] = []
    for project in module.projects:
        items.extend(platform.get_group_overlaps(module_id, project.id))
    items.extend(platform.get_cross_group_overlaps(module_id))
    if scope:
        items = [o for o in items if o.get("scope") == scope]
    return _filter_sort(items, status=status, sort=sort, order=order)


def list_confirmed_overlaps(
    module_id: str,
    group_id: str,
    **kwargs,
) -> list[dict]:
    """G2-127: confirmed only — never mixed with possible."""
    return list_group_overlaps(module_id, group_id, status="confirmed", **kwargs)


def list_possible_overlaps(
    module_id: str,
    group_id: str,
    **kwargs,
) -> list[dict]:
    """G2-127: borderline / possible only — separate list."""
    return list_group_overlaps(module_id, group_id, status="possible", **kwargs)


def _filter_sort(
    items: list[dict],
    *,
    status: str | None,
    sort: str,
    order: str,
) -> list[dict]:
    if status in ("confirmed", "possible"):
        items = [o for o in items if o.get("status") == status]
    reverse = order.lower() != "asc"
    if sort == "similarity":
        items.sort(key=lambda x: x.get("similarity", 0), reverse=reverse)
    elif sort == "detected_at":
        items.sort(key=lambda x: x.get("detected_at", ""), reverse=reverse)
    return items


def get_overlap(
    module_id: str,
    group_id: str,
    overlap_id: str,
    *,
    platform: PlatformStore | None = None,
) -> dict | None:
    platform = platform or store
    for o in platform.get_group_overlaps(module_id, group_id):
        if o.get("id") == overlap_id:
            return o
    for o in platform.get_cross_group_overlaps(module_id):
        if o.get("id") == overlap_id:
            return o
    return None


def collect_overlaps_for_export(
    module_id: str,
    group_id: str,
    *,
    platform: PlatformStore | None = None,
) -> dict:
    """G2-129: structured overlap report for dossier ZIP."""
    platform = platform or store
    within = list_group_overlaps(module_id, group_id, platform=platform)
    cross = platform.get_cross_group_overlaps(module_id)
    return {
        "module_id": module_id,
        "group_id": group_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "within_group": within,
        "cross_group": cross,
        "confirmed": [o for o in within + cross if o.get("status") == "confirmed"],
        "possible": [o for o in within + cross if o.get("status") == "possible"],
    }
