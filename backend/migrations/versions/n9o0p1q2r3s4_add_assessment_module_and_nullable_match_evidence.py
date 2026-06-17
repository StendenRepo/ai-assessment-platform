"""add module_id to assessments and make evidence_matches.evidence_id nullable

Revision ID: j5k6l7m8n9o0
Revises: i4j5k6l7m8n9
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "n9o0p1q2r3s4"
down_revision: Union[str, None] = "m8n9o0p1q2r3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "assessments",
        sa.Column("module_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_assessments_module_id",
        "assessments",
        "modules",
        ["module_id"],
        ["id"],
    )
    op.alter_column(
        "evidence_matches",
        "evidence_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "evidence_matches",
        "evidence_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.drop_constraint("fk_assessments_module_id", "assessments", type_="foreignkey")
    op.drop_column("assessments", "module_id")
