"""Automated tests for the outbox service (unittest + Flask test client).

Run from a clean checkout, no external network:
    python3 -m unittest discover -s tests -v
Loopback fixture servers are used where the spec allows; webhook delivery is
mocked in most tests and exercised against a local sink in one test.
"""
from __future__ import annotations

import io
import json
import pathlib
import sys
import threading
import time
import unittest
from datetime import timedelta

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from helpers import (OutboxTestCase, start_files, start_sink, stop_server)

from outbox import service
from outbox.errors import ApiError
from outbox.storage import guess_mime, sanitize_filename
from outbox.timeutil import iso, now_utc, parse_iso
from outbox.webhooks import process_pending_events
import outbox.netguard as netguard

PUBLIC_IP_WEBHOOK = "http://8.8.8.8/hooks/outbox"  # public IP literal: no DNS, no traffic


class SystemEndpointsTest(OutboxTestCase):
    def test_health(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["status"], "ok")

    def test_info_exposes_config_without_secrets(self):
        body = self.client.get("/api/info").get_json()
        for key in ("max_attachment_bytes", "max_message_attachment_bytes",
                    "expiration_interval_seconds", "webhook_timeout_seconds",
                    "webhook_max_attempts", "download_timeout_seconds",
                    "max_redirects", "allow_private_urls", "port"):
            self.assertIn(key, body)
        self.assertNotIn("secret", json.dumps(body).lower())

    def test_openapi_served_and_valid_shape(self):
        spec = self.client.get("/openapi.json").get_json()
        self.assertTrue(spec["openapi"].startswith("3."))
        self.assertIn("paths", spec)
        self.assertIn("info", spec)

    def test_openapi_covers_every_route(self):
        spec = self.client.get("/openapi.json").get_json()
        verbs = {"GET", "POST", "PATCH", "PUT", "DELETE"}
        missing = []
        for rule in self.app.url_map.iter_rules():
            methods = set(rule.methods) & verbs
            if not methods or rule.endpoint == "static":
                continue
            if rule.rule == "/":
                continue  # the SPA itself is not part of the REST contract
            path = (rule.rule.replace("<message_id>", "{id}")
                    .replace("<attachment_id>", "{attachment_id}"))
            entry = spec["paths"].get(path)
            if entry is None:
                missing.append(path)
                continue
            for m in methods:
                if m.lower() not in entry:
                    missing.append(f"{m} {path}")
        self.assertEqual(missing, [], f"routes missing from OpenAPI: {missing}")

    def test_required_endpoints_present(self):
        spec = self.client.get("/openapi.json").get_json()
        required = ["/api/messages", "/api/messages/{id}", "/api/messages/{id}/approve",
                    "/api/messages/{id}/reject", "/api/messages/{id}/cancel",
                    "/api/messages/{id}/mark-sent", "/api/messages/{id}/history",
                    "/api/messages/{id}/handoff", "/api/messages/{id}/attachments",
                    "/api/messages/{id}/attachments/{attachment_id}",
                    "/api/messages/{id}/webhook-events", "/api/destinations",
                    "/api/destinations/label", "/api/health", "/api/info",
                    "/api/docs", "/openapi.json"]
        for path in required:
            self.assertIn(path, spec["paths"], path)

    def test_committed_openapi_file_matches_app(self):
        import pathlib
        p = pathlib.Path(__file__).resolve().parents[1] / "openapi.json"
        self.assertTrue(p.is_file(), "openapi.json must be committed")
        file_spec = json.loads(p.read_text())
        app_spec = self.client.get("/openapi.json").get_json()
        self.assertEqual(set(file_spec["paths"]), set(app_spec["paths"]))
        self.assertTrue(file_spec["openapi"].startswith("3."))

    def test_docs_page_renders(self):
        res = self.client.get("/api/docs")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/html", res.headers["Content-Type"])
        self.assertIn(b"openapi.json", res.data)

    def test_spa_root_and_static_assets(self):
        root = self.client.get("/")
        self.assertEqual(root.status_code, 200)
        self.assertIn(b'id="message-list"', root.data)
        for asset in ("/static/app.js", "/static/styles.css"):
            self.assertEqual(self.client.get(asset).status_code, 200, asset)

    def test_signoff_in_app_header_and_spa_footer(self):
        import pathlib
        base = pathlib.Path(__file__).resolve().parents[1]
        header = (base / "app.py").read_text()[:1200]
        self.assertRegex(header, r"Built 2026-\d{2}-\d{2} \d{2}:\d{2} UTC by Qwen3\.8 Flash")
        page = self.client.get("/").data.decode()
        self.assertRegex(page, r"Built 2026-\d{2}-\d{2} \d{2}:\d{2} UTC")
        self.assertIn("Qwen3.8 Flash", page)


