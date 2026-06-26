"""add teacher_score override to rubric_scores

Revision ID: v7w8x9y0z1a2
Revises: u6b7v8w9x0y1
Create Date: 2026-06-24 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "v7w8x9y0z1a2"
down_revision: Union[str, None] = "u6b7v8w9x0y1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "rubric_scores", sa.Column("teacher_score", sa.Float(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("rubric_scores", "teacher_score")
