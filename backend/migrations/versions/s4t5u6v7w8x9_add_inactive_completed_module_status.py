"""add inactive and completed to module status

Revision ID: s4t5u6v7w8x9
Revises: r3s4t5u6v7w8
Create Date: 2026-06-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "s4t5u6v7w8x9"
down_revision: Union[str, None] = "r3s4t5u6v7w8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE modulestatus ADD VALUE IF NOT EXISTS 'inactive'")
    op.execute("ALTER TYPE modulestatus ADD VALUE IF NOT EXISTS 'completed'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values in-place safely.
    pass
