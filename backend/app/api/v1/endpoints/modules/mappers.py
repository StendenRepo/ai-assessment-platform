"""Response mappers for module endpoints."""
from __future__ import annotations

import json
from typing import Optional

from sqlalchemy.orm import Session

from app.models.assessment import Assessment
from app.models.file_record import FileRecord
from app.models.module import Module
from app.models.project import Project
from app.models.student import Student
from app.schemas.module import ModuleOut, RubricFileOut
from app.schemas.overlap import OverlapSignalOut
from app.schemas.project import ProjectOut, StudentOut
from app.services.overlap.integrity import derive_signal_metrics
from app.services.overlap.markers import dedupe_student_flag_dicts
from app.services.overlap.service import build_highlighted_documents, parse_signal_detail


def _assessment_status(latest: Optional[Assessment]) -> str:
    if latest is None:
        return "not-started"
    if latest.status.value == "final":
        return "completed"
    return "in-progress"


def _assessment_grade(latest: Optional[Assessment]) -> Optional[str]:
    if latest is None:
        return None

    for payload in (latest.final_form_json, latest.draft_form_json):
        data = payload
        if isinstance(payload, str):
            try:
                data = json.loads(payload)
            except Exception:
                continue

        if isinstance(data, dict):
            raw_grade = data.get("grade")
            if raw_grade is None:
                continue
            grade = str(raw_grade).strip()
            if grade:
                return grade
    return None


def _student_to_out(
    s: Student,
    assessment_status: str = "not-started",
    grade: Optional[str] = None,
    project_id: Optional[str] = None,
) -> StudentOut:
    return StudentOut(
        id=s.student_number,
        name=s.name,
        student_number=s.student_number,
        github_repo_url=s.github_repo_url,
        github_branch=s.github_branch,
        status=s.status.value if s.status else "active",
        consent_given=bool(s.consent_given),
        assessment_status=assessment_status,
        grade=grade,
        project_id=project_id,
    )


def _group_to_out(p: Project, student_count: int, file_count: int = 0) -> ProjectOut:
    return ProjectOut(
        id=str(p.id),
        name=p.name,
        group_name=p.group_name,
        github_repo_url=p.github_repo_url,
        github_branch=p.github_branch,
        module_id=str(p.module_id),
        status=p.status.value if p.status else "active",
        created_at=p.created_at,
        student_count=student_count,
        file_count=file_count,
    )


def _rubric_file_out(record: Optional[FileRecord]) -> Optional[RubricFileOut]:
    if not record:
        return None
    return RubricFileOut(
        id=str(record.id),
        file_name=record.file_name,
        file_type=record.file_type,
        size_bytes=record.size_bytes,
        uploaded_at=record.uploaded_at,
    )


def _module_to_out(m: Module, project_count: int, student_count: int, db: Session) -> ModuleOut:
    rubric = None
    if m.rubric_file_id:
        rubric = db.query(FileRecord).filter(FileRecord.id == m.rubric_file_id).first()
    module_book = None
    if m.module_book_id:
        module_book = db.query(FileRecord).filter(FileRecord.id == m.module_book_id).first()
    return ModuleOut(
        id=str(m.id),
        name=m.name,
        academic_year=m.academic_year,
        deadline=m.deadline,
        status=m.status.value if m.status else "active",
        created_at=m.created_at,
        project_count=project_count,
        student_count=student_count,
        rubric_file=_rubric_file_out(rubric),
        module_book_file=_rubric_file_out(module_book),
    )


def _signal_to_out(
    signal,
    student_names: dict,
    evidence_names: dict,
    *,
    db: Session | None = None,
    include_documents: bool = False,
) -> OverlapSignalOut:
    detail = parse_signal_detail(signal.snippet)
    confidence = round(float(signal.confidence or 0.0), 2)
    status = detail.get("status")
    if not status:
        status = "confirmed" if confidence >= 0.68 else "possible"
    integrity_type = detail.get("integrity_type") or "student_plagiarism"
    if integrity_type == "ai":
        view_mode = "single"
    else:
        view_mode = "side_by_side"
    document_a = document_b = None
    effective_flags = dedupe_student_flag_dicts(detail.get("flags") or [])
    if include_documents and db is not None:
        document_a, document_b, effective_flags = build_highlighted_documents(
            db, signal, detail=detail
        )
    metrics = derive_signal_metrics(detail, confidence, integrity_type)
    return OverlapSignalOut(
        id=str(signal.id),
        student_a_id=str(signal.student_a_id),
        student_a_name=student_names.get(signal.student_a_id, "Unknown student"),
        student_b_id=str(signal.student_b_id),
        student_b_name=student_names.get(signal.student_b_id, "Unknown student"),
        evidence_a_id=str(signal.evidence_a_id),
        evidence_a_name=evidence_names.get(signal.evidence_a_id, "Unknown evidence"),
        evidence_b_id=str(signal.evidence_b_id),
        evidence_b_name=evidence_names.get(signal.evidence_b_id, "Unknown evidence"),
        overlap_type=signal.overlap_type.value if signal.overlap_type else "textual",
        confidence=confidence,
        snippet=signal.snippet
        if not detail
        else detail.get("passage_a") or signal.snippet,
        detected_at=signal.detected_at,
        status=status,
        scope=detail.get("scope"),
        passage_a=detail.get("passage_a"),
        passage_b=detail.get("passage_b"),
        document_a=document_a,
        document_b=document_b,
        group_a_id=detail.get("group_a_id"),
        group_b_id=detail.get("group_b_id"),
        group_a_name=detail.get("group_a_name"),
        group_b_name=detail.get("group_b_name"),
        ai_verified=detail.get("ai_verified"),
        ai_explanation=detail.get("ai_explanation"),
        detection_method=detail.get("detection_method"),
        integrity_type=integrity_type,
        flags=effective_flags or None,
        view_mode=view_mode,
        ai_content_percent=metrics.get("ai_content_percent"),
        peak_ai_section_percent=metrics.get("peak_ai_section_percent"),
        student_match_count=metrics.get("student_match_count"),
        overlap_confidence_percent=metrics.get("overlap_confidence_percent"),
        detection_confidence_percent=metrics.get("detection_confidence_percent"),
        metrics_summary=metrics.get("metrics_summary"),
    )
