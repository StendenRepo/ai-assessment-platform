"""add github_branch to students and projects

Revision ID: r3s4t5u6v7w8
Revises: q2r3s4t5u6v7
Create Date: 2026-06-15 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "r3s4t5u6v7w8"
down_revision: Union[str, None] = "q2r3s4t5u6v7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("students", sa.Column("github_branch", sa.String(), nullable=True))
    op.add_column("projects", sa.Column("github_branch", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "github_branch")
    op.drop_column("students", "github_branch")
