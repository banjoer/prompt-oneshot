"""Domain service: submission, lifecycle transitions, revisions, expiration,
destinations, handoff preparation, and webhook event recording.

The HTTP layer (app.py) only parses requests and calls these functions.
Every state change happens inside a ``BEGIN IMMEDIATE`` transaction with
compare-and-set ``UPDATE ... WHERE status = <expected>`` semantics, so
duplicate or concurrent requests cannot both succeed. Webhook event rows are
committed together with the state change but delivered only afterwards, so a
delivery failure can never roll back a transition.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Iterable, Optional

from . import netguard
from .channels import Destination, HandoffRequest, allowed_channels, adapter_for
from .config import Config
from .db import transaction
from .errors import ApiError, bad_request, conflict, not_found
from .ids import new_message_id
from .storage import AttachmentStore, StoredAttachment
from .timeutil import iso, now_iso, now_utc, parse_iso, to_canonical

MAX_BODY_CHARS = 200_000
MAX_SUBJECT_CHARS = 500
MAX_LABEL_CHARS = 120
MAX_SOURCE_CHARS = 200
MAX_REFERENCES = 50
MAX_METADATA_BYTES = 65_536
MAX_TTL_SECONDS = 10 * 365 * 24 * 3600

TERMINAL_STATUSES = {"sent", "stale", "cancelled"}
ALL_STATUSES = {"pending", "approved", "sent", "rejected", "stale", "cancelled"}

ALLOWED_ACTIONS = {
    "pending": ["approve", "reject", "cancel", "patch"],
    "approved": ["handoff", "mark-sent", "cancel"],
    "rejected": ["patch", "cancel"],
    "sent": [],
    "stale": [],
    "cancelled": [],
}


@dataclass
class OutboxContext:
    cfg: Config
    store: AttachmentStore
    webhook_sender: Optional[Any] = None  # callable(url, payload, timeout) -> status; injectable in tests
    notifier: Optional[Any] = None        # callable() nudging the webhook worker

    def connect(self) -> sqlite3.Connection:
        from .db import connect
        return connect(self.cfg)

    def notify_webhooks(self) -> None:
        if self.notifier is not None:
            try:
                self.notifier()
            except Exception:
                pass


@dataclass
class Upload:
    """A multipart file part handed to the service layer."""
    filename: Optional[str]
    stream: Any


# ---------------------------------------------------------------------------
# payload validation
# ---------------------------------------------------------------------------

def _require_str(raw: dict, key: str, *, max_len: int, allow_empty: bool = False) -> str:
    if key not in raw:
        raise bad_request(f"'{key}' is required", field=key)
    value = raw[key]
    if not isinstance(value, str):
        raise bad_request(f"'{key}' must be a string", field=key)
    value = value.strip()
    if not allow_empty and not value:
        raise bad_request(f"'{key}' must be a non-empty string", field=key)
    if len(value) > max_len:
        raise bad_request(f"'{key}' is too long (max {max_len} characters)", field=key)
    return value


def _optional_str(raw: dict, key: str, *, max_len: int) -> Optional[str]:
    if key not in raw or raw[key] is None:
        return None
    if not isinstance(raw[key], str):
        raise bad_request(f"'{key}' must be a string", field=key)
    value = raw[key].strip()
    if not value:
        return None
    if len(value) > max_len:
        raise bad_request(f"'{key}' is too long (max {max_len} characters)", field=key)
    return value


def _validate_metadata(raw: dict) -> Optional[dict]:
    if "metadata" not in raw or raw["metadata"] is None:
        return None
    meta = raw["metadata"]
    if not isinstance(meta, dict):
        raise bad_request("'metadata' must be a JSON object", field="metadata")
    try:
        serialized = json.dumps(meta, ensure_ascii=False)
    except (TypeError, ValueError):
        raise bad_request("'metadata' must be JSON-serializable", field="metadata") from None
    if len(serialized.encode("utf-8")) > MAX_METADATA_BYTES:
        raise bad_request(f"'metadata' is too large (max {MAX_METADATA_BYTES} bytes serialized)",
                          field="metadata")
    return meta


def _validate_references(raw: dict, *, present: bool) -> Optional[list[str]]:
    if not present or raw is None:
        return None
    refs = raw
    if not isinstance(refs, list):
        raise bad_request("'references' must be a list of URL strings", field="references")
    if len(refs) > MAX_REFERENCES:
        raise bad_request(f"'references' may hold at most {MAX_REFERENCES} URLs", field="references")
    cleaned: list[str] = []
    for item in refs:
        if not isinstance(item, str):
            raise bad_request("each reference must be a URL string", field="references")
        item = item.strip()
        if not item:
            raise bad_request("references must be non-empty URL strings", field="references")
        if len(item) > 2048:
            raise bad_request("reference URL is too long (max 2048 characters)", field="references")
        scheme = item.split(":", 1)[0].lower() if ":" in item.split("/", 1)[0] else ""
        if scheme not in ("http", "https"):
            raise bad_request(f"reference {item!r} must use http or https", field="references")
        if item not in cleaned:
            cleaned.append(item)
    return cleaned


def _resolve_expiration(raw: dict, *, patch: bool) -> tuple[bool, Optional[str]]:
    """Returns (touched, canonical expires_at or None for 'cleared')."""
    has_abs = "expires_at" in raw
    has_ttl = "ttl_seconds" in raw
    if has_abs and has_ttl:
        raise bad_request("'expires_at' and 'ttl_seconds' are mutually exclusive",
                          field="expires_at")
    if not has_abs and not has_ttl:
        return False, None
    if has_ttl:
        ttl = raw["ttl_seconds"]
        if isinstance(ttl, bool) or not isinstance(ttl, int) or ttl <= 0:
            raise bad_request("'ttl_seconds' must be a positive integer", field="ttl_seconds")
        if ttl > MAX_TTL_SECONDS:
            raise bad_request(f"'ttl_seconds' exceeds the maximum of {MAX_TTL_SECONDS}",
                              field="ttl_seconds")
        return True, iso(now_utc() + timedelta(seconds=ttl))
    value = raw["expires_at"]
    if value is None:
        if not patch:
            raise bad_request("'expires_at' must be a timestamp", field="expires_at")
        return True, None  # explicit clear (PATCH only path)
    canonical = to_canonical(str(value), field_name="expires_at")
    if not patch and parse_iso(canonical) <= now_utc():
        raise bad_request("'expires_at' must be in the future", field="expires_at")
    return True, canonical


def _validate_webhook_url(value: Optional[str], cfg: Config) -> Optional[str]:
    if value is None:
        return None
    try:
        return netguard.validate_url(value, field="webhook_url",
                                     allow_private=cfg.allow_private_urls)
    except netguard.UrlBlockedError as exc:
        raise bad_request(f"invalid webhook_url: {exc.message}", field="webhook_url") from None


# ---------------------------------------------------------------------------
# submission
# ---------------------------------------------------------------------------

@dataclass
class ParsedContent:
    channel: str
    dest: Destination
    subject: Optional[str]
    body: str
    destination_label: Optional[str]
    expires_at: Optional[str]
    expiry_touched: bool
    webhook_url: Optional[str]
    source: Optional[str]
    metadata: Optional[dict]
    references: Optional[list[str]]


def parse_content(ctx: OutboxContext, raw: dict, *, patch: bool) -> ParsedContent:
    if "channel" not in raw:
        raise bad_request("'channel' is required", field="channel")
    channel = _require_str(raw, "channel", max_len=32).lower()
    adapter = adapter_for(channel)
    dest = adapter.validate_destination(_require_str(raw, "destination", max_len=300))
    body = _require_str(raw, "body", max_len=MAX_BODY_CHARS)
    subject = _optional_str(raw, "subject", max_len=MAX_SUBJECT_CHARS)
    label = _optional_str(raw, "destination_label", max_len=MAX_LABEL_CHARS)
    touched, expires_at = _resolve_expiration(raw, patch=patch)
    webhook_url = None
    if "webhook_url" in raw and raw["webhook_url"] is not None:
        webhook_url = _validate_webhook_url(
            _optional_str(raw, "webhook_url", max_len=2048), ctx.cfg)
    source = _optional_str(raw, "source", max_len=MAX_SOURCE_CHARS)
    metadata = _validate_metadata(raw) if "metadata" in raw else None
    references = _validate_references(raw.get("references"), present="references" in raw)
    return ParsedContent(channel, dest, subject, body, label, expires_at, touched,
                         webhook_url, source, metadata, references)


def process_attachment_specs(ctx: OutboxContext, raw: dict,
                             uploads: list[Upload],
                             message_id: str, revision_number: int,
                             conn: sqlite3.Connection,
                             total_budget: int) -> tuple[list[str], list[str]]:
    """Persist multipart uploads and JSON attachment specs / references.

    Returns (attachment_ids, reference_urls). Enforces size budgets; raises
    413/400 on violations. Reference-style specs are stored as external URL
    references and never fetched.
    """
    attachment_ids: list[str] = []
    references: list[str] = []
    created_stored: list[StoredAttachment] = []
    remaining = total_budget
    for up in uploads:
        if remaining <= 0:
            raise _cleanup_error(ctx, created_stored,
                                 "message attachment budget exceeded before all uploads were stored",
                                 per_message=True)
        stored = ctx.store.save_stream(
            up.stream, original_filename=up.filename,
            max_file_bytes=min(ctx.cfg.max_attachment_bytes, remaining))
        remaining -= stored.size_bytes
        _insert_attachment(conn, message_id, revision_number, stored)
        attachment_ids.append(stored.id)
        created_stored.append(stored)

    specs = raw.get("attachments")
    if specs is not None and not isinstance(specs, list):
        raise bad_request("'attachments' must be a list of objects with 'kind' and 'url'",
                          field="attachments")
    for spec in specs or []:
        if not isinstance(spec, dict):
            raise bad_request("each attachment must be an object", field="attachments")
        kind = spec.get("kind")
        url = spec.get("url")
        if kind not in ("url_reference", "url_download"):
            raise bad_request(
                "attachment 'kind' must be 'url_reference' or 'url_download'",
                field="attachments", allowed=["url_reference", "url_download"])
        if not isinstance(url, str) or not url.strip():
            raise bad_request("attachment 'url' must be a non-empty string", field="attachments")
        url = url.strip()
        if kind == "url_reference":
            # Stored as a reference; NEVER fetched.
            scheme = url.split(":", 1)[0].lower() if ":" in url.split("/", 1)[0] else ""
            if scheme not in ("http", "https"):
                raise bad_request(f"url_reference {url!r} must use http or https",
                                  field="attachments")
            if url not in references:
                references.append(url)
            continue
        if remaining <= 0:
            raise _cleanup_error(ctx, created_stored,
                                 "message attachment budget exceeded before all downloads completed",
                                 per_message=True)
        try:
            data, content_type, cd_filename = netguard.http_get(
                url, allow_private=ctx.cfg.allow_private_urls,
                timeout=ctx.cfg.download_timeout_seconds,
                max_bytes=min(ctx.cfg.max_attachment_bytes, remaining),
                max_redirects=ctx.cfg.max_redirects)
        except netguard.UrlBlockedError as exc:
            if "too large" in exc.message or "size limit" in exc.message:
                raise _cleanup_error(ctx, created_stored, exc.message, per_message=True) from None
            raise bad_request(f"url_download failed: {exc.message}", field="attachments",
                              url=url) from None
        declared_name = _optional_str(spec, "filename", max_len=255) if isinstance(spec, dict) else None
        stored = ctx.store.save_bytes(
            data, original_filename=declared_name or cd_filename or url,
            source_type="url_download", source_url=url, declared_mime=content_type)
        remaining -= stored.size_bytes
        _insert_attachment(conn, message_id, revision_number, stored)
        attachment_ids.append(stored.id)
        created_stored.append(stored)

    extra_refs = raw.get("references") if isinstance(raw.get("references"), list) else []
    for ref in extra_refs:
        if isinstance(ref, str) and ref.strip() and ref.strip() not in references:
            references.append(ref.strip())
    return attachment_ids, references


def _cleanup_error(ctx: OutboxContext, created: list[StoredAttachment], message: str, *,
                   per_message: bool) -> ApiError:
    ctx.store.delete_quietly(s.stored_name for s in created)
    if per_message:
        from .errors import too_large
        return too_large(message)
    return bad_request(message)


def submit_message(ctx: OutboxContext, raw: dict, uploads: list[Upload]) -> dict:
    content = parse_content(ctx, raw, patch=False)
    message_id = new_message_id()
    now = now_iso()
    conn = ctx.connect()
    try:
        with transaction(conn):
            conn.execute(
                """INSERT INTO messages (id, channel, destination, normalized_destination,
                       destination_kind, destination_label, subject, body, status, created_at,
                       updated_at, expires_at, webhook_url, revision_number, source, metadata_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (message_id, content.channel, content.dest.raw, content.dest.normalized,
                 content.dest.kind, content.destination_label, content.subject, content.body,
                 "pending", now, now, content.expires_at, content.webhook_url, 1,
                 content.source, json.dumps(content.metadata, ensure_ascii=False)
                 if content.metadata is not None else None))
            attachment_ids, references = _collect_specs(ctx, raw, uploads, message_id, 1, conn)
            _insert_revision(conn, message_id, 1, content, attachment_ids, references, now)
            _insert_references(conn, message_id, 1, references, now)
            _record_transition(conn, message_id, None, "pending", None, 1, now)
    finally:
        conn.close()
    return {
        "id": message_id,
        "status": "pending",
        "created_at": now,
        "revision_number": 1,
    }


