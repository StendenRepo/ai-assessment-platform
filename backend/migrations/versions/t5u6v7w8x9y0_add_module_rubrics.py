"""add module_rubrics table for multiple rubrics per module

Revision ID: t5u6v7w8x9y0
Revises: s4c5u6v7w8x0
Create Date: 2026-06-22 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "t5u6v7w8x9y0"
down_revision: Union[str, None] = "s4c5u6v7w8x0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "module_rubrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("module_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("weight", sa.Float(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["module_id"], ["modules.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["file_id"], ["file_records.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_module_rubrics_module_id", "module_rubrics", ["module_id"]
    )

    op.execute(
        """
        INSERT INTO module_rubrics (id, module_id, file_id, name, position, created_at)
        SELECT gen_random_uuid(), id, rubric_file_id, 'Rubric', 0, NOW()
        FROM modules
        WHERE rubric_file_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_module_rubrics_module_id", table_name="module_rubrics")
    op.drop_table("module_rubrics")
