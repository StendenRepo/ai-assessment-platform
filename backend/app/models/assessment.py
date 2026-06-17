import uuid
from sqlalchemy import Column, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
from app.models.enums import AssessmentStatus, ConsentStatus


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(String, ForeignKey("students.student_number"), nullable=False)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=False)
    module_id = Column(UUID(as_uuid=True), ForeignKey("modules.id"), nullable=True)
    status = Column(Enum(AssessmentStatus), default=AssessmentStatus.draft)
    draft_form_json = Column(JSONB, nullable=True)
    final_form_json = Column(JSONB, nullable=True)
    # Oral consent captured once per assessment, confirmed by the teacher.
    # Transcript/status/file now live on the recordings table (one assessment,
    # many recordings).
    consent_status = Column(
        Enum(ConsentStatus), default=ConsentStatus.pending, nullable=False
    )
    consent_confirmed_at = Column(DateTime, nullable=True)
    consent_confirmed_by = Column(
        UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=True
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    student = relationship("Student", back_populates="assessments")
    module = relationship("Module")
    teacher = relationship(
        "Teacher", back_populates="assessments", foreign_keys=[teacher_id]
    )
    chat_messages = relationship("ChatMessage", back_populates="assessment")
    evidence_matches = relationship("EvidenceMatch", back_populates="assessment")
    generation_runs = relationship(
        "GenerationRun",
        back_populates="assessment",
        order_by="GenerationRun.created_at.desc()",
        cascade="all, delete-orphan",
    )
    recordings = relationship(
        "Recording", back_populates="assessment", order_by="Recording.sequence_number"
    )