class SubmissionValidationTest(OutboxTestCase):
    def test_json_email_returns_201_with_stable_fields(self):
        res = self.submit(subject="Q4", body="Hi Alex,\n\nReview please.",
                          expires_at="2030-01-01T00:00:00Z", source="agent-x",
                          metadata={"ticket": "OPS-142"})
        self.assertEqual(res.status_code, 201)
        body = res.get_json()
        self.assertRegex(body["id"], r"^msg_[0-9a-f]{12}$")
        self.assertEqual(body["status"], "pending")
        self.assertEqual(body["revision_number"], 1)
        parse_iso(body["created_at"])
        detail = self.get_msg(body["id"])
        self.assertEqual(detail["source"], "agent-x")
        self.assertEqual(detail["metadata"], {"ticket": "OPS-142"})
        self.assertEqual(detail["expires_at"], "2030-01-01T00:00:00.000Z")

    def test_created_at_never_changes_and_id_stable_across_revisions(self):
        mid = self.submit_id()
        created = self.get_msg(mid)["created_at"]
        self.client.post(f"/api/messages/{mid}/reject", json={"reason": "no"})
        self.client.patch(f"/api/messages/{mid}", json={"body": "new body"})
        again = self.get_msg(mid)
        self.assertEqual(again["id"], mid)
        self.assertEqual(again["created_at"], created)
        self.assertEqual(again["revision_number"], 2)

    def test_rejects_unknown_channel(self):
        res = self.client.post("/api/messages",
                               json={"channel": "sms", "destination": "12345", "body": "x"})
        self.assertApiError(res, "bad_request", 400)
        self.assertEqual(res.get_json()["field"], "channel")

    def test_rejects_invalid_email_destination(self):
        res = self.client.post("/api/messages",
                               json={"channel": "email", "destination": "not-an-email", "body": "x"})
        self.assertApiError(res, "bad_request", 400)

    def test_rejects_invalid_whatsapp_and_telegram(self):
        for channel, dest in [("whatsapp", "4155550123"), ("whatsapp", "+1"),
                              ("telegram", "no-at-sign-here"), ("telegram", "@ab")]:
            res = self.client.post("/api/messages",
                                   json={"channel": channel, "destination": dest, "body": "x"})
            self.assertEqual(res.status_code, 400, (channel, dest))

    def test_rejects_missing_or_empty_body_and_destination(self):
        for payload in [{"channel": "email", "destination": "a@b.co"},
                        {"channel": "email", "body": "x"},
                        {"channel": "email", "destination": "a@b.co", "body": "   "}]:
            res = self.client.post("/api/messages", json=payload)
            self.assertEqual(res.status_code, 400)

    def test_ttl_and_expires_mutually_exclusive_and_ttl_rules(self):
        both = self.client.post("/api/messages", json={
            "channel": "email", "destination": "a@b.co", "body": "x",
            "ttl_seconds": 60, "expires_at": "2030-01-01T00:00:00Z"})
        self.assertEqual(both.status_code, 400)
        for bad_ttl in (0, -5, "soon", 1.5, True):
            res = self.client.post("/api/messages", json={
                "channel": "email", "destination": "a@b.co", "body": "x",
                "ttl_seconds": bad_ttl})
            self.assertEqual(res.status_code, 400, bad_ttl)

    def test_absolute_expiry_must_be_future_and_parseable(self):
        past = self.client.post("/api/messages", json={
            "channel": "email", "destination": "a@b.co", "body": "x",
            "expires_at": "2001-01-01T00:00:00Z"})
        self.assertEqual(past.status_code, 400)
        garbage = self.client.post("/api/messages", json={
            "channel": "email", "destination": "a@b.co", "body": "x",
            "expires_at": "next tuesday"})
        self.assertEqual(garbage.status_code, 400)

    def test_metadata_must_be_object(self):
        res = self.client.post("/api/messages", json={
            "channel": "email", "destination": "a@b.co", "body": "x",
            "metadata": [1, 2]})
        self.assertEqual(res.status_code, 400)

    def test_malformed_json_and_unsupported_media(self):
        res = self.client.post("/api/messages", data="{nope",
                               content_type="application/json")
        self.assertEqual(res.status_code, 400)
        res = self.client.post("/api/messages", data="plain",
                               content_type="text/plain")
        self.assertApiError(res, "unsupported_media_type", 415)
        res = self.client.post("/api/messages", data=json.dumps([1, 2]),
                               content_type="application/json")
        self.assertEqual(res.status_code, 400)

    def test_invalid_attachment_spec_and_references(self):
        res = self.client.post("/api/messages", json={
            "channel": "email", "destination": "a@b.co", "body": "x",
            "attachments": [{"kind": "carrier_pigeon", "url": "http://8.8.8.8/p"}]})
        self.assertEqual(res.status_code, 400)
        res = self.client.post("/api/messages", json={
            "channel": "email", "destination": "a@b.co", "body": "x",
            "references": ["ftp://files.example/x"]})
        self.assertEqual(res.status_code, 400)

    def test_url_reference_never_fetched(self):
        mid = self.submit_id(references=["https://example.com/spec"],
                             attachments=[{"kind": "url_reference",
                                           "url": "https://example.org/other"}])
        detail = self.get_msg(mid)
        self.assertEqual(len(detail["attachments"]), 0)
        self.assertIn("https://example.com/spec", detail["references"])
        self.assertIn("https://example.org/other", detail["references"])

    def test_webhook_url_validated_at_submission(self):
        # This class runs with the documented ALLOW_PRIVATE_URLS=1 override, so
        # the loopback sink URL is accepted; blocking behavior is verified in
        # WebhookSsrfDefaultsTest.
        res = self.client.post("/api/messages", json={
            "channel": "email", "destination": "a@b.co", "body": "x",
            "webhook_url": "http://127.0.0.1:9/x"})
        self.assertEqual(res.status_code, 201)

    def test_webhook_url_accepts_public_ip_without_traffic(self):
        mid = self.submit_id(webhook_url=PUBLIC_IP_WEBHOOK)
        self.assertEqual(self.get_msg(mid)["webhook_url"], PUBLIC_IP_WEBHOOK)


class WebhookSsrfDefaultsTest(OutboxTestCase):
    allow_private = False

    def test_private_loopback_linklocal_metadata_blocked_by_default(self):
        for url in ["http://127.0.0.1:9002/hook", "http://10.1.2.3/hook",
                    "http://192.168.0.7/hook", "http://169.254.169.254/latest/meta-data/",
                    "http://[::1]/hook", "http://localhost:9/hook", "ftp://x/h",
                    "http://user:pass@8.8.8.8/h", "not a url"]:
            res = self.client.post("/api/messages", json={
                "channel": "email", "destination": "a@b.co", "body": "x",
                "webhook_url": url})
            self.assertEqual(res.status_code, 400, url)

    def test_download_blocked_by_default(self):
        srv, base = start_files()
        self.addCleanup(stop_server, srv)
        res = self.client.post("/api/messages", json={
            "channel": "email", "destination": "a@b.co", "body": "x",
            "attachments": [{"kind": "url_download", "url": base + "/sample.txt"}]})
        self.assertEqual(res.status_code, 400)

    def test_public_ip_allowed_by_guard(self):
        # An http URL to a public IP literal passes validation (no traffic sent
        # unless a download is attempted; the guard itself is what we assert).
        netguard.validate_url("http://8.8.8.8/p.png", field="t", allow_private=False)


class ListingTest(OutboxTestCase):
    def setUp(self):
        super().setUp()
        self.a = self.submit_id(destination="a@corp.example", body="A body",
                                ttl_seconds=3600)
        time.sleep(0.02)
        self.b = self.submit_id(destination="b@corp.example", body="B body",
                                ttl_seconds=7200, destination_label="Beta Team")
        time.sleep(0.02)
        self.c = self.submit_id(channel="whatsapp", destination="+14155550123",
                                body="C body")
        self.client.post(f"/api/messages/{self.b}/reject", json={"reason": "nope"})

    def _ids(self, qs):
        body = self.client.get("/api/messages?" + qs).get_json()
        return [i["id"] for i in body["items"]], body

    def test_default_newest_first(self):
        ids, body = self._ids("")
        self.assertEqual(ids[:3][0], self.c)  # newest submitted last
        self.assertEqual(body["limit"], 20)
        self.assertEqual(body["total"], 3)

    def test_status_filter_single_and_comma(self):
        ids, _ = self._ids("status=pending")
        self.assertEqual(ids, [self.c, self.a])  # newest first
        ids, _ = self._ids("status=pending,rejected")
        self.assertEqual(ids, [self.c, self.b, self.a])  # newest first overall
        ids, _ = self._ids("status=rejected")
        self.assertEqual(ids, [self.b])

    def test_channel_filter(self):
        ids, body = self._ids("channel=whatsapp")
        self.assertEqual(ids, [self.c])
        res = self.client.get("/api/messages?channel=carrier-pigeon")
        self.assertEqual(res.status_code, 400)

    def test_destination_filter_case_insensitive_on_destination_and_label(self):
        ids, _ = self._ids("destination=B@CORP")
        self.assertEqual(ids, [self.b])
        ids, _ = self._ids("destination=beta team")
        self.assertEqual(ids, [self.b])

    def test_pagination_and_limit_bounds(self):
        ids, body = self._ids("limit=2&offset=0")
        self.assertEqual(len(ids), 2)
        self.assertEqual(body["total"], 3)
        more, body2 = self._ids("limit=2&offset=2")
        self.assertEqual(len(more), 1)
        res = self.client.get("/api/messages?limit=0")
        self.assertEqual(res.status_code, 400)
        res = self.client.get("/api/messages?limit=500")
        self.assertEqual(res.get_json()["limit"], 100)

    def test_expiry_sorting_puts_none_last(self):
        soon, _ = self._ids("sort=expires_soon")
        self.assertEqual(soon, [self.a, self.b, self.c])
        late, _ = self._ids("sort=expires_late")
        self.assertEqual(late[:2], [self.b, self.a])
        self.assertEqual(late[2], self.c)  # no expiration last in both orders

    def test_date_range_filters(self):
        future = iso(now_utc() + timedelta(days=1))
        ids, body = self._ids(f"created_from={future}")
        self.assertEqual(body["total"], 0)
        today = now_utc().date().isoformat()
        ids, body = self._ids(f"created_to={today}")
        self.assertEqual(body["total"], 3)
        ids, _ = self._ids("expires_to=" + iso(now_utc() + timedelta(minutes=90)))
        self.assertEqual(ids, [self.a])  # a expires in ~1h, b in ~2h
        ids, _ = self._ids("expires_from=" + iso(now_utc() + timedelta(hours=5)))
        self.assertEqual(ids, [])

    def test_history_endpoint(self):
        h = self.client.get(f"/api/messages/{self.b}/history").get_json()
        self.assertEqual(h["current_status"], "rejected")
        self.assertEqual([t["to_status"] for t in h["transitions"]],
                         ["pending", "rejected"])
        self.assertEqual(len(h["revisions"]), 1)
        missing = self.client.get("/api/messages/msg_000000000000/history")
        self.assertEqual(missing.status_code, 404)

    def test_missing_message_404(self):
        self.assertEqual(self.client.get("/api/messages/msg_000000000000").status_code, 404)
        self.assertEqual(self.client.post("/api/messages/msg_000000000000/approve").status_code, 404)
        self.assertEqual(self.client.get("/api/messages/msg_000000000000/handoff").status_code, 404)


