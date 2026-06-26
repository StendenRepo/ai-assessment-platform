"""add module co-teachers many-to-many

Revision ID: t5b6u7v8w9x0
Revises: t5u6v7w8x9y0
Create Date: 2026-06-23

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "t5b6u7v8w9x0"
down_revision = "t5u6v7w8x9y0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "module_teachers",
        sa.Column("module_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("modules.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("teacher_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("teachers.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("module_teachers")
