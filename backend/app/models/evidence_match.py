import uuid
from sqlalchemy import Column, String, Float, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class EvidenceMatch(Base):
    __tablename__ = "evidence_matches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id = Column(UUID(as_uuid=True), ForeignKey("assessments.id"), nullable=False)
    criterion_key = Column(String, nullable=False)
    evidence_id = Column(UUID(as_uuid=True), ForeignKey("evidence.id"), nullable=True)
    chunk_index = Column(Integer)
    confidence_score = Column(Float)
    supporting_quote = Column(Text)
    missing_note = Column(Text, nullable=True)
    rationale = Column(Text, nullable=True)

    # Relationships
    assessment = relationship("Assessment", back_populates="evidence_matches")
    evidence = relationship("Evidence", back_populates="evidence_matches")
