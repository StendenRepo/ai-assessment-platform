from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.project import ProjectOut


class ModuleCreate(BaseModel):
    name: str
    academic_year: Optional[str] = None

    @field_validator("name", "academic_year")
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
    status: str
    created_at: datetime
    project_count: int = 0
    student_count: int = 0
    has_rubric: bool = False
    has_module_guide: bool = False
    criteria: list[dict] = Field(default_factory=list)
    criteria_count: int = 0
    projects: list[ProjectOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}