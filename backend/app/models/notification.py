import uuid
from sqlalchemy import Column, DateTime, Text, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
from app.models.enums import NotificationType


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=False)
    assessment_id = Column(
        UUID(as_uuid=True), ForeignKey("assessments.id"), nullable=True
    )
    # Specific recording this notification concerns (G2-142). Nullable so older
    # assessment-only reminders remain valid.
    recording_id = Column(
        UUID(as_uuid=True), ForeignKey("recordings.id"), nullable=True
    )
    generation_run_id = Column(
        UUID(as_uuid=True), ForeignKey("generation_runs.id"), nullable=True
    )
    type = Column(Enum(NotificationType), nullable=False)
    message = Column(Text, nullable=False)
    target_path = Column(String, nullable=True)
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    read_at = Column(DateTime, nullable=True)

    teacher = relationship("Teacher")
    assessment = relationship("Assessment")
    recording = relationship("Recording")
    generation_run = relationship("GenerationRun")
