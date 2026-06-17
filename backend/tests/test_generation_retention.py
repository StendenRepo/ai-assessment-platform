import uuid
from datetime import datetime, timedelta

import pytest

from app.config import settings
from app.models.enums import NotificationType
from app.services import retention_service


@pytest.fixture
def assessment_with_run(db, teacher):
    from app.models.assessment import Assessment
    from app.models.generation_run import GenerationRun
    from app.models.notification import Notification
    from app.models.student import Student

    student = Student(student_number="S-900", name="Carol")
    db.add(student)
    db.flush()

    assessment = Assessment(
        id=uuid.uuid4(), student_id="S-900", teacher_id=teacher.id
    )
    db.add(assessment)
    db.flush()

    run = GenerationRun(
        id=uuid.uuid4(),
        assessment_id=assessment.id,
        created_by=teacher.id,
        mode="standard",
        criteria_total=3,
        criteria_covered=2,
        expires_at=datetime.utcnow()
        + timedelta(days=settings.GENERATION_REMINDER_LEAD_DAYS - 1),
    )
    db.add(run)
    db.commit()

    yield {"assessment": assessment, "run": run, "teacher": teacher}

    db.query(Notification).delete(synchronize_session=False)
    db.query(GenerationRun).delete(synchronize_session=False)
    db.query(Assessment).delete(synchronize_session=False)
    db.query(Student).filter(Student.student_number == "S-900").delete(
        synchronize_session=False
    )
    db.commit()
    db.expire_all()


def test_reminder_created_once_for_expiring_run(db, assessment_with_run):
    from app.models.notification import Notification

    run = assessment_with_run["run"]

    created = retention_service.create_generation_retention_reminders(db)
    assert created == 1

    note = (
        db.query(Notification)
        .filter(Notification.generation_run_id == run.id)
        .one()
    )
    assert note.type == NotificationType.deletion_reminder
    assert note.teacher_id == assessment_with_run["teacher"].id

    assert retention_service.create_generation_retention_reminders(db) == 0


def test_no_reminder_when_far_from_expiry(db, assessment_with_run):
    run = assessment_with_run["run"]
    run.expires_at = datetime.utcnow() + timedelta(
        days=settings.GENERATION_REMINDER_LEAD_DAYS + 30
    )
    db.commit()

    assert retention_service.create_generation_retention_reminders(db) == 0
