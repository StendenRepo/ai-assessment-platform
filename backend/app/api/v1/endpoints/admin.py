from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_admin, get_db
from app.core.security import hash_password
from app.models.department import Department
from app.models.teacher import Teacher
from app.schemas.admin import (
    DepartmentCreate,
    DepartmentOut,
    DepartmentUpdate,
    TeacherAdminOut,
    TeacherCreate,
    TeacherUpdate,
)

router = APIRouter()


def _teacher_to_out(t: Teacher) -> TeacherAdminOut:
    return TeacherAdminOut(
        id=str(t.id),
        name=t.name,
        email=t.email,
        is_admin=t.is_admin,
        is_protected=t.is_seed,
        department_id=str(t.department_id) if t.department_id else None,
        department_name=t.department.name if t.department else None,
        created_at=t.created_at,
        last_login=t.last_login,
    )


# ---------------------------------------------------------------------------
# Departments
# ---------------------------------------------------------------------------

@router.get("/departments", response_model=List[DepartmentOut])
def list_departments(
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_admin),
):
    departments = db.query(Department).order_by(Department.name).all()
    result = []
    for d in departments:
        count = db.query(Teacher).filter(Teacher.department_id == d.id).count()
        result.append(DepartmentOut(
            id=str(d.id),
            name=d.name,
            created_at=d.created_at,
            teacher_count=count,
        ))
    return result


@router.post("/departments", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
def create_department(
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_admin),
):
    if db.query(Department).filter(Department.name == payload.name).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Department name already exists")
    dept = Department(name=payload.name)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return DepartmentOut(id=str(dept.id), name=dept.name, created_at=dept.created_at, teacher_count=0)


@router.put("/departments/{dept_id}", response_model=DepartmentOut)
def update_department(
    dept_id: str,
    payload: DepartmentUpdate,
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_admin),
):
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    conflict = db.query(Department).filter(
        Department.name == payload.name, Department.id != dept.id
    ).first()
    if conflict:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Department name already exists")
    dept.name = payload.name
    db.commit()
    db.refresh(dept)
    count = db.query(Teacher).filter(Teacher.department_id == dept.id).count()
    return DepartmentOut(id=str(dept.id), name=dept.name, created_at=dept.created_at, teacher_count=count)


@router.delete("/departments/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(
    dept_id: str,
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_admin),
):
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    db.query(Teacher).filter(Teacher.department_id == dept.id).update({"department_id": None})
    db.delete(dept)
    db.commit()


# ---------------------------------------------------------------------------
# Teachers
# ---------------------------------------------------------------------------

@router.get("/teachers", response_model=List[TeacherAdminOut])
def list_teachers(
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_admin),
):
    teachers = (
        db.query(Teacher)
        .options(joinedload(Teacher.department))
        .order_by(Teacher.name)
        .all()
    )
    return [_teacher_to_out(t) for t in teachers]


@router.post("/teachers", response_model=TeacherAdminOut, status_code=status.HTTP_201_CREATED)
def create_teacher(
    payload: TeacherCreate,
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_admin),
):
    if db.query(Teacher).filter(Teacher.email == payload.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")

    dept_id = None
    if payload.department_id:
        dept = db.query(Department).filter(Department.id == payload.department_id).first()
        if not dept:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
        dept_id = dept.id

    teacher = Teacher(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        is_admin=payload.is_admin,
        department_id=dept_id,
    )
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    teacher = (
        db.query(Teacher)
        .options(joinedload(Teacher.department))
        .filter(Teacher.id == teacher.id)
        .first()
    )
    return _teacher_to_out(teacher)


@router.put("/teachers/{teacher_id}", response_model=TeacherAdminOut)
def update_teacher(
    teacher_id: str,
    payload: TeacherUpdate,
    db: Session = Depends(get_db),
    admin: Teacher = Depends(get_current_admin),
):
    teacher = (
        db.query(Teacher)
        .options(joinedload(Teacher.department))
        .filter(Teacher.id == teacher_id)
        .first()
    )
    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")

    if str(admin.id) == teacher_id and not payload.is_admin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot remove your own administrator access")

    if teacher.is_seed and not payload.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access cannot be removed from the seed account")

    if teacher.is_seed and payload.email != teacher.email:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="The seed admin account email cannot be changed")

    if payload.email != teacher.email:
        if db.query(Teacher).filter(Teacher.email == payload.email, Teacher.id != teacher.id).first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")

    teacher.name = payload.name
    teacher.email = payload.email
    teacher.is_admin = payload.is_admin

    if payload.password:
        teacher.password_hash = hash_password(payload.password)

    if payload.department_id:
        dept = db.query(Department).filter(Department.id == payload.department_id).first()
        if not dept:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
        teacher.department_id = dept.id
    else:
        teacher.department_id = None

    db.commit()
    teacher = (
        db.query(Teacher)
        .options(joinedload(Teacher.department))
        .filter(Teacher.id == teacher.id)
        .first()
    )
    return _teacher_to_out(teacher)


@router.delete("/teachers/{teacher_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_teacher(
    teacher_id: str,
    db: Session = Depends(get_db),
    admin: Teacher = Depends(get_current_admin),
):
    if str(admin.id) == teacher_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete your own account")
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
    if teacher.is_seed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="The seed admin account cannot be deleted")
    db.delete(teacher)
    db.commit()
