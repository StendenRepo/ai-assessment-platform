"""add extracted_text to file_records

Stores the plain text parsed from a rubric / module book at (re-)upload time so
the AI retrieval (TF-IDF) reads the latest version (G2-105). Nullable because
extraction is best-effort — an unparseable file leaves this empty.

Revision ID: d1e2f3a4b5c6
Revises: 21b302495d48
Create Date: 2026-06-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "21b302495d48"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("file_records", sa.Column("extracted_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("file_records", "extracted_text")
