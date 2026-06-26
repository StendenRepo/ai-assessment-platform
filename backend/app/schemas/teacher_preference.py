"""Schemas for teacher UI preferences."""
from pydantic import BaseModel

from app.models.enums import Theme, DateFormat, Language


class TeacherPreferenceOut(BaseModel):
    """Current teacher's UI preferences."""

    theme: Theme
    date_format: DateFormat
    language: Language

    model_config = {"from_attributes": True}


class TeacherPreferenceUpdate(BaseModel):
    """Payload for updating teacher preferences (all optional)."""

    theme: Theme | None = None
    date_format: DateFormat | None = None
    language: Language | None = None
