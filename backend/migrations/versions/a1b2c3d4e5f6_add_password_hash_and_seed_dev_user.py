"""add password_hash and seed dev user

Revision ID: a1b2c3d4e5f6
Revises: 809651cc93a6
Create Date: 2026-05-26 00:00:00.000000

"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from passlib.context import CryptContext

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '809651cc93a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def upgrade() -> None:
    op.add_column('teachers', sa.Column('password_hash', sa.String(), nullable=True))

    password_hash = _pwd_context.hash("admin")
    teacher_id = str(uuid.uuid4())

    op.execute(
        sa.text(
            "INSERT INTO teachers (id, name, email, password_hash, created_at) "
            "VALUES (:id, :name, :email, :password_hash, NOW()) "
            "ON CONFLICT (email) DO NOTHING"
        ).bindparams(
            id=teacher_id,
            name="Admin",
            email="admin@admin.nl",
            password_hash=password_hash,
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM teachers WHERE email = 'admin@admin.nl'"))
    op.drop_column('teachers', 'password_hash')
