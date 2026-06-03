"""merge file_name and deadline migration heads

Revision ID: 21b302495d48
Revises: b8c9d0e1f2a3, f1a2b3c4d5e6
Create Date: 2026-06-03 13:05:23.352835

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '21b302495d48'
down_revision: Union[str, None] = ('b8c9d0e1f2a3', 'f1a2b3c4d5e6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
