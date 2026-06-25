"""add inactive and completed to module status

Revision ID: u6v7w8x9y0z1
Revises: t5u6v7w8x9y0
Create Date: 2026-06-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "u6v7w8x9y0z1"
down_revision: Union[str, None] = "t5u6v7w8x9y0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE modulestatus ADD VALUE IF NOT EXISTS 'inactive'")
    op.execute("ALTER TYPE modulestatus ADD VALUE IF NOT EXISTS 'completed'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values in-place safely.
    pass
