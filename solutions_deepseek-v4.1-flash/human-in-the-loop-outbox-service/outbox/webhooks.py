"""Asynchronous webhook delivery with bounded exponential backoff."""

from __future__ import annotations

import json
import threading
import time
import uuid
from typing import Any, Callable

from .config import Config
from .db import Database
from .net import post_webhook
from .timeutil import now_iso


class WebhookDispatcher:
    def __init__(self, db: Database, config: Config) -> None:
        self.db = db
        self.config = config
        self._lock = threading.Lock()
        self._in_flight: set[str] = set()
        self._threads: list[threading.Thread] = []
        # Tests replace this callable to simulate success/failure/timeouts.
        self.send_once: Callable[[str, dict[str, Any]], tuple[bool, int | None, str | None, str | None]] = (
            self._default_send_once
        )

    def _default_send_once(
        self, url: str, payload: dict[str, Any]
    ) -> tuple[bool, int | None, str | None, str | None]:
        return post_webhook(
            url,
            payload,
            timeout=self.config.webhook_timeout_seconds,
            allow_private=self.config.allow_private_urls,
        )

    def enqueue(self, event_id: str) -> threading.Thread | None:
        if self.config.webhook_async:
            thread = threading.Thread(
                target=self.deliver_event,
                args=(event_id,),
                name=f"webhook-{event_id}",
                daemon=True,
            )
            with self._lock:
                self._threads = [t for t in self._threads if t.is_alive()]
                self._threads.append(thread)
            thread.start()
            return thread
        self.deliver_event(event_id)
        return None

    def wait_for_idle(self, timeout: float = 10.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                alive = [t for t in self._threads if t.is_alive()]
            if not alive:
                return
            for thread in alive:
                remaining = max(0.0, deadline - time.monotonic())
                thread.join(timeout=remaining)
            if time.monotonic() >= deadline:
                return

    def deliver_event(self, event_id: str) -> None:
        with self._lock:
            if event_id in self._in_flight:
                return
            self._in_flight.add(event_id)
        try:
            self._deliver_event(event_id)
        finally:
            with self._lock:
                self._in_flight.discard(event_id)

    def _deliver_event(self, event_id: str) -> None:
        conn = self.db.connect()
        try:
            event = conn.execute(
                "SELECT * FROM webhook_events WHERE id = ?", (event_id,)
            ).fetchone()
            if event is None:
                return
            if event["status"] in {"delivered", "failed"}:
                return
            message = conn.execute(
                "SELECT id, webhook_url FROM messages WHERE id = ?",
                (event["message_id"],),
            ).fetchone()
            if message is None:
                self._finish_event(conn, event_id, "failed", "Message no longer exists.")
                return
            url = message["webhook_url"]
            if not url:
                self._finish_event(conn, event_id, "failed", "No webhook_url configured.")
                return
            payload = json.loads(event["payload"])
            with self.db.transaction(conn, immediate=True):
                conn.execute(
                    "UPDATE webhook_events SET status = 'delivering', updated_at = ? WHERE id = ? AND status = 'pending'",
                    (now_iso(), event_id),
                )
            max_attempts = max(1, int(self.config.webhook_max_attempts))
            attempt = 0
            while attempt < max_attempts:
                attempt += 1
                started = now_iso()
                try:
                    ok, http_status, error, response_body = self.send_once(url, payload)
                except Exception as exc:  # injected senders may raise; record the attempt
                    ok, http_status, error, response_body = (
                        False,
                        None,
                        f"{type(exc).__name__}: {exc}",
                        None,
                    )
                finished = now_iso()
                with self.db.transaction(conn, immediate=True):
                    conn.execute(
                        """
                        INSERT INTO webhook_attempts(
                            event_id, attempt_number, status, started_at, finished_at,
                            http_status, error, response_body
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            event_id,
                            attempt,
                            "success" if ok else "failed",
                            started,
                            finished,
                            http_status,
                            error,
                            (response_body or "")[:1000] if response_body else None,
                        ),
                    )
                    conn.execute(
                        "UPDATE webhook_events SET attempt_count = ?, updated_at = ?, last_error = ? WHERE id = ?",
                        (attempt, finished, None if ok else error, event_id),
                    )
                if ok:
                    self._finish_event(conn, event_id, "delivered", None)
                    return
                if attempt < max_attempts:
                    delay = max(0.0, self.config.webhook_backoff_base_seconds) * (2 ** (attempt - 1))
                    if delay:
                        time.sleep(delay)
            self._finish_event(conn, event_id, "failed", error or "Delivery failed.")
        finally:
            conn.close()

    def _finish_event(self, conn, event_id: str, status: str, error: str | None) -> None:
        timestamp = now_iso()
        with self.db.transaction(conn, immediate=True):
            conn.execute(
                """
                UPDATE webhook_events
                SET status = ?, updated_at = ?, last_error = COALESCE(?, last_error),
                    delivered_at = CASE WHEN ? = 'delivered' THEN ? ELSE delivered_at END
                WHERE id = ?
                """,
                (
                    status,
                    timestamp,
                    error,
                    status,
                    timestamp,
                    event_id,
                ),
            )

    def event_with_attempts(self, event_row: Any) -> dict[str, Any]:
        conn = self.db.connect()
        try:
            attempts = conn.execute(
                "SELECT * FROM webhook_attempts WHERE event_id = ? ORDER BY attempt_number",
                (event_row["id"],),
            ).fetchall()
        finally:
            conn.close()
        event = dict(event_row)
        event["payload"] = json.loads(event["payload"]) if event.get("payload") else None
        event["attempts"] = [
            {
                "attempt_number": a["attempt_number"],
                "status": a["status"],
                "started_at": a["started_at"],
                "finished_at": a["finished_at"],
                "http_status": a["http_status"],
                "error": a["error"],
                "response_body": a["response_body"],
            }
            for a in attempts
        ]
        return event


def new_event_id() -> str:
    return "wh_" + uuid.uuid4().hex[:16]
