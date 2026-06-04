"""add recordings table (many recordings per assessment)

Moves transcript_text / transcription_status off assessments onto a new
recordings table, removes the one-to-one assessments.recording_file_id, adds
file_records.extension_count (GDPR extension cap), and migrates any existing
single recording into one recordings row.

Revision ID: d60d6f56f4a3
Revises: f6a7b8c9d0e1
Create Date: 2026-06-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d60d6f56f4a3"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Reuse the existing enum type; do not recreate it.
transcription_status_existing = postgresql.ENUM(
    "pending", "processing", "completed", "failed",
    name="transcriptionstatus",
    create_type=False,
)


def upgrade() -> None:
    # --- new recordings table ---
    op.create_table(
        "recordings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("transcript_text", sa.Text(), nullable=True),
        sa.Column(
            "transcription_status",
            transcription_status_existing,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"]),
        sa.ForeignKeyConstraint(["file_id"], ["file_records.id"]),
    )

    # --- file_records: extension cap counter ---
    op.add_column(
        "file_records",
        sa.Column(
            "extension_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    # --- data migration: existing single recording -> one recordings row ---
    op.execute(
        """
        INSERT INTO recordings
            (id, assessment_id, file_id, display_name, sequence_number,
             transcript_text, transcription_status, created_at, deleted_at)
        SELECT
            gen_random_uuid(),
            a.id,
            a.recording_file_id,
            'Recording 1',
            1,
            a.transcript_text,
            a.transcription_status,
            a.created_at,
            NULL
        FROM assessments a
        WHERE a.recording_file_id IS NOT NULL
        """
    )

    # --- drop the old one-to-one / moved columns from assessments ---
    op.drop_constraint("assessments_recording_file_id_fkey", "assessments", type_="foreignkey")
    op.drop_column("assessments", "recording_file_id")
    op.drop_column("assessments", "transcript_text")
    op.drop_column("assessments", "transcription_status")


def downgrade() -> None:
    # Re-add the assessment columns.
    op.add_column(
        "assessments",
        sa.Column(
            "transcription_status",
            transcription_status_existing,
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column("assessments", sa.Column("transcript_text", sa.Text(), nullable=True))
    op.add_column(
        "assessments",
        sa.Column("recording_file_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "assessments_recording_file_id_fkey",
        "assessments",
        "file_records",
        ["recording_file_id"],
        ["id"],
    )

    # Restore the first (lowest sequence) non-deleted recording back onto the assessment.
    op.execute(
        """
        UPDATE assessments a
        SET recording_file_id = r.file_id,
            transcript_text = r.transcript_text,
            transcription_status = r.transcription_status
        FROM (
            SELECT DISTINCT ON (assessment_id)
                assessment_id, file_id, transcript_text, transcription_status
            FROM recordings
            WHERE deleted_at IS NULL
            ORDER BY assessment_id, sequence_number
        ) r
        WHERE a.id = r.assessment_id
        """
    )

    op.drop_column("file_records", "extension_count")
    op.drop_table("recordings")
