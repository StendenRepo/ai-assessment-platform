"""audit_event timestamp: TIMESTAMP WITHOUT TIME ZONE -> TIMESTAMPTZ (UTC)

Revision ID: s4t5u6v7w8x9
Revises: r3s4t5u6v7w8
Create Date: 2026-06-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "s4t5u6v7w8x9"
down_revision: Union[str, None] = "r3s4t5u6v7w8"
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