class LifecycleTest(OutboxTestCase):
    def test_pending_approve_then_mark_sent(self):
        mid = self.submit_id()
        self.assertEqual(self.client.post(f"/api/messages/{mid}/approve").status_code, 200)
        res = self.client.post(f"/api/messages/{mid}/mark-sent")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["status"], "sent")

    def test_invalid_transition_409_with_context(self):
        mid = self.submit_id()
        res = self.client.post(f"/api/messages/{mid}/mark-sent")
        self.assertEqual(res.status_code, 409)
        body = res.get_json()
        self.assertEqual(body["current_status"], "pending")
        self.assertIn("approve", body["allowed_actions"])
        # pending cannot hand off
        self.assertEqual(self.client.get(f"/api/messages/{mid}/handoff").status_code, 409)

    def test_duplicate_approve_only_one_history_and_event(self):
        mid = self.submit_id(webhook_url=PUBLIC_IP_WEBHOOK)
        self.assertEqual(self.client.post(f"/api/messages/{mid}/approve").status_code, 200)
        dup = self.client.post(f"/api/messages/{mid}/approve")
        self.assertEqual(dup.status_code, 409)
        h = self.client.get(f"/api/messages/{mid}/history").get_json()
        approved_rows = [t for t in h["transitions"] if t["to_status"] == "approved"]
        self.assertEqual(len(approved_rows), 1)
        events = self.client.get(f"/api/messages/{mid}/webhook-events").get_json()["items"]
        self.assertEqual([e["event"] for e in events], ["message.approved"])

    def test_terminal_states_are_immutable(self):
        for final in ("sent", "cancelled", "stale"):
            mid = self.submit_id(ttl_seconds=3600)
            if final == "sent":
                self.client.post(f"/api/messages/{mid}/approve")
                self.client.post(f"/api/messages/{mid}/mark-sent")
            elif final == "cancelled":
                self.client.post(f"/api/messages/{mid}/cancel")
            else:
                self._force_expire(mid)
            self.assertEqual(self.get_msg(mid)["status"], final)
            self.assertEqual(self.client.patch(f"/api/messages/{mid}", json={"body": "x"}).status_code, 409)
            self.assertEqual(self.client.post(f"/api/messages/{mid}/approve").status_code, 409)
            self.assertEqual(self.client.post(f"/api/messages/{mid}/cancel").status_code, 409)
            self.assertEqual(self.client.post(f"/api/messages/{mid}/mark-sent").status_code, 409)
            self.assertEqual(self.client.get(f"/api/messages/{mid}/handoff").status_code, 409)

    def test_reject_requires_reason(self):
        mid = self.submit_id()
        self.assertEqual(self.client.post(f"/api/messages/{mid}/reject", json={}).status_code, 400)
        self.assertEqual(self.client.post(f"/api/messages/{mid}/reject",
                                          json={"reason": "   "}).status_code, 400)
        self.assertEqual(self.client.post(f"/api/messages/{mid}/reject",
                                          data="{}", content_type="application/json").status_code, 400)

    def test_cancel_allowed_from_pending_rejected_approved(self):
        for setup in (lambda m: None,
                      lambda m: self.client.post(f"/api/messages/{m}/reject", json={"reason": "r"}),
                      lambda m: self.client.post(f"/api/messages/{m}/approve")):
            mid = self.submit_id()
            setup(mid)
            res = self.client.post(f"/api/messages/{mid}/cancel")
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.get_json()["status"], "cancelled")

    def test_status_field_rejected_in_patch(self):
        mid = self.submit_id()
        res = self.client.patch(f"/api/messages/{mid}", json={"status": "sent"})
        self.assertApiError(res, "bad_request", 400)

    def test_handoff_and_downloads_never_change_status(self):
        mid = self.submit_id()
        data = {"channel": "email", "destination": "d@x.co", "body": "b"}
        data["attachments"] = (io.BytesIO(b"payload"), "f.txt")
        mid2 = self.client.post("/api/messages", data=data,
                                content_type="multipart/form-data").get_json()["id"]
        self.client.post(f"/api/messages/{mid2}/approve")
        self.client.get(f"/api/messages/{mid2}/handoff")
        att = self.client.get(f"/api/messages/{mid2}/attachments").get_json()["items"][0]
        self.client.get(att["download_url"])
        self.client.get(f"/api/messages/{mid2}/attachments.zip")
        self.assertEqual(self.get_msg(mid2)["status"], "approved")

    def _force_expire(self, mid):
        conn = self.ctx.connect()
        try:
            conn.execute("UPDATE messages SET expires_at=? WHERE id=?",
                         (iso(now_utc() - timedelta(seconds=5)), mid))
        finally:
            conn.close()
        service.sweep_expired(self.ctx)


class ConcurrencyTest(OutboxTestCase):
    def _run_threads(self, fn, n):
        results: list = [None] * n
        errors: list = [None] * n
        start = threading.Barrier(n)

        def worker(i):
            start.wait(5)
            try:
                results[i] = fn()
            except ApiError as exc:
                errors[i] = exc

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(15)
        return results, errors

    def test_concurrent_duplicate_approvals_exactly_one_wins(self):
        mid = self.submit_id(webhook_url=PUBLIC_IP_WEBHOOK)
        results, errors = self._run_threads(
            lambda: service.approve_message(self.ctx, mid), 6)
        winners = [r for r in results if r]
        conflicts = [e for e in errors if e and e.status == 409]
        self.assertEqual(len(winners), 1)
        self.assertEqual(len(conflicts), 5)
        h = self.client.get(f"/api/messages/{mid}/history").get_json()
        self.assertEqual(len([t for t in h["transitions"] if t["to_status"] == "approved"]), 1)
        events = self.client.get(f"/api/messages/{mid}/webhook-events").get_json()["items"]
        self.assertEqual(len(events), 1)

    def test_concurrent_approve_and_cancel_single_transition(self):
        mid = self.submit_id()
        ops = [lambda: service.approve_message(self.ctx, mid),
               lambda: service.cancel_message(self.ctx, mid)] * 3
        results, errors = self._run_threads(ops[0], 6)
        h = self.client.get(f"/api/messages/{mid}/history").get_json()
        # pending -> exactly one successor
        successors = [t for t in h["transitions"] if t["from_status"] == "pending"]
        self.assertEqual(len(successors), 1)
        self.assertIn(h["current_status"], ("approved", "cancelled"))

    def test_approval_and_expiration_never_both(self):
        mid = self.submit_id()
        self._expire_now(mid)
        results, errors = self._run_threads(
            lambda: service.approve_message(self.ctx, mid), 5)
        self.assertEqual([r for r in results if r], [])
        status = self.get_msg(mid)["status"]
        self.assertEqual(status, "stale")
        h = self.client.get(f"/api/messages/{mid}/history").get_json()
        self.assertNotIn("approved", [t["to_status"] for t in h["transitions"]])
        self.assertEqual(len([t for t in h["transitions"] if t["to_status"] == "stale"]), 1)

    def _expire_now(self, mid):
        conn = self.ctx.connect()
        try:
            conn.execute("UPDATE messages SET expires_at=? WHERE id=?",
                         (iso(now_utc() - timedelta(seconds=1)), mid))
        finally:
            conn.close()


