import uuid
from sqlalchemy import Column, String, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
from app.models.enums import ModuleStatus


class Module(Base):
    __tablename__ = "modules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=False)
    name = Column(String, nullable=False)
    academic_year = Column(String)
    rubric_file_id = Column(UUID(as_uuid=True), ForeignKey("file_records.id"), nullable=True)
    module_book_id = Column(UUID(as_uuid=True), ForeignKey("file_records.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(Enum(ModuleStatus), default=ModuleStatus.active)

    # Relationships
    teacher = relationship("Teacher", back_populates="modules")
    projects = relationship("Project", back_populates="module")
