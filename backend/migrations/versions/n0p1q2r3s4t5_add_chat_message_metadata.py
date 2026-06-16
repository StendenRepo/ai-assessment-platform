"""add metadata_json to chat_messages

Revision ID: n0p1q2r3s4t5
Revises: m8n9o0p1q2r3
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "n0p1q2r3s4t5"
down_revision: Union[str, None] = "m8n9o0p1q2r3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "metadata_json")
