#!/usr/bin/env python3
"""Post-import simulation: evidence files, overlap signals, and G2 assessment drafts.

Run after import_seed_to_postgres.py to get a demo-ready environment without Ollama.
"""
from __future__ import annotations

import copy
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.assessment import Assessment
from app.models.audit_event import AuditEvent
from app.models.chat_message import ChatMessage
from app.models.enums import (
    AssessmentStatus,
    AuditSource,
    EmbeddingStatus,
    FileType,
    SourceType,
)
from app.models.evidence import Evidence
from app.models.evidence_match import EvidenceMatch
from app.models.module import Module
from app.models.overlap_signal import OverlapSignal
from app.models.project import Project
from app.models.student import Student, student_projects
from app.services.draft_assessment_service import DEFAULT_CRITERIA, DRAFT_VERSION
from app.services.evidence_matcher import match_criterion_to_evidence, persist_matches
from app.services.evidence_service import EVIDENCE_UPLOAD_DIR
from app.services.overlap_service import OverlapService

# ── Demo content ─────────────────────────────────────────────────────────────

SHARED_OVERLAP_BLOCK = (
    "Our team implemented the authentication module using JWT tokens and bcrypt hashing. "
    "We documented the API endpoints in README.md and wrote integration tests for login "
    "and logout flows. The CLI planning application stores tasks in a local SQLite "
    "database with a clean repository pattern separating persistence from business logic."
)

DEMO_MODULE_NAME = "Programmeren 2 (HBO-ICT Informatica)"
DEMO_GROUP_NAME = "CLI Planningsapp in Python"

# student_number -> scenario
DEMO_SCENARIOS = {
    "0000001": "ai_only",       # fresh AI suggestions + overlap partner
    "0000002": "overrides",     # teacher overrides + chat refinement + overlap partner
    "0000003": "finalized",     # locked finalized form with transparency
    "0000004": "evidence_only", # evidence uploaded, no AI draft yet
}


def _ensure_assessment(
    db: Session, student: Student, module: Module
) -> Assessment:
    assessment = (
        db.query(Assessment)
        .filter(Assessment.student_id == student.student_number)
        .first()
    )
    if assessment:
        return assessment
    assessment = Assessment(
        id=_uid(f"assessment-{student.student_number}"),
        student_id=student.student_number,
        teacher_id=module.teacher_id,
        status=AssessmentStatus.draft,
    )
    db.add(assessment)
    db.flush()
    return assessment


def _uid(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"ai-assessment-seed::{name}")


def _now() -> datetime:
    return datetime.utcnow()


def _write_evidence_file(student_id: str, filename: str, content: str) -> tuple[str, Path]:
    upload_dir = EVIDENCE_UPLOAD_DIR / student_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    unique_name = f"sim_{uuid.uuid4().hex[:12]}_{filename}"
    full_path = upload_dir / unique_name
    full_path.write_text(content, encoding="utf-8")
    relative = str(full_path.relative_to(EVIDENCE_UPLOAD_DIR))
    return relative, full_path


def _evidence_content(student_number: str, filename: str) -> str:
    if student_number == "0000001":
        return (
            "# Sprint 3 submission — Student 001\n\n"
            f"{SHARED_OVERLAP_BLOCK}\n\n"
            "I led the repository layer refactor and added pytest coverage for task CRUD operations."
        )
    if student_number == "0000002":
        return (
            "# Team deliverable notes — Student 002\n\n"
            f"{SHARED_OVERLAP_BLOCK}\n\n"
            "I pair-programmed the JWT middleware and updated README.md with endpoint examples."
        )
    if student_number == "0000003":
        return (
            "# Individual reflection — Student 003\n\n"
            "Our group built a Kanban-style CLI with argparse subcommands and CSV export. "
            "I owned the persistence module and wrote unit tests for edge cases around "
            "duplicate task titles and timezone-aware due dates."
        )
    return (
        f"# Weekly log — Student {student_number}\n\n"
        "Implemented argparse commands, fixed lint issues, and participated in stand-ups. "
        "Evidence is mostly unique to this student with no significant textual overlap."
    )


def _create_evidence(db: Session, student: Student) -> list[Evidence]:
    files = ["submission_report.md", "technical_notes.md"]
    created: list[Evidence] = []
    for fname in files:
        rel_path, _ = _write_evidence_file(
            student.student_number,
            fname,
            _evidence_content(student.student_number, fname),
        )
        evidence = Evidence(
            id=_uid(f"evidence-{student.student_number}-{fname}"),
            student_id=student.student_number,
            file_name=fname,
            file_type=FileType.markdown,
            file_path=rel_path,
            source_type=SourceType.upload,
            embedding_status=EmbeddingStatus.pending,
            uploaded_at=_now() - timedelta(days=3),
        )
        db.add(evidence)
        created.append(evidence)
    db.flush()
    return created


