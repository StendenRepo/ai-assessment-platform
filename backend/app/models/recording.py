import uuid
from sqlalchemy import Column, String, Integer, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.encrypted_types import EncryptedText
from app.database import Base
from app.models.enums import TranscriptionStatus


class Recording(Base):
    """A single audio recording belonging to an assessment (FR-06, many per assessment).

    Consent is captured once on the assessment; each recording has its own file,
    transcript, transcription status and (via file_records) its own expiry.
    """

    __tablename__ = "recordings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id = Column(
        UUID(as_uuid=True), ForeignKey("assessments.id"), nullable=False
    )
    file_id = Column(UUID(as_uuid=True), ForeignKey("file_records.id"), nullable=True)
    display_name = Column(String, nullable=False)
    sequence_number = Column(Integer, nullable=False)
    transcript_text = Column(EncryptedText, nullable=True)
    transcription_status = Column(
        Enum(TranscriptionStatus), default=TranscriptionStatus.pending, nullable=False
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    # Soft-delete: row is kept for the audit trail; the file on disk is unlinked.
    deleted_at = Column(DateTime, nullable=True)

    assessment = relationship("Assessment", back_populates="recordings")
    file = relationship("FileRecord")
