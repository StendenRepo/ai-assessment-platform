"""merge migration heads

Revision ID: 8d3a3649844f
Revises: p1q2r3s4t5u6, r3s4t5u6v7w8
Create Date: 2026-06-19 14:49:57.287503

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8d3a3649844f'
down_revision: Union[str, None] = ('p1q2r3s4t5u6', 'r3s4t5u6v7w8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
