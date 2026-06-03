"""add fields used by module and project creation flows

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-06-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("modules", sa.Column("code", sa.String(), nullable=True))
    op.execute(
        "UPDATE modules SET code = 'MOD-' || LEFT(id::text, 8) WHERE code IS NULL"
    )
    op.alter_column("modules", "code", existing_type=sa.String(), nullable=False)
    op.create_unique_constraint("uq_modules_code", "modules", ["code"])

    op.add_column("projects", sa.Column("course", sa.String(), nullable=True))
    op.add_column("projects", sa.Column("deadline", sa.Date(), nullable=True))
    op.alter_column(
        "projects",
        "module_id",
        existing_type=sa.UUID(),
        nullable=True,
    )

    op.add_column("students", sa.Column("email", sa.String(), nullable=True))
    op.alter_column("students", "name", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    op.alter_column("students", "name", existing_type=sa.String(), nullable=False)
    op.drop_column("students", "email")

    op.alter_column(
        "projects",
        "module_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
    op.drop_column("projects", "deadline")
    op.drop_column("projects", "course")

    op.drop_constraint("uq_modules_code", "modules", type_="unique")
    op.drop_column("modules", "code")
