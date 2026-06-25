from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_teacher
from app.core.security import verify_password, hash_password, create_access_token
from app.models.enums import AuditSource
from app.models.teacher import Teacher
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    TeacherOut,
    SetPinRequest,
    RemovePinRequest,
)
from app.services import audit_service

router = APIRouter()


def _teacher_out(teacher: Teacher) -> TeacherOut:
    return TeacherOut(
        id=str(teacher.id),
        name=teacher.name,
        email=teacher.email,
        is_admin=teacher.is_admin,
        has_pin=bool(teacher.pin_hash),
    )


def _get_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = _get_ip(request)
    teacher = db.query(Teacher).filter(Teacher.email == body.email).first()

    if not teacher or not teacher.password_hash:
        audit_service.log_action(
            db,
            action="auth.login_failed",
            source=AuditSource.system,
            details={"email": body.email, "reason": "Unknown user"},
            ip_address=ip,
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    if not verify_password(body.password, teacher.password_hash):
        audit_service.log_action(
            db,
            action="auth.login_failed",
            source=AuditSource.system,
            teacher_id=teacher.id,
            teacher_name=teacher.name,
            details={"email": body.email, "reason": "Invalid password"},
            ip_address=ip,
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    if teacher.pin_hash:
        if body.pin is None:
            return TokenResponse(pin_required=True)
        if not verify_password(body.pin, teacher.pin_hash):
            audit_service.log_action(
                db,
                action="auth.login_failed",
                source=AuditSource.system,
                teacher_id=teacher.id,
                teacher_name=teacher.name,
                details={"email": body.email, "reason": "Invalid PIN"},
                ip_address=ip,
            )
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid PIN")

    teacher.last_login = datetime.now(timezone.utc)
    audit_service.log_action(
        db,
        action="auth.login",
        source=AuditSource.teacher,
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        details={"email": teacher.email, "role": "admin" if teacher.is_admin else "teacher"},
        ip_address=ip,
        commit=False,
    )
    db.commit()

    token = create_access_token(subject=str(teacher.id))
    return TokenResponse(access_token=token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    audit_service.log_action(
        db,
        action="auth.logout",
        source=AuditSource.teacher,
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        details={"email": teacher.email},
        ip_address=_get_ip(request),
    )


@router.get("/me", response_model=TeacherOut)
def me(teacher: Teacher = Depends(get_current_teacher)):
    return _teacher_out(teacher)


@router.get("/users", response_model=List[TeacherOut])
def list_users(is_admin: Optional[bool] = None, db: Session = Depends(get_db)):
    query = db.query(Teacher).filter(Teacher.password_hash.isnot(None))
    if is_admin is not None:
        query = query.filter(Teacher.is_admin == is_admin)
    teachers = query.order_by(Teacher.name).all()
    return [TeacherOut(id=str(t.id), name=t.name, email=t.email, is_admin=t.is_admin) for t in teachers]


@router.post("/pin", response_model=TeacherOut)
def set_pin(
    body: SetPinRequest,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    if not teacher.password_hash or not verify_password(
        body.password, teacher.password_hash
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid password")
    teacher.pin_hash = hash_password(body.pin)
    db.commit()
    db.refresh(teacher)
    return _teacher_out(teacher)


@router.delete("/pin", response_model=TeacherOut)
def remove_pin(
    body: RemovePinRequest,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    if not teacher.password_hash or not verify_password(
        body.password, teacher.password_hash
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid password")
    teacher.pin_hash = None
    db.commit()
    db.refresh(teacher)
    return _teacher_out(teacher)
