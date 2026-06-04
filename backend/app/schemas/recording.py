from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import ConsentStatus, TranscriptionStatus, NotificationType


class ConsentStateOut(BaseModel):
    """Consent gate state for an assessment (G2-138)."""

    assessment_id: str
    consent_status: ConsentStatus
    consent_confirmed_at: Optional[datetime] = None
    recording_count: int = 0

    model_config = {"from_attributes": True}


class RecordingSummary(BaseModel):
    """One recording in the list (name, status, expiry, flag)."""

    id: str
    display_name: str
    sequence_number: int
    transcription_status: TranscriptionStatus
    created_at: Optional[datetime] = None
    delete_after: Optional[datetime] = None
    flagged_for_deletion: bool = False
    extension_count: int = 0

    model_config = {"from_attributes": True}


class RecordingDetail(RecordingSummary):
    """A single recording including its transcript."""

    transcript_text: Optional[str] = None


class ExpiryExtendIn(BaseModel):
    # GDPR: each extension adds at most 90 days; a reason is mandatory.
    reason: str = Field(min_length=1)
    extra_days: int = Field(default=90, ge=1, le=90)


class RecordingPatchIn(BaseModel):
    """Rename and/or extend expiry in one call (both optional)."""

    display_name: Optional[str] = Field(default=None, min_length=1)
    extend_expiry: Optional[ExpiryExtendIn] = None


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
