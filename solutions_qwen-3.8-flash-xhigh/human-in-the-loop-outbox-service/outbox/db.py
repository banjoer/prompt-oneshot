"""SQLite connection handling, schema initialization, and migrations.

Migrations are applied through ``PRAGMA user_version``: each step is an
ordered SQL script that bumps the version. Initialization is idempotent and
runs on every startup. Foreign keys and WAL mode are enabled per connection.
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from typing import Iterator, Optional

from .config import Config

SCHEMA_VERSION = 1

_MIGRATIONS: dict[int, str] = {
    1: """
CREATE TABLE IF NOT EXISTS messages (
    id                   TEXT PRIMARY KEY,
    channel              TEXT NOT NULL CHECK (channel IN ('email','whatsapp','telegram')),
    destination          TEXT NOT NULL,
    normalized_destination TEXT NOT NULL,
    destination_kind     TEXT NOT NULL DEFAULT 'individual',
    destination_label    TEXT,
    subject              TEXT,
    body                 TEXT NOT NULL,
    status               TEXT NOT NULL
        CHECK (status IN ('pending','approved','sent','rejected','stale','cancelled')),
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL,
    expires_at           TEXT,
    webhook_url          TEXT,
    rejection_reason     TEXT,
    rejection_at         TEXT,
    revision_number      INTEGER NOT NULL DEFAULT 1 CHECK (revision_number >= 1),
    source               TEXT,
    metadata_json        TEXT
);
CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel);
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_messages_expires ON messages(expires_at);
CREATE INDEX IF NOT EXISTS idx_messages_normalized_dest ON messages(channel, normalized_destination);

CREATE TABLE IF NOT EXISTS message_revisions (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id           TEXT NOT NULL REFERENCES messages(id),
    revision_number      INTEGER NOT NULL CHECK (revision_number >= 1),
    channel              TEXT NOT NULL,
    destination          TEXT NOT NULL,
    normalized_destination TEXT NOT NULL,
    destination_kind     TEXT NOT NULL DEFAULT 'individual',
    destination_label    TEXT,
    subject              TEXT,
    body                 TEXT NOT NULL,
    metadata_json        TEXT,
    references_json      TEXT NOT NULL DEFAULT '[]',
    attachment_ids_json  TEXT NOT NULL DEFAULT '[]',
    expires_at           TEXT,
    rejection_reason     TEXT,
    rejection_at         TEXT,
    source               TEXT,
    webhook_url          TEXT,
    created_at           TEXT NOT NULL,
    UNIQUE (message_id, revision_number)
);

CREATE TABLE IF NOT EXISTS status_history (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id           TEXT NOT NULL REFERENCES messages(id),
    from_status          TEXT,
    to_status            TEXT NOT NULL,
    reason               TEXT,
    revision_number      INTEGER NOT NULL,
    created_at           TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_history_message ON status_history(message_id, id);

CREATE TABLE IF NOT EXISTS attachments (
    id                   TEXT PRIMARY KEY,
    message_id           TEXT NOT NULL REFERENCES messages(id),
    revision_number      INTEGER NOT NULL,
    filename             TEXT NOT NULL,
    stored_name          TEXT NOT NULL UNIQUE,
    mime_type            TEXT NOT NULL,
    size_bytes           INTEGER NOT NULL CHECK (size_bytes >= 0),
    source_type          TEXT NOT NULL CHECK (source_type IN ('multipart','url_download')),
    source_url           TEXT,
    uploaded_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attachments_message ON attachments(message_id, revision_number);

CREATE TABLE IF NOT EXISTS external_references (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id           TEXT NOT NULL REFERENCES messages(id),
    revision_number      INTEGER NOT NULL,
    url                  TEXT NOT NULL,
    created_at           TEXT NOT NULL,
    UNIQUE (message_id, revision_number, url)
);

CREATE TABLE IF NOT EXISTS destination_labels (
    channel              TEXT NOT NULL CHECK (channel IN ('email','whatsapp','telegram')),
    normalized_destination TEXT NOT NULL,
    label                TEXT NOT NULL,
    label_canonical      TEXT NOT NULL,
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL,
    PRIMARY KEY (channel, normalized_destination),
    UNIQUE (channel, label_canonical)
);

CREATE TABLE IF NOT EXISTS webhook_events (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id           TEXT NOT NULL REFERENCES messages(id),
    event                TEXT NOT NULL,
    revision_number      INTEGER NOT NULL,
    message_status       TEXT NOT NULL,
    idempotency_key      TEXT NOT NULL UNIQUE,
    payload_json         TEXT NOT NULL,
    state                TEXT NOT NULL DEFAULT 'queued'
        CHECK (state IN ('queued','delivering','delivered','failed')),
    attempts             INTEGER NOT NULL DEFAULT 0,
    last_status_code     INTEGER,
    last_error           TEXT,
    created_at           TEXT NOT NULL,
    next_attempt_at      TEXT,
    first_attempt_at     TEXT,
    last_attempt_at      TEXT,
    delivered_at         TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_message ON webhook_events(message_id, id);
CREATE INDEX IF NOT EXISTS idx_events_due ON webhook_events(state, next_attempt_at);

CREATE TABLE IF NOT EXISTS webhook_attempts (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id             INTEGER NOT NULL REFERENCES webhook_events(id),
    attempt_number       INTEGER NOT NULL,
    started_at           TEXT NOT NULL,
    finished_at          TEXT,
    http_status          INTEGER,
    error                TEXT
);
CREATE INDEX IF NOT EXISTS idx_attempts_event ON webhook_attempts(event_id, attempt_number);
"""
}

_init_lock = threading.Lock()


def connect(cfg: Config) -> sqlite3.Connection:
    """Open a tuned connection (WAL, foreign keys, busy timeout)."""
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(cfg.db_path), timeout=10.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def init_db(cfg: Config) -> int:
    """Idempotent schema initialization / migration. Returns final version."""
    with _init_lock:
        conn = connect(cfg)
        try:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            for step in sorted(_MIGRATIONS):
                if step <= version:
                    continue
                # executescript runs in autocommit with isolation_level=None.
                conn.executescript(_MIGRATIONS[step])
                conn.execute(f"PRAGMA user_version = {step}")
            return conn.execute("PRAGMA user_version").fetchone()[0]
        finally:
            conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Compare-and-set friendly write transaction (BEGIN IMMEDIATE ... COMMIT)."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    else:
        if conn.in_transaction:
            conn.execute("COMMIT")


@contextmanager
def read_conn(cfg: Config) -> Iterator[sqlite3.Connection]:
    conn = connect(cfg)
    try:
        yield conn
    finally:
        conn.close()


def row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict]:
    return None if row is None else dict(row)
