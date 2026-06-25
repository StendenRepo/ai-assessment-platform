from sqlalchemy import Column, String, DateTime, BigInteger, Integer, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base
from app.models.enums import AuditSource


class AuditEvent(Base):
    __tablename__ = "audit_events"

    # BigInteger on Postgres; Integer on SQLite so it aliases rowid and autoincrements (tests).
    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    assessment_id = Column(UUID(as_uuid=True), ForeignKey("assessments.id"), nullable=True)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=True)
    action = Column(String, nullable=False)
    details_json = Column(JSONB, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    source = Column(Enum(AuditSource))
    ip_address = Column(INET, nullable=True)

    teacher = relationship("Teacher", back_populates="audit_events")
