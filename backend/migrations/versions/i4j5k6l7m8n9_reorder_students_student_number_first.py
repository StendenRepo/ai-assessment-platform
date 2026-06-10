"""reorder students table so student_number is first column

Revision ID: i4j5k6l7m8n9
Revises: h3i4j5k6l7m8
Branch Labels: None
Depends On: None

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "i4j5k6l7m8n9"
down_revision: Union[str, None] = "h3i4j5k6l7m8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop FK constraints that reference students
    op.drop_constraint("student_projects_student_id_fkey", "student_projects", type_="foreignkey")
    op.drop_constraint("assessments_student_id_fkey", "assessments", type_="foreignkey")
    op.drop_constraint("evidence_student_id_fkey", "evidence", type_="foreignkey")
    op.drop_constraint("overlap_signals_student_a_id_fkey", "overlap_signals", type_="foreignkey")
    op.drop_constraint("overlap_signals_student_b_id_fkey", "overlap_signals", type_="foreignkey")

    # Recreate students table with student_number as first column
    op.execute(
        """
        CREATE TABLE students_new (
            student_number VARCHAR NOT NULL,
            name VARCHAR NOT NULL,
            status VARCHAR,
            consent_given BOOLEAN,
            PRIMARY KEY (student_number)
        )
        """
    )
    op.execute("INSERT INTO students_new SELECT student_number, name, status, consent_given FROM students")
    op.drop_table("students")
    op.execute("ALTER TABLE students_new RENAME TO students")

    # Restore FK constraints
    op.create_foreign_key(
        "student_projects_student_id_fkey",
        "student_projects", "students",
        ["student_id"], ["student_number"],
    )
    op.create_foreign_key(
        "assessments_student_id_fkey",
        "assessments", "students",
        ["student_id"], ["student_number"],
    )
    op.create_foreign_key(
        "evidence_student_id_fkey",
        "evidence", "students",
        ["student_id"], ["student_number"],
    )
    op.create_foreign_key(
        "overlap_signals_student_a_id_fkey",
        "overlap_signals", "students",
        ["student_a_id"], ["student_number"],
    )
    op.create_foreign_key(
        "overlap_signals_student_b_id_fkey",
        "overlap_signals", "students",
        ["student_b_id"], ["student_number"],
    )


def downgrade() -> None:
    # Column order cannot be meaningfully reversed; this is a no-op downgrade.
    pass
