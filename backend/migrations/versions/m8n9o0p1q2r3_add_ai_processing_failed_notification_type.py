"""add ai_processing_failed notification type

Revision ID: m8n9o0p1q2r3
Revises: l7m8n9o0p1q2
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "m8n9o0p1q2r3"
down_revision: Union[str, None] = "l7m8n9o0p1q2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'ai_processing_failed'"
    )


def downgrade() -> None:
    # PostgreSQL does not support removing enum values in-place safely.
    pass
