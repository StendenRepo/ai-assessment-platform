from sqlalchemy import Column, String, Boolean, Enum, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.enums import StudentStatus


student_projects = Table(
    "student_projects",
    Base.metadata,
    Column("student_id", String, ForeignKey("students.student_number"), primary_key=True),
    Column("project_id", UUID(as_uuid=True), ForeignKey("projects.id"), primary_key=True),
)


class Student(Base):
    __tablename__ = "students"

    student_number = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    github_repo_url = Column(String, nullable=True)
    github_branch = Column(String, nullable=True)
    status = Column(Enum(StudentStatus), default=StudentStatus.active)
    consent_given = Column(Boolean, default=False)

    # Relationships
    projects = relationship("Project", secondary=student_projects, back_populates="students")
    evidence = relationship("Evidence", back_populates="student")
    assessments = relationship("Assessment", back_populates="student")
