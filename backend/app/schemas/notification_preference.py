"""Schemas for per-event-type notification preferences (G2-220)."""
from pydantic import BaseModel

from app.models.enums import NotificationType


class NotificationPreferenceOut(BaseModel):
    """A teacher's effective preference for one notification type."""

    notification_type: NotificationType
    enabled: bool

    model_config = {"from_attributes": True}


class NotificationPreferenceUpdate(BaseModel):
    """Payload for toggling a single notification type on/off."""

    enabled: bool
