"""Shared test helpers: temp-dir apps, loopback fixture servers, fake senders.

Loopback fixtures are explicitly allowed by the task spec; the real network
is never required. Webhook delivery is mocked via ``ctx.webhook_sender``
except in one test that exercises the real sender against a local sink.
"""
from __future__ import annotations

import json
import pathlib
import socket
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app import create_app
from outbox.config import Config


def free_port_server(handler_cls) -> tuple[ThreadingHTTPServer, str]:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, f"http://127.0.0.1:{port}"


class _DownloadHandler(BaseHTTPRequestHandler):
    """Serves fixtures for url_download tests: files, redirects, delays."""

    def do_GET(self):  # noqa: N802
        if self.path == "/sample.txt":
            data = b"Outbox attachment fixture.\nThis file is intentionally small.\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif self.path.startswith("/redirect/"):
            target = self.path.split("/redirect/", 1)[1]
            self.send_response(302)
            self.send_header("Location", target)
            self.end_headers()
        elif self.path.startswith("/redirect-loop"):
            self.send_response(302)
            self.send_header("Location", "/redirect-loop")
            self.end_headers()
        elif self.path == "/big":
            n = 5_000_000
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(n))
            self.end_headers()
            self.wfile.write(b"x" * n)
        elif self.path == "/slow":
            import time
            time.sleep(3)
            self.send_response(200)
            self.end_headers()
        else:
            self.send_error(404)

    def log_message(self, *args):
        pass


class _SinkHandler(BaseHTTPRequestHandler):
    """Webhook sink: records POSTs; behavior from server.mode."""

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        srv = self.server
        srv.received.append(json.loads(body.decode("utf-8")))
        mode = getattr(srv, "mode", "ok")
        count = len(srv.received)
        if mode == "fail-always":
            self.send_response(500)
        elif mode == "flaky" and count <= 2:
            self.send_response(503)
        else:
            self.send_response(204)
        self.end_headers()

    def log_message(self, *args):
        pass


def start_sink() -> tuple[ThreadingHTTPServer, str]:
    srv, url = free_port_server(_SinkHandler)
    srv.received = []          # type: ignore[attr-defined]
    srv.mode = "ok"            # type: ignore[attr-defined]
    return srv, url


def start_files() -> tuple[ThreadingHTTPServer, str]:
    return free_port_server(_DownloadHandler)


def stop_server(srv: ThreadingHTTPServer) -> None:
    srv.shutdown()
    srv.server_close()


class OutboxTestCase(unittest.TestCase):
    """Base case with an isolated temp DATA_DIR, no background workers."""

    allow_private = True       # loopback fixtures need the documented override
    attachment_bytes = None    # per-file cap override (None -> default 10 MiB)
    message_bytes = None       # per-message cap override
    download_timeout = 2.0
    max_handoff_url_length = 1800

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="outbox-test-")
        root = pathlib.Path(self._tmp.name)
        self.cfg = Config(
            data_dir=root / "data",
            attachment_dir=root / "data" / "attachments",
            allow_private_urls=self.allow_private,
            webhook_backoff_base_seconds=0.15,
            webhook_timeout_seconds=0.5,
            download_timeout_seconds=self.download_timeout,
            max_attachment_bytes=self.attachment_bytes or 10 * 1024 * 1024,
            max_message_attachment_bytes=self.message_bytes or 25 * 1024 * 1024,
            max_handoff_url_length=self.max_handoff_url_length,
        )
        self.app = create_app(self.cfg, start_background=False)
        self.ctx = self.app.ctx
        self.client = self.app.test_client()
        self.addCleanup(self._tmp.cleanup)

    # -- convenience ----------------------------------------------------------

    def submit(self, **fields):
        base = {"channel": "email", "destination": "user@example.com",
                "body": "Hello there."}
        base.update(fields)
        res = self.client.post("/api/messages", json=base)
        self.assertIn(res.status_code, (200, 201), res.get_json())
        return res

    def submit_id(self, **fields) -> str:
        return self.submit(**fields).get_json()["id"]

    def get_msg(self, mid):
        return self.client.get(f"/api/messages/{mid}").get_json()

    def assertApiError(self, res, code, status):
        self.assertEqual(res.status_code, status, res.get_json())
        body = res.get_json()
        self.assertEqual(body.get("error"), code, body)
        self.assertTrue(body.get("message"))
