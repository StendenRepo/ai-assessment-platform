from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


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
