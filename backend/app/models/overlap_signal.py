import uuid
from sqlalchemy import Column, Float, String, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from app.core.encrypted_types import EncryptedText
from app.database import Base
from app.models.enums import OverlapType


class OverlapSignal(Base):
    __tablename__ = "overlap_signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_a_id = Column(String, ForeignKey("students.student_number"), nullable=False)
    student_b_id = Column(String, ForeignKey("students.student_number"), nullable=False)
    evidence_a_id = Column(UUID(as_uuid=True), ForeignKey("evidence.id"), nullable=False)
    evidence_b_id = Column(UUID(as_uuid=True), ForeignKey("evidence.id"), nullable=False)
    overlap_type = Column(Enum(OverlapType), default=OverlapType.textual)
    confidence = Column(Float)
    snippet = Column(EncryptedText)
    detected_at = Column(DateTime, default=datetime.utcnow)
