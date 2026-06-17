"""Application-layer encryption at rest (G2-162).

All student data is encrypted before it touches disk — both file artifacts on
the ``platform_data`` volume and PII/free-text columns in Postgres — and is only
decrypted in-process at runtime. There is no plaintext student data at rest.

Algorithm: AES-256-GCM (authenticated). Each value gets a fresh random 96-bit
nonce, stored alongside the ciphertext + 128-bit tag.

Wire formats
------------
* Binary blobs (files): ``MAGIC || nonce(12) || ciphertext+tag``.
* Text columns: ``"enc:v1:" || base64(nonce(12) || ciphertext+tag)``.

Key management
--------------
A single 32-byte key is loaded from ``settings.ENCRYPTION_KEY`` (base64 or hex).
If unset, it is derived from ``JWT_SECRET_KEY`` so development works without
extra config; production MUST set an explicit key. See ``app.config``.

Backward compatibility
-----------------------
Decrypt is *graceful*: a value that does not carry the encryption marker is
assumed to be legacy plaintext and returned unchanged. This lets data written
before this feature (and the JSONB→text column migrations) keep working; the
value is re-encrypted the next time it is written.
"""
from __future__ import annotations

import base64
import hashlib
import os
from functools import lru_cache

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Marker for binary file blobs and the prefix for text columns. Bumping the
# version digit lets a future format change be detected per-value.
_MAGIC = b"ENCb1:"
_TEXT_PREFIX = "enc:v1:"
_NONCE_LEN = 12  # 96-bit nonce, the AES-GCM standard/optimal size


def _load_key() -> bytes:
    """Return the 32-byte AES key from settings, deriving one if not configured.

    Imported lazily so that importing this module never forces ``app.config``
    (and its ``load_dotenv``) to run at import time, which keeps test patching
    of settings straightforward.
    """
    from app.config import settings

    raw = (settings.ENCRYPTION_KEY or "").strip()
    if raw:
        key = _decode_key_material(raw)
        if len(key) != 32:
            raise ValueError(
                "ENCRYPTION_KEY must decode to exactly 32 bytes (AES-256); "
                f"got {len(key)} bytes."
            )
        return key
    # Dev fallback: derive a stable 32-byte key from the JWT secret so the app
    # runs without extra config. Production should set ENCRYPTION_KEY explicitly.
    return hashlib.sha256(
        b"g2-162-encryption-at-rest|" + settings.JWT_SECRET_KEY.encode("utf-8")
    ).digest()


def _decode_key_material(raw: str) -> bytes:
    """Decode a configured key from base64, hex, or raw 32-char text."""
    # Try base64 (standard and urlsafe), then hex, then raw bytes.
    for decoder in (base64.b64decode, base64.urlsafe_b64decode):
        try:
            candidate = decoder(raw, validate=True)
            if len(candidate) == 32:
                return candidate
        except Exception:
            pass
    try:
        candidate = bytes.fromhex(raw)
        if len(candidate) == 32:
            return candidate
    except ValueError:
        pass
    return raw.encode("utf-8")


@lru_cache(maxsize=1)
def _cipher() -> AESGCM:
    return AESGCM(_load_key())


def reset_cipher_cache() -> None:
    """Drop the cached cipher. Tests call this after overriding the key."""
    _cipher.cache_clear()


# ---------------------------------------------------------------------------
# Binary (file) API
# ---------------------------------------------------------------------------
def encrypt_bytes(plaintext: bytes) -> bytes:
    """Encrypt raw bytes for storage on disk."""
    nonce = os.urandom(_NONCE_LEN)
    ct = _cipher().encrypt(nonce, plaintext, None)
    return _MAGIC + nonce + ct


def is_encrypted_bytes(blob: bytes) -> bool:
    return blob[: len(_MAGIC)] == _MAGIC


def decrypt_bytes(blob: bytes) -> bytes:
    """Decrypt bytes produced by :func:`encrypt_bytes`.

    Legacy plaintext (no marker) is returned unchanged so files written before
    this feature remain readable.
    """
    if not is_encrypted_bytes(blob):
        return blob
    body = blob[len(_MAGIC):]
    nonce, ct = body[:_NONCE_LEN], body[_NONCE_LEN:]
    return _cipher().decrypt(nonce, ct, None)


# ---------------------------------------------------------------------------
# Text (DB column) API
# ---------------------------------------------------------------------------
def encrypt_str(plaintext: str) -> str:
    """Encrypt a string into the ``enc:v1:<base64>`` column wire format."""
    nonce = os.urandom(_NONCE_LEN)
    ct = _cipher().encrypt(nonce, plaintext.encode("utf-8"), None)
    return _TEXT_PREFIX + base64.b64encode(nonce + ct).decode("ascii")


def is_encrypted_str(value: str) -> bool:
    return isinstance(value, str) and value.startswith(_TEXT_PREFIX)


def decrypt_str(value: str) -> str:
    """Decrypt a string produced by :func:`encrypt_str`.

    Legacy plaintext (no prefix) is returned unchanged.
    """
    if not is_encrypted_str(value):
        return value
    body = base64.b64decode(value[len(_TEXT_PREFIX):])
    nonce, ct = body[:_NONCE_LEN], body[_NONCE_LEN:]
    return _cipher().decrypt(nonce, ct, None).decode("utf-8")


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------
def write_encrypted_file(path, data: bytes) -> None:
    """Write *data* to *path*, encrypted at rest."""
    with open(path, "wb") as fh:
        fh.write(encrypt_bytes(data))


def read_encrypted_file(path) -> bytes:
    """Read *path* and return decrypted bytes (graceful for legacy plaintext)."""
    with open(path, "rb") as fh:
        return decrypt_bytes(fh.read())


def write_encrypted_text(path, text: str) -> None:
    """Write *text* (UTF-8) to *path*, encrypted at rest."""
    write_encrypted_file(path, text.encode("utf-8"))


def read_encrypted_text(path) -> str:
    """Read *path* and return decrypted UTF-8 text (graceful for legacy)."""
    return read_encrypted_file(path).decode("utf-8")
