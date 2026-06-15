"""add project-scoped evidence support

Revision ID: j5k6l7m8n9o0
Revises: i4j5k6l7m8n9
Branch Labels: None
Depends On: None

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "j5k6l7m8n9o0"
down_revision: Union[str, None] = "i4j5k6l7m8n9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("evidence", "student_id", existing_type=sa.String(), nullable=True)
    op.add_column("evidence", sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "evidence_project_id_fkey",
        "evidence",
        "projects",
        ["project_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("evidence_project_id_fkey", "evidence", type_="foreignkey")
    op.execute("DELETE FROM evidence WHERE project_id IS NOT NULL")
    op.drop_column("evidence", "project_id")
    op.alter_column("evidence", "student_id", existing_type=sa.String(), nullable=False)
