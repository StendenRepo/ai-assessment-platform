"""Per-teacher UI preferences (theme, language, date format).

A single row per teacher storing UI and localization preferences.
Default values are provided if no row exists yet.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.enums import Theme, DateFormat, Language


class TeacherPreference(Base):
    __tablename__ = "teacher_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id = Column(
        UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=False, unique=True
    )
    theme = Column(
        Enum(Theme), nullable=False, default=Theme.light, server_default="light"
    )
    date_format = Column(
        Enum(DateFormat),
        nullable=False,
        default=DateFormat.dd_mm_yyyy,
        server_default="DD-MM-YYYY",
    )
    language = Column(
        Enum(Language), nullable=False, default=Language.en, server_default="en"
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    teacher = relationship("Teacher")
