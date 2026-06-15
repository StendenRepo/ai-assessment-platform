"""add ai_processing_complete notification type

Revision ID: k6l7m8n9o0p1
Revises: j5k6l7m8n9o0
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "k6l7m8n9o0p1"
down_revision: Union[str, None] = "j5k6l7m8n9o0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'ai_processing_complete'"
    )


def downgrade() -> None:
    # PostgreSQL does not support removing enum values in-place safely.
    pass
