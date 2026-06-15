"""add generation_runs table and link evidence_matches + notifications

Revision ID: l7m8n9o0p1q2
Revises: k6l7m8n9o0p1
Create Date: 2026-06-15 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "p1q2r3s4t5u6"
down_revision: Union[str, None] = "o0p1q2r3s4t5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "generation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "assessment_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("mode", sa.String(), nullable=False, server_default="standard"),
        sa.Column("ai_model", sa.String(), nullable=True),
        sa.Column(
            "ai_used", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "criteria_total", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "criteria_covered", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "flagged_for_deletion",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["teachers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_generation_runs_assessment_id",
        "generation_runs",
        ["assessment_id"],
    )

    op.add_column(
        "evidence_matches",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_evidence_matches_run_id",
        "evidence_matches",
        "generation_runs",
        ["run_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.add_column(
        "notifications",
        sa.Column(
            "generation_run_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
    )
    op.create_foreign_key(
        "fk_notifications_generation_run_id",
        "notifications",
        "generation_runs",
        ["generation_run_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_notifications_generation_run_id", "notifications", type_="foreignkey"
    )
    op.drop_column("notifications", "generation_run_id")

    op.drop_constraint(
        "fk_evidence_matches_run_id", "evidence_matches", type_="foreignkey"
    )
    op.drop_column("evidence_matches", "run_id")

    op.drop_index(
        "ix_generation_runs_assessment_id", table_name="generation_runs"
    )
    op.drop_table("generation_runs")
