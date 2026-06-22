"""merge remaining migration heads

Revision ID: d20d8973e6be
Revises: 8d3a3649844f, s4t5u6v7w8x9
Create Date: 2026-06-19 17:50:05.753669

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = 'd20d8973e6be'
down_revision: Union[str, None] = ('8d3a3649844f', 's4t5u6v7w8x9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