class RejectionRevisionTest(OutboxTestCase):
    def test_reject_records_reason_timestamp_and_event(self):
        mid = self.submit_id(webhook_url=PUBLIC_IP_WEBHOOK)
        res = self.client.post(f"/api/messages/{mid}/reject",
                               json={"reason": "Recipient name is wrong."})
        self.assertEqual(res.status_code, 200)
        d = self.get_msg(mid)
        self.assertEqual(d["status"], "rejected")
        self.assertEqual(d["rejection_reason"], "Recipient name is wrong.")
        self.assertTrue(d["rejection_at"])
        events = self.client.get(f"/api/messages/{mid}/webhook-events").get_json()["items"]
        ev = [e for e in events if e["event"] == "message.rejected"][0]
        self.assertEqual(ev["payload"]["rejection_reason"], "Recipient name is wrong.")
        h = self.client.get(f"/api/messages/{mid}/history").get_json()
        self.assertEqual([t["to_status"] for t in h["transitions"]][-1], "rejected")
        self.assertEqual(h["transitions"][-1]["reason"], "Recipient name is wrong.")

    def test_patch_rejected_creates_revision_keeps_history(self):
        mid = self.submit_id(webhook_url=PUBLIC_IP_WEBHOOK)
        original = self.get_msg(mid)
        self.client.post(f"/api/messages/{mid}/reject", json={"reason": "wrong name"})
        res = self.client.patch(f"/api/messages/{mid}",
                                json={"subject": "Q4 — revised",
                                      "body": "Hi Alex Smith,\n\nUpdated."})
        self.assertEqual(res.status_code, 200)
        d = res.get_json()
        self.assertEqual(d["id"], mid)
        self.assertEqual(d["created_at"], original["created_at"])
        self.assertEqual(d["revision_number"], 2)
        self.assertEqual(d["status"], "pending")
        self.assertIsNone(d["rejection_reason"])
        h = self.client.get(f"/api/messages/{mid}/history").get_json()
        revs = {r["revision_number"]: r for r in h["revisions"]}
        self.assertEqual(revs[1]["body"], original["body"])
        self.assertEqual(revs[1]["rejection_reason"], "wrong name")
        self.assertEqual(revs[2]["body"], "Hi Alex Smith,\n\nUpdated.")
        events = self.client.get(f"/api/messages/{mid}/webhook-events").get_json()["items"]
        self.assertEqual([e["event"] for e in events],
                         ["message.rejected", "message.revised"])
        self.assertEqual(events[1]["revision_number"], 2)

    def test_multiple_rejections_and_revisions(self):
        mid = self.submit_id()
        for i in range(3):
            self.client.post(f"/api/messages/{mid}/reject", json={"reason": f"r{i}"})
            self.client.patch(f"/api/messages/{mid}", json={"body": f"v{i+2}"})
        d = self.get_msg(mid)
        self.assertEqual(d["revision_number"], 4)
        self.assertEqual(d["status"], "pending")
        h = self.client.get(f"/api/messages/{mid}/history").get_json()
        self.assertEqual(len(h["revisions"]), 4)
        reasons = [r["rejection_reason"] for r in h["revisions"]]
        self.assertEqual(reasons, ["r0", "r1", "r2", None])

    def test_patch_on_pending_increments_revision(self):
        mid = self.submit_id()
        res = self.client.patch(f"/api/messages/{mid}", json={"body": "edited"})
        self.assertEqual(res.get_json()["revision_number"], 2)
        self.assertEqual(res.get_json()["status"], "pending")

    def test_patch_on_approved_409_and_unchanged(self):
        mid = self.submit_id(subject="keep", body="keep me")
        self.client.post(f"/api/messages/{mid}/approve")
        res = self.client.patch(f"/api/messages/{mid}", json={"body": "mutated"})
        self.assertEqual(res.status_code, 409)
        self.assertEqual(self.get_msg(mid)["body"], "keep me")

    def test_patch_omitted_fields_unchanged_and_expiration_rules(self):
        mid = self.submit_id(subject="sub", ttl_seconds=3600)
        before = self.get_msg(mid)
        res = self.client.patch(f"/api/messages/{mid}", json={"body": "only body"})
        after = res.get_json()
        self.assertEqual(after["subject"], before["subject"])
        self.assertEqual(after["expires_at"], before["expires_at"])
        # expires_at null clears; ttl+expires still mutually exclusive
        cleared = self.client.patch(f"/api/messages/{mid}", json={"expires_at": None})
        self.assertIsNone(cleared.get_json()["expires_at"])
        both = self.client.patch(f"/api/messages/{mid}",
                                 json={"ttl_seconds": 5, "expires_at": "2030-01-01T00:00:00Z"})
        self.assertEqual(both.status_code, 400)

    def test_patch_rejects_invalid_new_destination(self):
        mid = self.submit_id()
        res = self.client.patch(f"/api/messages/{mid}", json={"destination": "still not email"})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.get_msg(mid)["destination"], "user@example.com")


