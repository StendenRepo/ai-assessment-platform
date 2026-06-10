"""student_number as primary key, migrate all UUID FKs to string

Revision ID: h3i4j5k6l7m8
Revises: g2h3i4j5k6l7
Branch Labels: None
Depends On: None

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "h3i4j5k6l7m8"
down_revision: Union[str, None] = "g2h3i4j5k6l7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. student_projects: student_id UUID → student_number STRING ────────
    op.drop_constraint("student_projects_student_id_fkey", "student_projects", type_="foreignkey")
    op.add_column("student_projects", sa.Column("student_id_new", sa.String(), nullable=True))
    op.execute(
        """
        UPDATE student_projects sp
        SET student_id_new = s.student_number
        FROM students s
        WHERE sp.student_id = s.id
        """
    )
    op.drop_column("student_projects", "student_id")
    op.alter_column("student_projects", "student_id_new", new_column_name="student_id", nullable=False)

    # ── 2. assessments: student_id UUID → student_number STRING ─────────────
    op.drop_constraint("assessments_student_id_fkey", "assessments", type_="foreignkey")
    op.add_column("assessments", sa.Column("student_id_new", sa.String(), nullable=True))
    op.execute(
        """
        UPDATE assessments a
        SET student_id_new = s.student_number
        FROM students s
        WHERE a.student_id = s.id
        """
    )
    op.drop_column("assessments", "student_id")
    op.alter_column("assessments", "student_id_new", new_column_name="student_id", nullable=False)

    # ── 3. evidence: student_id UUID → student_number STRING ────────────────
    op.drop_constraint("evidence_student_id_fkey", "evidence", type_="foreignkey")
    op.add_column("evidence", sa.Column("student_id_new", sa.String(), nullable=True))
    op.execute(
        """
        UPDATE evidence e
        SET student_id_new = s.student_number
        FROM students s
        WHERE e.student_id = s.id
        """
    )
    op.drop_column("evidence", "student_id")
    op.alter_column("evidence", "student_id_new", new_column_name="student_id", nullable=False)

    # ── 4. overlap_signals: student_a_id / student_b_id UUID → STRING ───────
    op.drop_constraint("overlap_signals_student_a_id_fkey", "overlap_signals", type_="foreignkey")
    op.drop_constraint("overlap_signals_student_b_id_fkey", "overlap_signals", type_="foreignkey")
    op.add_column("overlap_signals", sa.Column("student_a_id_new", sa.String(), nullable=True))
    op.add_column("overlap_signals", sa.Column("student_b_id_new", sa.String(), nullable=True))
    op.execute(
        """
        UPDATE overlap_signals os
        SET student_a_id_new = s.student_number
        FROM students s
        WHERE os.student_a_id = s.id
        """
    )
    op.execute(
        """
        UPDATE overlap_signals os
        SET student_b_id_new = s.student_number
        FROM students s
        WHERE os.student_b_id = s.id
        """
    )
    op.drop_column("overlap_signals", "student_a_id")
    op.drop_column("overlap_signals", "student_b_id")
    op.alter_column("overlap_signals", "student_a_id_new", new_column_name="student_a_id", nullable=False)
    op.alter_column("overlap_signals", "student_b_id_new", new_column_name="student_b_id", nullable=False)

    # ── 5. students: drop UUID id column, promote student_number to PK ───────
    # Drop the unique constraint on student_number (it will become the PK instead)
    op.drop_constraint("uq_students_student_number", "students", type_="unique")
    op.drop_column("students", "id")
    op.create_primary_key("pk_students", "students", ["student_number"])

    # ── 6. Re-add FK constraints pointing at students.student_number ─────────
    op.create_primary_key("pk_student_projects", "student_projects", ["student_id", "project_id"])
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
    # Re-add UUID id column to students
    op.add_column("students", sa.Column("id", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute("UPDATE students SET id = gen_random_uuid()")
    op.alter_column("students", "id", nullable=False)

    # Drop new FK constraints
    op.drop_constraint("overlap_signals_student_b_id_fkey", "overlap_signals", type_="foreignkey")
    op.drop_constraint("overlap_signals_student_a_id_fkey", "overlap_signals", type_="foreignkey")
    op.drop_constraint("evidence_student_id_fkey", "evidence", type_="foreignkey")
    op.drop_constraint("assessments_student_id_fkey", "assessments", type_="foreignkey")
    op.drop_constraint("student_projects_student_id_fkey", "student_projects", type_="foreignkey")

    # Restore students PK to id
    op.drop_constraint("pk_students", "students", type_="primary")
    op.create_primary_key("students_pkey", "students", ["id"])
    op.create_unique_constraint("uq_students_student_number", "students", ["student_number"])

    # Restore student_projects.student_id to UUID
    op.add_column("student_projects", sa.Column("student_id_old", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute(
        """
        UPDATE student_projects sp
        SET student_id_old = s.id
        FROM students s
        WHERE sp.student_id = s.student_number
        """
    )
    op.drop_column("student_projects", "student_id")
    op.alter_column("student_projects", "student_id_old", new_column_name="student_id", nullable=False)
    op.create_primary_key("pk_student_projects", "student_projects", ["student_id", "project_id"])
    op.create_foreign_key(
        "student_projects_student_id_fkey",
        "student_projects", "students",
        ["student_id"], ["id"],
    )

    # Restore assessments.student_id to UUID
    op.add_column("assessments", sa.Column("student_id_old", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute(
        """
        UPDATE assessments a
        SET student_id_old = s.id
        FROM students s
        WHERE a.student_id = s.student_number
        """
    )
    op.drop_column("assessments", "student_id")
    op.alter_column("assessments", "student_id_old", new_column_name="student_id", nullable=False)
    op.create_foreign_key(
        "assessments_student_id_fkey",
        "assessments", "students",
        ["student_id"], ["id"],
    )

    # Restore evidence.student_id to UUID
    op.add_column("evidence", sa.Column("student_id_old", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute(
        """
        UPDATE evidence e
        SET student_id_old = s.id
        FROM students s
        WHERE e.student_id = s.student_number
        """
    )
    op.drop_column("evidence", "student_id")
    op.alter_column("evidence", "student_id_old", new_column_name="student_id", nullable=False)
    op.create_foreign_key(
        "evidence_student_id_fkey",
        "evidence", "students",
        ["student_id"], ["id"],
    )

    # Restore overlap_signals student FK columns to UUID
    op.add_column("overlap_signals", sa.Column("student_a_id_old", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("overlap_signals", sa.Column("student_b_id_old", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute(
        """
        UPDATE overlap_signals os
        SET student_a_id_old = s.id
        FROM students s
        WHERE os.student_a_id = s.student_number
        """
    )
    op.execute(
        """
        UPDATE overlap_signals os
        SET student_b_id_old = s.id
        FROM students s
        WHERE os.student_b_id = s.student_number
        """
    )
    op.drop_column("overlap_signals", "student_a_id")
    op.drop_column("overlap_signals", "student_b_id")
    op.alter_column("overlap_signals", "student_a_id_old", new_column_name="student_a_id", nullable=False)
    op.alter_column("overlap_signals", "student_b_id_old", new_column_name="student_b_id", nullable=False)
    op.create_foreign_key(
        "overlap_signals_student_a_id_fkey",
        "overlap_signals", "students",
        ["student_a_id"], ["id"],
    )
    op.create_foreign_key(
        "overlap_signals_student_b_id_fkey",
        "overlap_signals", "students",
        ["student_b_id"], ["id"],
    )
