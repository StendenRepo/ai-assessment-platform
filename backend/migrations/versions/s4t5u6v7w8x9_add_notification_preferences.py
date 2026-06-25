"""add notification_preferences table (G2-220)

Per-teacher, per-event-type notification preferences. Absence of a row means the
default (enabled), so this table only stores explicit overrides.

Revision ID: s4t5u6v7w8x9
Revises: r3s4t5u6v7w8
Create Date: 2026-06-24 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "s4t5u6v7w8x9"
down_revision: Union[str, None] = "r3s4t5u6v7w8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Reuse the enum already created by the notifications table; do not recreate it.
notification_type_existing = postgresql.ENUM(
    "deletion_reminder",
    "ai_processing_complete",
    "ai_processing_failed",
    name="notificationtype",
    create_type=False,
)


def upgrade() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("teacher_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notification_type", notification_type_existing, nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"]),
        sa.UniqueConstraint(
            "teacher_id",
            "notification_type",
            name="uq_notification_pref_teacher_type",
        ),
    )


def downgrade() -> None:
    op.drop_table("notification_preferences")