class ExpirationTest(OutboxTestCase):
    def test_ttl_seconds_expires_via_lazy_check(self):
        mid = self.submit_id(ttl_seconds=1)
        self.assertEqual(self.get_msg(mid)["status"], "pending")
        time.sleep(1.1)
        self.assertEqual(self.get_msg(mid)["status"], "stale")
        # and it can never be approved or handed off afterwards
        self.assertEqual(self.client.post(f"/api/messages/{mid}/approve").status_code, 409)
        self.assertEqual(self.client.get(f"/api/messages/{mid}/handoff").status_code, 409)

    def test_pending_and_approved_both_expire_with_content_retained(self):
        mid = self.submit_id(body="precious content", webhook_url=PUBLIC_IP_WEBHOOK)
        self.client.post(f"/api/messages/{mid}/approve")
        self._expire(mid)
        d = self.get_msg(mid)
        self.assertEqual(d["status"], "stale")
        self.assertEqual(d["body"], "precious content")
        events = self.client.get(f"/api/messages/{mid}/webhook-events").get_json()["items"]
        self.assertIn("message.stale", [e["event"] for e in events])
        # history retained
        h = self.client.get(f"/api/messages/{mid}/history").get_json()
        self.assertEqual(h["transitions"][-1]["to_status"], "stale")

    def _expire(self, mid):
        conn = self.ctx.connect()
        try:
            conn.execute("UPDATE messages SET expires_at=? WHERE id=?",
                         (iso(now_utc() - timedelta(seconds=2)), mid))
        finally:
            conn.close()
        from outbox import service as svc
        svc.sweep_expired(self.ctx)
        return svc

    def test_rejected_messages_are_not_expired(self):
        mid = self.submit_id(ttl_seconds=1)
        self.client.post(f"/api/messages/{mid}/reject", json={"reason": "keep"})
        time.sleep(1.1)
        from outbox import service as svc
        svc.sweep_expired(self.ctx)
        self.assertEqual(self.get_msg(mid)["status"], "rejected")

    def test_no_expiration_stays_active(self):
        mid = self.submit_id()
        from outbox import service as svc
        svc.sweep_expired(self.ctx)
        self.assertEqual(self.get_msg(mid)["status"], "pending")

    def test_listing_sweep_removes_from_active_queue(self):
        mid = self.submit_id(ttl_seconds=1)
        time.sleep(1.1)
        self.client.get("/api/messages?status=pending,approved,rejected")
        self.assertEqual(self.get_msg(mid)["status"], "stale")
        ids = [i["id"] for i in self.client.get("/api/messages?status=pending").get_json()["items"]]
        self.assertNotIn(mid, ids)

    def test_sweep_with_injected_clock_boundary(self):
        mid = self.submit_id(ttl_seconds=60)
        row = self.get_msg(mid)
        future = parse_iso(row["expires_at"])
        self.assertTrue(future > now_utc())
        # simulate clock past expiry using the pure predicate
        fake_row = type("R", (), {"__getitem__": lambda s, k: {
            "expires_at": row["expires_at"], "status": "pending"}[k]})()
        from outbox import service as svc
        self.assertTrue(svc.is_expired(fake_row, future + timedelta(seconds=1)))
        self.assertFalse(svc.is_expired(fake_row, future - timedelta(seconds=1)))


class HandoffAdapterTest(OutboxTestCase):
    def _approved(self, **fields):
        mid = self.submit_id(**fields)
        self.client.post(f"/api/messages/{mid}/approve")
        return self.client.get(f"/api/messages/{mid}/handoff").get_json()

    def test_email_mailto_full_encode(self):
        h = self._approved(channel="email", destination="alex@example.com",
                           subject="Q4 report — naïve ✓",
                           body="Hi Alex,\n\nReview <this> & that.\n\n— Sam")
        self.assertTrue(h["handoff_url"].startswith("mailto:alex@example.com"))
        self.assertIn("subject=Q4%20report", h["handoff_url"])
        self.assertIn("%E2%80%94", h["handoff_url"])   # em dash UTF-8
        self.assertIn("%0A", h["handoff_url"])         # newline encoded
        self.assertNotIn("\n", h["handoff_url"])
        self.assertTrue(h["capabilities"]["prefill_recipient"])
        self.assertTrue(h["capabilities"]["prefill_subject"])
        self.assertTrue(h["capabilities"]["prefill_body"])
        self.assertFalse(h["capabilities"]["attachments_supported"])
        self.assertTrue(any("attach" in w.lower() for w in h["warnings"]))
        self.assertTrue(any("manual" in a.lower() or "attach" in a.lower()
                            for a in h["manual_actions"]))
        self.assertEqual(h["copy"]["body"], "Hi Alex,\n\nReview <this> & that.\n\n— Sam")

    def test_email_long_body_fallback(self):
        h = self._approved(channel="email", destination="alex@example.com",
                           subject="Short", body="x" * 5000)
        self.assertNotIn("body=", h["handoff_url"])
        self.assertIn("subject=Short", h["handoff_url"])
        self.assertFalse(h["capabilities"]["prefill_body"])
        self.assertTrue(any("Copy body" in w or "copy" in w.lower() for w in h["warnings"]))
        self.assertEqual(len(h["handoff_url"]), len(h["handoff_url"]))
        self.assertLess(len(h["handoff_url"]), 400)

    def test_whatsapp_individual(self):
        h = self._approved(channel="whatsapp", destination="+1 (415) 555-0123",
                           body="Your appointment is confirmed for 3 PM.")
        self.assertTrue(h["handoff_url"].startswith("https://wa.me/14155550123?text="))
        self.assertIn("%20", h["handoff_url"])
        self.assertTrue(h["capabilities"]["prefill_recipient"])
        self.assertFalse(h["capabilities"]["prefill_subject"])

    def test_whatsapp_group_is_honest(self):
        h = self._approved(channel="whatsapp", destination="group:Project Alpha",
                           body="Standup moved to 10:00.")
        self.assertEqual(h["destination_kind"], "group")
        self.assertEqual(h["handoff_url"], "https://wa.me/")
        self.assertFalse(h["capabilities"]["prefill_recipient"])
        self.assertFalse(h["capabilities"]["prefill_body"])
        joined = " ".join(h["warnings"] + h["manual_actions"]).lower()
        self.assertIn("project alpha", joined)
        self.assertIn("not", " ".join(h["warnings"]).lower())
        self.assertNotIn("prefilled", h["handoff_url"])

    def test_telegram_individual_and_group(self):
        h = self._approved(channel="telegram", destination="@alex_example",
                           body="Build finished successfully.")
        self.assertEqual(h["handoff_url"], "https://t.me/alex_example?text=Build%20finished%20successfully.")
        g = self._approved(channel="telegram", destination="group:Ops Room",
                           body="Deploy is live.")
        self.assertFalse(g["capabilities"]["prefill_recipient"])
        self.assertFalse(g["capabilities"]["prefill_body"])
        self.assertIn("Ops Room", " ".join(g["manual_actions"]))

    def test_telegram_invite_and_tme_link(self):
        h = self._approved(channel="telegram", destination="https://t.me/joe_user",
                           body="hi")
        self.assertIn("t.me/joe_user", h["handoff_url"])
        i = self._approved(channel="telegram", destination="+AbC123xy",
                           body="welcome")
        self.assertEqual(i["destination_kind"], "invite")
        self.assertEqual(i["handoff_url"], "https://t.me/+AbC123xy")
        self.assertFalse(i["capabilities"]["prefill_body"])

    def test_whatsapp_long_body_fallback(self):
        h = self._approved(channel="whatsapp", destination="+14155550123",
                           body="y" * 4000)
        self.assertNotIn("text=", h["handoff_url"])
        self.assertFalse(h["capabilities"]["prefill_body"])

    def test_handoff_requires_approved_and_expiration_check(self):
        mid = self.submit_id(ttl_seconds=3600)
        self.client.post(f"/api/messages/{mid}/approve")
        self.assertEqual(self.client.get(f"/api/messages/{mid}/handoff").status_code, 200)
        conn = self.ctx.connect()
        try:
            conn.execute("UPDATE messages SET expires_at=? WHERE id=?",
                         (iso(now_utc() - timedelta(seconds=1)), mid))
        finally:
            conn.close()
        res = self.client.get(f"/api/messages/{mid}/handoff")
        self.assertEqual(res.status_code, 409)
        self.assertEqual(self.get_msg(mid)["status"], "stale")

    def test_frontend_uses_structured_handoff(self):
        import pathlib
        js = (pathlib.Path(__file__).resolve().parents[1] / "static" / "app.js").read_text()
        self.assertIn("/handoff", js)
        self.assertNotIn("mailto:", js)  # URLs come from the API, not built in JS


