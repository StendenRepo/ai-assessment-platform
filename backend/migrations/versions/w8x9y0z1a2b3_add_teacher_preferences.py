"""add teacher_preferences table

Per-teacher UI preferences (theme, language, date format).

Revision ID: w8x9y0z1a2b3
Revises: v7w8x9y0z1a2
Create Date: 2026-06-25 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "w8x9y0z1a2b3"
down_revision: Union[str, None] = "v7w8x9y0z1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enums explicitly so checkfirst works; create_type=False on the
    # table columns prevents SQLAlchemy's _on_table_create hook from trying
    # to create them a second time and failing.
    postgresql.ENUM("light", "dark", name="theme").create(op.get_bind(), checkfirst=True)
    postgresql.ENUM("DD-MM-YYYY", "MM-DD-YYYY", "YYYY-MM-DD", name="dateformat").create(op.get_bind(), checkfirst=True)
    postgresql.ENUM("en", "nl", "de", name="language").create(op.get_bind(), checkfirst=True)

    theme_enum = postgresql.ENUM("light", "dark", name="theme", create_type=False)
    date_format_enum = postgresql.ENUM("DD-MM-YYYY", "MM-DD-YYYY", "YYYY-MM-DD", name="dateformat", create_type=False)
    language_enum = postgresql.ENUM("en", "nl", "de", name="language", create_type=False)

    op.create_table(
        "teacher_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("teacher_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("theme", theme_enum, nullable=False, server_default="light"),
        sa.Column(
            "date_format", date_format_enum, nullable=False, server_default="DD-MM-YYYY"
        ),
        sa.Column("language", language_enum, nullable=False, server_default="en"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"]),
        sa.UniqueConstraint("teacher_id", name="uq_teacher_preferences_teacher_id"),
    )
    op.create_index(
        "ix_teacher_preferences_teacher_id",
        "teacher_preferences",
        ["teacher_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("teacher_preferences")
    op.execute("DROP TYPE IF EXISTS theme")
    op.execute("DROP TYPE IF EXISTS dateformat")
    op.execute("DROP TYPE IF EXISTS language")
