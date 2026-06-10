"""student_number global unique and many-to-many projects

Revision ID: g2h3i4j5k6l7
Revises: a7b8c9d0e1f2
Branch Labels: None
Depends On: None

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "g2h3i4j5k6l7"
down_revision: Union[str, None] = "f7e8d9c0b1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the student_projects association table
    op.create_table(
        "student_projects",
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id"), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), primary_key=True),
    )

    # Migrate existing project_id relationships into the association table
    op.execute(
        """
        INSERT INTO student_projects (student_id, project_id)
        SELECT id, project_id FROM students
        WHERE project_id IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )

    # Drop the old composite unique constraint
    op.drop_constraint("uq_students_project_student_number", "students", type_="unique")

    # Make student_number non-nullable (fill any NULLs first to avoid constraint failure)
    op.execute("UPDATE students SET student_number = CAST(id AS TEXT) WHERE student_number IS NULL")
    op.alter_column("students", "student_number", nullable=False)

    # Add global unique constraint on student_number
    op.create_unique_constraint("uq_students_student_number", "students", ["student_number"])

    # Drop project_id FK constraint and column
    op.drop_constraint("students_project_id_fkey", "students", type_="foreignkey")
    op.drop_column("students", "project_id")


def downgrade() -> None:
    op.add_column(
        "students",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "students_project_id_fkey", "students", "projects", ["project_id"], ["id"]
    )

    # Restore project_id from the association table (last project wins for duplicates)
    op.execute(
        """
        UPDATE students s
        SET project_id = sp.project_id
        FROM student_projects sp
        WHERE sp.student_id = s.id
        """
    )

    op.drop_constraint("uq_students_student_number", "students", type_="unique")
    op.alter_column("students", "student_number", nullable=True)
    op.create_unique_constraint(
        "uq_students_project_student_number", "students", ["project_id", "student_number"]
    )

    op.drop_table("student_projects")
