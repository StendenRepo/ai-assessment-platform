import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class GenerationRun(Base):
    __tablename__ = "generation_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id = Column(
        UUID(as_uuid=True), ForeignKey("assessments.id"), nullable=False
    )
    created_by = Column(
        UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=True
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    mode = Column(String, nullable=False, default="standard")
    ai_model = Column(String, nullable=True)
    ai_used = Column(Boolean, nullable=False, default=False)
    criteria_total = Column(Integer, nullable=False, default=0)
    criteria_covered = Column(Integer, nullable=False, default=0)
    flagged_for_deletion = Column(Boolean, nullable=False, default=False)

    assessment = relationship("Assessment", back_populates="generation_runs")
    matches = relationship(
        "EvidenceMatch",
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
