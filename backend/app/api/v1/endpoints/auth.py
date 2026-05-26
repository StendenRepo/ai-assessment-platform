from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_teacher
from app.core.security import verify_password, create_access_token
from app.models.teacher import Teacher
from app.schemas.auth import LoginRequest, TokenResponse, TeacherOut

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    teacher = db.query(Teacher).filter(Teacher.email == body.email).first()
    if not teacher or not teacher.password_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not verify_password(body.password, teacher.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    teacher.last_login = datetime.now(timezone.utc)
    db.commit()

    token = create_access_token(subject=str(teacher.id))
    return TokenResponse(access_token=token)


@router.get("/me", response_model=TeacherOut)
def me(teacher: Teacher = Depends(get_current_teacher)):
    return TeacherOut(id=str(teacher.id), name=teacher.name, email=teacher.email)
