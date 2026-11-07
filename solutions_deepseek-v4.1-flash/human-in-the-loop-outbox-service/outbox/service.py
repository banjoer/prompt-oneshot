"""Domain service: messages, revisions, expiry, destinations and webhooks."""

from __future__ import annotations

import json
import mimetypes
import sqlite3
import uuid
from typing import Any, Iterable

from .channels import (
    CHANNELS,
    DESTINATION_LABEL_MAX,
    get_adapter,
    validate_url_reference,
)
from .config import Config
from .db import Database
from .errors import ConflictError, NotFoundError, TooLargeError, ValidationError
from .net import MIME_RE, safe_download, validate_outbound_url
from .storage import AttachmentStore, sanitize_filename
from .timeutil import expires_at_from_ttl, now_iso, parse_future_iso, utcnow
from .webhooks import WebhookDispatcher, new_event_id

STATUSES = ("pending", "approved", "sent", "rejected", "stale", "cancelled")
TERMINAL_STATUSES = {"sent", "stale", "cancelled"}
ACTIVE_STATUSES = {"pending", "approved"}
PATCHABLE_STATUSES = {"pending", "rejected"}
ALLOWED_CREATE_FIELDS = {
    "channel",
    "destination",
    "destination_label",
    "subject",
    "body",
    "expires_at",
    "ttl_seconds",
    "webhook_url",
    "source",
    "metadata",
    "references",
    "attachments",
}
ALLOWED_PATCH_FIELDS = {
    "channel",
    "destination",
    "destination_label",
    "subject",
    "body",
    "expires_at",
    "ttl_seconds",
    "references",
    "metadata",
    "attachments",
}
ALLOWED_ACTIONS_BY_STATUS: dict[str, list[str]] = {
    "pending": ["approve", "reject", "cancel", "revise"],
    "approved": ["handoff", "mark_sent", "cancel"],
    "rejected": ["revise", "cancel"],
    "sent": [],
    "stale": [],
    "cancelled": [],
}


def message_id() -> str:
    return "msg_" + uuid.uuid4().hex[:12]


def attachment_id() -> str:
    return "att_" + uuid.uuid4().hex[:16]


def _clean_optional_string(value: Any, field: str, max_length: int | None = None, allow_empty: bool = True) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a string.")
    cleaned = value.strip() if field != "body" else value
    if not allow_empty and not cleaned.strip():
        raise ValidationError(f"{field} must not be empty.")
    if max_length is not None and len(cleaned) > max_length:
        raise ValidationError(f"{field} must be at most {max_length} characters.")
    if field != "body" and cleaned == "":
        return None
    return cleaned