def _collect_specs(ctx: OutboxContext, raw: dict, uploads: list[Upload], message_id: str,
                   revision: int, conn: sqlite3.Connection) -> tuple[list[str], list[str]]:
    return process_attachment_specs(ctx, raw, uploads, message_id, revision, conn,
                                    ctx.cfg.max_message_attachment_bytes)


# ---------------------------------------------------------------------------
# views
# ---------------------------------------------------------------------------

def _attachments_for(conn: sqlite3.Connection, message_id: str, revision: int,
                     ids: Optional[list[str]] = None) -> list[dict]:
    if ids is not None:
        if not ids:
            return []
        marks = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT * FROM attachments WHERE message_id=? AND id IN ({marks}) ORDER BY uploaded_at, id",
            [message_id, *ids]).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM attachments WHERE message_id=? AND revision_number=? ORDER BY uploaded_at, id",
            (message_id, revision)).fetchall()
    return [
        {
            "id": r["id"], "filename": r["filename"], "mime_type": r["mime_type"],
            "size_bytes": r["size_bytes"], "storage_reference": r["stored_name"],
            "uploaded_at": r["uploaded_at"], "source_type": r["source_type"],
            "source_url": r["source_url"],
            "download_url": f"/api/messages/{message_id}/attachments/{r['id']}",
        } for r in rows
    ]