def _refs_from_matches(matches) -> list[dict]:
    return [
        {
            "evidence_id": str(m.evidence_id) if m.evidence_id else None,
            "file_name": m.file_name,
            "quote": m.quote,
            "confidence": m.confidence,
            "missing_note": m.missing_note,
        }
        for m in matches
    ]


def _criterion_entry(
    *,
    ai_score: float,
    ai_comment: str,
    file_name: str,
    quote: str,
    teacher_score: float | None = None,
    teacher_comment: str | None = None,
    refined_via_chat: bool = False,
    now: datetime,
) -> dict:
    evidence_refs = [
        {
            "evidence_id": None,
            "file_name": file_name,
            "quote": quote[:500],
            "confidence": 0.72,
            "missing_note": None,
        }
    ]
    ai = {
        "score": ai_score,
        "comment": ai_comment,
        "generated_at": now.isoformat(),
        "confidence": 0.78,
        "evidence_refs": evidence_refs,
    }
    if refined_via_chat:
        ai["refined_via_chat"] = True
    overridden = teacher_score is not None or teacher_comment is not None
    teacher = None
    if overridden:
        teacher = {
            "score": teacher_score if teacher_score is not None else ai_score,
            "comment": teacher_comment if teacher_comment is not None else ai_comment,
            "overridden_at": now.isoformat(),
        }
    effective_score = teacher["score"] if teacher else ai_score
    effective_comment = teacher["comment"] if teacher else ai_comment
    return {
        "ai": ai,
        "teacher": teacher,
        "is_overridden": overridden,
        "effective": {"score": effective_score, "comment": effective_comment},
    }


def _build_draft(
    scenario: str,
    evidence_rows: list[Evidence],
    assessment_id: uuid.UUID,
    db: Session,
) -> dict:
    now = _now()
    defs = copy.deepcopy(DEFAULT_CRITERIA)
    primary_file = evidence_rows[0].file_name if evidence_rows else "submission_report.md"
    quote = _evidence_content(evidence_rows[0].student_id, primary_file)[:400]

    base_comments = {
        "crit-1": f"Readable structure in [[{primary_file}]] with clear module boundaries.",
        "crit-2": f"README.md and inline comments in [[{primary_file}]] explain setup adequately.",
        "crit-3": "Stand-up notes show regular communication; contribution is documented.",
        "crit-4": f"Pytest coverage mentioned in [[{primary_file}]] for core task flows.",
        "crit-5": "Presentation transcript not uploaded; score based on written evidence only.",
    }
    base_scores = {
        "crit-1": 7.5,
        "crit-2": 7.0,
        "crit-3": 6.5,
        "crit-4": 6.0,
        "crit-5": 5.5,
    }

    criteria: dict[str, dict] = {}
    for d in defs:
        key = d["key"]
        teacher_score = None
        teacher_comment = None
        refined = False
        score = base_scores[key]
        comment = base_comments[key]

        if scenario == "overrides" and key == "crit-1":
            teacher_score = 9.0
            teacher_comment = (
                "Teacher disagrees — architecture refactor in submission_report.md "
                "shows excellent separation of concerns."
            )
        if scenario == "overrides" and key == "crit-4":
            refined = True
            score = 8.0
            comment = (
                f"Updated after chat: integration tests in [[{primary_file}]] cover login/logout "
                "and task persistence paths."
            )

        criteria[key] = _criterion_entry(
            ai_score=score,
            ai_comment=comment,
            file_name=primary_file,
            quote=quote,
            teacher_score=teacher_score,
            teacher_comment=teacher_comment,
            refined_via_chat=refined,
            now=now,
        )

        matches = match_criterion_to_evidence(
            key, d["name"], d["description"], evidence_rows
        )
        persist_matches(db, assessment_id=assessment_id, criterion_key=key, matches=matches)
        criteria[key]["ai"]["evidence_refs"] = _refs_from_matches(matches)

    scores = [criteria[k]["effective"]["score"] for k in criteria]
    avg = round(sum(scores) / len(scores), 2)
    grade = _score_to_grade(avg)
    summary_ai = (
        "AI draft summary: solid technical delivery with good code structure. "
        "Testing evidence improved after review; presentation remains thin."
    )

    draft = {
        "version": DRAFT_VERSION,
        "criteria_defs": defs,
        "criteria": criteria,
        "summary": {"ai": summary_ai, "teacher": None, "effective": summary_ai},
        "overall_grade": {"ai": grade, "teacher": None, "effective": grade},
        "locked": scenario == "finalized",
        "generated_at": now.isoformat(),
    }
    return draft


