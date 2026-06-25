"""Per-teacher UI preferences service (theme, language, date format).

Handles get/set/upsert for teacher UI preferences with defaults.
Every write is audited in the same transaction (NFR-02).
"""
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.enums import Theme, DateFormat, Language
from app.models.teacher_preference import TeacherPreference
from app.models.teacher import Teacher
from app.services import audit_service


def get_or_create_preferences(
    db: Session, *, teacher_id: UUID
) -> TeacherPreference:
    """Get preferences for a teacher, creating defaults if needed."""
    pref = (
        db.query(TeacherPreference)
        .filter(TeacherPreference.teacher_id == teacher_id)
        .first()
    )
    if pref is None:
        pref = TeacherPreference(
            teacher_id=teacher_id,
            theme=Theme.light.value,
            date_format=DateFormat.dd_mm_yyyy.value,
            language=Language.en.value,
        )
        db.add(pref)
        db.commit()
        db.refresh(pref)
    return pref


def set_preference(
    db: Session,
    *,
    teacher: Teacher,
    theme: Optional[Theme] = None,
    date_format: Optional[DateFormat] = None,
    language: Optional[Language] = None,
    ip_address: Optional[str] = None,
) -> TeacherPreference:
    """Update teacher preferences and audit the change in the same transaction.

    Returns the persisted row. The preference write and its audit entry are
    flushed together and committed once so NFR-02 holds even on partial failure.
    """
    pref = (
        db.query(TeacherPreference)
        .filter(TeacherPreference.teacher_id == teacher.id)
        .first()
    )
    if pref is None:
        pref = TeacherPreference(teacher_id=teacher.id)
        db.add(pref)

    details = {}
    if theme is not None:
        pref.theme = theme
        details["theme"] = theme.value

    if date_format is not None:
        pref.date_format = date_format
        details["date_format"] = date_format.value

    if language is not None:
        pref.language = language
        details["language"] = language.value

    audit_service.log_action(
        db,
        action="teacher_preference.updated",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        details=details,
        ip_address=ip_address,
        commit=False,
    )

    db.commit()
    db.refresh(pref)
    return pref
