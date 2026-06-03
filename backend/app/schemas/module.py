from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class RubricFileOut(BaseModel):
    id: str
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    size_bytes: Optional[int] = None
    uploaded_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ModuleCreate(BaseModel):
    name: str
    academic_year: Optional[str] = None
    deadline: Optional[str] = None

    @field_validator("name", "academic_year", "deadline")
    @classmethod
    def _trim(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        return value or None


class ModuleGroupCreate(BaseModel):
    name: str
    group_name: Optional[str] = None

    @field_validator("name", "group_name")
    @classmethod
    def _trim(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        return value or None


class StudentGroupUpdate(BaseModel):
    project_id: str


class ModuleOut(BaseModel):
    id: str
    name: str
    academic_year: Optional[str] = None
    deadline: Optional[str] = None
    status: str
    created_at: datetime
    project_count: int = 0
    student_count: int = 0
    rubric_file: Optional[RubricFileOut] = None
    module_book_file: Optional[RubricFileOut] = None

    model_config = {"from_attributes": True}
