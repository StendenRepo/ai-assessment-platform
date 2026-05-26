from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TeacherOut(BaseModel):
    id: str
    name: str
    email: str

    model_config = {"from_attributes": True}
