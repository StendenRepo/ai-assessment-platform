"""seed demo module and projects

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-01 00:00:00.000000

"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_MODULE_NAME = "Demo Module"
_PROJECT_NAMES = [
    "E-Commerce Platform",
    "Machine Learning Model",
    "Mobile App Prototype",
]


def upgrade() -> None:
    conn = op.get_bind()

    # Only seed an empty database so we never duplicate demo data or clobber
    # real projects on environments that have already been populated.
    existing = conn.execute(sa.text("SELECT COUNT(*) FROM projects")).scalar()
    if existing:
        return

    teacher_id = conn.execute(
        sa.text("SELECT id FROM teachers ORDER BY created_at LIMIT 1")
    ).scalar()
    if not teacher_id:
        # No teacher to own the module yet; nothing to seed.
        return

    module_id = str(uuid.uuid4())
    conn.execute(
        sa.text(
            "INSERT INTO modules (id, teacher_id, name, academic_year, created_at, status) "
            "VALUES (:id, :teacher_id, :name, :year, NOW(), 'active')"
        ).bindparams(
            id=module_id,
            teacher_id=str(teacher_id),
            name=_MODULE_NAME,
            year="2025-2026",
        )
    )

    for name in _PROJECT_NAMES:
        conn.execute(
            sa.text(
                "INSERT INTO projects (id, module_id, name, created_at, status) "
                "VALUES (:id, :module_id, :name, NOW(), 'active')"
            ).bindparams(
                id=str(uuid.uuid4()),
                module_id=module_id,
                name=name,
            )
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM students WHERE project_id IN ("
            "  SELECT p.id FROM projects p"
            "  JOIN modules m ON m.id = p.module_id"
            "  WHERE m.name = :module_name"
            ")"
        ).bindparams(module_name=_MODULE_NAME)
    )
    conn.execute(
        sa.text(
            "DELETE FROM projects WHERE module_id IN ("
            "  SELECT id FROM modules WHERE name = :module_name"
            ")"
        ).bindparams(module_name=_MODULE_NAME)
    )
    conn.execute(
        sa.text("DELETE FROM modules WHERE name = :module_name").bindparams(
            module_name=_MODULE_NAME
        )
    )
