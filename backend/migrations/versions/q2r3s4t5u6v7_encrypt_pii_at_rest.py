"""Encryption at rest (G2-162): convert JSONB PII columns to encrypted text.

Application-layer encryption (``app.core.encrypted_types``) stores ciphertext in
text columns. The free-text/PII columns that were already ``String``/``Text``
(student name, transcripts, chat content, evidence quotes, notifications,
extracted document text) need no schema change — the app encrypts new writes and
reads legacy plaintext gracefully.

The three JSONB columns that hold PII or free text must change type, because
ciphertext is not valid JSON and cannot live in a ``jsonb`` column:

* ``assessments.draft_form_json``
* ``assessments.final_form_json``
* ``audit_events.details_json``

Existing JSON is preserved as its textual form (``::text``); the app reads it as
plaintext JSON and re-encrypts on the next write.

Note: the downgrade casts text back to ``jsonb`` with ``::jsonb`` and therefore
only succeeds while the columns still hold plaintext JSON. Once encrypted data
has been written, decrypt it before downgrading.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "q2r3s4t5u6v7"
down_revision = "p1q2r3s4t5u6"
branch_labels = None
depends_on = None


_JSONB_COLUMNS = [
    ("assessments", "draft_form_json"),
    ("assessments", "final_form_json"),
    ("audit_events", "details_json"),
]


def upgrade() -> None:
    for table, column in _JSONB_COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.Text(),
            existing_type=postgresql.JSONB(),
            postgresql_using=f"{column}::text",
            existing_nullable=True,
        )


def downgrade() -> None:
    for table, column in _JSONB_COLUMNS:
        op.alter_column(
            table,
            column,
            type_=postgresql.JSONB(),
            existing_type=sa.Text(),
            postgresql_using=f"{column}::jsonb",
            existing_nullable=True,
        )
