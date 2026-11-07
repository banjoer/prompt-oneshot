"""Asynchronous webhook delivery with bounded exponential backoff.

Event rows are created transactionally with the state change (in service.py)
and delivered strictly afterwards, so delivery never blocks or rolls back a
transition. Each attempt is persisted; URLs are re-validated (SSRF guard)
before every single attempt.
"""
from __future__ import annotations

import json
import threading
from datetime import timedelta
from typing import Optional

from . import netguard
from .service import OutboxContext
from .timeutil import iso, now_iso, now_utc


def send_webhook(ctx: OutboxContext, url: str, payload: dict) -> int:
    """Real sender: revalidates the URL then POSTs JSON. Returns HTTP status.

    Raises UrlBlockedError on blocked URLs, timeouts, connection errors, or
    non-2xx responses (which count as failures).
    """
    status = netguard.http_post_json(
        url, payload, allow_private=ctx.cfg.allow_private_urls,
        timeout=ctx.cfg.webhook_timeout_seconds)
    if not (200 <= status < 300):
        raise netguard.UrlBlockedError(f"webhook returned HTTP status {status}")
    return status


def process_pending_events(ctx: OutboxContext, *, limit: int = 20) -> int:
    """Attempt every due event once. Returns the number of events attempted.

    Due = state queued/failed, attempts below the max, and next_attempt_at
    reached (or unset). Events are claimed with a compare-and-set update so
    two workers can never deliver the same event twice concurrently.
    """
    import json
    conn = ctx.connect()
    attempted = 0
    try:
        due = conn.execute(
            "SELECT * FROM webhook_events WHERE state IN ('queued','failed') "
            "AND attempts < ? AND (next_attempt_at IS NULL OR next_attempt_at <= ?) "
            "ORDER BY id LIMIT ?",
            (ctx.cfg.webhook_max_attempts, now_iso(), limit)).fetchall()
        for event in due:
            claim = conn.execute(
                "UPDATE webhook_events SET state='delivering' WHERE id=? AND state IN ('queued','failed')",
                (event["id"],))
            if claim.rowcount != 1:
                continue  # another worker claimed it
            payload = json.loads(event["payload_json"])
            attempt_no = event["attempts"] + 1
            started = now_iso()
            conn.execute(
                "UPDATE webhook_events SET attempts=?, first_attempt_at=COALESCE(first_attempt_at,?), "
                "last_attempt_at=? WHERE id=?", (attempt_no, started, started, event["id"]))
            conn.execute(
                "INSERT INTO webhook_attempts (event_id, attempt_number, started_at) "
                "VALUES (?,?,?)", (event["id"], attempt_no, started))
            attempted += 1
            http_status = None
            error: Optional[str] = None
            try:
                url = event_url(conn, event["message_id"])
                if not url:
                    raise netguard.UrlBlockedError("message has no webhook_url anymore")
                if ctx.webhook_sender is not None:
                    http_status = ctx.webhook_sender(url, payload,
                                                    ctx.cfg.webhook_timeout_seconds)
                    if isinstance(http_status, int) and not (200 <= http_status < 300):
                        raise netguard.UrlBlockedError(
                            f"webhook returned HTTP status {http_status}")
                else:
                    http_status = send_webhook(ctx, url, payload)
            except netguard.UrlBlockedError as exc:
                error = exc.message
            except Exception as exc:  # timeouts, socket errors, anything
                error = f"{type(exc).__name__}: {exc}"
            finished = now_iso()
            ok = error is None
            if ok:
                conn.execute(
                    "UPDATE webhook_events SET state='delivered', last_status_code=?, "
                    "last_error=NULL, delivered_at=?, next_attempt_at=NULL WHERE id=?",
                    (http_status, finished, event["id"]))
                conn.execute(
                    "UPDATE webhook_attempts SET finished_at=?, http_status=? WHERE "
                    "event_id=? AND attempt_number=?", (finished, http_status,
                                                        event["id"], attempt_no))
            else:
                failed_permanently = attempt_no >= ctx.cfg.webhook_max_attempts
                next_at = None
                if not failed_permanently:
                    delay = ctx.cfg.webhook_backoff_base_seconds * (2 ** (attempt_no - 1))
                    next_at = iso(now_utc() + timedelta(seconds=delay))
                conn.execute(
                    "UPDATE webhook_events SET state=?, last_status_code=?, last_error=?, "
                    "next_attempt_at=? WHERE id=?",
                    ("failed" if failed_permanently else "queued", http_status,
                     (error or "")[:500], next_at, event["id"]))
                conn.execute(
                    "UPDATE webhook_attempts SET finished_at=?, http_status=?, error=? "
                    "WHERE event_id=? AND attempt_number=?",
                    (finished, http_status, (error or "")[:500], event["id"], attempt_no))
    finally:
        conn.close()
    return attempted


def event_url(conn, message_id: str) -> str:
    row = conn.execute("SELECT webhook_url FROM messages WHERE id=?", (message_id,)).fetchone()
    return row["webhook_url"] if row and row["webhook_url"] else ""


class ExpirationWorker:
    """Background threads: expiration sweep + webhook delivery attempts."""

    def __init__(self, ctx: OutboxContext) -> None:
        self.ctx = ctx
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        t1 = threading.Thread(target=self._expire_loop, name="outbox-expirer", daemon=True)
        t2 = threading.Thread(target=self._webhook_loop, name="outbox-webhooker", daemon=True)
        self._threads = [t1, t2]
        self.ctx.notifier = self.wake
        t1.start()
        t2.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        for t in self._threads:
            t.join(timeout=2.0)
        if self.ctx.notifier is self.wake:
            self.ctx.notifier = None

    def wake(self) -> None:
        self._wake.set()

    def _expire_loop(self) -> None:
        while not self._stop.wait(self.ctx.cfg.expiration_interval_seconds):
            try:
                from .service import sweep_expired
                sweep_expired(self.ctx)
            except Exception:
                pass  # never crash the worker; next tick retries

    def _webhook_loop(self) -> None:
        while not self._stop.is_set():
            self._wake.wait(timeout=1.0)
            self._wake.clear()
            if self._stop.is_set():
                break
            try:
                while process_pending_events(self.ctx) > 0:
                    if self._stop.is_set():
                        break
            except Exception:
                pass  # never crash; the next tick retries
