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


class ModuleGroupUpdate(BaseModel):
    name: Optional[str] = None
    group_name: Optional[str] = None

    @field_validator("name", "group_name")
    @classmethod
    def _trim_non_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class StudentGroupUpdate(BaseModel):
    project_id: Optional[str] = None
    name: Optional[str] = None
    student_number: Optional[str] = None
    status: Optional[str] = None

    @field_validator("name", "student_number")
    @classmethod
    def _trim_non_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().lower()
        if normalized not in {"active", "inactive"}:
            raise ValueError("status must be 'active' or 'inactive'")
        return normalized


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

    model_config = {"from_attributes": True}
