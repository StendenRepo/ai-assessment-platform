import uuid
from sqlalchemy import Column, String, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
from app.models.enums import FileType, SourceType, EmbeddingStatus


class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(String, ForeignKey("students.student_number"), nullable=False)
    file_name = Column(String, nullable=False)
    file_type = Column(Enum(FileType))
    file_path = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    source_type = Column(Enum(SourceType))
    embedding_status = Column(Enum(EmbeddingStatus), default=EmbeddingStatus.pending)

    # Relationships
    student = relationship("Student", back_populates="evidence")
    evidence_matches = relationship("EvidenceMatch", back_populates="evidence")
