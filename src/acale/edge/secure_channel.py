"""HKDF-SHA256 key derivation and ChaCha20-Poly1305 secure sensor channel.

Nonce uniqueness is enforced across processes by an SQLite counter database.
Do not delete, roll back, or restore an older copy of that database while
continuing to use the same device/epoch key.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


ALGORITHM = "ChaCha20-Poly1305"
KDF_NAME = "HKDF-SHA256"
ENVELOPE_VERSION = 1
NONCE_SIZE = 12
KEY_SIZE = 32
HKDF_SALT = b"ACALE-HKDF-SHA256-v1"


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Value is not valid JSON metadata: {exc}") from exc


class PersistentNonceManager:
    """Allocate unique 96-bit nonces for each derived key using SQLite.

    Nonce = 4-byte key-specific prefix || 8-byte persistent counter.
    SQLite BEGIN IMMEDIATE serializes counter allocation across processes.
    The database must be durable and must not be rolled back or deleted.
    """

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS nonce_counters (
                    key_id TEXT PRIMARY KEY,
                    next_counter INTEGER NOT NULL
                )
            """)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self.database_path), timeout=30, isolation_level=None
        )
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def next_nonce(self, key: bytes) -> bytes:
        key_id = hashlib.sha256(key).hexdigest()
        prefix = hmac.new(
            key, b"ACALE-CHACHA20-NONCE-PREFIX-v1", hashlib.sha256
        ).digest()[:4]

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT next_counter FROM nonce_counters WHERE key_id = ?",
                (key_id,),
            ).fetchone()

            if row is None:
                counter = 0
                connection.execute(
                    "INSERT INTO nonce_counters(key_id, next_counter) VALUES (?, ?)",
                    (key_id, 1),
                )
            else:
                counter = int(row[0])
                if counter >= 2**64:
                    raise OverflowError("Nonce counter exhausted for this key.")
                connection.execute(
                    "UPDATE nonce_counters SET next_counter = ? WHERE key_id = ?",
                    (counter + 1, key_id),
                )
            connection.execute("COMMIT")
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

        return prefix + counter.to_bytes(8, byteorder="big")


class SecureChannel:
    """Encrypt/decrypt JSON-compatible sensor records for a device and epoch."""

    def __init__(
        self,
        master_secret: bytes,
        nonce_database: str | Path,
        device_id: str,
        key_epoch: int = 1,
    ):
        if not isinstance(master_secret, bytes) or len(master_secret) < 32:
            raise ValueError("master_secret must contain at least 32 bytes.")
        if not device_id or not isinstance(device_id, str):
            raise ValueError("device_id must be a non-empty string.")
        if not isinstance(key_epoch, int) or key_epoch < 0:
            raise ValueError("key_epoch must be a non-negative integer.")

        self.device_id = device_id
        self.key_epoch = key_epoch
        info = f"ACALE|device={device_id}|epoch={key_epoch}|v1".encode("utf-8")
        self._key = HKDF(
            algorithm=hashes.SHA256(),
            length=KEY_SIZE,
            salt=HKDF_SALT,
            info=info,
        ).derive(master_secret)
        self._aead = ChaCha20Poly1305(self._key)
        self._nonces = PersistentNonceManager(nonce_database)

    @property
    def key_fingerprint(self) -> str:
        """Non-secret identifier useful for diagnostics; never exposes the key."""
        return hashlib.sha256(self._key).hexdigest()[:16]

    def encrypt_record(self, record: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(record, Mapping):
            raise TypeError("record must be a mapping.")
        plaintext = _canonical_json(record)
        metadata = {
            "device_id": self.device_id,
            "key_epoch": self.key_epoch,
            "sensor_id": str(record.get("sensor_id", self.device_id)),
            "reading_id": str(record.get("reading_id", "")),
            "timestamp": str(record.get("timestamp", "")),
            "context_state": str(record.get("context_state", "")),
        }
        aad = _canonical_json(metadata)
        nonce = self._nonces.next_nonce(self._key)
        ciphertext = self._aead.encrypt(nonce, plaintext, aad)

        return {
            "envelope_version": ENVELOPE_VERSION,
            "algorithm": ALGORITHM,
            "kdf": KDF_NAME,
            "device_id": self.device_id,
            "key_epoch": self.key_epoch,
            "key_fingerprint": self.key_fingerprint,
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "aad": metadata,
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        }

    def decrypt_record(self, envelope: Mapping[str, Any]) -> dict[str, Any]:
        if envelope.get("envelope_version") != ENVELOPE_VERSION:
            raise ValueError("Unsupported envelope version.")
        if envelope.get("algorithm") != ALGORITHM or envelope.get("kdf") != KDF_NAME:
            raise ValueError("Unsupported cryptographic algorithm or KDF.")
        if envelope.get("device_id") != self.device_id:
            raise ValueError("Envelope device_id does not match this channel.")
        if envelope.get("key_epoch") != self.key_epoch:
            raise ValueError("Envelope key_epoch does not match this channel.")

        metadata = envelope.get("aad")
        if not isinstance(metadata, dict):
            raise ValueError("Envelope AAD metadata is missing or invalid.")
        if metadata.get("device_id") != self.device_id:
            raise ValueError("Authenticated device metadata mismatch.")
        if metadata.get("key_epoch") != self.key_epoch:
            raise ValueError("Authenticated key epoch mismatch.")

        try:
            nonce = base64.b64decode(envelope["nonce"], validate=True)
            ciphertext = base64.b64decode(envelope["ciphertext"], validate=True)
            if len(nonce) != NONCE_SIZE:
                raise ValueError("Invalid nonce length.")
            plaintext = self._aead.decrypt(nonce, ciphertext, _canonical_json(metadata))
            decoded = json.loads(plaintext.decode("utf-8"))
        except Exception as exc:
            # Do not expose detailed cryptographic parsing errors to callers.
            raise ValueError("Packet authentication/decryption failed.") from exc

        if not isinstance(decoded, dict):
            raise ValueError("Decrypted record must be a JSON object.")
        return decoded
