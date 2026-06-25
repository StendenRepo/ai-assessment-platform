"""SQLAlchemy column types that transparently encrypt at rest (G2-162).

These store ciphertext in the database and decrypt on load, so application and
ORM code is unchanged — a ``Column(EncryptedText)`` behaves like ``Text`` to the
rest of the app while only ciphertext ever lands in Postgres' data files.

Decryption is graceful: rows written before encryption (or migrated from JSONB)
are read back as plaintext and re-encrypted on the next write.
"""
from __future__ import annotations

import json

from sqlalchemy import String, Text, TypeDecorator

from app.core import crypto


class EncryptedString(TypeDecorator):
    """A ``String`` whose value is encrypted at rest."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return crypto.encrypt_str(str(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return crypto.decrypt_str(value)


class EncryptedText(TypeDecorator):
    """A ``Text`` whose value is encrypted at rest."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return crypto.encrypt_str(str(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return crypto.decrypt_str(value)


class EncryptedJSON(TypeDecorator):
    """A JSON-valued column stored as encrypted text.

    Replaces JSONB columns that hold PII/free text. JSON queryability is given
    up (none was relied on — no SQL-side JSON filters exist), in exchange for
    the value being opaque at rest.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return crypto.encrypt_str(json.dumps(value, separators=(",", ":")))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        plaintext = crypto.decrypt_str(value)
        if plaintext == "":
            return None
        return json.loads(plaintext)