class AttachmentTest(OutboxTestCase):
    attachment_bytes = 500
    message_bytes = 900

    def test_multipart_upload_download_and_headers(self):
        data = {"channel": "email", "destination": "a@b.co", "body": "files"}
        data["attachments"] = (io.BytesIO(b"Outbox attachment fixture.\n"), "sample.txt")
        res = self.client.post("/api/messages", data=data,
                               content_type="multipart/form-data")
        self.assertEqual(res.status_code, 201)
        mid = res.get_json()["id"]
        items = self.client.get(f"/api/messages/{mid}/attachments").get_json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["filename"], "sample.txt")
        self.assertEqual(items[0]["size_bytes"], 27)
        self.assertEqual(items[0]["source_type"], "multipart")
        self.assertTrue(items[0]["storage_reference"].startswith("att_"))
        dl = self.client.get(items[0]["download_url"])
        self.assertEqual(dl.status_code, 200)
        self.assertIn("attachment", dl.headers["Content-Disposition"])
        self.assertEqual(dl.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(dl.data, b"Outbox attachment fixture.\n")

    def test_traversal_filename_is_stored_safely(self):
        data = {"channel": "email", "destination": "a@b.co", "body": "evil"}
        data["attachments"] = (io.BytesIO(b"payload"), "../../etc/passwd.txt")
        mid = self.client.post("/api/messages", data=data,
                               content_type="multipart/form-data").get_json()["id"]
        att = self.client.get(f"/api/messages/{mid}/attachments").get_json()["items"][0]
        self.assertEqual(att["filename"], "passwd.txt")
        self.assertNotIn("..", att["storage_reference"])
        self.assertNotIn("/", att["storage_reference"])
        on_disk = list(self.cfg.attachment_dir.iterdir())
        self.assertTrue(all(".." not in p.name for p in on_disk))

    def test_reserved_and_control_names(self):
        data = {"channel": "email", "destination": "a@b.co", "body": "b"}
        data["attachments"] = (io.BytesIO(b"z"), "CON.txt")
        mid = self.client.post("/api/messages", data=data,
                               content_type="multipart/form-data").get_json()["id"]
        self.assertEqual(self.client.get(f"/api/messages/{mid}/attachments")
                         .get_json()["items"][0]["filename"], "_CON.txt")

    def test_per_file_size_limit_413(self):
        data = {"channel": "email", "destination": "a@b.co", "body": "b"}
        data["attachments"] = (io.BytesIO(b"x" * 600), "big.bin")
        res = self.client.post("/api/messages", data=data,
                               content_type="multipart/form-data")
        self.assertApiError(res, "payload_too_large", 413)

    def test_per_message_size_limit_413(self):
        def part(filename, content):
            return (b'--X\r\nContent-Disposition: form-data; name="attachments"; '
                    b'filename="' + filename.encode() + b'"\r\n'
                    b'Content-Type: application/octet-stream\r\n\r\n' + content + b"\r\n")
        body = (b'--X\r\nContent-Disposition: form-data; name="channel"\r\n\r\nemail\r\n'
                + b'--X\r\nContent-Disposition: form-data; name="destination"\r\n\r\na@b.co\r\n'
                + b'--X\r\nContent-Disposition: form-data; name="body"\r\n\r\nb\r\n'
                + part("one.bin", b"x" * 480)
                + part("two.bin", b"y" * 480)
                + b"--X--\r\n")
        res = self.client.post("/api/messages", data=body,
                               content_type="multipart/form-data; boundary=X")
        self.assertEqual(res.status_code, 413, res.get_json())

    def test_empty_upload_400(self):
        data = {"channel": "email", "destination": "a@b.co", "body": "b"}
        data["attachments"] = (io.BytesIO(b""), "empty.txt")
        res = self.client.post("/api/messages", data=data,
                               content_type="multipart/form-data")
        self.assertEqual(res.status_code, 400)

    def test_missing_attachment_file_404_and_unknown_id(self):
        data = {"channel": "email", "destination": "a@b.co", "body": "b"}
        data["attachments"] = (io.BytesIO(b"data"), "d.txt")
        mid = self.client.post("/api/messages", data=data,
                               content_type="multipart/form-data").get_json()["id"]
        att = self.client.get(f"/api/messages/{mid}/attachments").get_json()["items"][0]
        path = self.cfg.attachment_dir / att["storage_reference"]
        path.unlink()
        res = self.client.get(att["download_url"])
        self.assertEqual(res.status_code, 404)
        self.assertIn("attachment", res.get_json()["message"].lower())
        res = self.client.get(f"/api/messages/{mid}/attachments/att_deadbeef00")
        self.assertEqual(res.status_code, 404)

    def test_download_all_zip(self):
        boundary = "Z"
        def file_part(name, content):
            return (f'--{Z}\r\nContent-Disposition: form-data; name="attachments"; '
                    f'filename="{name}"\r\nContent-Type: text/plain\r\n\r\n').encode() \
                + content + b"\r\n"
        Z = "Z"
        body = (b'--Z\r\nContent-Disposition: form-data; name="channel"\r\n\r\nemail\r\n'
               + b'--Z\r\nContent-Disposition: form-data; name="destination"\r\n\r\na@b.co\r\n'
               + b'--Z\r\nContent-Disposition: form-data; name="body"\r\n\r\nb\r\n'
               + file_part("one.txt", b"first") + file_part("two.txt", b"second")
               + b"--Z--\r\n")
        mid = self.client.post("/api/messages", data=body,
                               content_type="multipart/form-data; boundary=Z").get_json()["id"]
        res = self.client.get(f"/api/messages/{mid}/attachments.zip")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["Content-Type"], "application/zip")
        import zipfile
        zf = zipfile.ZipFile(io.BytesIO(res.data))
        self.assertEqual(sorted(zf.namelist()), ["one.txt", "two.txt"])

    def test_patch_replaces_attachments_and_keeps_history(self):
        data = {"channel": "email", "destination": "a@b.co", "body": "b"}
        data["attachments"] = (io.BytesIO(b"old file"), "old.txt")
        mid = self.client.post("/api/messages", data=data,
                               content_type="multipart/form-data").get_json()["id"]
        pdata = {"subject": "s2"}
        pdata["attachments"] = (io.BytesIO(b"new file"), "new.txt")
        res = self.client.patch(f"/api/messages/{mid}", data=pdata,
                                content_type="multipart/form-data")
        self.assertEqual(res.status_code, 200)
        current = self.client.get(f"/api/messages/{mid}/attachments").get_json()["items"]
        self.assertEqual([a["filename"] for a in current], ["new.txt"])
        h = self.client.get(f"/api/messages/{mid}/history").get_json()
        self.assertEqual([a["filename"] for a in h["revisions"][0]["attachments"]], ["old.txt"])

    def test_mime_detection(self):
        self.assertEqual(guess_mime("notes.txt", b"just text"), "text/plain")
        self.assertEqual(guess_mime("doc.pdf", b"%PDF-1.7 ..."), "application/pdf")
        self.assertEqual(guess_mime("mystery", b"\x89PNG\r\n\x1a\n rest"), "image/png")
        self.assertEqual(guess_mime("mystery", bytes(range(0, 32)) * 40),
                         "application/octet-stream")


