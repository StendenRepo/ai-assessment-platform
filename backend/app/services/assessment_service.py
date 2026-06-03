"""Assessment-level operations for recording consent (G2-137, G2-138).

Consent is oral (spoken at the start of the recording) but confirmed by the
teacher after reviewing the transcript's opening segment. A declined assessment
proceeds without audio and the form shows "recording declined".
"""
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.assessment import Assessment
from app.models.enums import ConsentStatus
from app.models.teacher import Teacher
from app.services import audit_service


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
