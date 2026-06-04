"""add recording consent, transcription status, retention, notifications

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c5a1b2c3d401"
down_revision: Union[str, None] = "21b302495d48"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


consent_status = postgresql.ENUM(
    "pending", "accepted", "declined", name="consentstatus"
)
transcription_status = postgresql.ENUM(
    "pending", "processing", "completed", "failed", name="transcriptionstatus"
)
notification_type = postgresql.ENUM(
    "deletion_reminder", name="notificationtype"
)
notification_type_existing = postgresql.ENUM(
    "deletion_reminder", name="notificationtype", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    consent_status.create(bind, checkfirst=True)
    transcription_status.create(bind, checkfirst=True)
    notification_type.create(bind, checkfirst=True)

    # --- assessments: replace binary consent_recorded with richer consent state ---
    op.add_column(
        "assessments",
        sa.Column(
            "transcription_status",
            transcription_status,
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "assessments",
        sa.Column(
            "consent_status",
            consent_status,
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "assessments", sa.Column("consent_confirmed_at", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "assessments",
        sa.Column("consent_confirmed_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_assessments_consent_confirmed_by",
        "assessments",
        "teachers",
        ["consent_confirmed_by"],
        ["id"],
    )
    # Preserve any prior consent: a recorded consent becomes "accepted".
    op.execute(
        "UPDATE assessments SET consent_status = 'accepted' WHERE consent_recorded = true"
    )
    op.drop_column("assessments", "consent_recorded")

    # --- file_records: retention columns (GDPR 3-month deletion) ---
    op.add_column(
        "file_records", sa.Column("delete_after", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "file_records",
        sa.Column(
            "flagged_for_deletion",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "file_records", sa.Column("deleted_at", sa.DateTime(), nullable=True)
    )

    # --- notifications table (deletion reminders) ---
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("teacher_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("type", notification_type_existing, nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("due_date", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"]),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"]),
    )


def downgrade() -> None:
    op.drop_table("notifications")

    op.drop_column("file_records", "deleted_at")
    op.drop_column("file_records", "flagged_for_deletion")
    op.drop_column("file_records", "delete_after")

    op.add_column(
        "assessments",
        sa.Column("consent_recorded", sa.Boolean(), nullable=True),
    )
    op.execute(
        "UPDATE assessments SET consent_recorded = (consent_status = 'accepted')"
    )
    op.drop_constraint(
        "fk_assessments_consent_confirmed_by", "assessments", type_="foreignkey"
    )
    op.drop_column("assessments", "consent_confirmed_by")
    op.drop_column("assessments", "consent_confirmed_at")
    op.drop_column("assessments", "consent_status")
    op.drop_column("assessments", "transcription_status")

    bind = op.get_bind()
    notification_type.drop(bind, checkfirst=True)
    transcription_status.drop(bind, checkfirst=True)
    consent_status.drop(bind, checkfirst=True)
