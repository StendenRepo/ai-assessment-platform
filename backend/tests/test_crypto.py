"""Unit tests for application-layer encryption at rest (G2-162)."""
import base64

import pytest

from app.core import crypto


@pytest.fixture(autouse=True)
def _fresh_cipher():
    # The cipher is cached; ensure each test sees the configured key.
    crypto.reset_cipher_cache()
    yield
    crypto.reset_cipher_cache()


class TestByteRoundTrip:
    def test_round_trip(self):
        data = b"binary-audio-\x00\x01\x02-bytes"
        blob = crypto.encrypt_bytes(data)
        assert blob != data
        assert crypto.is_encrypted_bytes(blob)
        assert crypto.decrypt_bytes(blob) == data

    def test_nonce_is_random(self):
        data = b"same plaintext"
        assert crypto.encrypt_bytes(data) != crypto.encrypt_bytes(data)

    def test_legacy_plaintext_passes_through(self):
        # Bytes without the marker are treated as legacy plaintext.
        plaintext = b"not encrypted yet"
        assert not crypto.is_encrypted_bytes(plaintext)
        assert crypto.decrypt_bytes(plaintext) == plaintext

    def test_empty(self):
        blob = crypto.encrypt_bytes(b"")
        assert crypto.decrypt_bytes(blob) == b""


class TestStringRoundTrip:
    def test_round_trip(self):
        text = "Jane Doe. I consent. — café ☕"
        token = crypto.encrypt_str(text)
        assert token.startswith("enc:v1:")
        assert text not in token
        assert crypto.decrypt_str(token) == text

    def test_legacy_plaintext_passes_through(self):
        assert crypto.decrypt_str("plain legacy value") == "plain legacy value"


class TestFileHelpers:
    def test_file_round_trip(self, tmp_path):
        path = tmp_path / "blob.bin"
        crypto.write_encrypted_file(path, b"hello world")
        assert path.read_bytes() != b"hello world"
        assert crypto.read_encrypted_file(path) == b"hello world"

    def test_text_file_round_trip(self, tmp_path):
        path = tmp_path / "note.txt"
        crypto.write_encrypted_text(path, "secret note")
        assert crypto.read_encrypted_text(path) == "secret note"


class TestColumnEncryptionAtRest:
    """Prove encrypted columns store ciphertext while the ORM reads plaintext."""

    def test_student_name_is_ciphertext_in_db_but_plaintext_via_orm(self, db):
        from sqlalchemy import text

        from app.models.student import Student

        student = Student(student_number="S-CRYPTO-1", name="Jane Doe")
        db.add(student)
        db.commit()

        # Raw column value is ciphertext (the marker prefix, name absent).
        raw = db.execute(
            text("SELECT name FROM students WHERE student_number = :n"),
            {"n": "S-CRYPTO-1"},
        ).scalar_one()
        assert raw.startswith("enc:v1:")
        assert "Jane Doe" not in raw

        # ORM load transparently decrypts.
        db.expire_all()
        loaded = db.get(Student, "S-CRYPTO-1")
        assert loaded.name == "Jane Doe"

        db.delete(loaded)
        db.commit()


class TestKeyConfiguration:
    def test_explicit_base64_key_is_used(self, monkeypatch):
        from app.config import settings

        key = base64.b64encode(b"\x11" * 32).decode()
        monkeypatch.setattr(settings, "ENCRYPTION_KEY", key)
        crypto.reset_cipher_cache()
        blob = crypto.encrypt_bytes(b"x")
        assert crypto.decrypt_bytes(blob) == b"x"

    def test_wrong_length_key_rejected(self, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "ENCRYPTION_KEY", base64.b64encode(b"short").decode())
        crypto.reset_cipher_cache()
        with pytest.raises(ValueError):
            crypto.encrypt_bytes(b"x")
