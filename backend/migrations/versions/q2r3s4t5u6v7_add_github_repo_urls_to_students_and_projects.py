"""add GitHub repo URLs to students and projects

Revision ID: q2r3s4t5u6v7
Revises: p1q2r3s4t5u6
Create Date: 2026-06-15 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "q2r3s4t5u6v7"
down_revision: Union[str, None] = "p1q2r3s4t5u6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("students", sa.Column("github_repo_url", sa.String(), nullable=True))
    op.add_column("projects", sa.Column("github_repo_url", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "github_repo_url")
    op.drop_column("students", "github_repo_url")
