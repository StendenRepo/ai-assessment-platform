from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.enums import ConsentStatus, TranscriptionStatus, NotificationType


class RecordingStateOut(BaseModel):
    """Recording + consent state for the assessment form (G2-138)."""

    assessment_id: str
    has_recording: bool
    consent_status: ConsentStatus
    consent_confirmed_at: Optional[datetime] = None
    transcription_status: TranscriptionStatus
    transcript_text: Optional[str] = None
    delete_after: Optional[datetime] = None
    flagged_for_deletion: bool = False

    model_config = {"from_attributes": True}


class ConsentUpdate(BaseModel):
    status: ConsentStatus  # accepted or declined


class NotificationOut(BaseModel):
    id: str
    type: NotificationType
    message: str
    assessment_id: Optional[str] = None
    due_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    read_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
