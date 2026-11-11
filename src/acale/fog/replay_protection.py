"""Persistent, concurrency-safe replay detection for the ACALE fog node."""
from __future__ import annotations

import sqlite3
from pathlib import Path


class ReplayProtectionStore:
    """Remember authenticated packet nonces and non-empty reading IDs.

    Call register_packet only AFTER AEAD authentication succeeds. A SQLite
    BEGIN IMMEDIATE transaction prevents two workers accepting the same
    packet concurrently.
    """

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS accepted_packets (
                    device_id TEXT NOT NULL,
                    key_epoch INTEGER NOT NULL,
                    nonce TEXT NOT NULL,
                    reading_id TEXT NOT NULL DEFAULT '',
                    accepted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (device_id, key_epoch, nonce)
                )
            """)
            connection.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_device_epoch_reading
                ON accepted_packets(device_id, key_epoch, reading_id)
                WHERE reading_id <> ''
            """)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self.database_path), timeout=30, isolation_level=None
        )
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def register_packet(
        self, device_id: str, key_epoch: int, nonce: str, reading_id: str = ""
    ) -> tuple[bool, str]:
        """Return (accepted, reason); repeated nonce/reading ID is a replay."""
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing_nonce = connection.execute(
                """SELECT 1 FROM accepted_packets
                   WHERE device_id=? AND key_epoch=? AND nonce=?""",
                (device_id, key_epoch, nonce),
            ).fetchone()
            if existing_nonce:
                connection.execute("ROLLBACK")
                return False, "REPLAYED_NONCE"

            if reading_id:
                existing_reading = connection.execute(
                    """SELECT 1 FROM accepted_packets
                       WHERE device_id=? AND key_epoch=? AND reading_id=?""",
                    (device_id, key_epoch, reading_id),
                ).fetchone()
                if existing_reading:
                    connection.execute("ROLLBACK")
                    return False, "REPLAYED_READING_ID"

            connection.execute(
                """INSERT INTO accepted_packets
                   (device_id, key_epoch, nonce, reading_id)
                   VALUES (?, ?, ?, ?)""",
                (device_id, key_epoch, nonce, reading_id),
            )
            connection.execute("COMMIT")
            return True, "ACCEPTED"
        except sqlite3.IntegrityError:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            return False, "REPLAY_DETECTED_CONCURRENTLY"
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()
