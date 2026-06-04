"""add notifications.recording_id (per-recording deletion reminders)

Adds a nullable recording_id FK so a deletion reminder can reference the
specific recording it concerns (G2-142). No backfill: existing reminders stay
assessment-only (recording_id NULL).

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-06-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c5a1b2c3d403"
down_revision: Union[str, None] = "c5a1b2c3d402"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("recording_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "notifications_recording_id_fkey",
        "notifications",
        "recordings",
        ["recording_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "notifications_recording_id_fkey", "notifications", type_="foreignkey"
    )
    op.drop_column("notifications", "recording_id")
