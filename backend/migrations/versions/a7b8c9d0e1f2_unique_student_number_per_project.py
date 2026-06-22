"""unique student number per project

Revision ID: a7b8c9d0e1f2
Revises: e5f6a7b8c9d0
Create Date: 2026-06-01 09:30:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONSTRAINT = "uq_students_project_student_number"


def upgrade() -> None:
    # Enforce at the DB level what the API already checks, so two concurrent
    # requests can't both insert the same student number into one project.
    # (Postgres treats NULL student numbers as distinct, so existing rows
    # without a number are unaffected.)
    op.create_unique_constraint(
        _CONSTRAINT, "students", ["project_id", "student_number"]
    )


def downgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "students", type_="unique")