def _parse_metadata(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError("metadata must be a JSON object.")
    try:
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValidationError("metadata must be JSON-serialisable.") from exc
    return value


def _parse_ttl(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError("ttl_seconds must be a positive integer.")
    if value <= 0:
        raise ValidationError("ttl_seconds must be a positive integer.")
    return value


def _normalise_mime(value: str | None, filename: str) -> str:
    if isinstance(value, str):
        candidate = value.split(";", 1)[0].strip().lower()
        if MIME_RE.match(candidate):
            return candidate
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


class OutboxService:
    def __init__(
        self,
        db: Database,
        config: Config,
        dispatcher: WebhookDispatcher,
        store: AttachmentStore | None = None,
    ) -> None:
        self.db = db
        self.config = config
        self.dispatcher = dispatcher
        self.store = store or AttachmentStore(config.attachment_dir)
        self.conn = db.connect()

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:  # pragma: no cover - defensive
            pass

    # ------------------------------------------------------------------ helpers
    def _load_message(self, message_id_value: str) -> Any:
        row = self.conn.execute(
            "SELECT * FROM messages WHERE id = ?", (message_id_value,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"Message {message_id_value!r} was not found.")
        return row

    def _current_attachments(
        self, conn: Any, msg_id: str, revision_number: int | None = None
    ) -> list[dict[str, Any]]:
        if revision_number is None:
            revision_number = conn.execute(
                "SELECT revision_number FROM messages WHERE id = ?", (msg_id,)
            ).fetchone()["revision_number"]
        rows = conn.execute(
            """
            SELECT a.* FROM attachments a
            JOIN revision_attachments ra ON ra.attachment_id = a.id
            JOIN message_revisions r ON r.id = ra.revision_id
            WHERE r.message_id = ? AND r.revision_number = ?
            ORDER BY a.uploaded_at, a.id
            """,
            (msg_id, revision_number),
        ).fetchall()
        return [dict(r) for r in rows]

    def _references(
        self, conn: Any, msg_id: str, revision_number: int
    ) -> list[dict[str, Any]]:
        rows = conn.execute(
            "SELECT url, origin FROM message_references WHERE message_id = ? AND revision_number = ? ORDER BY id",
            (msg_id, revision_number),
        ).fetchall()
        return [dict(r) for r in rows]

    def _managed_label(self, conn: Any, channel: str, normalized: str) -> str | None:
        row = conn.execute(
            "SELECT label FROM destinations WHERE channel = ? AND destination_normalized = ?",
            (channel, normalized),
        ).fetchone()
        return row["label"] if row else None

    def _attachment_dict(self, msg_id: str, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "filename": row["original_filename"],
            "original_filename": row["original_filename"],
            "mime_type": row["mime_type"],
            "size_bytes": row["size_bytes"],
            "storage_ref": row["storage_name"],
            "storage_reference": row["storage_name"],
            "uploaded_at": row["uploaded_at"],
            "source_type": row["source_type"],
            "source_url": row["source_url"],
            "download_url": f"/api/messages/{msg_id}/attachments/{row['id']}",
        }

    def _serialize(self, conn: Any, row: Any, detail: bool = False) -> dict[str, Any]:
        data = dict(row)
        data["metadata"] = json.loads(data.get("metadata") or "{}")
        attachments = self._current_attachments(conn, data["id"], data["revision_number"])
        managed = self._managed_label(conn, data["channel"], data["destination_normalized"])
        data["managed_label"] = managed
        data["destination_label_effective"] = managed or data.get("destination_label")
        data["attachment_count"] = len(attachments)
        data["allowed_actions"] = list(ALLOWED_ACTIONS_BY_STATUS.get(data["status"], []))
        data["is_terminal"] = data["status"] in TERMINAL_STATUSES
        if data.get("expires_at"):
            try:
                from .timeutil import parse_iso

                delta = (parse_iso(data["expires_at"], "expires_at") - utcnow()).total_seconds()
                data["expires_in_seconds"] = int(delta)
            except Exception:  # pragma: no cover - stored values are validated
                data["expires_in_seconds"] = None
        else:
            data["expires_in_seconds"] = None
        if detail:
            data["attachments"] = [self._attachment_dict(data["id"], a) for a in attachments]
            refs = self._references(conn, data["id"], data["revision_number"])
            data["references"] = [r["url"] for r in refs]
            data["reference_details"] = refs
            data["has_webhook"] = bool(data.get("webhook_url"))
        return data

    def _discover_destination(
        self, conn: Any, channel: str, destination: str, normalized: str
    ) -> None:
        timestamp = now_iso()
        conn.execute(
            """
            INSERT INTO destinations(channel, destination_normalized, destination, label, created_at, updated_at)
            VALUES (?, ?, ?, NULL, ?, ?)
            ON CONFLICT(channel, destination_normalized) DO UPDATE SET
                destination = excluded.destination,
                updated_at = excluded.updated_at
            """,
            (channel, normalized, destination, timestamp, timestamp),
        )

    def _record_history(
        self,
        conn: Any,
        msg_id: str,
        from_status: str | None,
        to_status: str,
        reason: str | None,
        revision_number: int,
        timestamp: str | None = None,
    ) -> None:
        conn.execute(
            """
            INSERT INTO status_history(message_id, from_status, to_status, reason, revision_number, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (msg_id, from_status, to_status, reason, revision_number, timestamp or now_iso()),
        )

    def _emit_event(
        self, conn: Any, row: Any, event: str, details: dict[str, Any] | None = None
    ) -> str | None:
        if not row["webhook_url"]:
            return None
        timestamp = now_iso()
        payload: dict[str, Any] = {
            "event": event,
            "message_id": row["id"],
            "status": row["status"],
            "revision_number": row["revision_number"],
            "timestamp": timestamp,
        }
        if details:
            payload.update(details)
        event_id = new_event_id()
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO webhook_events(
                id, message_id, event, revision_number, status, payload, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)
            """,
            (
                event_id,
                row["id"],
                event,
                row["revision_number"],
                json.dumps(payload, ensure_ascii=False),
                timestamp,
                timestamp,
            ),
        )
        if cursor.rowcount == 0:
            existing = conn.execute(
                "SELECT id FROM webhook_events WHERE message_id = ? AND event = ? AND revision_number = ?",
                (row["id"], event, row["revision_number"]),
            ).fetchone()
            return existing["id"] if existing else None
        return event_id

    def _dispatch(self, event_ids: Iterable[str | None]) -> None:
        for event_id in event_ids:
            if event_id:
                self.dispatcher.enqueue(event_id)

    def _expire_row(self, conn: Any, row: Any, timestamp: str | None = None) -> str | None:
        ts = timestamp or now_iso()
        cursor = conn.execute(
            "UPDATE messages SET status = 'stale', updated_at = ? WHERE id = ? AND status IN ('pending', 'approved')",
            (ts, row["id"]),
        )
        if cursor.rowcount != 1:
            return None
        self._record_history(
            conn,
            row["id"],
            row["status"],
            "stale",
            "Expired",
            row["revision_number"],
            ts,
        )
        updated = conn.execute("SELECT * FROM messages WHERE id = ?", (row["id"],)).fetchone()
        return self._emit_event(
            conn,
            updated,
            "message.stale",
            {"expires_at": row["expires_at"]},
        )

    def expire_due(self) -> int:
        timestamp = now_iso()
        event_ids: list[str | None] = []
        count = 0
        with self.db.transaction(self.conn, immediate=True):
            rows = self.conn.execute(
                """
                SELECT * FROM messages
                WHERE status IN ('pending', 'approved')
                  AND expires_at IS NOT NULL
                  AND expires_at <= ?
                """,
                (timestamp,),
            ).fetchall()
            for row in rows:
                event_id = self._expire_row(self.conn, row, timestamp)
                if event_id is not None:
                    event_ids.append(event_id)
                count += 1
        self._dispatch(event_ids)
        return count

    # ---------------------------------------------------------------- submission
    def create_message(
        self,
        data: dict[str, Any],
        files: list[dict[str, Any]] | None = None,
        attachment_specs: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        files = files or []
        attachment_specs = attachment_specs or []
        if not isinstance(data, dict):
            raise ValidationError("Request body must be a JSON object.")
        unknown = sorted(set(data) - ALLOWED_CREATE_FIELDS)
        if unknown:
            raise ValidationError(
                f"Unsupported field(s): {', '.join(unknown)}."
            )
        channel = data.get("channel")
        if not isinstance(channel, str) or channel not in CHANNELS:
            raise ValidationError(
                f"channel is required and must be one of: {', '.join(CHANNELS)}."
            )
        adapter = get_adapter(channel)
        destination_raw = data.get("destination")
        if not isinstance(destination_raw, str):
            raise ValidationError("destination is required and must be a string.")
        normalized = adapter.normalize(destination_raw)
        destination = destination_raw.strip()
        destination_label = adapter.validate_label(data.get("destination_label"))

        subject = _clean_optional_string(data.get("subject"), "subject", max_length=100000)
        body = data.get("body")
        if not isinstance(body, str):
            raise ValidationError("body is required and must be a string.")
        if not body.strip():
            raise ValidationError("body must not be empty.")
        source = _clean_optional_string(data.get("source"), "source", max_length=1000)

        metadata: dict[str, Any] = {}
        if data.get("metadata") is not None:
            metadata = _parse_metadata(data.get("metadata"))

        expires_at = self._resolve_expiry_for_create(data)

        webhook_url = _clean_optional_string(
            data.get("webhook_url"), "webhook_url", max_length=2048
        )
        if webhook_url:
            validate_outbound_url(
                webhook_url,
                allow_private=self.config.allow_private_urls,
                require_resolution=False,
                field="webhook_url",
            )

        references: list[tuple[str, str]] = []
        if data.get("references") is not None:
            if not isinstance(data["references"], list):
                raise ValidationError("references must be a list of http(s) URL strings.")
            if len(data["references"]) > 1000:
                raise ValidationError("At most 1000 references are allowed per message.")
            for ref in data["references"]:
                references.append((validate_url_reference(ref), "reference"))

        if not isinstance(attachment_specs, list):
            raise ValidationError("attachments must be a list.")
        if not isinstance(files, list):
            raise ValidationError("attachments must be a list of uploaded files.")

        # Stage attachment bytes first (outside any DB transaction).
        staged: list[dict[str, Any]] = []
        stored_names: list[str] = []
        total_bytes = 0
        try:
            for uploaded in files:
                raw = uploaded.get("data") or b""
                if len(raw) > self.config.max_attachment_bytes:
                    raise TooLargeError(
                        f"Attachment {uploaded.get('filename')!r} exceeds the per-file limit of "
                        f"{self.config.max_attachment_bytes} bytes.",
                        {"max_attachment_bytes": self.config.max_attachment_bytes},
                    )
                total_bytes += len(raw)
                if total_bytes > self.config.max_message_attachment_bytes:
                    raise TooLargeError(
                        f"Attachments exceed the per-message limit of "
                        f"{self.config.max_message_attachment_bytes} bytes.",
                        {"max_message_attachment_bytes": self.config.max_message_attachment_bytes},
                    )
                filename = sanitize_filename(uploaded.get("filename"))
                stored = self.store.save_bytes(
                    filename=filename,
                    mime_type=_normalise_mime(uploaded.get("mime_type"), filename),
                    data=raw,
                    source_type="multipart",
                    source_url=None,
                )
                stored_names.append(stored["storage_name"])
                staged.append(stored)

            for spec in attachment_specs:
                if not isinstance(spec, dict):
                    raise ValidationError("Each attachment entry must be an object.")
                kind = spec.get("kind")
                url = spec.get("url")
                if kind not in {"url_reference", "url_download"}:
                    raise ValidationError(
                        "Attachment kind must be 'url_reference' or 'url_download'."
                    )
                validated_url = validate_url_reference(url)
                if kind == "url_reference":
                    references.append((validated_url, "attachment_reference"))
                    continue
                result = safe_download(
                    validated_url,
                    max_bytes=self.config.max_attachment_bytes,
                    timeout=self.config.download_timeout_seconds,
                    max_redirects=self.config.max_redirects,
                    allow_private=self.config.allow_private_urls,
                    override_filename=spec.get("filename"),
                )
                total_bytes += len(result.data)
                if total_bytes > self.config.max_message_attachment_bytes:
                    raise TooLargeError(
                        f"Attachments exceed the per-message limit of "
                        f"{self.config.max_message_attachment_bytes} bytes.",
                        {"max_message_attachment_bytes": self.config.max_message_attachment_bytes},
                    )
                filename = sanitize_filename(
                    spec.get("filename") or result.filename
                )
                stored = self.store.save_bytes(
                    filename=filename,
                    mime_type=_normalise_mime(result.mime_type, filename),
                    data=result.data,
                    source_type="url_download",
                    source_url=result.final_url,
                )
                stored_names.append(stored["storage_name"])
                staged.append(stored)
        except BaseException:
            for name in stored_names:
                try:
                    self.store.path_for(name).unlink(missing_ok=True)
                except Exception:  # pragma: no cover - best effort cleanup
                    pass
            raise

        new_id = message_id()
        timestamp = now_iso()
        try:
            with self.db.transaction(self.conn, immediate=True):
                self.conn.execute(
                    """
                    INSERT INTO messages(
                        id, channel, destination, destination_normalized, destination_label,
                        subject, body, status, created_at, updated_at, expires_at, webhook_url,
                        rejection_reason, rejection_at, revision_number, source, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, NULL, NULL, 1, ?, ?)
                    """,
                    (
                        new_id,
                        channel,
                        destination,
                        normalized.normalized,
                        destination_label,
                        subject,
                        body,
                        timestamp,
                        timestamp,
                        expires_at,
                        webhook_url,
                        source,
                        json.dumps(metadata, ensure_ascii=False),
                    ),
                )
                revised_id = self.conn.execute(
                    """
                    INSERT INTO message_revisions(
                        message_id, revision_number, channel, destination, destination_normalized,
                        destination_label, subject, body, expires_at, webhook_url, source,
                        metadata, rejection_reason, rejection_at, created_at
                    ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?)
                    """,
                    (
                        new_id,
                        channel,
                        destination,
                        normalized.normalized,
                        destination_label,
                        subject,
                        body,
                        expires_at,
                        webhook_url,
                        source,
                        json.dumps(metadata, ensure_ascii=False),
                        timestamp,
                    ),
                )
                revision_pk = revised_id.lastrowid
                for stored in staged:
                    att_id = attachment_id()
                    self.conn.execute(
                        """
                        INSERT INTO attachments(
                            id, message_id, original_filename, mime_type, size_bytes,
                            storage_name, uploaded_at, source_type, source_url
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            att_id,
                            new_id,
                            stored["original_filename"],
                            stored["mime_type"],
                            stored["size_bytes"],
                            stored["storage_name"],
                            timestamp,
                            stored["source_type"],
                            stored["source_url"],
                        ),
                    )
                    self.conn.execute(
                        "INSERT INTO revision_attachments(revision_id, attachment_id) VALUES (?, ?)",
                        (revision_pk, att_id),
                    )
                seen_refs: set[tuple[str, str]] = set()
                for url, origin in references:
                    key = (url, origin)
                    if key in seen_refs:
                        continue
                    seen_refs.add(key)
                    self.conn.execute(
                        """
                        INSERT INTO message_references(message_id, revision_number, url, origin, created_at)
                        VALUES (?, 1, ?, ?, ?)
                        """,
                        (new_id, url, origin, timestamp),
                    )
                self._record_history(
                    self.conn, new_id, None, "pending", "Message submitted", 1, timestamp
                )
                self._discover_destination(
                    self.conn, channel, destination, normalized.normalized
                )
                row = self.conn.execute(
                    "SELECT * FROM messages WHERE id = ?", (new_id,)
                ).fetchone()
                result = self._serialize(self.conn, row, detail=True)
        except BaseException:
            for name in stored_names:
                try:
                    self.store.path_for(name).unlink(missing_ok=True)
                except Exception:  # pragma: no cover
                    pass
            raise
        return result

    def _resolve_expiry_for_create(self, data: dict[str, Any]) -> str | None:
        has_abs = "expires_at" in data and data.get("expires_at") is not None
        has_ttl = "ttl_seconds" in data and data.get("ttl_seconds") is not None
        if "ttl_seconds" in data and data.get("ttl_seconds") is None:
            raise ValidationError("ttl_seconds must be a positive integer.")
        if "expires_at" in data and "ttl_seconds" in data:
            if data.get("expires_at") is not None and data.get("ttl_seconds") is not None:
                raise ValidationError("expires_at and ttl_seconds are mutually exclusive.")
        if has_ttl:
            ttl = _parse_ttl(data["ttl_seconds"])
            return expires_at_from_ttl(ttl)
        if has_abs:
            return parse_future_iso(data["expires_at"], "expires_at")
        return None

    # -------------------------------------------------------------------- listing
    def list_messages(self, params: dict[str, Any]) -> dict[str, Any]:
        self.expire_due()
        where: list[str] = []
        values: list[Any] = []

        status_values = _split_multi(params.get("status"))
        expanded_statuses: list[str] = []
        for status in status_values:
            if status == "all":
                continue
            if status == "active":
                expanded_statuses.extend(["pending", "approved", "rejected"])
                continue
            if status == "terminal":
                expanded_statuses.extend(["sent", "stale", "cancelled"])
                continue
            if status not in STATUSES:
                raise ValidationError(
                    f"Unknown status {status!r}. Expected one of: {', '.join(STATUSES)}."
                )
            expanded_statuses.append(status)
        status_values = list(dict.fromkeys(expanded_statuses))
        if status_values:
            where.append(f"m.status IN ({','.join('?' for _ in status_values)})")
            values.extend(status_values)

        channel_values = _split_multi(params.get("channel"))
        if channel_values == ["all"]:
            channel_values = []
        if channel_values:
            for channel in channel_values:
                if channel not in CHANNELS:
                    raise ValidationError(
                        f"Unknown channel {channel!r}. Expected one of: {', '.join(CHANNELS)}."
                    )
            where.append(f"m.channel IN ({','.join('?' for _ in channel_values)})")
            values.extend(channel_values)

        destination = params.get("destination")
        if destination is not None:
            if not isinstance(destination, str):
                raise ValidationError("destination filter must be a string.")
            value = destination.strip().lower()
            if value:
                needle = f"%{value}%"
                where.append(
                    "(LOWER(m.destination) LIKE ? OR LOWER(m.destination_normalized) LIKE ? "
                    "OR LOWER(COALESCE(m.destination_label, '')) LIKE ? "
                    "OR LOWER(COALESCE(d.label, '')) LIKE ?)"
                )
                values.extend([needle, needle, needle, needle])

        from .timeutil import parse_filter_bound

        for param, column, end in (
            ("created_from", "m.created_at", False),
            ("created_to", "m.created_at", True),
            ("created_after", "m.created_at", False),
            ("created_before", "m.created_at", True),
            ("expires_from", "m.expires_at", False),
            ("expires_to", "m.expires_at", True),
            ("expires_after", "m.expires_at", False),
            ("expires_before", "m.expires_at", True),
        ):
            raw = params.get(param)
            if raw is None or raw == "":
                continue
            if not isinstance(raw, str):
                raise ValidationError(f"{param} must be an ISO date or timestamp string.")
            bound = parse_filter_bound(raw, param, end_of_day=end)
            operator = "<=" if end else ">="
            if column == "m.expires_at":
                where.append(f"(m.expires_at IS NOT NULL AND m.expires_at {operator} ?)")
            else:
                where.append(f"m.created_at {operator} ?")
            values.append(bound)

        limit = _parse_pagination_int(params.get("limit"), "limit", default=20, minimum=1)
        if limit > 100:
            limit = 100
        offset = _parse_pagination_int(params.get("offset"), "offset", default=0, minimum=0)

        sort = params.get("sort") or "newest"
        order_by = {
            "newest": "m.created_at DESC, m.rowid DESC",
            "oldest": "m.created_at ASC, m.rowid ASC",
            "expires_soon": "(m.expires_at IS NULL) ASC, m.expires_at ASC, m.created_at DESC, m.rowid DESC",
            "expires_late": "(m.expires_at IS NULL) ASC, m.expires_at DESC, m.created_at DESC, m.rowid DESC",
        }.get(sort)
        if order_by is None:
            raise ValidationError(
                "sort must be one of: newest, oldest, expires_soon, expires_late."
            )

        where_sql = (" WHERE " + " AND ".join(where)) if where else ""
        base_from = (
            "FROM messages m LEFT JOIN destinations d "
            "ON d.channel = m.channel AND d.destination_normalized = m.destination_normalized"
        )
        total = self.conn.execute(
            f"SELECT COUNT(*) AS c {base_from}{where_sql}", values
        ).fetchone()["c"]
        rows = self.conn.execute(
            f"SELECT m.* {base_from}{where_sql} ORDER BY {order_by} LIMIT ? OFFSET ?",
            [*values, limit, offset],
        ).fetchall()
        items = [self._serialize(self.conn, row, detail=False) for row in rows]
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    # ----------------------------------------------------------------- retrieval
    def get_message(self, msg_id: str) -> dict[str, Any]:
        self.expire_due()
        row = self._load_message(msg_id)
        return self._serialize(self.conn, row, detail=True)

    def get_history(self, msg_id: str) -> dict[str, Any]:
        self.expire_due()
        row = self._load_message(msg_id)
        revisions = self.conn.execute(
            "SELECT * FROM message_revisions WHERE message_id = ? ORDER BY revision_number",
            (msg_id,),
        ).fetchall()
        history = self.conn.execute(
            "SELECT * FROM status_history WHERE message_id = ? ORDER BY id",
            (msg_id,),
        ).fetchall()
        revision_payloads: list[dict[str, Any]] = []
        for revision in revisions:
            data = dict(revision)
            data["metadata"] = json.loads(data.get("metadata") or "{}")
            attachments = self._current_attachments(
                self.conn, msg_id, revision["revision_number"]
            )
            data["attachments"] = [
                self._attachment_dict(msg_id, a) for a in attachments
            ]
            data["attachment_count"] = len(attachments)
            refs = self._references(self.conn, msg_id, revision["revision_number"])
            data["references"] = [r["url"] for r in refs]
            data["reference_details"] = refs
            revision_payloads.append(data)
        return {
            "message_id": row["id"],
            "status": row["status"],
            "current_revision_number": row["revision_number"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "rejection_reason": row["rejection_reason"],
            "rejection_at": row["rejection_at"],
            "revisions": revision_payloads,
            "status_history": [dict(h) for h in history],
        }

    # ---------------------------------------------------------------- transitions
    def approve(self, msg_id: str) -> dict[str, Any]:
        conflict: str | None = None
        event_id: str | None = None
        expiry_event_id: str | None = None
        result: dict[str, Any] | None = None
        with self.db.transaction(self.conn, immediate=True):
            row = self._load_message(msg_id)
            if self._is_expired(row):
                expiry_event_id = self._expire_row(self.conn, row)
                conflict = "stale"
            else:
                if row["status"] != "pending":
                    raise ConflictError(
                        f"Cannot approve a message in status {row['status']!r}.",
                        row["status"],
                        ALLOWED_ACTIONS_BY_STATUS.get(row["status"], []),
                    )
                timestamp = now_iso()
                cursor = self.conn.execute(
                    "UPDATE messages SET status = 'approved', updated_at = ? WHERE id = ? AND status = 'pending'",
                    (timestamp, msg_id),
                )
                if cursor.rowcount != 1:
                    raise ConflictError("The message changed concurrently.", row["status"])
                self._record_history(
                    self.conn, msg_id, "pending", "approved", None, row["revision_number"], timestamp
                )
                updated = self.conn.execute(
                    "SELECT * FROM messages WHERE id = ?", (msg_id,)
                ).fetchone()
                event_id = self._emit_event(self.conn, updated, "message.approved")
                result = self._serialize(self.conn, updated, detail=True)
        self._dispatch([event_id, expiry_event_id])
        if conflict:
            raise ConflictError(
                "The message expired before it could be approved.",
                "stale",
                [],
            )
        assert result is not None
        return result

    def reject(self, msg_id: str, reason: Any) -> dict[str, Any]:
        if not isinstance(reason, str) or not reason.strip():
            raise ValidationError("A non-empty rejection reason is required.")
        reason = reason.strip()
        if len(reason) > 10000:
            raise ValidationError("The rejection reason is too long (maximum 10000 characters).")
        conflict: str | None = None
        event_id: str | None = None
        expiry_event_id: str | None = None
        result: dict[str, Any] | None = None
        with self.db.transaction(self.conn, immediate=True):
            row = self._load_message(msg_id)
            if self._is_expired(row):
                expiry_event_id = self._expire_row(self.conn, row)
                conflict = "stale"
            else:
                if row["status"] != "pending":
                    raise ConflictError(
                        f"Cannot reject a message in status {row['status']!r}.",
                        row["status"],
                        ALLOWED_ACTIONS_BY_STATUS.get(row["status"], []),
                    )
                timestamp = now_iso()
                cursor = self.conn.execute(
                    """
                    UPDATE messages
                    SET status = 'rejected', rejection_reason = ?, rejection_at = ?, updated_at = ?
                    WHERE id = ? AND status = 'pending'
                    """,
                    (reason, timestamp, timestamp, msg_id),
                )
                if cursor.rowcount != 1:
                    raise ConflictError("The message changed concurrently.", row["status"])
                self.conn.execute(
                    """
                    UPDATE message_revisions SET rejection_reason = ?, rejection_at = ?
                    WHERE message_id = ? AND revision_number = ?
                    """,
                    (reason, timestamp, msg_id, row["revision_number"]),
                )
                self._record_history(
                    self.conn,
                    msg_id,
                    "pending",
                    "rejected",
                    reason,
                    row["revision_number"],
                    timestamp,
                )
                updated = self.conn.execute(
                    "SELECT * FROM messages WHERE id = ?", (msg_id,)
                ).fetchone()
                event_id = self._emit_event(
                    self.conn,
                    updated,
                    "message.rejected",
                    {"rejection_reason": reason},
                )
                result = self._serialize(self.conn, updated, detail=True)
        self._dispatch([event_id, expiry_event_id])
        if conflict:
            raise ConflictError(
                "The message expired before it could be rejected.", "stale", []
            )
        assert result is not None
        return result

    def cancel(self, msg_id: str, reason: Any = None) -> dict[str, Any]:
        if reason is not None and not isinstance(reason, str):
            raise ValidationError("reason must be a string.")
        reason = reason.strip() if isinstance(reason, str) else None
        if reason == "":
            reason = None
        conflict: str | None = None
        event_id: str | None = None
        expiry_event_id: str | None = None
        result: dict[str, Any] | None = None
        with self.db.transaction(self.conn, immediate=True):
            row = self._load_message(msg_id)
            if self._is_expired(row):
                expiry_event_id = self._expire_row(self.conn, row)
                conflict = "stale"
            else:
                if row["status"] not in {"pending", "approved", "rejected"}:
                    raise ConflictError(
                        f"Cannot cancel a message in status {row['status']!r}.",
                        row["status"],
                        ALLOWED_ACTIONS_BY_STATUS.get(row["status"], []),
                    )
                timestamp = now_iso()
                cursor = self.conn.execute(
                    "UPDATE messages SET status = 'cancelled', updated_at = ? WHERE id = ? AND status = ?",
                    (timestamp, msg_id, row["status"]),
                )
                if cursor.rowcount != 1:
                    raise ConflictError("The message changed concurrently.", row["status"])
                self._record_history(
                    self.conn,
                    msg_id,
                    row["status"],
                    "cancelled",
                    reason,
                    row["revision_number"],
                    timestamp,
                )
                updated = self.conn.execute(
                    "SELECT * FROM messages WHERE id = ?", (msg_id,)
                ).fetchone()
                details = {"reason": reason} if reason else None
                event_id = self._emit_event(
                    self.conn, updated, "message.cancelled", details
                )
                result = self._serialize(self.conn, updated, detail=True)
        self._dispatch([event_id, expiry_event_id])
        if conflict:
            raise ConflictError(
                "The message expired before it could be cancelled.", "stale", []
            )
        assert result is not None
        return result

    def mark_sent(self, msg_id: str) -> dict[str, Any]:
        conflict: str | None = None
        event_id: str | None = None
        expiry_event_id: str | None = None
        result: dict[str, Any] | None = None
        with self.db.transaction(self.conn, immediate=True):
            row = self._load_message(msg_id)
            if self._is_expired(row):
                expiry_event_id = self._expire_row(self.conn, row)
                conflict = "stale"
            else:
                if row["status"] != "approved":
                    raise ConflictError(
                        f"Cannot mark a message sent from status {row['status']!r}.",
                        row["status"],
                        ALLOWED_ACTIONS_BY_STATUS.get(row["status"], []),
                    )
                timestamp = now_iso()
                cursor = self.conn.execute(
                    "UPDATE messages SET status = 'sent', updated_at = ? WHERE id = ? AND status = 'approved'",
                    (timestamp, msg_id),
                )
                if cursor.rowcount != 1:
                    raise ConflictError("The message changed concurrently.", row["status"])
                self._record_history(
                    self.conn, msg_id, "approved", "sent", None, row["revision_number"], timestamp
                )
                updated = self.conn.execute(
                    "SELECT * FROM messages WHERE id = ?", (msg_id,)
                ).fetchone()
                event_id = self._emit_event(self.conn, updated, "message.sent")
                result = self._serialize(self.conn, updated, detail=True)
        self._dispatch([event_id, expiry_event_id])
        if conflict:
            raise ConflictError(
                "The message expired before it could be marked sent.", "stale", []
            )
        assert result is not None
        return result

    # -------------------------------------------------------------------- revision
    def patch_message(self, msg_id: str, data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValidationError("Request body must be a JSON object.")
        if "status" in data:
            raise ValidationError(
                "The status is not editable through PATCH; use the explicit lifecycle operations."
            )
        unknown = sorted(set(data) - ALLOWED_PATCH_FIELDS)
        if unknown:
            raise ValidationError(
                f"Unsupported PATCH field(s): {', '.join(unknown)}."
            )
        if "expires_at" in data and "ttl_seconds" in data:
            if data.get("expires_at") is not None and data.get("ttl_seconds") is not None:
                raise ValidationError("expires_at and ttl_seconds are mutually exclusive.")

        # Pre-flight read so we can validate against the current channel/state.
        row = self._load_message(msg_id)
        if self._is_expired(row):
            self.expire_due()
            row = self._load_message(msg_id)
            if row["status"] not in PATCHABLE_STATUSES:
                raise ConflictError(
                    f"Cannot revise a message in status {row['status']!r}.",
                    row["status"],
                    ALLOWED_ACTIONS_BY_STATUS.get(row["status"], []),
                )
        if row["status"] not in PATCHABLE_STATUSES:
            raise ConflictError(
                f"Cannot revise a message in status {row['status']!r}.",
                row["status"],
                ALLOWED_ACTIONS_BY_STATUS.get(row["status"], []),
            )

        channel = data.get("channel", row["channel"])
        if not isinstance(channel, str) or channel not in CHANNELS:
            raise ValidationError(
                f"channel must be one of: {', '.join(CHANNELS)}."
            )
        adapter = get_adapter(channel)
        destination_raw = data.get("destination", row["destination"])
        if not isinstance(destination_raw, str):
            raise ValidationError("destination must be a string.")
        normalized = adapter.normalize(destination_raw)
        destination = destination_raw.strip()

        if "destination_label" in data:
            destination_label = adapter.validate_label(data.get("destination_label"))
        else:
            destination_label = row["destination_label"]

        subject = (
            _clean_optional_string(data.get("subject"), "subject", max_length=100000)
            if "subject" in data
            else row["subject"]
        )
        body = data.get("body", row["body"])
        if not isinstance(body, str):
            raise ValidationError("body must be a string.")
        if not body.strip():
            raise ValidationError("body must not be empty.")

        metadata = row["metadata"]
        if "metadata" in data:
            metadata_obj = _parse_metadata(data.get("metadata"))
            metadata = json.dumps(metadata_obj, ensure_ascii=False)

        expires_at = row["expires_at"]
        if "ttl_seconds" in data:
            if data.get("ttl_seconds") is None:
                raise ValidationError("ttl_seconds must be a positive integer.")
            expires_at = expires_at_from_ttl(_parse_ttl(data.get("ttl_seconds")))
        elif "expires_at" in data:
            if data.get("expires_at") is None:
                expires_at = None
            else:
                expires_at = parse_future_iso(data.get("expires_at"), "expires_at")

        current_attachments = self._current_attachments(
            self.conn, msg_id, row["revision_number"]
        )
        current_refs = self._references(self.conn, msg_id, row["revision_number"])

        keep_attachments: list[str] = [a["id"] for a in current_attachments]
        staged_downloads: list[dict[str, Any]] = []
        staged_names: list[str] = []
        reference_rows: list[tuple[str, str]] = []
        if "references" in data:
            refs = data.get("references")
            if refs is None:
                refs = []
            if not isinstance(refs, list):
                raise ValidationError("references must be a list of http(s) URL strings.")
            if len(refs) > 1000:
                raise ValidationError("At most 1000 references are allowed per message.")
            for ref in refs:
                reference_rows.append((validate_url_reference(ref), "reference"))
        else:
            reference_rows.extend(
                (r["url"], "reference")
                for r in current_refs
                if r["origin"] == "reference"
            )

        if "attachments" in data:
            specs = data.get("attachments")
            if specs is None:
                specs = []
            if not isinstance(specs, list):
                raise ValidationError("attachments must be a list.")
            # Validate every entry before downloading/storing anything so an
            # invalid later entry cannot leave orphan blobs behind.
            for spec in specs:
                if not isinstance(spec, dict):
                    raise ValidationError("Each attachment entry must be an object.")
                kind = spec.get("kind")
                if kind == "existing":
                    owned = self.conn.execute(
                        "SELECT id FROM attachments WHERE id = ? AND message_id = ?",
                        (spec.get("attachment_id"), msg_id),
                    ).fetchone()
                    if owned is None:
                        raise ValidationError(
                            f"Attachment {spec.get('attachment_id')!r} does not belong to this message."
                        )
                elif kind in {"url_reference", "url_download"}:
                    validate_url_reference(spec.get("url"))
                else:
                    raise ValidationError(
                        "Attachment kind must be 'existing', 'url_reference' or 'url_download'."
                    )
            keep_attachments = []
            for spec in specs:
                if not isinstance(spec, dict):
                    raise ValidationError("Each attachment entry must be an object.")
                kind = spec.get("kind")
                if kind == "existing":
                    existing_id = spec.get("attachment_id")
                    owned = self.conn.execute(
                        "SELECT id FROM attachments WHERE id = ? AND message_id = ?",
                        (existing_id, msg_id),
                    ).fetchone()
                    if owned is None:
                        raise ValidationError(
                            f"Attachment {existing_id!r} does not belong to this message."
                        )
                    if existing_id not in keep_attachments:
                        keep_attachments.append(existing_id)
                    continue
                url = spec.get("url")
                if kind == "url_reference":
                    reference_rows.append((validate_url_reference(url), "attachment_reference"))
                elif kind == "url_download":
                    validated_url = validate_url_reference(url)
                    result = safe_download(
                        validated_url,
                        max_bytes=self.config.max_attachment_bytes,
                        timeout=self.config.download_timeout_seconds,
                        max_redirects=self.config.max_redirects,
                        allow_private=self.config.allow_private_urls,
                        override_filename=spec.get("filename"),
                    )
                    filename = sanitize_filename(spec.get("filename") or result.filename)
                    stored = self.store.save_bytes(
                        filename=filename,
                        mime_type=_normalise_mime(result.mime_type, filename),
                        data=result.data,
                        source_type="url_download",
                        source_url=result.final_url,
                    )
                    staged_downloads.append(stored)
                    staged_names.append(stored["storage_name"])
                else:
                    raise ValidationError(
                        "Attachment kind must be 'existing', 'url_reference' or 'url_download'."
                    )
        else:
            reference_rows.extend(
                (r["url"], "attachment_reference")
                for r in current_refs
                if r["origin"] == "attachment_reference"
            )

        # Enforce the per-message limit against attachments carried into the revision.
        existing_size = sum(
            r["size_bytes"]
            for r in self.conn.execute(
                f"SELECT size_bytes FROM attachments WHERE id IN ({','.join('?' for _ in keep_attachments)})",
                keep_attachments,
            ).fetchall()
        ) if keep_attachments else 0
        total_size = existing_size + sum(s["size_bytes"] for s in staged_downloads)
        if total_size > self.config.max_message_attachment_bytes:
            for name in staged_names:
                try:
                    self.store.path_for(name).unlink(missing_ok=True)
                except Exception:  # pragma: no cover
                    pass
            raise TooLargeError(
                f"Attachments exceed the per-message limit of {self.config.max_message_attachment_bytes} bytes."
            )

        conflict: str | None = None
        event_id: str | None = None
        expiry_event_id: str | None = None
        result: dict[str, Any] | None = None
        try:
            with self.db.transaction(self.conn, immediate=True):
                fresh = self._load_message(msg_id)
                if self._is_expired(fresh):
                    expiry_event_id = self._expire_row(self.conn, fresh)
                    conflict = "stale"
                elif fresh["status"] not in PATCHABLE_STATUSES:
                    conflict = fresh["status"]
                else:
                    new_revision = fresh["revision_number"] + 1
                    timestamp = now_iso()
                    revision_pk = self.conn.execute(
                        """
                        INSERT INTO message_revisions(
                            message_id, revision_number, channel, destination, destination_normalized,
                            destination_label, subject, body, expires_at, webhook_url, source,
                            metadata, rejection_reason, rejection_at, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?)
                        """,
                        (
                            msg_id,
                            new_revision,
                            channel,
                            destination,
                            normalized.normalized,
                            destination_label,
                            subject,
                            body,
                            expires_at,
                            fresh["webhook_url"],
                            fresh["source"],
                            metadata,
                            timestamp,
                        ),
                    ).lastrowid
                    for stored in staged_downloads:
                        att_id = self._insert_attachment(
                            self.conn, msg_id, stored, timestamp, commit_now=False
                        )
                        if att_id not in keep_attachments:
                            keep_attachments.append(att_id)
                    for att_id in keep_attachments:
                        self.conn.execute(
                            "INSERT INTO revision_attachments(revision_id, attachment_id) VALUES (?, ?)",
                            (revision_pk, att_id),
                        )
                    seen: set[tuple[str, str]] = set()
                    for url, origin in reference_rows:
                        if (url, origin) in seen:
                            continue
                        seen.add((url, origin))
                        self.conn.execute(
                            """
                            INSERT INTO message_references(message_id, revision_number, url, origin, created_at)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (msg_id, new_revision, url, origin, timestamp),
                        )
                    cursor = self.conn.execute(
                        """
                        UPDATE messages SET
                            channel = ?, destination = ?, destination_normalized = ?,
                            destination_label = ?, subject = ?, body = ?, expires_at = ?,
                            metadata = ?, status = 'pending', rejection_reason = NULL,
                            rejection_at = NULL, revision_number = ?, updated_at = ?
                        WHERE id = ? AND status = ? AND revision_number = ?
                        """,
                        (
                            channel,
                            destination,
                            normalized.normalized,
                            destination_label,
                            subject,
                            body,
                            expires_at,
                            metadata,
                            new_revision,
                            timestamp,
                            msg_id,
                            fresh["status"],
                            fresh["revision_number"],
                        ),
                    )
                    if cursor.rowcount != 1:
                        raise ConflictError("The message changed concurrently.", fresh["status"])
                    if fresh["status"] == "rejected":
                        self._record_history(
                            self.conn,
                            msg_id,
                            "rejected",
                            "pending",
                            "Revised after rejection",
                            new_revision,
                            timestamp,
                        )
                    self._discover_destination(
                        self.conn, channel, destination, normalized.normalized
                    )
                    updated = self.conn.execute(
                        "SELECT * FROM messages WHERE id = ?", (msg_id,)
                    ).fetchone()
                    event_id = self._emit_event(
                        self.conn,
                        updated,
                        "message.revised",
                        {
                            "previous_revision_number": new_revision - 1,
                            "rejection_cleared": fresh["status"] == "rejected",
                        },
                    )
                    result = self._serialize(self.conn, updated, detail=True)
        except BaseException:
            # A failed revision may have stored URL-download bytes; history keeps
            # referenced attachments, but freshly downloaded orphan blobs are cleaned.
            for name in staged_names:
                try:
                    self.store.path_for(name).unlink(missing_ok=True)
                except Exception:  # pragma: no cover
                    pass
            raise
        if result is None:
            for name in staged_names:
                try:
                    self.store.path_for(name).unlink(missing_ok=True)
                except Exception:  # pragma: no cover
                    pass
        self._dispatch([event_id, expiry_event_id])
        if conflict is not None:
            if conflict == "stale":
                raise ConflictError(
                    "The message expired before it could be revised.", "stale", []
                )
            raise ConflictError(
                f"Cannot revise a message in status {conflict!r}.",
                conflict,
                ALLOWED_ACTIONS_BY_STATUS.get(conflict, []),
            )
        assert result is not None
        return result

    def _insert_attachment(
        self,
        conn: Any,
        msg_id: str,
        stored: dict[str, Any],
        timestamp: str,
        *,
        commit_now: bool,
    ) -> str:
        target = conn or self.conn
        att_id = attachment_id()
        target.execute(
            """
            INSERT INTO attachments(
                id, message_id, original_filename, mime_type, size_bytes,
                storage_name, uploaded_at, source_type, source_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                att_id,
                msg_id,
                stored["original_filename"],
                stored["mime_type"],
                stored["size_bytes"],
                stored["storage_name"],
                timestamp,
                stored["source_type"],
                stored["source_url"],
            ),
        )
        return att_id

    # --------------------------------------------------------------------- expiry
    def _is_expired(self, row: Any) -> bool:
        if row["status"] not in ACTIVE_STATUSES:
            return False
        return bool(row["expires_at"] and row["expires_at"] <= now_iso())

    # -------------------------------------------------------------------- handoff
    def get_handoff(self, msg_id: str) -> dict[str, Any]:
        conflict = False
        expiry_event_id: str | None = None
        result: dict[str, Any] | None = None
        with self.db.transaction(self.conn, immediate=True):
            row = self._load_message(msg_id)
            if self._is_expired(row):
                expiry_event_id = self._expire_row(self.conn, row)
                conflict = True
            elif row["status"] != "approved":
                raise ConflictError(
                    f"Handoff is only available for approved messages; this message is {row['status']!r}.",
                    row["status"],
                    ALLOWED_ACTIONS_BY_STATUS.get(row["status"], []),
                )
            else:
                attachments = self._current_attachments(
                    self.conn, msg_id, row["revision_number"]
                )
                adapter = get_adapter(row["channel"])
                result = adapter.handoff(dict(row), attachments)
        self._dispatch([expiry_event_id])
        if conflict:
            raise ConflictError(
                "The message expired before handoff could be prepared.", "stale", []
            )
        assert result is not None
        return result

    # ---------------------------------------------------------------- attachments
    def list_attachments(self, msg_id: str) -> dict[str, Any]:
        self.expire_due()
        row = self._load_message(msg_id)
        attachments = self._current_attachments(
            self.conn, msg_id, row["revision_number"]
        )
        items = [self._attachment_dict(msg_id, a) for a in attachments]
        return {
            "message_id": msg_id,
            "items": items,
            "attachments": items,
            "total": len(items),
            "attachment_count": len(items),
        }

    def get_attachment(self, msg_id: str, att_id: str) -> tuple[dict[str, Any], bytes]:
        self._load_message(msg_id)
        row = self.conn.execute(
            "SELECT * FROM attachments WHERE id = ? AND message_id = ?",
            (att_id, msg_id),
        ).fetchone()
        if row is None:
            raise NotFoundError(
                f"Attachment {att_id!r} was not found for message {msg_id!r}."
            )
        try:
            data = self.store.read_bytes(row["storage_name"])
        except (FileNotFoundError, ValidationError) as exc:
            raise NotFoundError(
                "The attachment record exists but the stored file is missing.",
                {"attachment_id": att_id},
            ) from exc
        return dict(row), data

    def download_zip(self, msg_id: str) -> tuple[str, bytes]:
        import io
        import zipfile

        self.expire_due()
        row = self._load_message(msg_id)
        attachments = self._current_attachments(
            self.conn, msg_id, row["revision_number"]
        )
        if not attachments:
            raise NotFoundError("This message has no attachments to download.")
        buffer = io.BytesIO()
        used: set[str] = set()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for attachment in attachments:
                try:
                    data = self.store.read_bytes(attachment["storage_name"])
                except (FileNotFoundError, ValidationError):
                    continue
                name = sanitize_filename(attachment["original_filename"])
                base, dot, ext = name.rpartition(".")
                if not dot:
                    base, ext = name, ""
                candidate = name
                counter = 2
                while candidate.lower() in used:
                    candidate = f"{base} ({counter}){'.' + ext if ext else ''}"
                    counter += 1
                used.add(candidate.lower())
                archive.writestr(candidate, data)
        return f"message-{msg_id}-attachments.zip", buffer.getvalue()

    # ------------------------------------------------------------------ destinations
    def list_destinations(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}
        where: list[str] = []
        values: list[Any] = []
        channel = params.get("channel")
        if channel:
            if channel not in CHANNELS:
                raise ValidationError(f"Unknown channel {channel!r}.")
            where.append("d.channel = ?")
            values.append(channel)
        search = params.get("q") or params.get("destination")
        if search:
            needle = f"%{str(search).strip().lower()}%"
            where.append(
                "(LOWER(d.destination) LIKE ? OR LOWER(d.destination_normalized) LIKE ? OR LOWER(COALESCE(d.label,'')) LIKE ?)"
            )
            values.extend([needle, needle, needle])
        where_sql = (" WHERE " + " AND ".join(where)) if where else ""
        rows = self.conn.execute(
            f"""
            SELECT d.*,
                (SELECT COUNT(*) FROM messages m
                 WHERE m.channel = d.channel AND m.destination_normalized = d.destination_normalized) AS message_count,
                (SELECT MAX(m.created_at) FROM messages m
                 WHERE m.channel = d.channel AND m.destination_normalized = d.destination_normalized) AS last_used_at
            FROM destinations d
            {where_sql}
            ORDER BY d.channel, d.destination_normalized
            """,
            values,
        ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["label"] = item.get("label")
            items.append(item)
        return {"items": items, "destinations": items, "total": len(items)}

    def set_destination_label(
        self, channel: Any, destination: Any, label: Any
    ) -> dict[str, Any]:
        if not isinstance(channel, str) or channel not in CHANNELS:
            raise ValidationError(f"channel must be one of: {', '.join(CHANNELS)}.")
        adapter = get_adapter(channel)
        if not isinstance(destination, str):
            raise ValidationError("destination must be a string.")
        normalized = adapter.normalize(destination)
        if not isinstance(label, str):
            raise ValidationError("label must be a non-empty string.")
        cleaned = label.strip()
        if not cleaned:
            raise ValidationError("label must be a non-empty string.")
        if len(cleaned) > DESTINATION_LABEL_MAX:
            raise ValidationError(
                f"label must be at most {DESTINATION_LABEL_MAX} characters."
            )
        row = self.conn.execute(
            "SELECT * FROM destinations WHERE channel = ? AND destination_normalized = ?",
            (channel, normalized.normalized),
        ).fetchone()
        if row is None:
            raise NotFoundError(
                "Destination has not been discovered from any message yet.",
                {"channel": channel, "destination": destination},
            )
        duplicate = self.conn.execute(
            """
            SELECT 1 FROM destinations
            WHERE channel = ? AND label IS NOT NULL AND label = ? COLLATE NOCASE
              AND destination_normalized <> ?
            """,
            (channel, cleaned, normalized.normalized),
        ).fetchone()
        if duplicate:
            raise ConflictError(
                f"Label {cleaned!r} is already used by another {channel} destination.",
                details={"label": cleaned, "channel": channel},
            )
        timestamp = now_iso()
        try:
            with self.db.transaction(self.conn, immediate=True):
                self.conn.execute(
                    "UPDATE destinations SET label = ?, updated_at = ? WHERE channel = ? AND destination_normalized = ?",
                    (cleaned, timestamp, channel, normalized.normalized),
                )
        except sqlite3.IntegrityError as exc:
            raise ConflictError(
                f"Label {cleaned!r} is already used by another {channel} destination.",
                details={"label": cleaned, "channel": channel},
            ) from exc
        return {
            "channel": channel,
            "destination": row["destination"],
            "destination_normalized": normalized.normalized,
            "label": cleaned,
            "updated_at": timestamp,
        }

    def remove_destination_label(
        self, channel: Any, destination: Any
    ) -> dict[str, Any]:
        if not isinstance(channel, str) or channel not in CHANNELS:
            raise ValidationError(f"channel must be one of: {', '.join(CHANNELS)}.")
        adapter = get_adapter(channel)
        if not isinstance(destination, str):
            raise ValidationError("destination must be a string.")
        normalized = adapter.normalize(destination)
        row = self.conn.execute(
            "SELECT * FROM destinations WHERE channel = ? AND destination_normalized = ?",
            (channel, normalized.normalized),
        ).fetchone()
        if row is None:
            raise NotFoundError(
                "Destination has not been discovered from any message yet.",
                {"channel": channel, "destination": destination},
            )
        timestamp = now_iso()
        with self.db.transaction(self.conn, immediate=True):
            self.conn.execute(
                "UPDATE destinations SET label = NULL, updated_at = ? WHERE channel = ? AND destination_normalized = ?",
                (timestamp, channel, normalized.normalized),
            )
        return {
            "channel": channel,
            "destination": row["destination"],
            "destination_normalized": normalized.normalized,
            "label": None,
            "removed": row["label"] is not None,
            "updated_at": timestamp,
        }

    # --------------------------------------------------------------------- webhook
    def webhook_events(self, msg_id: str) -> dict[str, Any]:
        self._load_message(msg_id)
        rows = self.conn.execute(
            "SELECT * FROM webhook_events WHERE message_id = ? ORDER BY created_at, rowid",
            (msg_id,),
        ).fetchall()
        events = [self.dispatcher.event_with_attempts(row) for row in rows]
        return {
            "message_id": msg_id,
            "items": events,
            "events": events,
            "total": len(events),
        }


def _split_multi(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        parts = []
        for item in value:
            parts.extend(str(item).split(","))
    else:
        parts = str(value).split(",")
    return [part.strip() for part in parts if part.strip()]


def _parse_pagination_int(
    value: Any, field: str, *, default: int, minimum: int
) -> int:
    if value is None or value == "":
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be an integer.") from exc
    if parsed < minimum:
        raise ValidationError(f"{field} must be at least {minimum}.")
    return parsed
