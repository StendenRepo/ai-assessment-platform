"""add departments table and is_admin flag to teachers

Revision ID: d4e5f6a7b8c9
Revises: a1b2c3d4e5f6
Create Date: 2026-05-29 00:00:00.000000

"""
import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "departments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.add_column(
        "teachers",
        sa.Column(
            "is_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    op.add_column(
        "teachers",
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_teachers_department_id",
        "teachers",
        "departments",
        ["department_id"],
        ["id"],
        ondelete="SET NULL",
    )

    admin_email = os.getenv("SEED_ADMIN_EMAIL", "admin@admin.nl")
    op.execute(
        sa.text("UPDATE teachers SET is_admin = true WHERE email = :email").bindparams(
            email=admin_email
        )
    )


def downgrade() -> None:
    op.drop_constraint("fk_teachers_department_id", "teachers", type_="foreignkey")
    op.drop_column("teachers", "department_id")
    op.drop_column("teachers", "is_admin")
    op.drop_table("departments")
