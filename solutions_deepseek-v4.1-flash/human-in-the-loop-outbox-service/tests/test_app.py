"""End-to-end tests for the human-in-the-loop outbox service.

Run from the project root:
    python3 -m unittest discover -s tests -v

All network fixtures are loopback-only. Webhook delivery is normally mocked
through the dispatcher's injectable send_once callable; a couple of tests use a
local HTTP fixture to verify real delivery and timeout handling.
"""

from __future__ import annotations

import io
import json
import re
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from outbox.api import create_app
from outbox.storage import sanitize_filename

STATIC_DIR = PROJECT_ROOT / "static"
OPENAPI_PATH = PROJECT_ROOT / "openapi.json"
MONO_TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


class FixtureHandler(BaseHTTPRequestHandler):
    posts: list[dict] = []

    def log_message(self, *args):  # noqa: D401
        pass

    def _send(self, status: int, body: bytes = b"", content_type: str = "application/octet-stream", extra=None):
        self.send_response(status)
        if content_type:
            self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b""
        if self.path == "/slow":
            time.sleep(0.5)
            self._send(204)
            return
        if self.path == "/fail":
            self._send(500, b"nope", "text/plain")
            return
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else None
        except ValueError:
            payload = raw.decode("utf-8", "replace")
        FixtureHandler.posts.append({"path": self.path, "payload": payload, "headers": dict(self.headers)})
        self._send(204)

    def do_GET(self):
        if self.path == "/redirect":
            self._send(302, b"", "text/plain", {"Location": "/sample.txt"})
            return
        if self.path == "/loop-redirect":
            self._send(302, b"", "text/plain", {"Location": "/loop-redirect"})
            return
        if self.path == "/sample.txt":
            self._send(200, b"fixture download\n", "text/plain; charset=utf-8")
            return
        if self.path == "/image.png":
            self._send(200, b"\x89PNG\r\n\x1a\nfakepng", "image/png")
            return
        if self.path == "/badmime":
            self._send(200, b"bad mime body", "definitely not a mime type")
            return
        if self.path == "/big":
            self._send(200, b"x" * 4096, "application/octet-stream")
            return
        self._send(404, b"not found", "text/plain")


class OutboxTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        cls.server.daemon_threads = True
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=5)

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory(prefix="outbox-test-")
        self.addCleanup(self.tempdir.cleanup)
        FixtureHandler.posts = []
        self.app = self.make_app()
        self.client = self.app.test_client()
        self.dispatcher = self.app.extensions["outbox"]["dispatcher"]
        self.sent: list[tuple[str, dict]] = []
        self.webhook_mode = "success"
        self.dispatcher.send_once = self._fake_webhook

    def make_app(self, **overrides):
        settings = {
            "data_dir": str(Path(self.tempdir.name) / "data"),
            "attachment_dir": str(Path(self.tempdir.name) / "data" / "attachments"),
            "static_dir": str(STATIC_DIR),
            "openapi_path": str(OPENAPI_PATH),
            "start_workers": False,
            "webhook_async": False,
            "webhook_backoff_base_seconds": 0,
            "webhook_max_attempts": 3,
            "allow_private_urls": False,
        }
        settings.update(overrides)
        return create_app(settings, base_dir=self.tempdir.name)

    def _fake_webhook(self, url, payload):
        self.sent.append((url, payload))
        if self.webhook_mode == "success":
            return True, 204, None, ""
        if self.webhook_mode == "timeout":
            return False, None, "timed out", None
        return False, 500, "HTTP 500", "error body"

    def submit(self, **fields):
        payload = {"channel": "email", "destination": "alex@example.com", "body": "Hello there"}
        payload.update(fields)
        return self.client.post("/api/messages", json=payload)

    def submit_ok(self, **fields):
        response = self.submit(**fields)
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.get_json()

    def approve(self, msg_id):
        return self.client.post(f"/api/messages/{msg_id}/approve")

    def reject(self, msg_id, reason="Wrong name"):
        return self.client.post(f"/api/messages/{msg_id}/reject", json={"reason": reason})

    def db(self):
        return self.app.extensions["outbox"]["database"].connect()


