"""Assessment-level operations for recording consent (G2-137, G2-138).

Consent is oral (spoken at the start of the recording) but confirmed by the
teacher after reviewing the transcript's opening segment. A declined assessment
proceeds without audio and the form shows "recording declined".
"""
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.assessment import Assessment
from app.models.enums import ConsentStatus
from app.models.student import Student
from app.models.teacher import Teacher
from app.services import audit_service


def get_or_create_for_student(
    db: Session, *, student_id: str, teacher: Teacher
) -> Assessment | None:
    """Return the current teacher's assessment for a student, creating one if none.

    Recording/consent endpoints are keyed on an assessment id; the UI only knows
    the student, so it resolves (or lazily creates) the assessment here. Returns
    None if the student does not exist (caller raises 404).
    """
    student = db.get(Student, student_id)
    if student is None:
        return None

    assessment = (
        db.query(Assessment)
        .filter(
            Assessment.student_id == student_id,
            Assessment.teacher_id == teacher.id,
        )
        .order_by(Assessment.created_at.desc())
        .first()
    )
    if assessment is not None:
        return assessment

    assessment = Assessment(student_id=student_id, teacher_id=teacher.id)
    db.add(assessment)
    db.flush()  # populate assessment.id
    audit_service.log_action(
        db,
        action="assessment.created",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        assessment_id=assessment.id,
        details={"student_id": str(student_id)},
        commit=False,
    )
    db.commit()
    db.refresh(assessment)
    return assessment


def set_consent(
    db: Session,
    *,
    assessment: Assessment,
    teacher: Teacher,
    status: ConsentStatus,
    ip_address: str | None = None,
) -> Assessment:
    """Record the teacher's consent decision for an assessment.

    ``accepted``  — student gave oral consent; recording is kept.
    ``declined``  — student refused; assessment proceeds without audio.
    """
    if status == ConsentStatus.pending:
        raise ValueError("Cannot set consent back to pending")

    assessment.consent_status = status
    assessment.consent_confirmed_at = datetime.utcnow()
    assessment.consent_confirmed_by = teacher.id

    audit_service.log_action(
        db,
        action=f"consent.{status.value}",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        assessment_id=assessment.id,
        details={"consent_status": status.value},
        ip_address=ip_address,
        commit=False,
    )
    db.commit()
    db.refresh(assessment)
    return assessment
