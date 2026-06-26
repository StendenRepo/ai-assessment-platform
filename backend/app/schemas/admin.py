from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr

from app.models.enums import AuditSource


class DepartmentOut(BaseModel):
    id: str
    name: str
    created_at: datetime
    teacher_count: int = 0

    model_config = {"from_attributes": True}


class DepartmentCreate(BaseModel):
    name: str


class DepartmentUpdate(BaseModel):
    name: str


class TeacherAdminOut(BaseModel):
    id: str
    name: str
    email: str
    is_admin: bool
    is_protected: bool = False
    department_id: Optional[str] = None
    department_name: Optional[str] = None
    created_at: datetime
    last_login: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TeacherCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    department_id: Optional[str] = None
    is_admin: bool = False


class TeacherUpdate(BaseModel):
    name: str
    email: EmailStr
    password: Optional[str] = None
    department_id: Optional[str] = None
    is_admin: bool


class AuditEventOut(BaseModel):
    id: int
    timestamp: datetime
    action: str
    source: Optional[AuditSource] = None
    teacher_id: Optional[str] = None
    teacher_name: Optional[str] = None
    assessment_id: Optional[str] = None
    ip_address: Optional[str] = None
    details_json: Optional[dict[str, Any]] = None
