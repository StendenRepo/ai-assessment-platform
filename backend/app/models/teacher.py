import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    email = Column(String, unique=True)
    pin_hash = Column(String, nullable=True)
    password_hash = Column(String, nullable=True)
    is_admin = Column(Boolean, nullable=False, default=False, server_default="false")
    is_seed = Column(Boolean, nullable=False, default=False, server_default="false")
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    department = relationship("Department", back_populates="teachers")
    modules = relationship("Module", back_populates="teacher", foreign_keys="Module.teacher_id")
    co_taught_modules = relationship(
        "Module",
        secondary="module_teachers",
        back_populates="co_teachers",
    )
    assessments = relationship(
        "Assessment",
        back_populates="teacher",
        foreign_keys="Assessment.teacher_id",
    )
    audit_events = relationship("AuditEvent", back_populates="teacher")
