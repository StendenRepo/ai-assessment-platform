"""merge generation_runs and github-support migration heads

Revision ID: s4t5u6v7w8x9
Revises: p1q2r3s4t5u6, r3s4t5u6v7w8
Create Date: 2026-06-17 12:45:00.000000

"""
from typing import Sequence, Union

revision: str = "s4t5u6v7w8x9"
down_revision: Union[str, Sequence[str], None] = (
    "p1q2r3s4t5u6",
    "r3s4t5u6v7w8",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
