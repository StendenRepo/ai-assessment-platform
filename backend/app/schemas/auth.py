from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    pin: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: Optional[str] = None
    token_type: str = "bearer"
    pin_required: bool = False


class TeacherOut(BaseModel):
    id: str
    name: str
    email: str
    is_admin: bool = False
    has_pin: bool = False

    model_config = {"from_attributes": True}


class SetPinRequest(BaseModel):
    password: str
    pin: str

    @field_validator("pin")
    @classmethod
    def _valid_pin(cls, value: str) -> str:
        value = value.strip()
        if not (value.isdigit() and 4 <= len(value) <= 6):
            raise ValueError("PIN must be 4 to 6 digits")
        return value


class RemovePinRequest(BaseModel):
    password: str
