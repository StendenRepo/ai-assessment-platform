"""audit_event timestamp: TIMESTAMP WITHOUT TIME ZONE -> TIMESTAMPTZ (UTC)

Revision ID: s4c5u6v7w8x0
Revises: s4b5u6v7w8x0
Create Date: 2026-06-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "s4c5u6v7w8x0"
down_revision: Union[str, None] = "s4b5u6v7w8x0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing values were written via datetime.utcnow() so they are already
    # UTC; USING instructs Postgres to reinterpret them as UTC when converting.
    op.execute(
        "ALTER TABLE audit_events "
        "ALTER COLUMN timestamp TYPE TIMESTAMPTZ "
        "USING timestamp AT TIME ZONE 'UTC'"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE audit_events "
        "ALTER COLUMN timestamp TYPE TIMESTAMP WITHOUT TIME ZONE "
        "USING timestamp AT TIME ZONE 'UTC'"
    )