def _score_to_grade(avg: float) -> str:
    if avg >= 9:
        return "A"
    if avg >= 8.5:
        return "A-"
    if avg >= 8:
        return "B+"
    if avg >= 7.5:
        return "B"
    if avg >= 7:
        return "B-"
    if avg >= 6.5:
        return "C+"
    if avg >= 6:
        return "C"
    return "D"


def _final_payload(draft: dict, teacher_notes: str) -> dict:
    now = _now()
    transparency = {}
    criteria_out = {}
    for d in draft["criteria_defs"]:
        key = d["key"]
        entry = draft["criteria"][key]
        eff = entry["effective"]
        criteria_out[key] = {
            "name": d["name"],
            "score": eff["score"],
            "comment": eff["comment"],
        }
        transparency[key] = {
            "ai": entry.get("ai"),
            "teacher": entry.get("teacher"),
            "is_overridden": entry.get("is_overridden", False),
        }
    scores = [criteria_out[k]["score"] for k in criteria_out]
    avg = round(sum(scores) / len(scores), 2)
    return {
        "version": DRAFT_VERSION,
        "finalized_at": now.isoformat(),
        "finalized_by": "simulation",
        "teacher_notes": teacher_notes,
        "overall_score": avg,
        "grade": draft["overall_grade"]["effective"],
        "summary": draft["summary"]["effective"],
        "criteria": criteria_out,
        "transparency": transparency,
    }


def _clear_demo_artifacts(db: Session, student_numbers: list[str]) -> None:
    assessment_ids = [
        row[0]
        for row in db.query(Assessment.id)
        .filter(Assessment.student_id.in_(student_numbers))
        .all()
    ]
    if assessment_ids:
        db.query(EvidenceMatch).filter(
            EvidenceMatch.assessment_id.in_(assessment_ids)
        ).delete(synchronize_session=False)
        db.query(ChatMessage).filter(
            ChatMessage.assessment_id.in_(assessment_ids)
        ).delete(synchronize_session=False)
        extra_audit = db.query(AuditEvent).filter(
            AuditEvent.assessment_id.in_(assessment_ids),
            AuditEvent.action.in_(
                [
                    "assessment.suggestions_generated",
                    "assessment.suggestion_overridden",
                    "assessment.chat_refine",
                    "assessment.finalized",
                ]
            ),
        )
        extra_audit.delete(synchronize_session=False)

    for ev in db.query(Evidence).filter(Evidence.student_id.in_(student_numbers)).all():
        path = EVIDENCE_UPLOAD_DIR / ev.file_path
        if path.exists():
            path.unlink()

    db.query(OverlapSignal).filter(
        OverlapSignal.student_a_id.in_(student_numbers),
        OverlapSignal.student_b_id.in_(student_numbers),
    ).delete(synchronize_session=False)

    db.query(Evidence).filter(Evidence.student_id.in_(student_numbers)).delete(
        synchronize_session=False
    )
    db.flush()


def _add_audit(
    db: Session,
    *,
    assessment: Assessment,
    action: str,
    details: dict,
    source: AuditSource = AuditSource.teacher,
    offset_minutes: int = 0,
) -> None:
    db.add(
        AuditEvent(
            assessment_id=assessment.id,
            teacher_id=assessment.teacher_id,
            action=action,
            details_json=details,
            timestamp=_now() + timedelta(minutes=offset_minutes),
            source=source,
            ip_address="127.0.0.1",
        )
    )


def _seed_chat(db: Session, assessment: Assessment) -> None:
    base = _now() - timedelta(hours=1)
    db.add_all(
        [
            ChatMessage(
                assessment_id=assessment.id,
                role="teacher",
                content="Please raise the testing score — integration tests were added in submission_report.md.",
                timestamp=base,
            ),
            ChatMessage(
                assessment_id=assessment.id,
                role="assistant",
                content=(
                    "I've updated the testing criterion based on submission_report.md — "
                    "integration tests now cover login, logout, and task persistence."
                ),
                timestamp=base + timedelta(minutes=1),
            ),
        ]
    )


