"""Map dev UI routes (project → group → student) onto the JSON platform store."""

from __future__ import annotations

from pathlib import Path

from app.store import PlatformStore, Student, EvidenceFile
from datetime import datetime, timezone

FIXTURES = Path(__file__).resolve().parent.parent / "ai" / "fixtures"

# Dev UI mock student ids → display name, number, optional fixture file
DEV_STUDENTS: dict[str, tuple[str, str, str | None]] = {
    "student-1": ("Lisa Anderson", "S2034567", "student_a.txt"),
    "student-2": ("Thomas Johnson", "S2034789", "student_b.txt"),
    "student-3": ("Maya Patel", "S2035012", None),
    "student-4": ("Mark Davis", "S2034891", None),
}


def ensure_dev_context(store: PlatformStore, module_id: str, project_id: str) -> None:
    """
    module_id = dev projectId (e.g. proj-1)
    project_id = dev groupId (e.g. group-1)
    """
    module = store.modules.get(module_id)
    if not module:
        from app.store import DEFAULT_CRITERIA, Module

        module = Module(
            id=module_id,
            name=f"Project {module_id}",
            academic_year="2025-2026",
            criteria=[dict(c) for c in DEFAULT_CRITERIA],
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        store.modules[module_id] = module

    project = store._find_project(module_id, project_id)
    if not project:
        from app.store import Project

        project = Project(id=project_id, name=f"Group {project_id}", phase="ingest")
        module.projects.append(project)

    existing_ids = {s.id for s in project.students}
    for sid, (name, number, fixture) in DEV_STUDENTS.items():
        if sid in existing_ids:
            continue
        student = Student(id=sid, name=name, student_number=number, phase="ingest")
        if fixture:
            fpath = FIXTURES / fixture
            if fpath.exists():
                text = fpath.read_text(encoding="utf-8")
                ev_id = store._new_id()
                student.evidence.append(
                    EvidenceFile(
                        id=ev_id,
                        filename=fixture,
                        content_preview=text[:400],
                        uploaded_at=datetime.now(timezone.utc).isoformat(),
                        file_type="txt",
                    )
                )
                store._evidence_content[ev_id] = text
        project.students.append(student)

    if project.students:
        project.phase = "ingest"
    store.save()


def student_name_for_id(student_id: str) -> str | None:
    row = DEV_STUDENTS.get(student_id)
    return row[0] if row else None


def analysis_to_insights(analysis: dict | None, student_id: str, student_name: str) -> list[dict]:
    if not analysis:
        return []

    insights: list[dict] = []
    idx = 0

    for overlap in analysis.get("overlaps") or []:
        involved = {overlap.get("student_a"), overlap.get("student_b")}
        if student_name not in involved:
            continue
        idx += 1
        severity = "high" if overlap.get("similarity", 0) >= 0.5 else "medium"
        other = (
            overlap.get("student_b")
            if overlap.get("student_a") == student_name
            else overlap.get("student_a")
        )
        insights.append(
            {
                "id": f"ai-overlap-{idx}",
                "type": "overlap",
                "severity": severity,
                "title": f"Overlap with {other} ({overlap.get('similarity_percent', 0)}% similar)",
                "description": overlap.get("excerpt")
                or "Similar text found between students. Review recommended.",
                "affectedStudents": [student_id],
                "evidence": [],
                "sourceFiles": [overlap.get("file_a"), overlap.get("file_b")],
            }
        )

    for match in analysis.get("evidence_matches") or []:
        if match.get("student") != student_name:
            continue
        score = float(match.get("score") or 0)
        if score >= 0.35:
            continue
        idx += 1
        insights.append(
            {
                "id": f"ai-match-{idx}",
                "type": "suggestion",
                "severity": "medium",
                "title": f"Weak evidence for: {match.get('criterion', 'criterion')}",
                "description": match.get("snippet") or "Low TF-IDF match — additional evidence may be needed.",
                "affectedStudents": [student_id],
                "evidence": [],
                "sourceFiles": [match.get("source_file") or "unknown"],
            }
        )

    for draft in analysis.get("draft_suggestions") or []:
        if draft.get("student") != student_name:
            continue
        idx += 1
        insights.append(
            {
                "id": f"ai-draft-{idx}",
                "type": "suggestion",
                "severity": "low",
                "title": f"Draft: {draft.get('criterion', 'Assessment')}",
                "description": draft.get("suggestion") or "",
                "affectedStudents": [student_id],
                "evidence": [],
                "sourceFiles": [],
            }
        )

    return insights
