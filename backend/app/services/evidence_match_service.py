import uuid as _uuid
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.ai import ai_judge, evidence_matcher
from app.ai.chunking import chunk_text
from app.ai.evidence_matcher import EvidenceChunk
from app.ai.rubric_criteria import extract_criteria
from app.config import settings
from app.models.assessment import Assessment
from app.models.enums import AuditSource
from app.models.evidence import Evidence
from app.models.evidence_match import EvidenceMatch
from app.models.file_record import FileRecord
from app.models.generation_run import GenerationRun
from app.models.module import Module
from app.models.project import Project
from app.models.student import Student, student_projects
from app.models.teacher import Teacher
from app.services import assessment_service, audit_service
from app.services.evidence_service import _full_path_for
from app.services.module_service import RUBRIC_UPLOAD_DIR

_MISSING_NOTE = "No supporting evidence found"


def _mode_settings(mode: str) -> tuple[str, int, str]:
    if mode == "thorough":
        return (
            "thorough",
            settings.MATCH_CANDIDATE_POOL_THOROUGH,
            settings.MATCH_AI_MODEL_THOROUGH,
        )
    return "standard", settings.MATCH_CANDIDATE_POOL, settings.MATCH_AI_MODEL


def run_matching(
    db: Session,
    *,
    student_id: str,
    teacher: Teacher,
    module_id=None,
    mode: str = "standard",
) -> dict:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found")

    module, rubric = _resolve_module_and_rubric(db, student, teacher, module_id)

    criteria = extract_criteria(
        _rubric_path(module, rubric),
        f".{rubric.file_type}" if rubric.file_type else None,
        rubric.extracted_text,
    )
    if not criteria:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Could not read any criteria from the rubric. Re-upload it as a "
            "structured .xlsx file (one criterion per row).",
        )

    mode, candidate_pool, ai_model = _mode_settings(mode)
    chunks = _evidence_chunks(db, student_id)

    candidate_results = evidence_matcher.match_criteria(
        criteria,
        chunks,
        threshold=0.0,
        top_k=candidate_pool,
    )

    assessment = assessment_service.get_or_create_for_student(
        db, student_id=student_id, teacher=teacher, module_id=module.id
    )

    run = GenerationRun(
        assessment_id=assessment.id,
        created_by=teacher.id,
        mode=mode,
        ai_model=ai_model if settings.MATCH_USE_AI else None,
        criteria_total=len(criteria),
        expires_at=datetime.utcnow()
        + timedelta(days=settings.GENERATION_RETENTION_DAYS),
    )
    db.add(run)
    db.flush()

    covered = 0
    ai_used = False
    for result in candidate_results:
        pool = [(i, m) for i, m in enumerate(result.matches) if m.score > 0]

        verdict = None
        if settings.MATCH_USE_AI and pool:
            verdict = ai_judge.judge_criterion(
                result.criterion.text,
                [(label, m.chunk.text) for label, m in pool],
                model=ai_model,
            )
            if verdict is not None:
                ai_used = True

        tfidf_best = pool[0][1] if pool else None
        very_strong = (
            tfidf_best is not None
            and tfidf_best.score >= settings.MATCH_STRONG_THRESHOLD
        )
        grounded = (
            tfidf_best is not None
            and tfidf_best.score >= settings.MATCH_CONFIDENCE_THRESHOLD
        )
        ai_available = verdict is not None
        ai_supported = ai_available and verdict["supported"]
        ai_rejected = ai_available and not verdict["supported"]

        chosen = None
        rationale = None
        note = _MISSING_NOTE

        if very_strong or (grounded and not ai_rejected):
            chosen = tfidf_best
            if ai_supported:
                rationale = verdict["reason"] or None
        elif ai_rejected and verdict["reason"]:
            note = verdict["reason"]

        if chosen is not None:
            covered += 1
            db.add(
                EvidenceMatch(
                    assessment_id=assessment.id,
                    run_id=run.id,
                    criterion_key=result.criterion.key,
                    evidence_id=_uuid.UUID(chosen.chunk.evidence_id),
                    chunk_index=chosen.chunk.chunk_index,
                    confidence_score=round(chosen.score, 4),
                    supporting_quote=chosen.chunk.text,
                    rationale=rationale,
                )
            )
        else:
            db.add(
                EvidenceMatch(
                    assessment_id=assessment.id,
                    run_id=run.id,
                    criterion_key=result.criterion.key,
                    missing_note=note,
                )
            )

    run.criteria_covered = covered
    run.ai_used = ai_used

    audit_service.log_action(
        db,
        action="ai.evidence_matching.run",
        source=AuditSource.ai,
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        assessment_id=assessment.id,
        details={
            "run_id": str(run.id),
            "mode": mode,
            "module_id": str(module.id),
            "criteria_total": len(criteria),
            "criteria_covered": covered,
            "evidence_chunks": len(chunks),
            "ai_used": ai_used,
        },
        commit=False,
    )
    db.commit()

    return _build_report(db, assessment, run)


def get_report(
    db: Session, *, student_id: str, teacher: Teacher, run_id=None
) -> dict:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found")

    assessment = _latest_assessment(db, student_id, teacher)
    if assessment is None:
        return _empty_report()

    runs = _runs_for(db, assessment)
    if not runs:
        return _empty_report(assessment)

    if run_id is not None:
        run = next((r for r in runs if r.id == run_id), None)
        if run is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    else:
        run = runs[0]

    return _build_report(db, assessment, run, runs=runs)


