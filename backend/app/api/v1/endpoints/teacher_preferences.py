"""Teacher preference endpoints for UI settings (theme, language, date format)."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_teacher
from app.models.teacher import Teacher
from app.schemas.teacher_preference import TeacherPreferenceOut, TeacherPreferenceUpdate
from app.services import teacher_preference_service

router = APIRouter()


@router.get("/teacher-preferences", response_model=TeacherPreferenceOut)
def get_teacher_preferences(
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    """Get current teacher's UI preferences.
    
    Returns defaults if no preferences have been set yet.
    """
    prefs = teacher_preference_service.get_or_create_preferences(
        db, teacher_id=teacher.id
    )
    return TeacherPreferenceOut(
        theme=prefs.theme,
        date_format=prefs.date_format,
        language=prefs.language,
    )


@router.put("/teacher-preferences", response_model=TeacherPreferenceOut)
def update_teacher_preferences(
    body: TeacherPreferenceUpdate,
    request: Request,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    """Update current teacher's UI preferences.
    
    Only provided fields are updated; omitted fields remain unchanged.
    Changes are audited.
    """
    pref = teacher_preference_service.set_preference(
        db,
        teacher=teacher,
        theme=body.theme,
        date_format=body.date_format,
        language=body.language,
        ip_address=request.client.host if request.client else None,
    )
    return TeacherPreferenceOut(
        theme=pref.theme,
        date_format=pref.date_format,
        language=pref.language,
    )