class SystemEndpointTests(OutboxTestBase):
    def test_health_info_docs_and_openapi(self):
        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.get_json()["status"], "ok")
        info = self.client.get("/api/info").get_json()
        self.assertEqual(info["author"], "DeepSeek V4.1 Flash")
        self.assertEqual(info["built_at"], "2026-11-07T00:09:15.580Z")
        config = info["config"]
        for key in (
            "data_dir",
            "attachment_dir",
            "max_attachment_bytes",
            "max_message_attachment_bytes",
            "expiration_interval_seconds",
            "webhook_timeout_seconds",
            "webhook_max_attempts",
            "webhook_backoff_base_seconds",
            "download_timeout_seconds",
            "max_redirects",
            "allow_private_urls",
            "port",
        ):
            self.assertIn(key, config)
        self.assertFalse(config["allow_private_urls"])

        spec_response = self.client.get("/openapi.json")
        self.assertEqual(spec_response.status_code, 200)
        spec = spec_response.get_json()
        self.assertTrue(spec["openapi"].startswith("3."))
        required_paths = {
            "/api/messages",
            "/api/messages/{id}",
            "/api/messages/{id}/approve",
            "/api/messages/{id}/reject",
            "/api/messages/{id}/cancel",
            "/api/messages/{id}/mark-sent",
            "/api/messages/{id}/history",
            "/api/messages/{id}/handoff",
            "/api/messages/{id}/attachments",
            "/api/messages/{id}/attachments/{attachment_id}",
            "/api/messages/{id}/webhook-events",
            "/api/destinations",
            "/api/destinations/label",
            "/api/health",
            "/api/info",
            "/api/docs",
            "/openapi.json",
        }
        self.assertTrue(required_paths.issubset(set(spec["paths"])))
        self.assertIn("Message", spec["components"]["schemas"])
        self.assertIn("Error", spec["components"]["schemas"])

        docs = self.client.get("/api/docs")
        self.assertEqual(docs.status_code, 200)
        self.assertIn("POST", docs.get_data(as_text=True))
        self.assertIn("DeepSeek V4.1 Flash", docs.get_data(as_text=True))

    def test_spa_served_with_signoff(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        text = response.get_data(as_text=True)
        self.assertIn("DeepSeek V4.1 Flash", text)
        self.assertIn("Built", text)
        self.assertIn("prefers-reduced-motion", text)
        self.assertIn("Mark as sent", text)

    def test_app_py_header_has_signoff(self):
        text = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("Built 2026-11-07 00:09 UTC by DeepSeek V4.1 Flash", text)

    def test_unknown_api_route_is_json_404(self):
        response = self.client.get("/api/nope")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"]["code"], "http_error")


class SubmissionTests(OutboxTestBase):
    def test_json_submission_minimal(self):
        response = self.submit()
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertRegex(data["id"], r"^msg_[a-f0-9]{12}$")
        self.assertEqual(data["status"], "pending")
        self.assertEqual(data["revision_number"], 1)
        self.assertTrue(MONO_TS.match(data["created_at"]))
        self.assertTrue(MONO_TS.match(data["updated_at"]))
        self.assertEqual(data["created_at"], data["updated_at"])
        self.assertEqual(response.headers["Location"], f"/api/messages/{data['id']}")

    def test_json_submission_full_fields(self):
        data = self.submit_ok(
            subject="Q4 report draft",
            body="Hi Alex,\n\nReview & send.",
            expires_at="2030-01-01T00:00:00Z",
            source="report-agent",
            metadata={"ticket": "OPS-142", "nested": {"n": 1}},
            destination_label="Alex — Client",
        )
        self.assertEqual(data["subject"], "Q4 report draft")
        self.assertEqual(data["expires_at"], "2030-01-01T00:00:00.000Z")
        self.assertEqual(data["metadata"]["ticket"], "OPS-142")
        self.assertEqual(data["source"], "report-agent")
        self.assertEqual(data["destination_label"], "Alex — Client")
        self.assertEqual(data["destination_normalized"], "alex@example.com")

    def test_simple_email_address_is_rejected(self):
        response = self.submit(destination="not-an-email")
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.get_json()["error"]["message"].lower())

    def test_invalid_channel_destination_body_and_metadata(self):
        self.assertEqual(self.submit(channel="sms").status_code, 400)
        self.assertEqual(self.submit(destination="  ").status_code, 400)
        self.assertEqual(self.submit(body="   ").status_code, 400)
        self.assertEqual(self.submit(metadata=["not", "an", "object"]).status_code, 400)
        self.assertEqual(
            self.client.post("/api/messages", json=["not", "an", "object"]).status_code, 400
        )

    def test_expiry_validation(self):
        self.assertEqual(
            self.submit(expires_at="2030-01-01T00:00:00Z", ttl_seconds=60).status_code, 400
        )
        self.assertEqual(self.submit(ttl_seconds=0).status_code, 400)
        self.assertEqual(self.submit(ttl_seconds=-2).status_code, 400)
        self.assertEqual(self.submit(ttl_seconds="60").status_code, 400)
        self.assertEqual(self.submit(ttl_seconds=None).status_code, 400)
        self.assertEqual(self.submit(expires_at="2000-01-01T00:00:00Z").status_code, 400)
        data = self.submit_ok(ttl_seconds=60)
        self.assertIsNotNone(data["expires_at"])
        self.assertGreater(data["expires_in_seconds"], 0)

    def test_absolute_expiry_is_canonical_utc(self):
        data = self.submit_ok(expires_at="2030-01-01T00:00:00+02:00")
        self.assertEqual(data["expires_at"], "2029-12-31T22:00:00.000Z")
        self.assertTrue(data["expires_at"].endswith("Z"))

    def test_multipart_submission_with_unsafe_filename(self):
        response = self.client.post(
            "/api/messages",
            data={
                "channel": "email",
                "destination": "alex@example.com",
                "subject": "File",
                "body": "See attached",
                "attachments": (io.BytesIO(b"hello attachment"), "../../evil.txt"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        data = response.get_json()
        self.assertEqual(data["attachment_count"], 1)
        attachment = data["attachments"][0]
        self.assertEqual(attachment["original_filename"], "evil.txt")
        self.assertEqual(attachment["size_bytes"], 16)
        self.assertEqual(attachment["source_type"], "multipart")
        self.assertRegex(attachment["storage_ref"], r"^[a-f0-9]{32}\.txt$")
        stored_path = self.app.extensions["outbox"]["store"].path_for(attachment["storage_ref"])
        self.assertTrue(str(stored_path).startswith(str(Path(self.tempdir.name) / "data" / "attachments")))
        self.assertFalse((Path(self.tempdir.name) / "evil.txt").exists())

    def test_multipart_multiple_attachments_and_fields(self):
        response = self.client.post(
            "/api/messages",
            data={
                "channel": "whatsapp",
                "destination": "+1 (415) 555-0123",
                "body": "Two files",
                "metadata": json.dumps({"ticket": "X"}),
                "references": json.dumps(["https://example.com/a"]),
                "attachments": [
                    (io.BytesIO(b"one"), "one.txt"),
                    (io.BytesIO(b"two"), "two.bin"),
                ],
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        data = response.get_json()
        self.assertEqual(data["attachment_count"], 2)
        self.assertEqual(data["metadata"], {"ticket": "X"})
        self.assertEqual(data["references"], ["https://example.com/a"])

    def test_unsupported_media_type_and_malformed_json(self):
        response = self.client.post("/api/messages", data="channel=email", content_type="text/plain")
        self.assertEqual(response.status_code, 415)
        response = self.client.post(
            "/api/messages", data="{bad json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"]["code"], "bad_request")

    def test_attachment_size_limits(self):
        small = self.make_app(max_attachment_bytes=5, max_message_attachment_bytes=20)
        client = small.test_client()
        response = client.post(
            "/api/messages",
            data={
                "channel": "email",
                "destination": "a@b.com",
                "body": "x",
                "attachments": (io.BytesIO(b"123456"), "six.txt"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 413)

        total_limited = self.make_app(max_attachment_bytes=10, max_message_attachment_bytes=12)
        client = total_limited.test_client()
        response = client.post(
            "/api/messages",
            data={
                "channel": "email",
                "destination": "a@b.com",
                "body": "x",
                "attachments": [
                    (io.BytesIO(b"1234567"), "a.txt"),
                    (io.BytesIO(b"1234567"), "b.txt"),
                ],
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 413)


class DownloadAndReferenceTests(OutboxTestBase):
    def test_references_and_url_reference_are_never_fetched(self):
        data = self.submit_ok(
            references=["https://example.com/spec"],
            attachments=[{"kind": "url_reference", "url": "https://example.com/other"}],
        )
        self.assertEqual(data["attachment_count"], 0)
        self.assertEqual(
            data["references"],
            ["https://example.com/spec", "https://example.com/other"],
        )
        origins = {r["url"]: r["origin"] for r in data["reference_details"]}
        self.assertEqual(origins["https://example.com/spec"], "reference")
        self.assertEqual(origins["https://example.com/other"], "attachment_reference")
        self.assertFalse(FixtureHandler.posts)

    def test_invalid_reference_url(self):
        self.assertEqual(self.submit(references=["javascript:alert(1)"]).status_code, 400)
        self.assertEqual(
            self.submit(attachments=[{"kind": "url_reference", "url": "/relative"}]).status_code,
            400,
        )

    def test_url_download_with_local_fixture(self):
        app = self.make_app(allow_private_urls=True)
        client = app.test_client()
        response = client.post(
            "/api/messages",
            json={
                "channel": "email",
                "destination": "alex@example.com",
                "subject": "Reference and file",
                "body": "See the external reference and the attached file.",
                "references": ["https://example.com/spec"],
                "attachments": [
                    {"kind": "url_download", "url": self.base_url + "/sample.txt", "filename": "sample.txt"}
                ],
            },
        )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        data = response.get_json()
        self.assertEqual(data["attachment_count"], 1)
        attachment = data["attachments"][0]
        self.assertEqual(attachment["source_type"], "url_download")
        self.assertEqual(attachment["original_filename"], "sample.txt")
        self.assertEqual(attachment["mime_type"], "text/plain")
        self.assertTrue(attachment["source_url"].endswith("/sample.txt"))
        download = client.get(attachment["download_url"])
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.data, b"fixture download\n")

    def test_url_download_follows_validated_redirect(self):
        app = self.make_app(allow_private_urls=True)
        client = app.test_client()
        response = client.post(
            "/api/messages",
            json={
                "channel": "email",
                "destination": "a@b.com",
                "body": "redirect",
                "attachments": [{"kind": "url_download", "url": self.base_url + "/redirect"}],
            },
        )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        attachment = response.get_json()["attachments"][0]
        self.assertTrue(attachment["source_url"].endswith("/sample.txt"))

    def test_redirect_loop_is_reported(self):
        app = self.make_app(allow_private_urls=True, max_redirects=2)
        client = app.test_client()
        response = client.post(
            "/api/messages",
            json={
                "channel": "email",
                "destination": "a@b.com",
                "body": "loop",
                "attachments": [{"kind": "url_download", "url": self.base_url + "/loop-redirect"}],
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("redirect", response.get_json()["error"]["message"].lower())

    def test_invalid_download_mime_falls_back_safely(self):
        app = self.make_app(allow_private_urls=True)
        client = app.test_client()
        response = client.post(
            "/api/messages",
            json={
                "channel": "email",
                "destination": "a@b.com",
                "body": "mime",
                "attachments": [{"kind": "url_download", "url": self.base_url + "/badmime"}],
            },
        )
        self.assertEqual(response.status_code, 201)
        attachment = response.get_json()["attachments"][0]
        self.assertRegex(attachment["mime_type"], r"^[a-z0-9.+-]+/[a-z0-9.+-]+$")
        self.assertEqual(attachment["mime_type"], "application/octet-stream")

    def test_ssrf_blocks_private_download_by_default(self):
        response = self.submit(
            attachments=[{"kind": "url_download", "url": self.base_url + "/sample.txt"}]
        )
        self.assertEqual(response.status_code, 400)
        message = response.get_json()["error"]["message"].lower()
        self.assertTrue("private" in message or "blocked" in message)

    def test_ssrf_blocks_metadata_and_literal_private_addresses(self):
        for url in (
            "http://169.254.169.254/latest/meta-data/",
            "http://127.0.0.1/x",
            "http://10.0.0.1/x",
            "http://[::1]/x",
            "http://192.168.1.10/x",
            "http://localhost/x",
        ):
            response = self.submit(attachments=[{"kind": "url_download", "url": url}])
            self.assertEqual(response.status_code, 400, url)

    def test_webhook_url_ssrf_validation(self):
        response = self.submit(webhook_url="http://127.0.0.1:9002/hooks/outbox")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.submit(webhook_url="ftp://example.com/hook").status_code, 400)
        app = self.make_app(allow_private_urls=True)
        client = app.test_client()
        response = client.post(
            "/api/messages",
            json={
                "channel": "email",
                "destination": "a@b.com",
                "body": "ok",
                "webhook_url": self.base_url + "/webhook",
            },
        )
        self.assertEqual(response.status_code, 201)

    def test_response_size_limit_is_enforced_while_downloading(self):
        app = self.make_app(allow_private_urls=True, max_attachment_bytes=1024)
        client = app.test_client()
        response = client.post(
            "/api/messages",
            json={
                "channel": "email",
                "destination": "a@b.com",
                "body": "big",
                "attachments": [{"kind": "url_download", "url": self.base_url + "/big"}],
            },
        )
        self.assertEqual(response.status_code, 413)


class AttachmentServingTests(OutboxTestBase):
    def _create_with_attachment(self):
        response = self.client.post(
            "/api/messages",
            data={
                "channel": "email",
                "destination": "alex@example.com",
                "body": "attachment",
                "attachments": (io.BytesIO(b"payload bytes"), "report 2026.txt"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 201)
        return response.get_json()

    def test_list_and_download_attachment_headers(self):
        data = self._create_with_attachment()
        attachment = data["attachments"][0]
        listing = self.client.get(f"/api/messages/{data['id']}/attachments")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.get_json()["total"], 1)
        download = self.client.get(attachment["download_url"])
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.data, b"payload bytes")
        disposition = download.headers["Content-Disposition"]
        self.assertIn("attachment;", disposition)
        self.assertIn("filename*=UTF-8''report%202026.txt", disposition)
        self.assertEqual(download.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(download.headers["Cache-Control"], "no-store")
        self.assertNotIn("\n", disposition)

    def test_download_does_not_change_status(self):
        data = self._create_with_attachment()
        self.approve(data["id"])
        attachment = data["attachments"][0]
        self.client.get(attachment["download_url"])
        self.client.get(f"/api/messages/{data['id']}/handoff")
        status = self.client.get(f"/api/messages/{data['id']}").get_json()["status"]
        self.assertEqual(status, "approved")

    def test_zip_download(self):
        data = self._create_with_attachment()
        response = self.client.get(f"/api/messages/{data['id']}/attachments.zip")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/zip")
        self.assertTrue(response.data.startswith(b"PK"))

    def test_missing_stored_file_returns_clear_404(self):
        data = self._create_with_attachment()
        attachment = data["attachments"][0]
        store = self.app.extensions["outbox"]["store"]
        store.path_for(attachment["storage_ref"]).unlink()
        response = self.client.get(attachment["download_url"])
        self.assertEqual(response.status_code, 404)
        self.assertIn("missing", response.get_json()["error"]["message"].lower())

    def test_unknown_attachment_and_path_traversal(self):
        data = self._create_with_attachment()
        self.assertEqual(
            self.client.get(f"/api/messages/{data['id']}/attachments/att_deadbeef").status_code,
            404,
        )
        self.assertEqual(
            self.client.get(f"/api/messages/{data['id']}/attachments/..%2f..%2fetc%2fpasswd").status_code,
            404,
        )
        self.assertEqual(
            self.client.get("/api/messages/msg_missing/attachments/att_missing").status_code, 404
        )

    def test_unowned_attachment_is_not_served_under_other_message(self):
        first = self._create_with_attachment()
        second = self._create_with_attachment()
        attachment = first["attachments"][0]
        response = self.client.get(f"/api/messages/{second['id']}/attachments/{attachment['id']}")
        self.assertEqual(response.status_code, 404)

    def test_sanitize_filename_rules(self):
        self.assertEqual(sanitize_filename("../../evil.txt"), "evil.txt")
        self.assertEqual(sanitize_filename("..\\..\\evil.txt"), "evil.txt")
        self.assertEqual(sanitize_filename("CON.txt"), "_CON.txt")
        self.assertEqual(sanitize_filename("\x00\x01bad\nname.txt"), "badname.txt")
        self.assertNotIn("/", sanitize_filename("a/b/c.txt"))
        self.assertTrue(sanitize_filename("").startswith("attachment"))


class LifecycleTests(OutboxTestBase):
    def test_approve_handoff_and_mark_sent(self):
        data = self.submit_ok(subject="Hello", body="Line one\nLine two & more")
        self.assertEqual(self.approve(data["id"]).status_code, 200)
        message = self.client.get(f"/api/messages/{data['id']}").get_json()
        self.assertEqual(message["status"], "approved")
        self.assertIn("mark_sent", message["allowed_actions"])
        handoff = self.client.get(f"/api/messages/{data['id']}/handoff")
        self.assertEqual(handoff.status_code, 200)
        handoff = handoff.get_json()
        self.assertTrue(handoff["handoff_url"].startswith("mailto:alex@example.com?"))
        parsed = urllib.parse.urlsplit(handoff["handoff_url"])
        query = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(query["subject"], ["Hello"])
        self.assertEqual(query["body"], ["Line one\nLine two & more"])
        self.assertTrue(handoff["capabilities"]["attachments_supported"] is False)

        sent = self.client.post(f"/api/messages/{data['id']}/mark-sent")
        self.assertEqual(sent.status_code, 200)
        self.assertEqual(sent.get_json()["status"], "sent")
        self.assertEqual(self.client.get(f"/api/messages/{data['id']}/handoff").status_code, 409)
        self.assertEqual(self.client.post(f"/api/messages/{data['id']}/mark-sent").status_code, 409)
        self.assertEqual(self.client.post(f"/api/messages/{data['id']}/cancel").status_code, 409)
        self.assertEqual(self.client.patch(f"/api/messages/{data['id']}", json={"body": "x"}).status_code, 409)

    def test_handoff_requires_approval(self):
        data = self.submit_ok()
        response = self.client.get(f"/api/messages/{data['id']}/handoff")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["current_status"], "pending")
        self.assertIn("approve", response.get_json()["allowed_actions"])

    def test_invalid_transitions(self):
        data = self.submit_ok()
        self.assertEqual(self.client.post(f"/api/messages/{data['id']}/mark-sent").status_code, 409)
        self.assertEqual(self.approve(data["id"]).status_code, 200)
        self.assertEqual(self.approve(data["id"]).status_code, 409)
        self.assertEqual(self.reject(data["id"]).status_code, 409)
        self.assertEqual(self.client.get("/api/messages/msg_missing").status_code, 404)
        self.assertEqual(self.client.post("/api/messages/msg_missing/approve").status_code, 404)

    def test_reject_requires_reason_and_records_history(self):
        data = self.submit_ok(webhook_url=None)
        self.assertEqual(self.client.post(f"/api/messages/{data['id']}/reject", json={}).status_code, 400)
        self.assertEqual(self.client.post(f"/api/messages/{data['id']}/reject", json={"reason": "   "}).status_code, 400)
        response = self.reject(data["id"], "The recipient name is wrong.")
        self.assertEqual(response.status_code, 200)
        rejected = response.get_json()
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["rejection_reason"], "The recipient name is wrong.")
        self.assertTrue(MONO_TS.match(rejected["rejection_at"]))
        history = self.client.get(f"/api/messages/{data['id']}/history").get_json()
        transitions = history["status_history"]
        self.assertEqual(transitions[-1]["from_status"], "pending")
        self.assertEqual(transitions[-1]["to_status"], "rejected")
        self.assertEqual(transitions[-1]["reason"], "The recipient name is wrong.")
        self.assertEqual(history["revisions"][0]["rejection_reason"], "The recipient name is wrong.")

    def test_cancel_pending_approved_rejected(self):
        pending = self.submit_ok()
        self.assertEqual(self.client.post(f"/api/messages/{pending['id']}/cancel", json={"reason": "duplicate"}).status_code, 200)
        self.assertEqual(self.client.get(f"/api/messages/{pending['id']}").get_json()["status"], "cancelled")

        approved = self.submit_ok()
        self.approve(approved["id"])
        self.assertEqual(self.client.post(f"/api/messages/{approved['id']}/cancel").status_code, 200)

        rejected = self.submit_ok()
        self.reject(rejected["id"])
        self.assertEqual(self.client.post(f"/api/messages/{rejected['id']}/cancel").status_code, 200)

    def test_exactly_one_concurrent_approval_wins(self):
        data = self.submit_ok()
        barrier = threading.Barrier(2)
        results: list[int] = []

        def attempt():
            with self.app.test_client() as client:
                barrier.wait(timeout=5)
                response = client.post(f"/api/messages/{data['id']}/approve")
                results.append(response.status_code)

        threads = [threading.Thread(target=attempt) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertEqual(sorted(results), [200, 409])
        history = self.client.get(f"/api/messages/{data['id']}/history").get_json()
        approved_rows = [h for h in history["status_history"] if h["to_status"] == "approved"]
        self.assertEqual(len(approved_rows), 1)

    def test_concurrent_terminal_transitions_never_both_win(self):
        data = self.submit_ok()
        self.assertEqual(self.approve(data["id"]).status_code, 200)
        barrier = threading.Barrier(2)
        outcomes: list[tuple[str, int]] = []

        def call(action):
            with self.app.test_client() as client:
                barrier.wait(timeout=5)
                response = client.post(f"/api/messages/{data['id']}/{action}")
                outcomes.append((action, response.status_code))

        threads = [
            threading.Thread(target=call, args=("mark-sent",)),
            threading.Thread(target=call, args=("cancel",)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertEqual(len([code for _, code in outcomes if code == 200]), 1)
        self.assertEqual(len([code for _, code in outcomes if code == 409]), 1)
        final = self.client.get(f"/api/messages/{data['id']}").get_json()["status"]
        self.assertIn(final, {"sent", "cancelled"})


class RevisionTests(OutboxTestBase):
    def test_patch_pending_creates_revision(self):
        data = self.submit_ok(subject="One", body="First", metadata={"a": 1})
        response = self.client.patch(
            f"/api/messages/{data['id']}",
            json={"subject": "Two", "body": "Second", "ttl_seconds": 120},
        )
        self.assertEqual(response.status_code, 200)
        revised = response.get_json()
        self.assertEqual(revised["id"], data["id"])
        self.assertEqual(revised["created_at"], data["created_at"])
        self.assertEqual(revised["revision_number"], 2)
        self.assertEqual(revised["status"], "pending")
        self.assertEqual(revised["subject"], "Two")
        self.assertEqual(revised["body"], "Second")
        self.assertEqual(revised["metadata"], {"a": 1})
        history = self.client.get(f"/api/messages/{data['id']}/history").get_json()
        self.assertEqual([r["revision_number"] for r in history["revisions"]], [1, 2])
        self.assertEqual(history["revisions"][0]["body"], "First")

    def test_rejected_message_revision_preserves_rejection_history(self):
        data = self.submit_ok(subject="Draft", body="Hi Alex Doe", webhook_url=None)
        self.reject(data["id"], "Recipient name is wrong")
        response = self.client.patch(
            f"/api/messages/{data['id']}",
            json={"subject": "Draft revised", "body": "Hi Alex Smith", "expires_at": None},
        )
        self.assertEqual(response.status_code, 200)
        revised = response.get_json()
        self.assertEqual(revised["id"], data["id"])
        self.assertEqual(revised["created_at"], data["created_at"])
        self.assertEqual(revised["status"], "pending")
        self.assertEqual(revised["revision_number"], 2)
        self.assertIsNone(revised["rejection_reason"])
        self.assertIsNone(revised["rejection_at"])
        history = self.client.get(f"/api/messages/{data['id']}/history").get_json()
        self.assertEqual(len(history["revisions"]), 2)
        self.assertEqual(history["revisions"][0]["rejection_reason"], "Recipient name is wrong")
        self.assertEqual(history["revisions"][0]["body"], "Hi Alex Doe")
        self.assertEqual(history["revisions"][1]["body"], "Hi Alex Smith")
        self.assertIsNone(history["revisions"][1]["rejection_reason"])
        transitions = [(h["from_status"], h["to_status"]) for h in history["status_history"]]
        self.assertIn(("rejected", "pending"), transitions)

    def test_two_consecutive_revisions_keep_all_history(self):
        data = self.submit_ok()
        for index in (2, 3):
            response = self.client.patch(
                f"/api/messages/{data['id']}",
                json={"body": f"Revision {index}"},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["revision_number"], index)
        history = self.client.get(f"/api/messages/{data['id']}/history").get_json()
        self.assertEqual(
            [r["body"] for r in history["revisions"]],
            ["Hello there", "Revision 2", "Revision 3"],
        )

    def test_patch_cannot_change_status(self):
        data = self.submit_ok()
        response = self.client.patch(f"/api/messages/{data['id']}", json={"status": "approved"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("status", response.get_json()["error"]["message"])

    def test_patch_unknown_and_conflicting_fields(self):
        data = self.submit_ok()
        self.assertEqual(self.client.patch(f"/api/messages/{data['id']}", json={"webhook_url": "https://example.com/h"}).status_code, 400)
        self.assertEqual(
            self.client.patch(
                f"/api/messages/{data['id']}",
                json={"expires_at": "2030-01-01T00:00:00Z", "ttl_seconds": 5},
            ).status_code,
            400,
        )
        self.assertEqual(self.client.patch(f"/api/messages/{data['id']}", json={"body": "  "}).status_code, 400)

    def test_patch_clears_expiration(self):
        data = self.submit_ok(ttl_seconds=300)
        self.assertIsNotNone(data["expires_at"])
        response = self.client.patch(f"/api/messages/{data['id']}", json={"expires_at": None})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get_json()["expires_at"])

    def test_patch_attachments_preserve_existing_blob(self):
        response = self.client.post(
            "/api/messages",
            data={
                "channel": "email",
                "destination": "a@b.com",
                "body": "with attachment",
                "attachments": (io.BytesIO(b"keep me"), "keep.txt"),
            },
            content_type="multipart/form-data",
        )
        data = response.get_json()
        attachment = data["attachments"][0]
        revised = self.client.patch(
            f"/api/messages/{data['id']}",
            json={
                "body": "revised",
                "attachments": [{"kind": "existing", "attachment_id": attachment["id"]}],
            },
        )
        self.assertEqual(revised.status_code, 200, revised.get_data(as_text=True))
        self.assertEqual(revised.get_json()["attachment_count"], 1)
        download = self.client.get(attachment["download_url"])
        self.assertEqual(download.data, b"keep me")
        history = self.client.get(f"/api/messages/{data['id']}/history").get_json()
        self.assertEqual(history["revisions"][0]["attachment_count"], 1)
        self.assertEqual(history["revisions"][1]["attachment_count"], 1)

    def test_patch_attachment_must_belong_to_message(self):
        first = self.submit_ok()
        second = self.client.post(
            "/api/messages",
            data={
                "channel": "email",
                "destination": "b@b.com",
                "body": "x",
                "attachments": (io.BytesIO(b"x"), "x.txt"),
            },
            content_type="multipart/form-data",
        ).get_json()
        response = self.client.patch(
            f"/api/messages/{first['id']}",
            json={"attachments": [{"kind": "existing", "attachment_id": second["attachments"][0]["id"]}]},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("does not belong", response.get_json()["error"]["message"])

    def test_patch_rejected_approved_sent_stale_cancelled(self):
        approved = self.submit_ok()
        self.approve(approved["id"])
        self.assertEqual(self.client.patch(f"/api/messages/{approved['id']}", json={"body": "no"}).status_code, 409)

        sent = self.submit_ok()
        self.approve(sent["id"])
        self.client.post(f"/api/messages/{sent['id']}/mark-sent")
        self.assertEqual(self.client.patch(f"/api/messages/{sent['id']}", json={"body": "no"}).status_code, 409)

        cancelled = self.submit_ok()
        self.client.post(f"/api/messages/{cancelled['id']}/cancel")
        self.assertEqual(self.client.patch(f"/api/messages/{cancelled['id']}", json={"body": "no"}).status_code, 409)

        stale = self.submit_ok(ttl_seconds=1)
        time.sleep(1.1)
        self.assertEqual(self.client.get(f"/api/messages/{stale['id']}").get_json()["status"], "stale")
        self.assertEqual(self.client.patch(f"/api/messages/{stale['id']}", json={"body": "no"}).status_code, 409)


class ExpirationTests(OutboxTestBase):
    def test_ttl_expiration_marks_stale_and_blocks_actions(self):
        data = self.submit_ok(ttl_seconds=1)
        time.sleep(1.15)
        message = self.client.get(f"/api/messages/{data['id']}").get_json()
        self.assertEqual(message["status"], "stale")
        self.assertEqual(message["body"], "Hello there")
        self.assertEqual(self.approve(data["id"]).status_code, 409)
        self.assertEqual(self.client.get(f"/api/messages/{data['id']}/handoff").status_code, 409)
        self.assertEqual(self.client.post(f"/api/messages/{data['id']}/mark-sent").status_code, 409)
        self.assertEqual(self.reject(data["id"]).status_code, 409)
        self.assertEqual(self.client.post(f"/api/messages/{data['id']}/cancel").status_code, 409)
        history = self.client.get(f"/api/messages/{data['id']}/history").get_json()
        self.assertEqual(history["status"], "stale")
        self.assertTrue(any(h["to_status"] == "stale" for h in history["status_history"]))
        self.assertEqual(history["revisions"][0]["body"], "Hello there")

    def test_absolute_expiration_in_past_rejected(self):
        self.assertEqual(self.submit(expires_at="2020-01-01T00:00:00Z").status_code, 400)

    def test_no_expiration_stays_active(self):
        data = self.submit_ok()
        self.assertIsNone(data["expires_at"])
        time.sleep(0.05)
        self.assertEqual(self.client.get(f"/api/messages/{data['id']}").get_json()["status"], "pending")

    def test_stale_messages_removed_from_active_filter(self):
        stale = self.submit_ok(ttl_seconds=1)
        active = self.submit_ok()
        time.sleep(1.15)
        listing = self.client.get("/api/messages?status=pending,approved,rejected").get_json()
        ids = {item["id"] for item in listing["items"]}
        self.assertNotIn(stale["id"], ids)
        self.assertIn(active["id"], ids)
        self.assertEqual(len(listing["items"]), 1)
        all_listing = self.client.get("/api/messages?status=stale").get_json()
        self.assertEqual(all_listing["items"][0]["id"], stale["id"])

    def test_expiration_worker_sweep(self):
        data = self.submit_ok(ttl_seconds=1)
        time.sleep(1.1)
        # Avoid API expiration check: call the worker sweep directly.
        from outbox.service import OutboxService

        service = OutboxService(
            self.app.extensions["outbox"]["database"],
            self.app.extensions["outbox"]["config"],
            self.dispatcher,
        )
        try:
            count = service.expire_due()
        finally:
            service.close()
        self.assertGreaterEqual(count, 1)
        self.assertEqual(self.client.get(f"/api/messages/{data['id']}").get_json()["status"], "stale")

    def test_approval_expiration_race_never_approves_expired_message(self):
        data = self.submit_ok(ttl_seconds=1)
        time.sleep(1.1)
        barrier = threading.Barrier(2)
        results: list[int] = []

        def attempt():
            with self.app.test_client() as client:
                barrier.wait(timeout=5)
                results.append(client.post(f"/api/messages/{data['id']}/approve").status_code)

        threads = [threading.Thread(target=attempt) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertEqual(results, [409, 409])
        final = self.client.get(f"/api/messages/{data['id']}").get_json()
        self.assertEqual(final["status"], "stale")
        history = self.client.get(f"/api/messages/{data['id']}/history").get_json()
        self.assertEqual(
            len([h for h in history["status_history"] if h["to_status"] == "stale"]), 1
        )


class ListingTests(OutboxTestBase):
    def test_listing_envelope_filters_and_destination_label(self):
        first = self.submit_ok(subject="Alpha")
        second = self.submit_ok(destination="+1 (415) 555-0123", channel="whatsapp", subject=None)
        self.client.put(
            "/api/destinations/label",
            json={"channel": "email", "destination": "alex@example.com", "label": "Alex — Client"},
        )
        listing = self.client.get("/api/messages").get_json()
        self.assertEqual(listing["total"], 2)
        self.assertEqual(listing["limit"], 20)
        self.assertEqual(listing["offset"], 0)
        self.assertEqual(len(listing["items"]), 2)
        self.assertIn("attachment_count", listing["items"][0])

        filtered = self.client.get("/api/messages?channel=whatsapp").get_json()
        self.assertEqual([i["id"] for i in filtered["items"]], [second["id"]])
        self.assertEqual(filtered["items"][0]["destination"], "+1 (415) 555-0123")

        by_status = self.client.get("/api/messages?status=pending").get_json()
        self.assertEqual(by_status["total"], 2)
        by_status = self.client.get("/api/messages?status=approved").get_json()
        self.assertEqual(by_status["total"], 0)

        by_destination = self.client.get("/api/messages?destination=alex").get_json()
        self.assertEqual([i["id"] for i in by_destination["items"]], [first["id"]])
        by_label = self.client.get("/api/messages?destination=client").get_json()
        self.assertEqual([i["id"] for i in by_label["items"]], [first["id"]])
        self.assertEqual(by_destination["items"][0]["destination_label_effective"], "Alex — Client")

    def test_pagination_and_invalid_pagination(self):
        for index in range(3):
            self.submit_ok(body=f"Message {index}")
        page = self.client.get("/api/messages?limit=2&offset=0").get_json()
        self.assertEqual(page["total"], 3)
        self.assertEqual(len(page["items"]), 2)
        page2 = self.client.get("/api/messages?limit=2&offset=2").get_json()
        self.assertEqual(len(page2["items"]), 1)
        self.assertEqual(self.client.get("/api/messages?limit=0").status_code, 400)
        self.assertEqual(self.client.get("/api/messages?offset=-1").status_code, 400)
        self.assertEqual(self.client.get("/api/messages?limit=bad").status_code, 400)
        self.assertEqual(self.client.get("/api/messages?limit=1000").get_json()["limit"], 100)
        self.assertEqual(self.client.get("/api/messages?sort=sideways").status_code, 400)

    def test_sorting_newest_oldest_and_no_expiration_last(self):
        old = self.submit_ok(body="old", expires_at="2031-01-01T00:00:00Z")
        time.sleep(0.02)
        middle = self.submit_ok(body="middle")
        time.sleep(0.02)
        new = self.submit_ok(body="new", expires_at="2032-01-01T00:00:00Z")
        newest = self.client.get("/api/messages?sort=newest").get_json()["items"]
        self.assertEqual(newest[0]["id"], new["id"])
        oldest = self.client.get("/api/messages?sort=oldest").get_json()["items"]
        self.assertEqual(oldest[0]["id"], old["id"])
        soon = self.client.get("/api/messages?sort=expires_soon").get_json()["items"]
        self.assertEqual(soon[0]["id"], old["id"])
        self.assertEqual(soon[-1]["id"], middle["id"])
        late = self.client.get("/api/messages?sort=expires_late").get_json()["items"]
        self.assertEqual(late[0]["id"], new["id"])
        self.assertEqual(late[-1]["id"], middle["id"])

    def test_created_and_expiry_date_filters(self):
        with_expiry = self.submit_ok(expires_at="2031-01-01T00:00:00Z")
        without = self.submit_ok()
        today = time.strftime("%Y-%m-%d", time.gmtime())
        created = self.client.get(f"/api/messages?created_from={today}&created_to={today}").get_json()
        self.assertEqual(created["total"], 2)
        created = self.client.get("/api/messages?created_from=2099-01-01").get_json()
        self.assertEqual(created["total"], 0)
        expiry = self.client.get("/api/messages?expires_from=2030-01-01").get_json()
        self.assertEqual([i["id"] for i in expiry["items"]], [with_expiry["id"]])
        expiry = self.client.get("/api/messages?expires_to=2030-01-01").get_json()
        self.assertEqual(expiry["total"], 0)

    def test_invalid_status_and_channel_filters(self):
        self.assertEqual(self.client.get("/api/messages?status=nope").status_code, 400)
        self.assertEqual(self.client.get("/api/messages?channel=sms").status_code, 400)

    def test_get_missing_message(self):
        response = self.client.get("/api/messages/msg_doesnotexist")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"]["code"], "not_found")
        self.assertEqual(self.client.get("/api/messages/msg_doesnotexist/history").status_code, 404)

    def test_detail_includes_attachments_references_and_history(self):
        data = self.submit_ok(
            references=["https://example.com/spec"],
            attachments=[{"kind": "url_reference", "url": "https://example.com/ref"}],
        )
        detail = self.client.get(f"/api/messages/{data['id']}").get_json()
        self.assertEqual(detail["references"], ["https://example.com/spec", "https://example.com/ref"])
        self.assertEqual(detail["attachment_count"], 0)
        self.assertEqual(detail["status"], "pending")
        self.assertEqual(detail["id"], data["id"])
        self.assertEqual(len(detail["references"]), 2)


class DestinationTests(OutboxTestBase):
    def test_discovery_and_labels(self):
        self.submit_ok(destination="alex@example.com")
        self.submit_ok(destination="ALEX@example.com")
        self.submit_ok(destination="bob@example.com")
        destinations = self.client.get("/api/destinations").get_json()
        self.assertEqual(destinations["total"], 2)
        alex = next(d for d in destinations["items"] if d["destination_normalized"] == "alex@example.com")
        self.assertEqual(alex["message_count"], 2)
        self.assertIsNone(alex["label"])
        self.assertTrue(alex["last_used_at"])

        response = self.client.put(
            "/api/destinations/label",
            json={"channel": "email", "destination": "alex@example.com", "label": "Alex — Client"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["label"], "Alex — Client")

        response = self.client.put(
            "/api/destinations/label",
            json={"channel": "email", "destination": "bob@example.com", "label": "alex — client"},
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("already used", response.get_json()["error"]["message"])

        response = self.client.put(
            "/api/destinations/label",
            json={"channel": "email", "destination": "alex@example.com", "label": "Alex — VIP Client"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["label"], "Alex — VIP Client")

        message = self.client.get(
            "/api/messages?destination=alex@example.com"
        ).get_json()["items"][0]
        self.assertEqual(message["managed_label"], "Alex — VIP Client")
        self.assertEqual(message["destination_label_effective"], "Alex — VIP Client")

        removed = self.client.delete(
            "/api/destinations/label?channel=email&destination=alex@example.com"
        )
        self.assertEqual(removed.status_code, 200)
        self.assertTrue(removed.get_json()["removed"])
        self.assertIsNone(removed.get_json()["label"])
        # Messages still exist and keep their snapshot.
        still_there = self.client.get("/api/messages").get_json()
        self.assertEqual(still_there["total"], 3)
        # Label can be reused after removal.
        reused = self.client.put(
            "/api/destinations/label",
            json={"channel": "email", "destination": "alex@example.com", "label": "Client again"},
        )
        self.assertEqual(reused.status_code, 200)

    def test_label_snapshot_preserved_when_managed_label_removed(self):
        data = self.submit_ok(destination="snap@example.com", destination_label="Snapshot label")
        self.client.put(
            "/api/destinations/label",
            json={"channel": "email", "destination": "snap@example.com", "label": "Managed label"},
        )
        message = self.client.get(f"/api/messages/{data['id']}").get_json()
        self.assertEqual(message["managed_label"], "Managed label")
        self.assertEqual(message["destination_label"], "Snapshot label")
        self.assertEqual(message["destination_label_effective"], "Managed label")
        self.client.delete("/api/destinations/label?channel=email&destination=snap@example.com")
        message = self.client.get(f"/api/messages/{data['id']}").get_json()
        self.assertEqual(message["destination_label_effective"], "Snapshot label")

    def test_label_validation_and_unknown_destination(self):
        self.submit_ok()
        self.assertEqual(
            self.client.put("/api/destinations/label", json={"channel": "email", "destination": "a@b.com", "label": ""}).status_code,
            400,
        )
        self.assertEqual(
            self.client.put("/api/destinations/label", json={"channel": "email", "destination": "a@b.com", "label": "x" * 121}).status_code,
            400,
        )
        self.assertEqual(
            self.client.put("/api/destinations/label", json={"channel": "email", "destination": "unknown@example.com", "label": "X"}).status_code,
            404,
        )
        self.assertEqual(
            self.client.delete("/api/destinations/label?channel=email&destination=unknown@example.com").status_code,
            404,
        )

    def test_destination_query_and_filter(self):
        self.submit_ok(destination="alex@example.com")
        self.submit_ok(destination="+1 (415) 555-0123", channel="whatsapp")
        self.client.put(
            "/api/destinations/label",
            json={"channel": "whatsapp", "destination": "+1 (415) 555-0123", "label": "Alex phone"},
        )
        all_dest = self.client.get("/api/destinations").get_json()
        self.assertEqual(all_dest["total"], 2)
        email_only = self.client.get("/api/destinations?channel=email").get_json()
        self.assertEqual(email_only["total"], 1)
        search = self.client.get("/api/destinations?q=phone").get_json()
        self.assertEqual(search["total"], 1)
        self.assertEqual(search["items"][0]["label"], "Alex phone")


class HandoffTests(OutboxTestBase):
    def _approved(self, **fields):
        data = self.submit_ok(**fields)
        self.assertEqual(self.approve(data["id"]).status_code, 200)
        response = self.client.get(f"/api/messages/{data['id']}/handoff")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return data, response.get_json()

    def test_email_handoff_encoding_and_attachment_instructions(self):
        data = self.client.post(
            "/api/messages",
            data={
                "channel": "email",
                "destination": "alex@example.com",
                "subject": "Q4 & review",
                "body": "Hi Alex,\n\nReview & send — thanks!\n",
                "attachments": (io.BytesIO(b"file"), "report.txt"),
            },
            content_type="multipart/form-data",
        ).get_json()
        self.approve(data["id"])
        handoff = self.client.get(f"/api/messages/{data['id']}/handoff").get_json()
        url = handoff["handoff_url"]
        self.assertTrue(url.startswith("mailto:alex@example.com?"))
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        self.assertEqual(query["subject"], ["Q4 & review"])
        self.assertEqual(query["body"], ["Hi Alex,\n\nReview & send — thanks!\n"])
        self.assertIn("%0A", url)
        self.assertIn("%26", url)
        self.assertEqual(handoff["channel"], "email")
        self.assertEqual(handoff["destination_kind"], "individual")
        self.assertTrue(handoff["capabilities"]["prefill_recipient"])
        self.assertTrue(handoff["capabilities"]["prefill_subject"])
        self.assertTrue(handoff["capabilities"]["prefill_body"])
        self.assertFalse(handoff["capabilities"]["attachments_supported"])
        manual = " ".join(handoff["manual_actions"]).lower()
        self.assertIn("attach", manual)
        self.assertIn("download", manual)
        self.assertEqual(len(handoff["attachments"]), 1)
        self.assertTrue(handoff["copy"]["subject"])

    def test_email_long_body_uses_safe_fallback(self):
        data, handoff = self._approved(body="x" * 5000, subject="A long one")
        self.assertLessEqual(len(handoff["handoff_url"]), 1800)
        self.assertNotEqual(handoff["mode"], "prefill")
        self.assertFalse(handoff["capabilities"]["prefill_body"])
        self.assertTrue(any("too long" in w.lower() for w in handoff["warnings"]))
        self.assertEqual(handoff["copy"]["body"], "x" * 5000)
        parsed = urllib.parse.urlsplit(handoff["handoff_url"])
        self.assertEqual(parsed.scheme, "mailto")

    def test_whatsapp_individual_normalizes_and_prefills(self):
        data, handoff = self._approved(
            channel="whatsapp",
            destination="+1 (415) 555-0123",
            body="Your appointment is confirmed for 3 PM.\nBring ID.",
        )
        self.assertEqual(handoff["normalized_destination"], "+14155550123")
        self.assertTrue(handoff["handoff_url"].startswith("https://wa.me/14155550123?text="))
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(handoff["handoff_url"]).query)
        self.assertEqual(query["text"], ["Your appointment is confirmed for 3 PM.\nBring ID."])
        self.assertTrue(handoff["capabilities"]["prefill_recipient"])
        self.assertTrue(handoff["capabilities"]["prefill_body"])
        self.assertFalse(handoff["capabilities"]["prefill_subject"])

    def test_whatsapp_group_is_honest_manual_fallback(self):
        data, handoff = self._approved(
            channel="whatsapp", destination="group:Project Alpha", body="Standup moved to 10:00."
        )
        self.assertEqual(handoff["destination_kind"], "group")
        self.assertEqual(handoff["normalized_destination"], "group:project alpha")
        self.assertEqual(handoff["handoff_url"], "https://wa.me/")
        self.assertEqual(handoff["mode"], "manual_fallback")
        self.assertFalse(handoff["capabilities"]["prefill_recipient"])
        self.assertFalse(handoff["capabilities"]["prefill_body"])
        self.assertIn("Project Alpha", " ".join(handoff["manual_actions"]))
        self.assertTrue(any("cannot be preselected" in w for w in handoff["warnings"]))
        self.assertEqual(handoff["copy"]["body"], "Standup moved to 10:00.")

    def test_telegram_individual_username_variants(self):
        for destination in ("@alex_example", "t.me/alex_example", "https://t.me/alex_example"):
            data, handoff = self._approved(
                channel="telegram", destination=destination, body="Build finished successfully."
            )
            self.assertEqual(handoff["normalized_destination"], "@alex_example")
            self.assertTrue(handoff["handoff_url"].startswith("https://t.me/alex_example?text="))
            self.assertTrue(handoff["capabilities"]["prefill_recipient"])
            self.assertTrue(handoff["capabilities"]["prefill_body"])

    def test_telegram_group_and_invite_use_manual_fallback(self):
        data, handoff = self._approved(channel="telegram", destination="group:Ops Room", body="Deploy is live.")
        self.assertEqual(handoff["destination_kind"], "group")
        self.assertEqual(handoff["handoff_url"], "https://t.me/")
        self.assertEqual(handoff["mode"], "manual_fallback")
        self.assertFalse(any(handoff["capabilities"].values()))
        self.assertIn("Ops Room", " ".join(handoff["manual_actions"]))

        data, handoff = self._approved(
            channel="telegram", destination="t.me/+AbCdEf123456", body="Private update"
        )
        self.assertEqual(handoff["destination_kind"], "invite")
        self.assertIn("+AbCdEf123456", handoff["handoff_url"])
        self.assertEqual(handoff["mode"], "manual_fallback")
        self.assertFalse(any(handoff["capabilities"].values()))
        self.assertTrue(any("invite" in w.lower() for w in handoff["warnings"]))

    def test_invalid_channel_destinations(self):
        cases = [
            {"channel": "email", "destination": "alex@@example.com"},
            {"channel": "email", "destination": "alex@example"},
            {"channel": "whatsapp", "destination": "not a number"},
            {"channel": "whatsapp", "destination": "123"},
            {"channel": "telegram", "destination": "alex_example"},
            {"channel": "telegram", "destination": "https://evil.example/@alex_example"},
            {"channel": "telegram", "destination": "t.me/+bad"},
        ]
        for fields in cases:
            payload = {"body": "x", "destination": "a@b.com", "channel": "email"}
            payload.update(fields)
            response = self.client.post("/api/messages", json=payload)
            self.assertEqual(response.status_code, 400, fields)

    def test_handoff_after_expiration_is_409(self):
        data = self.submit_ok(ttl_seconds=3)
        self.approve(data["id"])
        time.sleep(3.1)
        response = self.client.get(f"/api/messages/{data['id']}/handoff")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["current_status"], "stale")

    def test_whatsapp_long_body_fallback(self):
        data, handoff = self._approved(
            channel="whatsapp", destination="+14155550123", body="y" * 4000
        )
        self.assertEqual(handoff["handoff_url"], "https://wa.me/14155550123")
        self.assertEqual(handoff["mode"], "manual_fallback")
        self.assertFalse(handoff["capabilities"]["prefill_body"])


class WebhookTests(OutboxTestBase):
    def setUp(self):
        super().setUp()
        # Recreate with the documented local-testing override so loopback
        # webhook URLs are accepted while the rest of the suite keeps SSRF on.
        self.app = self.make_app(allow_private_urls=True)
        self.client = self.app.test_client()
        self.dispatcher = self.app.extensions["outbox"]["dispatcher"]
        self.sent = []
        self.webhook_mode = "success"
        self.dispatcher.send_once = self._fake_webhook

    def _with_webhook(self, **fields):
        return self.submit_ok(webhook_url="http://127.0.0.1:9002/hooks/outbox", **fields)

    def test_rejected_event_payload_and_delivery_history(self):
        app = self.make_app(allow_private_urls=True)
        client = app.test_client()
        dispatcher = app.extensions["outbox"]["dispatcher"]
        sent = []

        def fake(url, payload):
            sent.append((url, payload))
            return True, 204, None, ""

        dispatcher.send_once = fake
        response = client.post(
            "/api/messages",
            json={
                "channel": "email",
                "destination": "alex@example.com",
                "body": "Hello",
                "webhook_url": "http://127.0.0.1:9002/hooks/outbox",
            },
        )
        msg_id = response.get_json()["id"]
        client.post(f"/api/messages/{msg_id}/reject", json={"reason": "Wrong recipient"})
        self.assertEqual(len(sent), 1)
        url, payload = sent[0]
        self.assertEqual(url, "http://127.0.0.1:9002/hooks/outbox")
        self.assertEqual(payload["event"], "message.rejected")
        self.assertEqual(payload["message_id"], msg_id)
        self.assertEqual(payload["status"], "rejected")
        self.assertEqual(payload["revision_number"], 1)
        self.assertEqual(payload["rejection_reason"], "Wrong recipient")
        self.assertTrue(MONO_TS.match(payload["timestamp"]))

        events = client.get(f"/api/messages/{msg_id}/webhook-events").get_json()
        self.assertEqual(events["total"], 1)
        event = events["items"][0]
        self.assertEqual(event["status"], "delivered")
        self.assertEqual(event["attempt_count"], 1)
        self.assertEqual(event["attempts"][0]["http_status"], 204)
        self.assertEqual(event["payload"]["event"], "message.rejected")

    def test_all_required_event_types(self):
        data = self._with_webhook()
        self.approve(data["id"])
        self.client.post(f"/api/messages/{data['id']}/mark-sent")
        self.assertEqual([p["event"] for _, p in self.sent], ["message.approved", "message.sent"])

        rejected = self._with_webhook()
        self.reject(rejected["id"])
        self.assertEqual(self.sent[-1][1]["event"], "message.rejected")

        revised = self._with_webhook()
        self.reject(revised["id"])
        self.client.patch(f"/api/messages/{revised['id']}", json={"body": "new body"})
        self.assertEqual(self.sent[-1][1]["event"], "message.revised")
        self.assertEqual(self.sent[-1][1]["revision_number"], 2)

        cancelled = self._with_webhook()
        self.client.post(f"/api/messages/{cancelled['id']}/cancel")
        self.assertEqual(self.sent[-1][1]["event"], "message.cancelled")

        stale = self._with_webhook(ttl_seconds=1)
        time.sleep(1.1)
        self.client.get(f"/api/messages/{stale['id']}")
        self.assertEqual(self.sent[-1][1]["event"], "message.stale")

    def test_webhook_failure_never_rolls_back_state(self):
        self.webhook_mode = "failure"
        data = self._with_webhook()
        response = self.reject(data["id"], "Bad content")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "rejected")
        self.assertEqual(self.client.get(f"/api/messages/{data['id']}").get_json()["status"], "rejected")
        events = self.client.get(f"/api/messages/{data['id']}/webhook-events").get_json()
        event = events["items"][0]
        self.assertEqual(event["status"], "failed")
        self.assertEqual(event["attempt_count"], 3)
        self.assertEqual(len(event["attempts"]), 3)
        self.assertTrue(all(a["status"] == "failed" for a in event["attempts"]))
        self.assertIn("500", event["last_error"])

    def test_webhook_timeout_retries_and_records_event(self):
        self.webhook_mode = "timeout"
        data = self._with_webhook()
        self.approve(data["id"])
        events = self.client.get(f"/api/messages/{data['id']}/webhook-events").get_json()
        event = events["items"][0]
        self.assertEqual(event["status"], "failed")
        self.assertEqual(event["attempt_count"], 3)
        self.assertIn("timed out", event["last_error"])

    def test_no_webhook_configured_writes_no_events(self):
        data = self.submit_ok()
        self.approve(data["id"])
        self.assertEqual(self.sent, [])
        events = self.client.get(f"/api/messages/{data['id']}/webhook-events").get_json()
        self.assertEqual(events["total"], 0)
        self.assertEqual(self.approve(data["id"]).status_code, 409)

    def test_webhook_events_are_idempotent_per_revision(self):
        data = self._with_webhook()
        self.approve(data["id"])
        events = self.client.get(f"/api/messages/{data['id']}/webhook-events").get_json()
        self.assertEqual(events["total"], 1)
        # Re-delivering an already delivered event must not duplicate it.
        self.dispatcher.enqueue(events["items"][0]["id"])
        events_again = self.client.get(f"/api/messages/{data['id']}/webhook-events").get_json()
        self.assertEqual(events_again["total"], 1)
        self.assertEqual(events_again["items"][0]["attempt_count"], 1)

    def test_real_webhook_delivery_to_loopback_fixture(self):
        app = self.make_app(allow_private_urls=True, webhook_async=False)
        client = app.test_client()
        response = client.post(
            "/api/messages",
            json={
                "channel": "email",
                "destination": "a@b.com",
                "body": "real delivery",
                "webhook_url": self.base_url + "/webhook",
            },
        )
        msg_id = response.get_json()["id"]
        client.post(f"/api/messages/{msg_id}/approve")
        self.assertEqual(len(FixtureHandler.posts), 1)
        record = FixtureHandler.posts[0]
        self.assertEqual(record["payload"]["event"], "message.approved")
        self.assertEqual(record["headers"].get("Content-Type"), "application/json; charset=utf-8")
        events = client.get(f"/api/messages/{msg_id}/webhook-events").get_json()
        self.assertEqual(events["items"][0]["status"], "delivered")

    def test_real_webhook_failure_is_recorded(self):
        app = self.make_app(allow_private_urls=True, webhook_async=False, webhook_max_attempts=2)
        client = app.test_client()
        response = client.post(
            "/api/messages",
            json={
                "channel": "email",
                "destination": "a@b.com",
                "body": "real failure",
                "webhook_url": self.base_url + "/fail",
            },
        )
        msg_id = response.get_json()["id"]
        self.assertEqual(client.post(f"/api/messages/{msg_id}/approve").status_code, 200)
        events = client.get(f"/api/messages/{msg_id}/webhook-events").get_json()
        event = events["items"][0]
        self.assertEqual(event["status"], "failed")
        self.assertEqual(event["attempt_count"], 2)
        self.assertEqual(event["attempts"][0]["http_status"], 500)
        self.assertEqual(client.get(f"/api/messages/{msg_id}").get_json()["status"], "approved")

    def test_real_webhook_timeout(self):
        app = self.make_app(
            allow_private_urls=True,
            webhook_async=False,
            webhook_max_attempts=1,
            webhook_timeout_seconds=0.15,
        )
        client = app.test_client()
        response = client.post(
            "/api/messages",
            json={
                "channel": "email",
                "destination": "a@b.com",
                "body": "timeout",
                "webhook_url": self.base_url + "/slow",
            },
        )
        msg_id = response.get_json()["id"]
        client.post(f"/api/messages/{msg_id}/approve")
        events = client.get(f"/api/messages/{msg_id}/webhook-events").get_json()
        self.assertEqual(events["items"][0]["status"], "failed")
        self.assertIn("timed out", (events["items"][0]["last_error"] or "").lower())


class SecurityAndValidationTests(OutboxTestBase):
    def test_transition_errors_have_status_and_allowed_actions(self):
        data = self.submit_ok()
        response = self.client.get(f"/api/messages/{data['id']}/handoff")
        self.assertEqual(response.status_code, 409)
        payload = response.get_json()
        self.assertEqual(payload["current_status"], "pending")
        self.assertIn("approve", payload["allowed_actions"])
        self.assertEqual(payload["error"]["details"]["current_status"], "pending")

    def test_unsupported_media_types(self):
        data = self.submit_ok()
        response = self.client.patch(
            f"/api/messages/{data['id']}", data='{"body":"x"}', content_type="text/plain"
        )
        self.assertEqual(response.status_code, 415)
        response = self.client.post(
            f"/api/messages/{data['id']}/reject", data="reason=x", content_type="text/plain"
        )
        self.assertEqual(response.status_code, 415)

    def test_error_shapes_are_consistent(self):
        for response, status in (
            (self.client.get("/api/messages/msg_nope"), 404),
            (self.submit(destination="bad"), 400),
            (self.client.get("/api/messages?limit=0"), 400),
        ):
            self.assertEqual(response.status_code, status)
            error = response.get_json()["error"]
            self.assertIn("code", error)
            self.assertIn("message", error)
            self.assertIn("details", error)
            self.assertIsInstance(error["message"], str)

    def test_invalid_metadata_and_reference_shapes(self):
        self.assertEqual(self.submit(metadata=["not", "an", "object"]).status_code, 400)
        self.assertEqual(self.submit(references="not a list").status_code, 400)
        self.assertEqual(self.submit(references=[1]).status_code, 400)
        self.assertEqual(
            self.submit(attachments=[{"kind": "download", "url": "https://example.com/x"}]).status_code,
            400,
        )

    def test_attachment_id_mismatch_and_message_mismatch(self):
        first = self.submit_ok()
        second = self.submit_ok()
        self.assertEqual(
            self.client.get(f"/api/messages/{first['id']}/attachments/att_notthere").status_code,
            404,
        )
        self.assertEqual(
            self.client.get(f"/api/messages/{second['id']}/attachments.zip").status_code, 404
        )

    def test_patch_download_respects_size_limit(self):
        app = self.make_app(allow_private_urls=True, max_attachment_bytes=1024)
        client = app.test_client()
        created = client.post(
            "/api/messages",
            json={"channel": "email", "destination": "a@b.com", "body": "x"},
        ).get_json()
        response = client.patch(
            f"/api/messages/{created['id']}",
            json={"attachments": [{"kind": "url_download", "url": self.base_url + "/big"}]},
        )
        self.assertEqual(response.status_code, 413)
        # The message stayed at revision 1 and pending.
        message = client.get(f"/api/messages/{created['id']}").get_json()
        self.assertEqual(message["revision_number"], 1)
        self.assertEqual(message["attachment_count"], 0)


if __name__ == "__main__":
    unittest.main()
