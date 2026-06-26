import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class RubricScore(Base):
    __tablename__ = "rubric_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=False,
    )
    rubric_id = Column(
        UUID(as_uuid=True),
        ForeignKey("module_rubrics.id", ondelete="CASCADE"),
        nullable=False,
    )
    score = Column(Float, nullable=True)
    grade = Column(String, nullable=True)
    teacher_score = Column(Float, nullable=True)
    summary = Column(Text, nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow)

    rubric = relationship("ModuleRubric")
