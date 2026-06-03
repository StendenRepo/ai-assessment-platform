from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, field_validator


class StudentCreate(BaseModel):
    email: Optional[str] = None
    student_number: Optional[str] = None


class ProjectCreate(BaseModel):
    name: str
    course: Optional[str] = None
    group_name: Optional[str] = None
    deadline: Optional[date] = None
    module_id: Optional[UUID] = None
    students: Optional[List[StudentCreate]] = []

    @field_validator("name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must not be blank")
        return v.strip()


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    course: Optional[str]
    group_name: Optional[str]
    deadline: Optional[date]
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
