"""add is_seed to teachers

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-29 00:00:00.000000

"""
import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "teachers",
        sa.Column(
            "is_seed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    admin_email = os.getenv("SEED_ADMIN_EMAIL", "admin@admin.nl")
    op.execute(
        sa.text("UPDATE teachers SET is_seed = true WHERE email = :email").bindparams(
            email=admin_email
        )
    )


def downgrade() -> None:
    op.drop_column("teachers", "is_seed")
