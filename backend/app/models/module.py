import uuid
from sqlalchemy import Column, String, DateTime, Enum, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
from app.models.enums import ModuleStatus


# Association table for module co-teachers (many-to-many)
module_teachers = Table(
    "module_teachers",
    Base.metadata,
    Column(
        "module_id",
        UUID(as_uuid=True),
        ForeignKey("modules.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "teacher_id",
        UUID(as_uuid=True),
        ForeignKey("teachers.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Module(Base):
    __tablename__ = "modules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=False)
    name = Column(String, nullable=False)
    academic_year = Column(String)
    deadline = Column(String)
    rubric_file_id = Column(UUID(as_uuid=True), ForeignKey("file_records.id"), nullable=True)
    module_book_id = Column(UUID(as_uuid=True), ForeignKey("file_records.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(Enum(ModuleStatus), default=ModuleStatus.active)

    # Relationships
    teacher = relationship("Teacher", back_populates="modules", foreign_keys=[teacher_id])
    projects = relationship("Project", back_populates="module")
    co_teachers = relationship(
        "Teacher",
        secondary=module_teachers,
        back_populates="co_taught_modules",
    )
