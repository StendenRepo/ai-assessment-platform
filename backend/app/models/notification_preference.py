"""Per-teacher, per-event-type notification preferences (G2-220).

A row records a teacher's explicit override for one NotificationType. Absence of
a row means the default (enabled); preferences are therefore opt-out. Reads are
enforced server-side in notification_service.list_for_teacher so a disabled type
never reaches the client.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.enums import NotificationType


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (
        UniqueConstraint(
            "teacher_id",
            "notification_type",
            name="uq_notification_pref_teacher_type",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id = Column(
        UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=False
    )
    notification_type = Column(Enum(NotificationType), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    teacher = relationship("Teacher")
