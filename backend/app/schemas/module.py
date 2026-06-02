from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class RubricFileOut(BaseModel):
    id: str
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    size_bytes: Optional[int] = None
    uploaded_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ModuleOut(BaseModel):
    id: str
    name: str
    academic_year: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None
    rubric_file: Optional[RubricFileOut] = None

    model_config = {"from_attributes": True}


class ModuleCreate(BaseModel):
    name: str
    academic_year: Optional[str] = None
