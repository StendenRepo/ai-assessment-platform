import uuid
from sqlalchemy import Column, String, Boolean, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.enums import StudentStatus


class Student(Base):
    __tablename__ = "students"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    name = Column(String, nullable=False)
    student_number = Column(String)
    status = Column(Enum(StudentStatus), default=StudentStatus.active)
    consent_given = Column(Boolean, default=False)

    # Relationships
    project = relationship("Project", back_populates="students")
    evidence = relationship("Evidence", back_populates="student")
    assessments = relationship("Assessment", back_populates="student")
