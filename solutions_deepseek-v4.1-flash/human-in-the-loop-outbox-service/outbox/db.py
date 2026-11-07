"""SQLite persistence, schema migration, and transaction helpers."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .timeutil import now_iso

SCHEMA_VERSION = 1

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    channel TEXT NOT NULL CHECK (channel IN ('email', 'whatsapp', 'telegram')),
    destination TEXT NOT NULL,
    destination_normalized TEXT NOT NULL,
    destination_label TEXT,
    subject TEXT,
    body TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'sent', 'rejected', 'stale', 'cancelled')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT,
    webhook_url TEXT,
    rejection_reason TEXT,
    rejection_at TEXT,
    revision_number INTEGER NOT NULL DEFAULT 1 CHECK (revision_number >= 1),
    source TEXT,
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status);
CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel);
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_messages_expires ON messages(expires_at);
CREATE INDEX IF NOT EXISTS idx_messages_dest ON messages(channel, destination_normalized);

CREATE TABLE IF NOT EXISTS message_revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE RESTRICT,
    revision_number INTEGER NOT NULL,
    channel TEXT NOT NULL,
    destination TEXT NOT NULL,
    destination_normalized TEXT NOT NULL,
    destination_label TEXT,
    subject TEXT,
    body TEXT NOT NULL,
    expires_at TEXT,
    webhook_url TEXT,
    source TEXT,
    metadata TEXT NOT NULL DEFAULT '{}',
    rejection_reason TEXT,
    rejection_at TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (message_id, revision_number)
);

CREATE INDEX IF NOT EXISTS idx_revisions_message ON message_revisions(message_id, revision_number);

CREATE TABLE IF NOT EXISTS attachments (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE RESTRICT,
    original_filename TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
    storage_name TEXT NOT NULL UNIQUE,
    uploaded_at TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN ('multipart', 'url_download')),
    source_url TEXT
);

CREATE INDEX IF NOT EXISTS idx_attachments_message ON attachments(message_id);

CREATE TABLE IF NOT EXISTS revision_attachments (
    revision_id INTEGER NOT NULL REFERENCES message_revisions(id) ON DELETE RESTRICT,
    attachment_id TEXT NOT NULL REFERENCES attachments(id) ON DELETE RESTRICT,
    PRIMARY KEY (revision_id, attachment_id)
);

CREATE TABLE IF NOT EXISTS message_references (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE RESTRICT,
    revision_number INTEGER NOT NULL,
    url TEXT NOT NULL,
    origin TEXT NOT NULL DEFAULT 'reference',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_references_message ON message_references(message_id, revision_number);

CREATE TABLE IF NOT EXISTS status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE RESTRICT,
    from_status TEXT,
    to_status TEXT NOT NULL,
    reason TEXT,
    revision_number INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_status_history_message ON status_history(message_id, id);

CREATE TABLE IF NOT EXISTS destinations (
    channel TEXT NOT NULL,
    destination_normalized TEXT NOT NULL,
    destination TEXT NOT NULL,
    label TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (channel, destination_normalized)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_destinations_label_unique
    ON destinations(channel, label COLLATE NOCASE)
    WHERE label IS NOT NULL;

CREATE TABLE IF NOT EXISTS webhook_events (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE RESTRICT,
    event TEXT NOT NULL,
    revision_number INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'delivering', 'delivered', 'failed')),
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    delivered_at TEXT,
    UNIQUE (message_id, event, revision_number)
);

CREATE INDEX IF NOT EXISTS idx_webhook_events_message ON webhook_events(message_id, created_at);

CREATE TABLE IF NOT EXISTS webhook_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL REFERENCES webhook_events(id) ON DELETE RESTRICT,
    attempt_number INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('success', 'failed')),
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    http_status INTEGER,
    error TEXT,
    response_body TEXT
);

CREATE INDEX IF NOT EXISTS idx_webhook_attempts_event ON webhook_attempts(event_id, attempt_number);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
"""

MIGRATIONS: list[tuple[int, str]] = [(1, SCHEMA_V1)]


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            str(self.path),
            timeout=15.0,
            isolation_level=None,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 15000")
        conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    def initialize(self) -> None:
        conn = self.connect()
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            applied = {
                int(row["version"])
                for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
            }
            for version, script in MIGRATIONS:
                if version in applied:
                    continue
                conn.executescript(script)
                conn.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (version, now_iso()),
                )
            # Keep WAL enabled even when switching databases between processes.
            conn.execute("PRAGMA journal_mode = WAL")
        finally:
            conn.close()

    @contextmanager
    def transaction(
        self, conn: sqlite3.Connection, immediate: bool = True
    ) -> Iterator[sqlite3.Connection]:
        conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
        try:
            yield conn
        except BaseException:
            conn.rollback()
            raise
        else:
            conn.commit()
