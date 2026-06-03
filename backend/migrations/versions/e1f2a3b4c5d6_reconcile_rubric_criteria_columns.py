"""reconcile rubric_criteria column types

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-06-03 00:00:00.000000

Brings the rubric_criteria table in line with the reconciled spec:

  * widen `category` from VARCHAR(32) to VARCHAR(50) (no data loss; the
    whitelist values "technical"/"communication"/"process" all fit comfortably
    in either width — this just gives Walter more headroom for future
    category names like "professionalism").

  * switch `created_at` and `updated_at` from TIMESTAMP WITHOUT TIME ZONE to
    TIMESTAMP WITH TIME ZONE. Existing rows (if any) are reinterpreted as UTC
    via the USING clause. Older tables in this codebase remain naive; the
    rubric table is the first one to use TIMESTAMPTZ, and aligning the rest
    is tracked separately.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "rubric_criteria",
        "category",
        existing_type=sa.String(length=32),
        type_=sa.String(length=50),
        existing_nullable=False,
    )

    op.execute(
        "ALTER TABLE rubric_criteria "
        "ALTER COLUMN created_at TYPE TIMESTAMPTZ "
        "USING created_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE rubric_criteria "
        "ALTER COLUMN updated_at TYPE TIMESTAMPTZ "
        "USING updated_at AT TIME ZONE 'UTC'"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE rubric_criteria "
        "ALTER COLUMN updated_at TYPE TIMESTAMP "
        "USING updated_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE rubric_criteria "
        "ALTER COLUMN created_at TYPE TIMESTAMP "
        "USING created_at AT TIME ZONE 'UTC'"
    )

    op.alter_column(
        "rubric_criteria",
        "category",
        existing_type=sa.String(length=50),
        type_=sa.String(length=32),
        existing_nullable=False,
    )
