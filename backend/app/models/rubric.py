"""RubricCriterion model.

A criterion belongs to one Project. Categories are stored as a free-form string
rather than a PG enum or a separate `categories` table, on purpose: Walter has
flagged that new categories may be introduced later, and a String column lets
us extend the whitelist with a one-line Pydantic change instead of a DB
migration. The trade-off is that DB-level integrity for the category value is
weaker — we rely on the API layer (schemas/rubric.py) to enforce the
allowed set. All writes go through that single router, so in practice the
constraint holds.

Timestamps on this table are timezone-aware (TIMESTAMPTZ) per the rubric spec.
This is intentionally different from older tables in this codebase which use
naive UTC; flagged in code review as something to align project-wide.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RubricCriterion(Base):
    __tablename__ = "rubric_criteria"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    points = Column(Integer, nullable=False)
    position = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )

    project = relationship("Project", back_populates="rubric_criteria")
