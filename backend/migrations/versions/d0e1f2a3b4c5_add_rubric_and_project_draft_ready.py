"""add rubric_criteria table + draft/ready values to ProjectStatus

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-06-03 00:00:00.000000

Notes
-----
Two-stage project creation introduces:

  * a new `rubric_criteria` table (per-project assessment criteria), with
    ON DELETE CASCADE so removing a project cleans up its criteria, but
    deleting a single criterion never touches the project.

  * two new ProjectStatus enum values: `draft` (new projects start here) and
    `ready` (set by the bulk-save endpoint once the rubric is complete).

Grandfathering: any existing rows in `projects` predate the rubric flow and
have no criteria attached. We mark them as `ready` rather than leaving them
in `draft` limbo, otherwise the older projects would suddenly appear in a
"needs rubric setup" state in the UI even though they were finalised under
the old flow. New projects from this revision onward default to `draft`.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extend the projectstatus PG enum with the new values.
    #    ALTER TYPE ... ADD VALUE cannot run inside a transaction block, so
    #    we use COMMIT/BEGIN around it. Alembic's autocommit_block handles this.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE projectstatus ADD VALUE IF NOT EXISTS 'draft'")
        op.execute("ALTER TYPE projectstatus ADD VALUE IF NOT EXISTS 'ready'")

    # 2. Grandfather existing rows: mark them ready (see module docstring).
    op.execute("UPDATE projects SET status = 'ready' WHERE status = 'active'")

    # 3. Change the column default for new rows.
    op.alter_column(
        "projects",
        "status",
        server_default=sa.text("'draft'"),
        existing_type=postgresql.ENUM(
            "draft", "ready", "active", "completed", "archived",
            name="projectstatus",
            create_type=False,
        ),
        existing_nullable=True,
        nullable=False,
    )

    # 4. New rubric_criteria table.
    op.create_table(
        "rubric_criteria",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("points > 0", name="ck_rubric_criteria_points_positive"),
    )
    op.create_index(
        "ix_rubric_criteria_project_id",
        "rubric_criteria",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_rubric_criteria_project_id", table_name="rubric_criteria")
    op.drop_table("rubric_criteria")

    # Revert column default. We do NOT remove the enum values: PostgreSQL has
    # no built-in way to drop enum values, and rolling back the data would
    # require resolving every row that may now hold "draft" or "ready". If a
    # full rollback is required, recreate the enum manually.
    op.alter_column(
        "projects",
        "status",
        server_default=sa.text("'active'"),
        existing_type=postgresql.ENUM(
            "draft", "ready", "active", "completed", "archived",
            name="projectstatus",
            create_type=False,
        ),
        existing_nullable=False,
        nullable=True,
    )
    op.execute("UPDATE projects SET status = 'active' WHERE status IN ('draft', 'ready')")
