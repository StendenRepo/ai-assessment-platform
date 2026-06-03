import uuid
from sqlalchemy import Column, String, DateTime, Date, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
from app.models.enums import ProjectStatus


class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    module_id = Column(UUID(as_uuid=True), ForeignKey("modules.id"), nullable=True)
    name = Column(String, nullable=False)
    course = Column(String, nullable=True)
    group_name = Column(String, nullable=True)
    deadline = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(Enum(ProjectStatus), default=ProjectStatus.active)

    # Relationships
    module = relationship("Module", back_populates="projects")
    students = relationship("Student", back_populates="project")