def managed_label(conn: sqlite3.Connection, channel: str, normalized_destination: str) -> Optional[str]:
    row = conn.execute(
        "SELECT label FROM destination_labels WHERE channel=? AND normalized_destination=?",
        (channel, normalized_destination)).fetchone()
    return row["label"] if row else None


def message_view(conn: sqlite3.Connection, row: sqlite3.Row, *, full: bool) -> dict:
    view = {
        "id": row["id"],
        "channel": row["channel"],
        "destination": row["destination"],
        "normalized_destination": row["normalized_destination"],
        "destination_kind": row["destination_kind"],
        "destination_label": row["destination_label"],
        "label": managed_label(conn, row["channel"], row["normalized_destination"])
                 or row["destination_label"],
        "subject": row["subject"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "expires_at": row["expires_at"],
        "revision_number": row["revision_number"],
        "source": row["source"],
        "webhook_url": row["webhook_url"],
        "allowed_actions": ALLOWED_ACTIONS.get(row["status"], []),
    }
    if full:
        view["body"] = row["body"]
        view["rejection_reason"] = row["rejection_reason"]
        view["rejection_at"] = row["rejection_at"]
        view["metadata"] = json.loads(row["metadata_json"]) if row["metadata_json"] else None
        attachment_ids, references = current_revision_refs(conn, row["id"], row["revision_number"])
        view["attachments"] = _attachments_for(conn, row["id"], row["revision_number"], attachment_ids)
        view["attachment_count"] = len(view["attachments"])
        view["references"] = references
    else:
        preview = (row["body"] or "").replace("\r\n", "\n")
        view["body_preview"] = preview if len(preview) <= 300 else preview[:297] + "..."
        att_count = conn.execute(
            "SELECT COUNT(*) AS c FROM attachments WHERE message_id=? AND revision_number=?",
            (row["id"], row["revision_number"])).fetchone()["c"]
        view["attachment_count"] = att_count
    return view


def current_revision_refs(conn: sqlite3.Connection, message_id: str,
                          revision: int) -> tuple[list[str], list[str]]:
    row = conn.execute(
        "SELECT attachment_ids_json, references_json FROM message_revisions "
        "WHERE message_id=? AND revision_number=?", (message_id, revision)).fetchone()
    if row is None:
        return [], []
    return json.loads(row["attachment_ids_json"]), json.loads(row["references_json"])


# ---------------------------------------------------------------------------
# expiration
# ---------------------------------------------------------------------------

def expire_message_in_tx(conn: sqlite3.Connection, row: sqlite3.Row, reason_ts: str,
                         reason: str = "expired") -> dict:
    """Transactional pending/approved -> stale via CAS. Caller holds the txn."""
    cur = conn.execute(
        "UPDATE messages SET status='stale', updated_at=?, rejection_reason=NULL WHERE id=? "
        "AND status IN ('pending','approved')", (reason_ts, row["id"]))
    if cur.rowcount != 1:
        refreshed = conn.execute("SELECT status FROM messages WHERE id=?", (row["id"],)).fetchone()
        return {"won": False, "status": refreshed["status"] if refreshed else None}
    _record_transition(conn, row["id"], row["status"], "stale", reason,
                       row["revision_number"], reason_ts)
    _emit_event(conn, row, "message.stale", "stale", reason_ts,
                extra={"expires_at": row["expires_at"], "cause": reason})
    return {"won": True, "status": "stale"}


def is_expired(row: sqlite3.Row, now_dt=None) -> bool:
    if not row["expires_at"] or row["status"] not in ("pending", "approved"):
        return False
    return parse_iso(row["expires_at"]) <= (now_dt or now_utc())


def sweep_expired(ctx: OutboxContext, *, ids: Optional[Iterable[str]] = None) -> int:
    """Flip all expired pending/approved messages to stale. Returns count."""
    conn = ctx.connect()
    changed = 0
    try:
        while True:
            with transaction(conn):
                if ids is not None:
                    placeholders = [i for i in ids]
                    rows = []
                    for mid in placeholders:
                        r = conn.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()
                        if r is not None:
                            rows.append(r)
                else:
                    rows = conn.execute(
                        "SELECT * FROM messages WHERE status IN ('pending','approved') "
                        "AND expires_at IS NOT NULL").fetchall()
                now = now_utc()
                progressed = 0
                for row in rows:
                    if is_expired(row, now):
                        if expire_message_in_tx(conn, row, now_iso())["won"]:
                            progressed += 1
                changed += progressed
                if progressed == 0:
                    break
            # re-run to catch rows expiring between attempts; loop is safety-bounded
            # because progressed==0 always breaks above.
            if ids is not None:
                break
    finally:
        conn.close()
        if changed:
            ctx.notify_webhooks()
    return changed


def _ensure_not_expired(conn: sqlite3.Connection, row: sqlite3.Row) -> sqlite3.Row:
    """Lazy expiration check used before reads/transitions/handoff. Returns fresh row."""
    if is_expired(row):
        with transaction(conn):
            row2 = conn.execute("SELECT * FROM messages WHERE id=?", (row["id"],)).fetchone()
            if row2 is not None and is_expired(row2):
                expire_message_in_tx(conn, row2, now_iso())
        row = conn.execute("SELECT * FROM messages WHERE id=?", (row["id"],)).fetchone() or row
    return row


# ---------------------------------------------------------------------------
# reads
# ---------------------------------------------------------------------------

def get_message_row(conn: sqlite3.Connection, message_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
    if row is None:
        raise not_found(f"message {message_id!r} does not exist", message_id=message_id)
    return row


def get_message(ctx: OutboxContext, message_id: str) -> dict:
    conn = ctx.connect()
    try:
        row = get_message_row(conn, message_id)
        row = _ensure_not_expired(conn, row)
        return message_view(conn, row, full=True)
    finally:
        conn.close()


def list_messages(ctx: OutboxContext, *, status: Optional[str] = None,
                  channel: Optional[str] = None, destination: Optional[str] = None,
                  created_from: Optional[str] = None, created_to: Optional[str] = None,
                  expires_from: Optional[str] = None, expires_to: Optional[str] = None,
                  limit: int = 20, offset: int = 0, sort: str = "newest") -> dict:
    where: list[str] = []
    params: list[Any] = []
    if status:
        wanted = [s.strip() for s in status.split(",") if s.strip()]
        bad = [s for s in wanted if s not in ALL_STATUSES]
        if bad:
            raise bad_request(f"unknown status filter: {bad[0]!r}", field="status",
                              allowed=sorted(ALL_STATUSES))
        where.append("messages.status IN (" + ",".join("?" * len(wanted)) + ")")
        params.extend(wanted)
    if channel:
        if channel not in allowed_channels():
            raise bad_request(f"unknown channel filter: {channel!r}", field="channel",
                              allowed=allowed_channels())
        where.append("messages.channel = ?")
        params.append(channel)
    if destination:
        needle = "%" + _like_escape(destination.strip().lower()) + "%"
        where.append("(lower(messages.destination) LIKE ? ESCAPE '\\' "
                     "OR lower(messages.normalized_destination) LIKE ? ESCAPE '\\' "
                     "OR lower(messages.destination_label) LIKE ? ESCAPE '\\' "
                     "OR EXISTS (SELECT 1 FROM destination_labels dl WHERE "
                     "dl.channel = messages.channel AND dl.normalized_destination = "
                     "messages.normalized_destination AND lower(dl.label) LIKE ? ESCAPE '\\'))")
        params.extend([needle, needle, needle, needle])
    if created_from:
        where.append("messages.created_at >= ?")
        params.append(to_canonical(created_from, field_name="created_from"))
    if created_to:
        from .timeutil import end_of_day_iso
        where.append("messages.created_at <= ?")
        params.append(end_of_day_iso(created_to, field_name="created_to"))
    if expires_from:
        where.append("messages.expires_at IS NOT NULL AND messages.expires_at >= ?")
        params.append(to_canonical(expires_from, field_name="expires_from"))
    if expires_to:
        from .timeutil import end_of_day_iso
        where.append("messages.expires_at IS NOT NULL AND messages.expires_at <= ?")
        params.append(end_of_day_iso(expires_to, field_name="expires_to"))

    sort_sql = {
        "newest": "messages.created_at DESC, messages.id DESC",
        "oldest": "messages.created_at ASC, messages.id ASC",
        "expires_soon": "CASE WHEN messages.expires_at IS NULL THEN 1 ELSE 0 END, "
                        "messages.expires_at ASC, messages.created_at DESC",
        "expires_late": "CASE WHEN messages.expires_at IS NULL THEN 1 ELSE 0 END, "
                        "messages.expires_at DESC, messages.created_at DESC",
    }[sort]
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    conn = ctx.connect()
    try:
        sweep_expired(ctx, ids=None)
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM messages {clause}", params).fetchone()["c"]
        rows = conn.execute(
            f"SELECT messages.* FROM messages {clause} ORDER BY {sort_sql} LIMIT ? OFFSET ?",
            [*params, limit, offset]).fetchall()
        items = [message_view(conn, r, full=False) for r in rows]
    finally:
        conn.close()
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def _like_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def history(ctx: OutboxContext, message_id: str) -> dict:
    conn = ctx.connect()
    try:
        row = get_message_row(conn, message_id)
        row = _ensure_not_expired(conn, row)
        revisions = []
        for r in conn.execute(
                "SELECT * FROM message_revisions WHERE message_id=? ORDER BY revision_number",
                (message_id,)).fetchall():
            attachment_ids = json.loads(r["attachment_ids_json"])
            entry = {
                "revision_number": r["revision_number"],
                "created_at": r["created_at"],
                "change": "created" if r["revision_number"] == 1 else "revised",
                "channel": r["channel"],
                "destination": r["destination"],
                "subject": r["subject"],
                "body": r["body"],
                "metadata": json.loads(r["metadata_json"]) if r["metadata_json"] else None,
                "references": json.loads(r["references_json"]),
                "expires_at": r["expires_at"],
                "rejection_reason": r["rejection_reason"],
                "rejection_at": r["rejection_at"],
                "attachments": _attachments_for(conn, message_id, r["revision_number"],
                                                json.loads(r["attachment_ids_json"])),
            }
            revisions.append(entry)
        transitions = [
            {
                "from_status": t["from_status"], "to_status": t["to_status"],
                "reason": t["reason"], "revision_number": t["revision_number"],
                "timestamp": t["created_at"],
            }
            for t in conn.execute(
                "SELECT * FROM status_history WHERE message_id=? ORDER BY id", (message_id,)
            ).fetchall()
        ]
        events = webhook_event_rows(conn, message_id, include_payload=False)
        timeline = sorted(
            [{"kind": "transition", "timestamp": t["timestamp"], "data": t} for t in transitions],
            key=lambda e: e["timestamp"])
        return {
            "message_id": message_id,
            "current_status": row["status"],
            "revision_number": row["revision_number"],
            "revisions": revisions,
            "transitions": transitions,
            "timeline": timeline,
            "webhook_events": events,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# lifecycle transitions
# ---------------------------------------------------------------------------

def _record_transition(conn: sqlite3.Connection, message_id: str, from_status: Optional[str],
                       to_status: str, reason: Optional[str], revision: int, ts: str) -> None:
    conn.execute(
        "INSERT INTO status_history (message_id, from_status, to_status, reason, revision_number, "
        "created_at) VALUES (?,?,?,?,?,?)",
        (message_id, from_status, to_status, reason, revision, ts))


def _emit_event(conn: sqlite3.Connection, msg_row: sqlite3.Row, event: str, status_after: str,
                ts: str, extra: Optional[dict] = None) -> None:
    """Persist a webhook event inside the caller's transaction (delivery is async)."""
    if not msg_row["webhook_url"]:
        return
    payload = {
        "event": event,
        "message_id": msg_row["id"],
        "status": status_after,
        "revision_number": msg_row["revision_number"],
        "timestamp": ts,
    }
    if extra:
        payload.update(extra)
    key = f"{msg_row['id']}|{event}|{msg_row['revision_number']}"
    conn.execute(
        "INSERT OR IGNORE INTO webhook_events (message_id, event, revision_number, "
        "message_status, idempotency_key, payload_json, created_at, next_attempt_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (msg_row["id"], event, msg_row["revision_number"], status_after, key,
         json.dumps(payload, ensure_ascii=False), ts, ts))


def _cas_update(conn: sqlite3.Connection, message_id: str, expected: tuple[str, ...],
                **fields: Any) -> int:
    sets = ", ".join(f"{k} = ?" for k in fields)
    params = list(fields.values()) + [message_id]
    placeholders = ",".join("?" * len(expected))
    params += list(expected)
    cur = conn.execute(
        f"UPDATE messages SET {sets} WHERE id = ? AND status IN ({placeholders})", params)
    return cur.rowcount


def _transition(ctx: OutboxContext, message_id: str, to_status: str, *,
                from_statuses: tuple[str, ...], reason: Optional[str],
                event: str, extra_sets: dict,
                extra_payload: Optional[dict] = None) -> dict:
    conn = ctx.connect()
    try:
        row = get_message_row(conn, message_id)
        row = _ensure_not_expired(conn, row)
        with transaction(conn):
            row = conn.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
            if row is None:
                raise not_found(f"message {message_id!r} does not exist", message_id=message_id)
            if row["status"] not in from_statuses:
                raise conflict(
                    f"the requested transition is not allowed from status {row['status']!r}",
                    current_status=row["status"],
                    allowed_actions=ALLOWED_ACTIONS.get(row["status"], []))
            now = now_iso()
            sets = {"status": to_status, "updated_at": now, **extra_sets}
            won = _cas_update(conn, message_id, (row["status"],), **sets)
            if won != 1:
                refreshed = conn.execute("SELECT status FROM messages WHERE id=?",
                                         (message_id,)).fetchone()
                raise conflict("the message changed concurrently; retry with a fresh view",
                               current_status=refreshed["status"],
                               allowed_actions=ALLOWED_ACTIONS.get(refreshed["status"], []))
            _record_transition(conn, message_id, row["status"], to_status, reason,
                               row["revision_number"], now)
            updated_row = conn.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
            _emit_event(conn, updated_row, event, to_status, now, extra_payload)
            view = message_view(conn, updated_row, full=True)
        ctx.notify_webhooks()
        return view
    finally:
        conn.close()


def approve_message(ctx: OutboxContext, message_id: str) -> dict:
    return _transition(
        ctx, message_id, "approved", from_statuses=("pending",), reason=None,
        event="message.approved", extra_sets={"rejection_reason": None,
                                              "rejection_at": None},
        extra_payload=None)


def reject_message(ctx: OutboxContext, message_id: str, reason: str) -> dict:
    if not isinstance(reason, str) or not reason.strip():
        raise bad_request("rejection requires a non-empty 'reason'", field="reason")
    reason = reason.strip()
    if len(reason) > 2000:
        raise bad_request("'reason' is too long (max 2000 characters)", field="reason")
    return _transition(
        ctx, message_id, "rejected", from_statuses=("pending",), reason=reason,
        event="message.rejected",
        extra_sets={"rejection_reason": reason, "rejection_at": now_iso()},
        extra_payload={"rejection_reason": reason})


def cancel_message(ctx: OutboxContext, message_id: str, reason: Optional[str] = None) -> dict:
    if reason is not None and (not isinstance(reason, str) or len(reason) > 2000):
        raise bad_request("'reason' must be a string up to 2000 characters", field="reason")
    return _transition(
        ctx, message_id, "cancelled", from_statuses=("pending", "rejected", "approved"),
        reason=reason or "cancelled", event="message.cancelled",
        extra_sets={"rejection_reason": None, "rejection_at": None},
        extra_payload={"cancellation_reason": reason} if reason else None)


def mark_sent(ctx: OutboxContext, message_id: str, note: Optional[str] = None) -> dict:
    if note is not None and (not isinstance(note, str) or len(note) > 2000):
        raise bad_request("'note' must be a string up to 2000 characters", field="note")
    return _transition(
        ctx, message_id, "sent", from_statuses=("approved",), reason=note or "marked sent by reviewer",
        event="message.sent", extra_sets={},
        extra_payload={"note": note} if note else None)


# ---------------------------------------------------------------------------
# revision (PATCH)
# ---------------------------------------------------------------------------

def patch_message(ctx: OutboxContext, message_id: str, raw: dict, uploads: list[Upload]) -> dict:
    if "status" in raw:
        raise bad_request(
            "'status' cannot be changed through PATCH; use the approve/reject/cancel/mark-sent "
            "operations", field="status")
    conn = ctx.connect()
    try:
        row = get_message_row(conn, message_id)
        row = _ensure_not_expired(conn, row)
        if row["status"] not in ("pending", "rejected"):
            raise conflict(
                f"a message in status {row['status']!r} cannot be revised",
                current_status=row["status"],
                allowed_actions=ALLOWED_ACTIONS.get(row["status"], []))
        base = {
            "channel": row["channel"], "destination": row["destination"],
            "subject": row["subject"], "body": row["body"],
            "destination_label": row["destination_label"], "source": row["source"],
            "webhook_url": row["webhook_url"],
            "metadata": json.loads(row["metadata_json"]) if row["metadata_json"] else None,
        }
        if not isinstance(raw, dict):
            raise bad_request("PATCH body must be a JSON object", field="body")
        merged = dict(base)
        for key in ("channel", "destination", "subject", "body", "destination_label",
                    "source", "webhook_url", "metadata"):
            if key in raw:
                merged[key] = raw[key]
        if "expires_at" in raw or "ttl_seconds" in raw:
            touched, expires = _resolve_expiration(raw, patch=True)
            merged["expires_at"] = expires
        else:
            merged["expires_at"] = row["expires_at"]
        if "references" in raw:
            merged["references"] = _validate_references(raw.get("references"), present=True)
        else:
            merged["references"] = current_revision_refs(conn, message_id,
                                                         row["revision_number"])[1]
        if "metadata" in raw and raw["metadata"] is not None:
            merged["metadata"] = _validate_metadata(raw)
        filtered = {k: v for k, v in merged.items() if k != "expires_at"}
        if "webhook_url" not in raw:
            # Keep the existing webhook without re-validating (and re-resolving
            # DNS for) it; only a newly supplied webhook_url must pass the SSRF
            # guard again.
            filtered.pop("webhook_url", None)
        content = parse_content(ctx, filtered, patch=True)
        if "webhook_url" not in raw:
            content.webhook_url = row["webhook_url"]
        new_rev = row["revision_number"] + 1
        now = now_iso()
        had_attachments_provided = ("attachments" in raw) or bool(uploads)
        with transaction(conn):
            live = conn.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
            if live["status"] != row["status"] or live["revision_number"] != row["revision_number"]:
                raise conflict("the message changed concurrently; retry the PATCH",
                               current_status=live["status"],
                               allowed_actions=ALLOWED_ACTIONS.get(live["status"], []))
            if had_attachments_provided:
                attachment_ids, references = _collect_specs(
                    ctx, {**raw, "references": merged["references"]}, uploads,
                    message_id, new_rev, conn)
            else:
                attachment_ids = _existing_ids_for_revision(
                    conn, message_id, current_revision_refs(conn, message_id,
                                                            row["revision_number"])[0])
                references = merged["references"]
            # Snapshot the outgoing revision together with its rejection data.
            conn.execute(
                "UPDATE message_revisions SET rejection_reason=?, rejection_at=? "
                "WHERE message_id=? AND revision_number=?",
                (live["rejection_reason"], live["rejection_at"], message_id,
                 row["revision_number"]))
            won = _cas_update(
                conn, message_id, (row["status"],),
                channel=content.channel, destination=content.dest.raw,
                normalized_destination=content.dest.normalized,
                destination_kind=content.dest.kind,
                destination_label=content.destination_label,
                subject=content.subject, body=content.body,
                expires_at=merged["expires_at"], webhook_url=content.webhook_url,
                source=content.source,
                metadata_json=json.dumps(content.metadata, ensure_ascii=False)
                if content.metadata is not None else None,
                rejection_reason=None, rejection_at=None,
                status="pending", updated_at=now, revision_number=new_rev)
            if won != 1:
                raise conflict("the message changed concurrently; retry the PATCH",
                               current_status="unknown")
            _insert_revision(conn, message_id, new_rev, content, attachment_ids,
                             references, now, expires_at=merged["expires_at"])
            _insert_references(conn, message_id, new_rev, references, now)
            _record_transition(conn, message_id, row["status"], "pending",
                               "revised via PATCH" + (f" (previous rejection: {live['rejection_reason']})"
                                                      if live["rejection_reason"] else ""),
                               new_rev, now)
            updated = conn.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
            _emit_event(conn, updated, "message.revised", "pending", now,
                        {"previous_revision": row["revision_number"]})
            view = message_view(conn, updated, full=True)
        ctx.notify_webhooks()
        return view
    finally:
        conn.close()


def _existing_ids_for_revision(conn: sqlite3.Connection, message_id: str,
                               ids: list[str]) -> list[str]:
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT id FROM attachments WHERE message_id=? AND id IN ({marks})",
        [message_id, *ids]).fetchall()
    return [r["id"] for r in rows]


def _insert_revision(conn: sqlite3.Connection, message_id: str, revision: int,
                     content: ParsedContent, attachment_ids: list[str],
                     references: list[str], ts: str,
                     expires_at: Optional[str] = "__unset__") -> None:  # type: ignore[assignment]
    if expires_at == "__unset__":
        expires_at = content.expires_at
    conn.execute(
        """INSERT INTO message_revisions (message_id, revision_number, channel, destination,
           normalized_destination, destination_kind, destination_label, subject, body,
           metadata_json, references_json, attachment_ids_json, expires_at, source,
           webhook_url, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (message_id, revision, content.channel, content.dest.raw, content.dest.normalized,
         content.dest.kind, content.destination_label, content.subject, content.body,
         json.dumps(content.metadata, ensure_ascii=False) if content.metadata is not None else None,
         json.dumps(references, ensure_ascii=False), json.dumps(attachment_ids),
         expires_at, content.source, content.webhook_url, ts))


def _insert_attachment(conn: sqlite3.Connection, message_id: str, revision: int,
                       stored: StoredAttachment) -> None:
    conn.execute(
        """INSERT INTO attachments (id, message_id, revision_number, filename, stored_name,
               mime_type, size_bytes, source_type, source_url, uploaded_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (stored.id, message_id, revision, stored.filename, stored.stored_name,
         stored.mime_type, stored.size_bytes, stored.source_type, stored.source_url,
         stored.uploaded_at))


def _insert_references(conn: sqlite3.Connection, message_id: str, revision: int,
                      references: list[str], ts: str) -> None:
    for url in references:
        conn.execute(
            "INSERT OR IGNORE INTO external_references (message_id, revision_number, url, "
            "created_at) VALUES (?,?,?,?)", (message_id, revision, url, ts))


# ---------------------------------------------------------------------------
# handoff
# ---------------------------------------------------------------------------

def handoff(ctx: OutboxContext, message_id: str) -> dict:
    conn = ctx.connect()
    try:
        row = get_message_row(conn, message_id)
        row = _ensure_not_expired(conn, row)
        if row["status"] != "approved":
            raise conflict(
                f"handoff is only available for approved messages (current status: "
                f"{row['status']!r})",
                current_status=row["status"],
                allowed_actions=ALLOWED_ACTIONS.get(row["status"], []))
        adapter = adapter_for(row["channel"])
        dest = Destination(raw=row["destination"], normalized=row["normalized_destination"],
                           kind=row["destination_kind"],
                           display_name=row["destination"] if row["destination_kind"] != "individual"
                           else None)
        result = adapter.build_handoff(HandoffRequest(
            destination=dest, subject=row["subject"], body=row["body"],
            max_url_length=ctx.cfg.max_handoff_url_length))
        attachment_ids, references = current_revision_refs(conn, message_id,
                                                           row["revision_number"])
        attachments = _attachments_for(conn, message_id, row["revision_number"], attachment_ids)
        return {
            "message_id": message_id,
            "channel": row["channel"],
            "destination": row["destination"],
            "normalized_destination": row["normalized_destination"],
            "destination_kind": dest.kind,
            "group_name": result.extra.get("group_name"),
            "handoff_url": result.handoff_url,
            "capabilities": result.capabilities,
            "manual_actions": result.manual_actions,
            "warnings": result.warnings,
            "attachment_instructions": adapter.attachment_instructions(),
            "attachments": attachments,
            "references": references,
            "copy": {"subject": row["subject"] or "", "body": row["body"]},
            "revision_number": row["revision_number"],
            "status": row["status"],
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# attachments listing
# ---------------------------------------------------------------------------

def list_attachments(ctx: OutboxContext, message_id: str) -> list[dict]:
    conn = ctx.connect()
    try:
        row = get_message_row(conn, message_id)
        row = _ensure_not_expired(conn, row)
        attachment_ids, _ = current_revision_refs(conn, message_id, row["revision_number"])
        return _attachments_for(conn, message_id, row["revision_number"], attachment_ids)
    finally:
        conn.close()


def get_attachment(ctx: OutboxContext, message_id: str,
                   attachment_id: str) -> tuple[dict, AttachmentStore]:
    conn = ctx.connect()
    try:
        row = get_message_row(conn, message_id)
        found = conn.execute(
            "SELECT * FROM attachments WHERE id=? AND message_id=?",
            (attachment_id, message_id)).fetchone()
        if found is None:
            raise not_found(f"attachment {attachment_id!r} not found on message {message_id!r}",
                            message_id=message_id, attachment_id=attachment_id)
        return dict(found), ctx.store
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# destinations & labels
# ---------------------------------------------------------------------------

def list_destinations(ctx: OutboxContext) -> list[dict]:
    conn = ctx.connect()
    try:
        rows = conn.execute(
            """SELECT m.channel AS channel, m.normalized_destination AS norm,
                      MAX(m.created_at) AS last_used, COUNT(*) AS message_count,
                      (SELECT destination FROM messages m2
                        WHERE m2.channel=m.channel AND m2.normalized_destination=m.normalized_destination
                        ORDER BY m2.created_at DESC LIMIT 1) AS destination,
                      dl.label AS label
               FROM messages m
               LEFT JOIN destination_labels dl
                     ON dl.channel=m.channel AND dl.normalized_destination=m.normalized_destination
               GROUP BY m.channel, m.normalized_destination
               ORDER BY last_used DESC""").fetchall()
        return [
            {"channel": r["channel"], "destination": r["destination"],
             "normalized_destination": r["norm"], "label": r["label"],
             "message_count": r["message_count"], "last_used": r["last_used"]}
            for r in rows
        ]
    finally:
        conn.close()


def set_label(ctx: OutboxContext, channel: str, destination: str, label: str) -> dict:
    adapter = adapter_for(channel)
    dest = adapter.validate_destination(destination)
    if not isinstance(label, str) or not label.strip():
        raise bad_request("'label' must be a non-empty string", field="label")
    label = label.strip()
    if len(label) > MAX_LABEL_CHARS:
        raise bad_request(f"'label' is too long (max {MAX_LABEL_CHARS} characters)", field="label")
    canonical = label.lower()
    now = now_iso()
    conn = ctx.connect()
    try:
        with transaction(conn):
            existing = conn.execute(
                "SELECT channel, normalized_destination FROM destination_labels "
                "WHERE channel=? AND label_canonical=? AND normalized_destination<>?",
                (channel, canonical, dest.normalized)).fetchone()
            if existing:
                raise conflict(
                    f"label {label!r} is already used for destination "
                    f"{existing['normalized_destination']!r} on channel {channel!r}",
                    current_label=label, channel=channel)
            cur = conn.execute(
                """INSERT INTO destination_labels (channel, normalized_destination, label,
                        label_canonical, created_at, updated_at)
                   VALUES (?,?,?,?,?,?)
                   ON CONFLICT(channel, normalized_destination)
                   DO UPDATE SET label=excluded.label, label_canonical=excluded.label_canonical,
                                 updated_at=excluded.updated_at""",
                (channel, dest.normalized, label, canonical, now, now))
        row = conn.execute(
            "SELECT * FROM destination_labels WHERE channel=? AND normalized_destination=?",
            (channel, dest.normalized)).fetchone()
        return dict(row)
    finally:
        conn.close()


def remove_label(ctx: OutboxContext, channel: str, destination: str) -> dict:
    adapter = adapter_for(channel)
    dest = adapter.validate_destination(destination)
    conn = ctx.connect()
    try:
        cur = conn.execute(
            "DELETE FROM destination_labels WHERE channel=? AND normalized_destination=?",
            (channel, dest.normalized))
        return {"deleted": cur.rowcount == 1, "channel": channel,
                "normalized_destination": dest.normalized}
    finally:
        conn.close()


def webhook_event_rows(conn: sqlite3.Connection, message_id: str,
                       *, include_payload: bool) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM webhook_events WHERE message_id=? ORDER BY id", (message_id,)).fetchall()
    out = []
    for r in rows:
        attempts = conn.execute(
            "SELECT attempt_number, started_at, finished_at, http_status, error "
            "FROM webhook_attempts WHERE event_id=? ORDER BY attempt_number",
            (r["id"],)).fetchall()
        item = {
            "event": r["event"],
            "message_id": r["message_id"],
            "revision_number": r["revision_number"],
            "message_status": r["message_status"],
            "state": r["state"],
            "attempts": r["attempts"],
            "last_status_code": r["last_status_code"],
            "last_error": r["last_error"],
            "created_at": r["created_at"],
            "next_attempt_at": r["next_attempt_at"],
            "delivered_at": r["delivered_at"],
            "attempt_history": [dict(a) for a in attempts],
        }
        if include_payload:
            item["payload"] = json.loads(r["payload_json"])
        out.append(item)
    return out


def list_webhook_events(ctx: OutboxContext, message_id: str) -> list[dict]:
    conn = ctx.connect()
    try:
        get_message_row(conn, message_id)
        return webhook_event_rows(conn, message_id, include_payload=True)
    finally:
        conn.close()
