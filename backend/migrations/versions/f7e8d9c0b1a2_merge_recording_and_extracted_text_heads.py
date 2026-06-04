"""merge recording and extracted_text heads

Revision ID: f7e8d9c0b1a2
Revises: c5a1b2c3d403, d1e2f3a4b5c6
Create Date: 2026-06-04 21:45:00.000000

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "f7e8d9c0b1a2"
down_revision: Union[str, None] = ("c5a1b2c3d403", "d1e2f3a4b5c6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