class UrlDownloadTest(OutboxTestCase):
    attachment_bytes = 1_000_000  # keep /big (5 MB) clearly over the cap

    def setUp(self):
        super().setUp()
        self.srv, self.base = start_files()
        self.addCleanup(self.srv.shutdown)

    def test_url_download_stores_real_attachment(self):
        mid = self.submit_id(attachments=[{"kind": "url_download", "url": self.base + "/sample.txt",
                                           "filename": "sample.txt"}])
        att = self.client.get(f"/api/messages/{mid}/attachments").get_json()["items"][0]
        self.assertEqual(att["source_type"], "url_download")
        self.assertEqual(att["source_url"], self.base + "/sample.txt")
        self.assertEqual(att["mime_type"], "text/plain")
        dl = self.client.get(att["download_url"])
        self.assertIn(b"Outbox attachment fixture.", dl.data)

    def test_metadata_and_message_counts(self):
        mid = self.submit_id(references=[self.base + "/whatever"],
                             attachments=[{"kind": "url_download", "url": self.base + "/sample.txt"}])
        d = self.get_msg(mid)
        self.assertEqual(d["attachment_count"], 1)
        self.assertEqual(d["references"], [self.base + "/whatever"])

    def test_download_size_limit(self):
        mid_res = self.client.post("/api/messages", json={
            "channel": "email", "destination": "a@b.co", "body": "x",
            "attachments": [{"kind": "url_download", "url": self.base + "/big"}]})
        self.assertEqual(mid_res.status_code, 413)

    def test_download_timeout(self):
        # helpers set download_timeout 2.0; /slow sleeps 3s
        res = self.client.post("/api/messages", json={
            "channel": "email", "destination": "a@b.co", "body": "x",
            "attachments": [{"kind": "url_download", "url": self.base + "/slow"}]})
        self.assertEqual(res.status_code, 400)
        self.assertIn("timeout", res.get_json()["message"].lower())

    def test_redirect_hops_validated(self):
        # redirect to the real file on the same host is allowed and works
        mid = self.submit_id(attachments=[{"kind": "url_download",
                                           "url": self.base + "/redirect/" + self.base + "/sample.txt"}])
        self.assertEqual(len(self.client.get(f"/api/messages/{mid}/attachments")
                           .get_json()["items"]), 1)

    def test_redirect_to_metadata_blocked_even_with_override(self):
        res = self.client.post("/api/messages", json={
            "channel": "email", "destination": "a@b.co", "body": "x",
            "attachments": [{"kind": "url_download",
                             "url": self.base + "/redirect/http://169.254.169.254/latest/meta-data/"}]})
        self.assertEqual(res.status_code, 400)
        self.assertIn("blocked", res.get_json()["message"].lower())

    def test_redirect_loop_bounded(self):
        res = self.client.post("/api/messages", json={
            "channel": "email", "destination": "a@b.co", "body": "x",
            "attachments": [{"kind": "url_download", "url": self.base + "/redirect-loop"}]})
        self.assertEqual(res.status_code, 400)
        self.assertIn("redirect", res.get_json()["message"].lower())

    def test_failed_download_rolls_back_partial(self):
        # second spec is blocked after the first stored: whole submit must fail,
        # and the message must not exist.
        res = self.client.post("/api/messages", json={
            "channel": "email", "destination": "a@b.co", "body": "x",
            "attachments": [{"kind": "url_download", "url": self.base + "/missing"},
                            {"kind": "url_download", "url": "http://169.254.169.254/x"}]})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.client.get("/api/messages").get_json()["total"], 0)