def _get_demo_students(db: Session) -> tuple[Module, Project, list[Student]]:
    module = (
        db.query(Module).filter(Module.name == DEMO_MODULE_NAME).first()
    )
    if not module:
        raise SystemExit(f"Module not found: {DEMO_MODULE_NAME!r}. Run import seed first.")

    project = (
        db.query(Project)
        .filter(Project.module_id == module.id, Project.name == DEMO_GROUP_NAME)
        .first()
    )
    if not project:
        raise SystemExit(f"Group not found: {DEMO_GROUP_NAME!r}")

    rows = (
        db.query(Student)
        .join(student_projects, Student.student_number == student_projects.c.student_id)
        .filter(student_projects.c.project_id == project.id)
        .order_by(Student.student_number)
        .all()
    )
    return module, project, rows


def simulate(db: Session) -> dict:
    module, project, group_students = _get_demo_students(db)
    demo_students = [s for s in group_students if s.student_number in DEMO_SCENARIOS]
    if len(demo_students) < 4:
        raise SystemExit("Expected at least 4 demo students in the seed group.")

    student_numbers = [s.student_number for s in demo_students]
    _clear_demo_artifacts(db, student_numbers)

    evidence_by_student: dict[str, list[Evidence]] = {}
    for student in demo_students:
        evidence_by_student[student.student_number] = _create_evidence(db, student)
    db.commit()

    overlap_count = len(
        OverlapService.analyze_module_overlap(db, str(module.id))
    )
    db.commit()

    for student in demo_students:
        scenario = DEMO_SCENARIOS[student.student_number]
        assessment = _ensure_assessment(db, student, module)

        evidence_rows = evidence_by_student[student.student_number]

        if scenario == "evidence_only":
            assessment.draft_form_json = None
            assessment.final_form_json = None
            assessment.status = AssessmentStatus.draft
            assessment.completed_at = None
            db.add(assessment)
            continue

        draft = _build_draft(scenario, evidence_rows, assessment.id, db)
        assessment.draft_form_json = draft
        assessment.status = AssessmentStatus.draft
        assessment.final_form_json = None
        assessment.completed_at = None

        _add_audit(
            db,
            assessment=assessment,
            action="assessment.suggestions_generated",
            details={"simulated": True, "criteria_count": len(DEFAULT_CRITERIA)},
            source=AuditSource.ai,
        )

        if scenario == "overrides":
            _add_audit(
                db,
                assessment=assessment,
                action="assessment.suggestion_overridden",
                details={
                    "criterion_key": "crit-1",
                    "ai": draft["criteria"]["crit-1"]["ai"],
                    "teacher": draft["criteria"]["crit-1"]["teacher"],
                },
                offset_minutes=5,
            )
            _add_audit(
                db,
                assessment=assessment,
                action="assessment.chat_refine",
                details={
                    "teacher_message": "Raise testing score — integration tests added.",
                    "updates_applied": 1,
                    "changes": [{"criterion_key": "crit-4"}],
                },
                source=AuditSource.ai,
                offset_minutes=10,
            )
            _seed_chat(db, assessment)

        if scenario == "finalized":
            assessment.status = AssessmentStatus.final
            assessment.completed_at = _now()
            assessment.final_form_json = _final_payload(
                draft,
                "Reviewed with team — finalized for grade export demo.",
            )
            draft["locked"] = True
            assessment.draft_form_json = draft
            _add_audit(
                db,
                assessment=assessment,
                action="assessment.finalized",
                details={
                    "grade": draft["overall_grade"]["effective"],
                    "simulated": True,
                },
                offset_minutes=15,
            )

        db.add(assessment)

    db.commit()

    return {
        "module_id": str(module.id),
        "project_id": str(project.id),
        "overlap_signals": overlap_count,
        "demo_students": list(DEMO_SCENARIOS.keys()),
    }


def main() -> None:
    db = SessionLocal()
    try:
        result = simulate(db)
    finally:
        db.close()

    module_id = result["module_id"]
    project_id = result["project_id"]
    print("Simulated demo environment ready.")
    print(f"  overlap_signals={result['overlap_signals']}")
    print(f"  module_id={module_id}")
    print(f"  group_id={project_id}")
    print()
    print("Log in: admin@admin.com / admin  (or alice.johnson@university.edu / password123)")
    print()
    print("Demo students (Programmeren 2 → CLI Planningsapp in Python):")
    print("  0000001 — AI suggestions only + overlap with 0000002")
    print("  0000002 — teacher overrides + chat refinement + overlap with 0000001")
    print("  0000003 — finalized (read-only) assessment")
    print("  0000004 — evidence uploaded, generate AI yourself")
    print()
    print("Student 001 URL:")
    print(
        f"  http://localhost:3000/modules/{module_id}/groups/{project_id}/students/0000001"
    )
    print("Overlaps page:")
    print(f"  http://localhost:3000/modules/{module_id}/overlaps")


if __name__ == "__main__":
    main()