def delete_run(
    db: Session, *, student_id: str, teacher: Teacher, run_id
) -> dict:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found")

    assessment = _latest_assessment(db, student_id, teacher)
    run = None
    if assessment is not None:
        run = (
            db.query(GenerationRun)
            .filter(
                GenerationRun.id == run_id,
                GenerationRun.assessment_id == assessment.id,
            )
            .first()
        )
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")

    db.delete(run)
    audit_service.log_action(
        db,
        action="ai.evidence_matching.run_deleted",
        source=AuditSource.teacher,
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        assessment_id=assessment.id,
        details={"run_id": str(run_id)},
        commit=False,
    )
    db.commit()

    return get_report(db, student_id=student_id, teacher=teacher)


def _latest_assessment(db: Session, student_id: str, teacher: Teacher):
    return (
        db.query(Assessment)
        .filter_by(student_id=student_id, teacher_id=teacher.id)
        .order_by(Assessment.created_at.desc())
        .first()
    )


def _runs_for(db: Session, assessment) -> list[GenerationRun]:
    return (
        db.query(GenerationRun)
        .filter(GenerationRun.assessment_id == assessment.id)
        .order_by(GenerationRun.created_at.desc())
        .all()
    )


def _empty_report(assessment=None) -> dict:
    return {
        "assessment_id": assessment.id if assessment else None,
        "module_id": assessment.module_id if assessment else None,
        "run_id": None,
        "created_at": None,
        "mode": None,
        "expires_at": None,
        "criteria": [],
        "runs": [],
    }


def _resolve_module_and_rubric(
    db: Session, student: Student, teacher: Teacher, module_id
) -> tuple[Module, FileRecord]:
    if module_id is not None:
        module = (
            db.query(Module)
            .filter(Module.id == module_id, Module.teacher_id == teacher.id)
            .first()
        )
        if module is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Module not found")
    else:
        modules = (
            db.query(Module)
            .join(Project, Project.module_id == Module.id)
            .join(student_projects, student_projects.c.project_id == Project.id)
            .filter(
                student_projects.c.student_id == student.student_number,
                Module.teacher_id == teacher.id,
                Module.rubric_file_id.isnot(None),
            )
            .distinct()
            .all()
        )
        if not modules:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "No rubric is attached to this student's module.",
            )
        if len(modules) > 1:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "This student is in several modules; specify which one to grade "
                f"(module_id). Candidates: {[str(m.id) for m in modules]}",
            )
        module = modules[0]

    if not module.rubric_file_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "This module has no rubric attached.",
        )
    rubric = db.get(FileRecord, module.rubric_file_id)
    if rubric is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "The module's rubric file record is missing.",
        )
    return module, rubric


def _rubric_path(module: Module, rubric: FileRecord):
    return RUBRIC_UPLOAD_DIR / str(module.id) / rubric.path


def _evidence_chunks(db: Session, student_id: str) -> list[EvidenceChunk]:
    evidence_list = (
        db.query(Evidence).filter(Evidence.student_id == student_id).all()
    )
    chunks: list[EvidenceChunk] = []
    for evidence in evidence_list:
        text = _evidence_text(evidence)
        if not text:
            continue
        for index, chunk in enumerate(
            chunk_text(
                text,
                chunk_size=settings.MATCH_CHUNK_SIZE,
                overlap=settings.MATCH_CHUNK_OVERLAP,
            )
        ):
            chunks.append(
                EvidenceChunk(
                    evidence_id=str(evidence.id),
                    chunk_index=index,
                    text=chunk,
                )
            )
    return chunks


def _evidence_text(evidence: Evidence) -> str | None:
    from app.services.evidence_service import EvidenceService

    full_path = _full_path_for(evidence.file_path)
    if not full_path.exists():
        return None
    try:
        return EvidenceService._read_or_rebuild_text_content(evidence)
    except Exception:
        return None


def _run_summary(run: GenerationRun, now: datetime) -> dict:
    return {
        "run_id": run.id,
        "created_at": run.created_at,
        "mode": run.mode,
        "ai_model": run.ai_model,
        "ai_used": run.ai_used,
        "criteria_total": run.criteria_total,
        "criteria_covered": run.criteria_covered,
        "expires_at": run.expires_at,
        "expired": run.expires_at is not None and run.expires_at <= now,
    }


def _build_report(
    db: Session,
    assessment,
    run: GenerationRun,
    runs: list[GenerationRun] | None = None,
) -> dict:
    rows = (
        db.query(EvidenceMatch)
        .filter(EvidenceMatch.run_id == run.id)
        .all()
    )

    groups: dict[str, dict] = {}
    for row in rows:
        group = groups.setdefault(
            row.criterion_key, {"matches": [], "missing_note": None}
        )
        if row.evidence_id is not None:
            group["matches"].append(
                {
                    "evidence_id": row.evidence_id,
                    "file_name": row.evidence.file_name if row.evidence else None,
                    "file_type": (
                        row.evidence.file_type.value
                        if row.evidence and row.evidence.file_type
                        else None
                    ),
                    "chunk_index": row.chunk_index,
                    "supporting_quote": row.supporting_quote,
                    "confidence_score": row.confidence_score,
                    "rationale": row.rationale,
                }
            )
        elif row.missing_note:
            group["missing_note"] = row.missing_note

    criteria = []
    for key in sorted(groups):
        group = groups[key]
        group["matches"].sort(
            key=lambda m: m["confidence_score"] or 0.0, reverse=True
        )
        criteria.append(
            {
                "criterion_key": key,
                "covered": bool(group["matches"]),
                "missing_note": group["missing_note"],
                "matches": group["matches"],
            }
        )

    if runs is None:
        runs = _runs_for(db, assessment)
    now = datetime.utcnow()

    return {
        "assessment_id": assessment.id,
        "module_id": assessment.module_id,
        "run_id": run.id,
        "created_at": run.created_at,
        "mode": run.mode,
        "expires_at": run.expires_at,
        "criteria": criteria,
        "runs": [_run_summary(r, now) for r in runs],
    }
