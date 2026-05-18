import uuid
from sqlalchemy import Column, String, DateTime, Boolean, Text, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
from app.models.enums import AssessmentStatus


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=False)
    status = Column(Enum(AssessmentStatus), default=AssessmentStatus.draft)
    draft_form_json = Column(JSONB, nullable=True)
    final_form_json = Column(JSONB, nullable=True)
    recording_file_id = Column(UUID(as_uuid=True), ForeignKey("file_records.id"), nullable=True)
    transcript_text = Column(Text, nullable=True)
    consent_recorded = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    student = relationship("Student", back_populates="assessments")
    teacher = relationship("Teacher", back_populates="assessments")
    chat_messages = relationship("ChatMessage", back_populates="assessment")
    evidence_matches = relationship("EvidenceMatch", back_populates="assessment")
