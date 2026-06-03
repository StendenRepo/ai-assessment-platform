from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator


class ModuleCreate(BaseModel):
    name: str
    code: str
    academic_year: str | None = None

    @field_validator("name", "code")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must not be blank")
        return v.strip()


class ModuleResponse(BaseModel):
    id: UUID
    name: str
    code: str
    academic_year: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
