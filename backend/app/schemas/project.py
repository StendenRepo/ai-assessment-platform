from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, field_validator


class StudentCreate(BaseModel):
    name: str
    student_number: str

    @field_validator("name", "student_number")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class StudentOut(BaseModel):
    id: str
    project_id: str
    name: str
    # Every student created through the add/import endpoints has a number, so
    # we expose it as required rather than optional.
    student_number: str
    status: str
    consent_given: bool = False

    model_config = {"from_attributes": True}


class ProjectOut(BaseModel):
    id: str
    name: str
    group_name: Optional[str] = None
    module_id: str
    status: str
    created_at: Optional[datetime] = None
    student_count: int = 0

    model_config = {"from_attributes": True}


class ImportRowError(BaseModel):
    row: int
    student_number: Optional[str] = None
    message: str


class StudentImportResult(BaseModel):
    imported_count: int
    error_count: int
    total_rows: int
    errors: List[ImportRowError]
    students: List[StudentOut]
