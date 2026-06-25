"""add module co-teachers many-to-many

Revision ID: s4t5u6v7w8x9
Revises: r3s4t5u6v7w8
Create Date: 2026-06-23

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "s4t5u6v7w8x9"
down_revision = "r3s4t5u6v7w8"
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