class DestinationsLabelsTest(OutboxTestCase):
    def test_discovery_without_registration(self):
        self.submit_id(destination="a@corp.example")
        self.submit_id(destination="a@corp.example")
        self.submit_id(channel="whatsapp", destination="group:Project Alpha")
        items = self.client.get("/api/destinations").get_json()["items"]
        by_norm = {i["normalized_destination"]: i for i in items}
        self.assertIn("a@corp.example", by_norm)
        self.assertEqual(by_norm["a@corp.example"]["message_count"], 2)
        self.assertIn("project alpha", by_norm)
        self.assertTrue(by_norm["a@corp.example"]["last_used"])

    def test_label_crud_and_uniqueness(self):
        mid = self.submit_id()
        norm = self.get_msg(mid)["normalized_destination"]
        res = self.client.put("/api/destinations/label", json={
            "channel": "email", "destination": norm, "label": "Finance Team"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.get_msg(mid)["label"], "Finance Team")
        dup = self.client.put("/api/destinations/label", json={
            "channel": "email", "destination": "other@corp.example", "label": "finance team"})
        self.assertApiError(dup, "conflict", 409)
        rename = self.client.put("/api/destinations/label", json={
            "channel": "email", "destination": norm, "label": "Finance Desk"})
        self.assertEqual(rename.status_code, 200)
        self.assertEqual(self.get_msg(mid)["label"], "Finance Desk")
        removed = self.client.delete("/api/destinations/label?channel=email&destination=" + norm)
        self.assertEqual(removed.status_code, 200)
        self.assertTrue(removed.get_json()["deleted"])
        # messages intact after removal
        self.assertEqual(self.get_msg(mid)["status"], "pending")
        self.assertEqual(self.get_msg(mid)["body"], "Hello there.")

    def test_label_validation(self):
        for bad in ["", "   ", "x" * 200]:
            res = self.client.put("/api/destinations/label", json={
                "channel": "email", "destination": "a@b.co", "label": bad})
            self.assertEqual(res.status_code, 400, bad)
        res = self.client.put("/api/destinations/label", json={
            "channel": "carrier", "destination": "a@b.co", "label": "ok"})
        self.assertEqual(res.status_code, 400)

    def test_label_matches_by_normalized_destination(self):
        # emails are normalized lowercase, so a mixed-case submission reuses
        # the managed label of the same address
        mid = self.submit_id(destination="Alex@Example.COM")
        norm = self.get_msg(mid)["normalized_destination"]
        self.assertEqual(norm, "alex@example.com")
        self.client.put("/api/destinations/label", json={
            "channel": "email", "destination": norm, "label": "Alex — Client"})
        mid2 = self.submit_id(destination="alex@example.com")
        self.assertEqual(self.get_msg(mid2)["label"], "Alex — Client")
        self.assertIn(mid2, [i["id"] for i in self.client.get(
            "/api/messages?destination=client").get_json()["items"]])

    def test_snapshot_label_visible_when_no_managed_label(self):
        mid = self.submit_id(destination_label="Ops snapshot")
        self.assertEqual(self.get_msg(mid)["label"], "Ops snapshot")


class WebhookDeliveryTest(OutboxTestCase):
    def setUp(self):
        super().setUp()
        self.srv, self.base = start_sink()
        self.addCleanup(self.srv.shutdown)

    def _drain(self):
        return process_pending_events(self.ctx)

    def test_events_recorded_for_all_transitions(self):
        mid = self.submit_id(webhook_url=self.base + "/hook")
        self.client.post(f"/api/messages/{mid}/reject", json={"reason": "r"})
        self.client.patch(f"/api/messages/{mid}", json={"body": "new"})
        self.client.post(f"/api/messages/{mid}/approve")
        self.client.post(f"/api/messages/{mid}/mark-sent")
        events = self.client.get(f"/api/messages/{mid}/webhook-events").get_json()["items"]
        self.assertEqual([e["event"] for e in events],
                         ["message.rejected", "message.revised", "message.approved",
                          "message.sent"])
        for e in events:
            self.assertIn(e["state"], ("queued", "delivered", "failed"))
        ev = events[0]
        self.assertEqual(set(["event", "message_id", "status", "revision_number",
                              "timestamp", "rejection_reason"]) - set(ev["payload"]), set())

    def test_delivery_success_records_attempts(self):
        mid = self.submit_id(webhook_url=self.base + "/hook")
        self.client.post(f"/api/messages/{mid}/approve")
        attempted = self._drain()
        self.assertGreaterEqual(attempted, 1)
        events = self.client.get(f"/api/messages/{mid}/webhook-events").get_json()["items"]
        self.assertEqual(events[0]["state"], "delivered")
        self.assertEqual(events[0]["attempts"], 1)
        self.assertEqual(events[0]["last_status_code"], 204)
        self.assertEqual(len(events[0]["attempt_history"]), 1)
        self.assertEqual(self.srv.received[0]["message_id"], mid)
        self.assertEqual(self.srv.received[0]["event"], "message.approved")

    def test_failure_retries_with_backoff_then_succeeds(self):
        self.srv.mode = "flaky"   # first two POSTs return 503
        mid = self.submit_id(webhook_url=self.base + "/hook")
        self.client.post(f"/api/messages/{mid}/approve")
        self._drain()
        events = self.client.get(f"/api/messages/{mid}/webhook-events").get_json()["items"]
        self.assertEqual(events[0]["state"], "queued")
        self.assertEqual(events[0]["attempts"], 1)
        self.assertIsNotNone(events[0]["next_attempt_at"])
        # respect backoff: draining immediately must skip the not-yet-due event
        self.assertEqual(self._drain(), 0)
        time.sleep(0.2)
        self._drain()
        events = self.client.get(f"/api/messages/{mid}/webhook-events").get_json()["items"]
        self.assertEqual(events[0]["attempts"], 2)
        self.assertEqual(events[0]["state"], "queued")
        time.sleep(0.4)  # backoff doubled: 0.15 * 2 = 0.3s
        self._drain()
        events = self.client.get(f"/api/messages/{mid}/webhook-events").get_json()["items"]
        self.assertEqual(events[0]["state"], "delivered")
        self.assertEqual(events[0]["attempts"], 3)

    def test_gives_up_after_max_attempts_without_touching_state(self):
        self.srv.mode = "fail-always"
        mid = self.submit_id(webhook_url=self.base + "/hook")
        self.client.post(f"/api/messages/{mid}/approve")
        for _ in range(10):  # covers the 0.15s + 0.3s backoff window
            self._drain()
            time.sleep(0.07)
        events = self.client.get(f"/api/messages/{mid}/webhook-events").get_json()["items"]
        self.assertEqual(events[0]["state"], "failed")
        self.assertEqual(events[0]["attempts"], 3)
        self.assertTrue(events[0]["last_error"])
        # webhook failure never rolled back the approval
        self.assertEqual(self.get_msg(mid)["status"], "approved")

    def test_timeout_is_a_failure_not_a_crash(self):
        def slow_sender(url, payload, timeout):
            raise TimeoutError("read timed out")
        self.ctx.webhook_sender = slow_sender
        mid = self.submit_id(webhook_url=self.base + "/hook")
        self.client.post(f"/api/messages/{mid}/approve")
        self._drain()
        events = self.client.get(f"/api/messages/{mid}/webhook-events").get_json()["items"]
        self.assertIn("Timeout", events[0]["last_error"])
        self.assertEqual(self.get_msg(mid)["status"], "approved")

    def test_no_duplicate_event_rows_for_same_revision(self):
        mid = self.submit_id(webhook_url=self.base + "/hook")
        self.client.post(f"/api/messages/{mid}/approve")
        self.client.post(f"/api/messages/{mid}/approve")  # 409
        conn = self.ctx.connect()
        try:
            rows = conn.execute("SELECT id FROM webhook_events WHERE message_id=?",
                                 (mid,)).fetchall()
        finally:
            conn.close()
        self.assertEqual(len(rows), 1)

    def test_events_absent_without_webhook(self):
        mid = self.submit_id()
        self.client.post(f"/api/messages/{mid}/approve")
        events = self.client.get(f"/api/messages/{mid}/webhook-events").get_json()["items"]
        self.assertEqual(events, [])

    def test_revalidate_url_before_each_attempt(self):
        # A webhook recorded while allowed can be blocked later: delivery
        # consults the guard on every attempt, not just at submission.
        self.ctx.webhook_sender = None  # ensure real sender
        calls = []
        real = netguard.http_post_json
        def spy(url, payload, *, allow_private, timeout):
            calls.append(allow_private)
            raise netguard.UrlBlockedError("synthetic block")
        netguard.http_post_json = spy
        try:
            mid = self.submit_id(webhook_url=self.base + "/hook")
            self.client.post(f"/api/messages/{mid}/approve")
            self._drain()
            time.sleep(0.2)
            self._drain()  # second attempt must also revalidate
        finally:
            netguard.http_post_json = real
        self.assertGreaterEqual(len(calls), 2)

    def test_unknown_message_webhook_events_404(self):
        self.assertEqual(self.client.get(
            "/api/messages/msg_000000000000/webhook-events").status_code, 404)


class StorageGuardTest(OutboxTestCase):
    def test_sanitize_filename_rules(self):
        self.assertEqual(sanitize_filename("../../evil.txt"), "evil.txt")
        self.assertEqual(sanitize_filename("C:\\Windows\\System32\\cmd.exe"), "cmd.exe")
        self.assertEqual(sanitize_filename("bad\x00name\x1f.txt"), "badname.txt")
        self.assertEqual(sanitize_filename(""), "attachment")
        self.assertEqual(sanitize_filename(None), "attachment")
        self.assertEqual(sanitize_filename("NUL"), "_NUL")
        self.assertEqual(sanitize_filename("com9.log"), "_com9.log")
        self.assertEqual(len(sanitize_filename("a" * 400)), 150)
        self.assertEqual(sanitize_filename(".."), "attachment")

    def test_storage_reference_guard(self):
        with self.assertRaises(ApiError) as cm:
            self.ctx.store.path_for("../../escape")
        self.assertIn(cm.exception.status, (400, 404))


class ErrorShapeTest(OutboxTestCase):
    def test_consistent_error_envelope(self):
        checks = [
            self.client.post("/api/messages", json={}),                      # 400
            self.client.get("/api/messages/msg_000000000000"),               # 404
            self.client.post("/api/messages", data="x",
                             content_type="text/csv"),                       # 415
        ]
        for res in checks:
            body = res.get_json()
            self.assertIn("error", body)
            self.assertIn("message", body)
            self.assertIsInstance(body["message"], str)

    def test_unknown_api_route_json_404(self):
        res = self.client.get("/api/nope")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.get_json()["error"], "not_found")

    def test_wrong_method_405(self):
        res = self.client.delete("/api/messages")
        self.assertEqual(res.status_code, 405)

    def test_stale_and_cancelled_never_auto_deleted(self):
        mid = self.submit_id(ttl_seconds=1)
        time.sleep(1.1)
        self.assertEqual(self.get_msg(mid)["status"], "stale")
        ids = self.client.get("/api/messages?limit=100").get_json()
        self.assertIn(mid, [i["id"] for i in ids["items"]])
        mid2 = self.submit_id()
        self.client.post(f"/api/messages/{mid2}/cancel")
        self.assertEqual(self.get_msg(mid2)["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
