"""add notifications.recording_id (per-recording deletion reminders)

Adds a nullable recording_id FK so a deletion reminder can reference the
specific recording it concerns (G2-142). No backfill: existing reminders stay
assessment-only (recording_id NULL).

Revision ID: 802c192a51d0
Revises: d60d6f56f4a3
Create Date: 2026-06-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "802c192a51d0"
down_revision: Union[str, None] = "d60d6f56f4a3"
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
