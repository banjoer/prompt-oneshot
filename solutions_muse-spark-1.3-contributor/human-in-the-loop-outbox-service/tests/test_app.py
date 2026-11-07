import io
import json
import os
import shutil
import socket
import tempfile
import threading
import time
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class CapturingSink(BaseHTTPRequestHandler):
    store = []
    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(n)
        CapturingSink.store.append({"path": self.path, "body": body})
        self.send_response(204)
        self.end_headers()
    def log_message(self, *a):
        pass


class FileHandler(BaseHTTPRequestHandler):
    payload = b"hello-download-content"
    def do_GET(self):
        if self.path == "/sample.txt":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(FileHandler.payload)))
            self.end_headers()
            self.wfile.write(FileHandler.payload)
        elif self.path == "/redir":
            self.send_response(302)
            self.send_header("Location", "/sample.txt")
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, *a):
        pass


import importlib

TMP = None
appmod = None


def setUpModule():
    global TMP, appmod
    TMP = tempfile.mkdtemp(prefix="outbox-test-")
    data = os.path.join(TMP, "data")
    att = os.path.join(TMP, "data", "attachments")
    os.environ["DATA_DIR"] = data
    os.environ["ATTACHMENT_DIR"] = att
    os.environ["ALLOW_PRIVATE_URLS"] = "1"
    os.environ["WEBHOOK_TIMEOUT_SECONDS"] = "2"
    os.environ["WEBHOOK_MAX_ATTEMPTS"] = "3"
    os.environ["WEBHOOK_BACKOFF_BASE_SECONDS"] = "0"
    os.environ["DOWNLOAD_TIMEOUT_SECONDS"] = "5"
    os.environ["EXPIRATION_INTERVAL_SECONDS"] = "3600"
    import app as m
    appmod = importlib.reload(m)
    appmod.CONFIG["ALLOW_PRIVATE_URLS"] = True
    appmod.CONFIG["WEBHOOK_BACKOFF_BASE_SECONDS"] = 0
    appmod.init_db()


def tearDownModule():
    shutil.rmtree(TMP, ignore_errors=True)


def make_client():
    appmod.app.config["TESTING"] = True
    return appmod.app.test_client()


def submit(client, payload):
    return client.post("/api/messages", json=payload)


def wait_for(cond, timeout=8.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if cond():
            return True
        time.sleep(0.05)
    return cond()


class Base(unittest.TestCase):
    def setUp(self):
        # wipe db between tests
        conn = appmod.get_db()
        for t in ("webhook_attempts", "webhook_events", "attachments", "msg_refs",
                  "revisions", "status_history", "messages", "destination_labels"):
            conn.execute(f"DELETE FROM {t}")
        conn.commit()
        conn.close()
        for f in os.listdir(appmod.CONFIG["ATTACHMENT_DIR"]):
            try:
                os.remove(os.path.join(appmod.CONFIG["ATTACHMENT_DIR"], f))
            except Exception:
                pass


class TestSubmission(Base):
    def test_email_json(self):
        c = make_client()
        r = submit(c, {"channel": "email", "destination": "alex@example.com",
                       "subject": "Q4 report draft", "body": "Hi Alex,\nreview please",
                       "source": "report-agent", "metadata": {"ticket": "OPS-142"}})
        self.assertEqual(r.status_code, 201)
        j = r.get_json()
        self.assertIn("id", j)
        self.assertEqual(j["status"], "pending")
        self.assertEqual(j["revision_number"], 1)
        g = c.get(f"/api/messages/{j['id']}")
        self.assertEqual(g.status_code, 200)
        m = g.get_json()
        self.assertEqual(m["destination"], "alex@example.com")
        self.assertEqual(m["metadata"], {"ticket": "OPS-142"})

    def test_expiry_absolute_and_ttl(self):
        c = make_client()
        r = submit(c, {"channel": "email", "destination": "a@b.com", "body": "x",
                       "expires_at": "2030-01-01T00:00:00Z"})
        self.assertEqual(r.status_code, 201)
        r = submit(c, {"channel": "email", "destination": "a@b.com", "body": "x", "ttl_seconds": 3600})
        self.assertEqual(r.status_code, 201)
        r = submit(c, {"channel": "email", "destination": "a@b.com", "body": "x",
                       "ttl_seconds": 10, "expires_at": "2030-01-01T00:00:00Z"})
        self.assertEqual(r.status_code, 400)
        r = submit(c, {"channel": "email", "destination": "a@b.com", "body": "x", "ttl_seconds": -3})
        self.assertEqual(r.status_code, 400)
        r = submit(c, {"channel": "email", "destination": "a@b.com", "body": "x",
                       "expires_at": "2000-01-01T00:00:00Z"})
        self.assertEqual(r.status_code, 400)

    def test_invalid_destination(self):
        c = make_client()
        for ch, dest in (("email", "not-an-email"), ("whatsapp", "abc"),
                         ("telegram", "!!!"), ("sms", "x"), ("email", "")):
            r = submit(c, {"channel": ch, "destination": dest, "body": "hi"})
            self.assertIn(r.status_code, (400,), f"{ch}/{dest}")

    def test_empty_body_rejected(self):
        c = make_client()
        r = submit(c, {"channel": "email", "destination": "a@b.com", "body": "  "})
        self.assertEqual(r.status_code, 400)

    def test_metadata_must_be_object(self):
        c = make_client()
        r = submit(c, {"channel": "email", "destination": "a@b.com", "body": "x", "metadata": [1]})
        self.assertEqual(r.status_code, 400)

    def test_references_must_be_list(self):
        c = make_client()
        r = submit(c, {"channel": "email", "destination": "a@b.com", "body": "x", "references": "nope"})
        self.assertEqual(r.status_code, 400)

    def test_malformed_json(self):
        c = make_client()
        r = c.post("/api/messages", data="{bad json", content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_missing_message_404(self):
        c = make_client()
        self.assertEqual(c.get("/api/messages/msg_nope").status_code, 404)
        self.assertEqual(c.get("/api/messages/msg_nope/history").status_code, 404)

    def test_multipart_upload(self):
        c = make_client()
        r = c.post("/api/messages", data={
            "channel": "email", "destination": "alex@example.com",
            "subject": "s", "body": "b",
            "attachments": (io.BytesIO(b"hello file"), "sample.txt")},
            content_type="multipart/form-data")
        self.assertEqual(r.status_code, 201)
        mid = r.get_json()["id"]
        g = c.get(f"/api/messages/{mid}")
        self.assertEqual(g.get_json()["attachment_count"], 1)
        att = g.get_json()["attachments"][0]
        d = c.get(f"/api/messages/{mid}/attachments/{att['id']}")
        self.assertEqual(d.status_code, 200)
        self.assertEqual(d.data, b"hello file")
        self.assertIn("attachment", d.headers.get("Content-Disposition", ""))
        self.assertEqual(d.headers.get("X-Content-Type-Options"), "nosniff")


class TestListing(Base):
    def _seed(self, c):
        ids = []
        for i, ch in enumerate(["email", "whatsapp", "telegram"]):
            dest = ["u%d@example.com" % i, "+1415555000%d" % i, "@user%dabc" % i][i]
            r = submit(c, {"channel": ch, "destination": dest, "body": f"body {i} {ch}"})
            ids.append(r.get_json()["id"])
            time.sleep(0.01)
        return ids

    def test_pagination_sort_filter(self):
        c = make_client()
        self._seed(c)
        j = c.get("/api/messages?limit=2&offset=0").get_json()
        self.assertEqual(j["limit"], 2)
        self.assertEqual(j["total"], 3)
        self.assertEqual(len(j["items"]), 2)
        newest = c.get("/api/messages?sort=newest").get_json()["items"]
        oldest = c.get("/api/messages?sort=oldest").get_json()["items"]
        self.assertEqual(newest[0]["id"], oldest[-1]["id"])
        by_ch = c.get("/api/messages?channel=email").get_json()
        self.assertTrue(all(m["channel"] == "email" for m in by_ch["items"]))
        by_dest = c.get("/api/messages?destination=1415555").get_json()
        self.assertTrue(len(by_dest["items"]) >= 1)
        lim = c.get("/api/messages?limit=999").get_json()
        self.assertLessEqual(lim["limit"], 100)

    def test_expiry_sort_nonexpiry_last(self):
        c = make_client()
        r1 = submit(c, {"channel": "email", "destination": "a@b.com", "body": "noexp"})
        r2 = submit(c, {"channel": "email", "destination": "b@b.com", "body": "exp", "ttl_seconds": 3600})
        soon = c.get("/api/messages?sort=expires_soon").get_json()["items"]
        self.assertEqual(soon[0]["id"], r2.get_json()["id"])
        late = c.get("/api/messages?sort=expires_late").get_json()["items"]
        self.assertEqual(late[0]["id"], r2.get_json()["id"])
        self.assertEqual(late[-1]["id"], r1.get_json()["id"])

    def test_default_newest(self):
        c = make_client()
        self._seed(c)
        j = c.get("/api/messages").get_json()
        ts = [m["created_at"] for m in j["items"]]
        self.assertEqual(ts, sorted(ts, reverse=True))


class TestLifecycle(Base):
    def test_approve_handoff_no_autosend(self):
        c = make_client()
        mid = submit(c, {"channel": "email", "destination": "alex@example.com",
                         "subject": "Hi", "body": "Hello world"}).get_json()["id"]
        self.assertEqual(c.post(f"/api/messages/{mid}/approve").status_code, 200)
        h = c.get(f"/api/messages/{mid}/handoff").get_json()
        self.assertTrue(h["handoff_url"].startswith("mailto:"))
        self.assertIn("alex@example.com", h["handoff_url"])
        # handoff + listing must not change status
        self.assertEqual(c.get(f"/api/messages/{mid}").get_json()["status"], "approved")

    def test_reject_requires_reason(self):
        c = make_client()
        mid = submit(c, {"channel": "email", "destination": "a@b.com", "body": "x"}).get_json()["id"]
        self.assertEqual(c.post(f"/api/messages/{mid}/reject", json={}).status_code, 400)
        self.assertEqual(c.post(f"/api/messages/{mid}/reject", json={"reason": " "}).status_code, 400)
        r = c.post(f"/api/messages/{mid}/reject", json={"reason": "wrong name"})
        self.assertEqual(r.status_code, 200)
        m = c.get(f"/api/messages/{mid}").get_json()
        self.assertEqual(m["status"], "rejected")
        self.assertEqual(m["rejection_reason"], "wrong name")

    def test_mark_sent_flow(self):
        c = make_client()
        mid = submit(c, {"channel": "email", "destination": "a@b.com", "body": "x"}).get_json()["id"]
        self.assertEqual(c.post(f"/api/messages/{mid}/mark-sent").status_code, 409)
        c.post(f"/api/messages/{mid}/approve")
        self.assertEqual(c.post(f"/api/messages/{mid}/mark-sent").status_code, 200)
        self.assertEqual(c.post(f"/api/messages/{mid}/mark-sent").status_code, 409)
        self.assertEqual(c.post(f"/api/messages/{mid}/approve").status_code, 409)

    def test_cancel_and_terminal_immutable(self):
        c = make_client()
        mid = submit(c, {"channel": "email", "destination": "a@b.com", "body": "x"}).get_json()["id"]
        self.assertEqual(c.post(f"/api/messages/{mid}/cancel", json={}).status_code, 200)
        self.assertEqual(c.patch(f"/api/messages/{mid}", json={"body": "y"}).status_code, 409)
        self.assertEqual(c.post(f"/api/messages/{mid}/approve").status_code, 409)

    def test_patch_status_rejected(self):
        c = make_client()
        mid = submit(c, {"channel": "email", "destination": "a@b.com", "body": "x"}).get_json()["id"]
        self.assertEqual(c.patch(f"/api/messages/{mid}", json={"status": "approved", "body": "y"}).status_code, 400)

    def test_revision_flow(self):
        c = make_client()
        mid = submit(c, {"channel": "email", "destination": "a@b.com", "subject": "v1", "body": "one"}).get_json()["id"]
        c.post(f"/api/messages/{mid}/reject", json={"reason": "fix it"})
        r = c.patch(f"/api/messages/{mid}", json={"subject": "v2", "body": "two fixed"})
        self.assertEqual(r.status_code, 200)
        m = r.get_json()
        self.assertEqual(m["id"], mid)
        self.assertEqual(m["revision_number"], 2)
        self.assertEqual(m["status"], "pending")
        self.assertIsNone(m["rejection_reason"])
        h = c.get(f"/api/messages/{mid}/history").get_json()
        self.assertEqual(len(h["revisions"]), 2)
        self.assertEqual(h["revisions"][0]["body"], "one")
        self.assertEqual(h["revisions"][0]["rejection_reason"], "fix it")
        self.assertTrue(any(t["to_status"] == "rejected" for t in h["transitions"]))
        # pending PATCH keeps pending, bumps rev
        r2 = c.patch(f"/api/messages/{mid}", json={"body": "three"})
        self.assertEqual(r2.get_json()["revision_number"], 3)
        self.assertEqual(r2.get_json()["status"], "pending")

    def test_patch_approved_409(self):
        c = make_client()
        mid = submit(c, {"channel": "email", "destination": "a@b.com", "body": "x"}).get_json()["id"]
        c.post(f"/api/messages/{mid}/approve")
        self.assertEqual(c.patch(f"/api/messages/{mid}", json={"body": "y"}).status_code, 409)

    def test_concurrent_approve_single_winner(self):
        c = make_client()
        mid = submit(c, {"channel": "email", "destination": "a@b.com", "body": "x"}).get_json()["id"]
        results = []
        bar = threading.Barrier(2)
        def go():
            cc = make_client()
            bar.wait()
            results.append(cc.post(f"/api/messages/{mid}/approve").status_code)
        ts = [threading.Thread(target=go) for _ in range(2)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertIn(200, results)
        self.assertIn(409, results)
        conn = appmod.get_db()
        n = conn.execute("SELECT COUNT(*) AS c FROM status_history WHERE message_id=? AND to_status='approved'", (mid,)).fetchone()["c"]
        conn.close()
        self.assertEqual(n, 1)


class TestExpiration(Base):
    def test_ttl_expires(self):
        c = make_client()
        mid = submit(c, {"channel": "email", "destination": "a@b.com", "body": "x", "ttl_seconds": 1}).get_json()["id"]
        time.sleep(1.3)
        m = c.get(f"/api/messages/{mid}").get_json()
        self.assertEqual(m["status"], "stale")
        self.assertEqual(c.post(f"/api/messages/{mid}/approve").status_code, 409)
        self.assertEqual(c.get(f"/api/messages/{mid}/handoff").status_code, 409)

    def test_approved_expires(self):
        c = make_client()
        mid = submit(c, {"channel": "email", "destination": "a@b.com", "body": "x", "ttl_seconds": 1}).get_json()["id"]
        c.post(f"/api/messages/{mid}/approve")
        time.sleep(1.3)
        m = c.get(f"/api/messages/{mid}").get_json()
        self.assertEqual(m["status"], "stale")

    def test_no_expiry_stays(self):
        c = make_client()
        mid = submit(c, {"channel": "email", "destination": "a@b.com", "body": "x"}).get_json()["id"]
        m = c.get(f"/api/messages/{mid}").get_json()
        self.assertEqual(m["status"], "pending")

    def test_approval_race_never_approved(self):
        c = make_client()
        mid = submit(c, {"channel": "email", "destination": "a@b.com", "body": "x", "ttl_seconds": 1}).get_json()["id"]
        time.sleep(1.2)
        r = c.post(f"/api/messages/{mid}/approve")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(c.get(f"/api/messages/{mid}").get_json()["status"], "stale")

    def test_patch_clears_expiry(self):
        c = make_client()
        mid = submit(c, {"channel": "email", "destination": "a@b.com", "body": "x", "ttl_seconds": 60}).get_json()["id"]
        r = c.patch(f"/api/messages/{mid}", json={"expires_at": None})
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.get_json()["expires_at"])


class TestChannels(unittest.TestCase):
    def test_whatsapp_individual(self):
        from app import build_handoff
        h = build_handoff({"channel": "whatsapp", "destination": "+1 (415) 555-0123",
                           "destination_norm": "+14155550123", "subject": "", "body": "hi there"})
        self.assertTrue(h["handoff_url"].startswith("https://wa.me/14155550123?text="))

    def test_whatsapp_group_fallback(self):
        from app import build_handoff
        h = build_handoff({"channel": "whatsapp", "destination": "group:Project Alpha",
                           "destination_norm": "group:project alpha", "subject": "", "body": "standup"})
        self.assertIn("WhatsApp", h["handoff_url"] + "".join(h["manual_actions"]))
        self.assertFalse(h["capabilities"]["prefill_recipient"])
        self.assertTrue(any("presel" in w.lower() or "fallback" in w.lower() or "no " in w.lower() or "cannot" in w.lower() or "manual" in w.lower()
                            for w in h["warnings"] + h["manual_actions"]))

    def test_telegram_individual(self):
        from app import build_handoff
        h = build_handoff({"channel": "telegram", "destination": "@alex_example",
                           "destination_norm": "@alex_example", "subject": "", "body": "build done"})
        self.assertIn("t.me", h["handoff_url"])

    def test_telegram_group_fallback(self):
        from app import build_handoff
        h = build_handoff({"channel": "telegram", "destination": "group:Ops Room",
                           "destination_norm": "group:ops room", "subject": "", "body": "deploy live"})
        self.assertTrue(h["handoff_url"].startswith("https://"))
        self.assertFalse(h["capabilities"]["prefill_recipient"])

    def test_encoding(self):
        c = make_client()
        mid = submit(c, {"channel": "whatsapp", "destination": "+14155550123",
                         "body": "héllo & bye\nline2 😀"}).get_json()["id"]
        c.post(f"/api/messages/{mid}/approve")
        h = c.get(f"/api/messages/{mid}/handoff").get_json()
        raw = urllib.parse.unquote(urllib.parse.urlparse(h["handoff_url"]).query)
        self.assertIn("héllo & bye\nline2 😀", raw)

    def test_long_body_fallback(self):
        c = make_client()
        big = "A" * 5000
        mid = submit(c, {"channel": "email", "destination": "a@b.com", "subject": "S", "body": big}).get_json()["id"]
        c.post(f"/api/messages/{mid}/approve")
        h = c.get(f"/api/messages/{mid}/handoff").get_json()
        self.assertLessEqual(len(h["handoff_url"]), 1800)
        self.assertTrue(len(h["warnings"]) >= 1)
        self.assertEqual(h["body"], big)


class TestAttachmentsRefs(Base):
    @classmethod
    def setUpClass(cls):
        cls.file_srv = HTTPServer(("127.0.0.1", 0), FileHandler)
        cls.file_port = cls.file_srv.server_address[1]
        cls.t = threading.Thread(target=cls.file_srv.serve_forever, daemon=True)
        cls.t.start()

    @classmethod
    def tearDownClass(cls):
        cls.file_srv.shutdown()

    def setUp(self):
        conn = appmod.get_db()
        for t in ("webhook_attempts", "webhook_events", "attachments", "msg_refs",
                  "revisions", "status_history", "messages", "destination_labels"):
            conn.execute(f"DELETE FROM {t}")
        conn.commit()
        conn.close()

    def test_url_reference_not_downloaded(self):
        c = make_client()
        r = submit(c, {"channel": "email", "destination": "a@b.com", "subject": "s", "body": "b",
                       "references": ["https://example.com/spec"]})
        self.assertEqual(r.status_code, 201)
        m = c.get(f"/api/messages/{r.get_json()['id']}").get_json()
        self.assertIn("https://example.com/spec", m["references"])
        self.assertEqual(m["attachment_count"], 0)

    def test_url_download(self):
        c = make_client()
        url = f"http://127.0.0.1:{self.file_port}/sample.txt"
        r = submit(c, {"channel": "email", "destination": "a@b.com", "subject": "s", "body": "b",
                       "attachments": [{"kind": "url_download", "url": url, "filename": "sample.txt"}]})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        m = c.get(f"/api/messages/{r.get_json()['id']}").get_json()
        self.assertEqual(m["attachment_count"], 1)
        att = m["attachments"][0]
        d = c.get(f"/api/messages/{m['id']}/attachments/{att['id']}")
        self.assertEqual(d.data, FileHandler.payload)

    def test_traversal_filename_safe(self):
        c = make_client()
        r = c.post("/api/messages", data={"channel": "email", "destination": "a@b.com", "body": "x",
                   "attachments": (io.BytesIO(b"evil"), "../../evil.txt")},
                   content_type="multipart/form-data")
        self.assertEqual(r.status_code, 201)
        m = c.get(f"/api/messages/{r.get_json()['id']}").get_json()
        fn = m["attachments"][0]["filename"]
        self.assertNotIn("..", fn)
        self.assertNotIn("/", fn)
        att = m["attachments"][0]
        d = c.get(f"/api/messages/{m['id']}/attachments/{att['id']}")
        self.assertEqual(d.status_code, 200)

    def test_missing_attachment_404(self):
        c = make_client()
        mid = submit(c, {"channel": "email", "destination": "a@b.com", "body": "x"}).get_json()["id"]
        self.assertEqual(c.get(f"/api/messages/{mid}/attachments/nope").status_code, 404)

    def test_size_limit(self):
        c = make_client()
        old = appmod.CONFIG["MAX_ATTACHMENT_BYTES"]
        appmod.CONFIG["MAX_ATTACHMENT_BYTES"] = 100
        try:
            r = c.post("/api/messages", data={"channel": "email", "destination": "a@b.com", "body": "x",
                       "attachments": (io.BytesIO(b"z" * 200), "big.bin")},
                       content_type="multipart/form-data")
            self.assertEqual(r.status_code, 413)
        finally:
            appmod.CONFIG["MAX_ATTACHMENT_BYTES"] = old

    def test_ssrf_blocked_by_default(self):
        c = make_client()
        old = appmod.CONFIG["ALLOW_PRIVATE_URLS"]
        appmod.CONFIG["ALLOW_PRIVATE_URLS"] = False
        try:
            r = submit(c, {"channel": "email", "destination": "a@b.com", "body": "x",
                           "webhook_url": "http://127.0.0.1:9/hooks"})
            self.assertEqual(r.status_code, 400)
            url = f"http://127.0.0.1:{self.file_port}/sample.txt"
            r2 = submit(c, {"channel": "email", "destination": "a@b.com", "body": "x",
                            "attachments": [{"kind": "url_download", "url": url}]})
            self.assertEqual(r2.status_code, 400)
            r3 = submit(c, {"channel": "email", "destination": "a@b.com", "body": "x",
                            "webhook_url": "http://169.254.169.254/latest"})
            self.assertEqual(r3.status_code, 400)
        finally:
            appmod.CONFIG["ALLOW_PRIVATE_URLS"] = old

    def test_invalid_webhook_url(self):
        c = make_client()
        r = submit(c, {"channel": "email", "destination": "a@b.com", "body": "x",
                       "webhook_url": "ftp://example.com/hook"})
        self.assertEqual(r.status_code, 400)


class TestWebhooks(Base):
    @classmethod
    def setUpClass(cls):
        CapturingSink.store = []
        cls.srv = HTTPServer(("127.0.0.1", 0), CapturingSink)
        cls.port = cls.srv.server_address[1]
        cls.t = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.t.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        CapturingSink.store = []
        conn = appmod.get_db()
        for t in ("webhook_attempts", "webhook_events", "attachments", "msg_refs",
                  "revisions", "status_history", "messages", "destination_labels"):
            conn.execute(f"DELETE FROM {t}")
        conn.commit()
        conn.close()

    def _hook(self):
        return f"http://127.0.0.1:{self.port}/hooks/outbox"

    def test_full_lifecycle_events(self):
        c = make_client()
        mid = submit(c, {"channel": "email", "destination": "a@b.com", "body": "x",
                         "webhook_url": self._hook()}).get_json()["id"]
        c.post(f"/api/messages/{mid}/approve")
        c.post(f"/api/messages/{mid}/mark-sent")
        ok = wait_for(lambda: len(CapturingSink.store) >= 2, timeout=8)
        self.assertTrue(ok, CapturingSink.store)
        bodies = [json.loads(x["body"]) for x in CapturingSink.store]
        events = {b["event"] for b in bodies}
        self.assertIn("message.approved", events)
        self.assertIn("message.sent", events)
        ev = c.get(f"/api/messages/{mid}/webhook-events").get_json()["events"]
        self.assertTrue(any(e["event"] == "message.approved" for e in ev))
        # no duplicate on failed repeat
        n0 = len(ev)
        c.post(f"/api/messages/{mid}/approve")
        ev2 = c.get(f"/api/messages/{mid}/webhook-events").get_json()["events"]
        self.assertEqual(len(ev2), n0)

    def test_rejected_and_revised_events(self):
        c = make_client()
        mid = submit(c, {"channel": "email", "destination": "a@b.com", "body": "x",
                         "webhook_url": self._hook()}).get_json()["id"]
        c.post(f"/api/messages/{mid}/reject", json={"reason": "bad"})
        c.patch(f"/api/messages/{mid}", json={"body": "fixed"})
        ok = wait_for(lambda: len(CapturingSink.store) >= 2, timeout=8)
        self.assertTrue(ok)
        bodies = [json.loads(x["body"]) for x in CapturingSink.store]
        self.assertIn("message.rejected", {b["event"] for b in bodies})
        self.assertIn("message.revised", {b["event"] for b in bodies})
        rej = [b for b in bodies if b["event"] == "message.rejected"][0]
        self.assertEqual(rej["rejection_reason"], "bad")

    def test_failure_no_rollback(self):
        c = make_client()
        bad = "http://127.0.0.1:1/nope"
        mid = submit(c, {"channel": "email", "destination": "a@b.com", "body": "x",
                         "webhook_url": bad}).get_json()["id"]
        r = c.post(f"/api/messages/{mid}/approve")
        self.assertEqual(r.status_code, 200)
        ok = wait_for(lambda: len(c.get(f"/api/messages/{mid}/webhook-events").get_json()["events"]) >= 1
                      and len(c.get(f"/api/messages/{mid}/webhook-events").get_json()["events"][0]["attempts"]) >= 3,
                      timeout=12)
        self.assertTrue(ok)
        ev = c.get(f"/api/messages/{mid}/webhook-events").get_json()["events"][0]
        self.assertTrue(all(a["success"] == 0 for a in ev["attempts"]))

    def test_no_webhook_still_works(self):
        c = make_client()
        mid = submit(c, {"channel": "email", "destination": "a@b.com", "body": "x"}).get_json()["id"]
        self.assertEqual(c.post(f"/api/messages/{mid}/approve").status_code, 200)
        ev = c.get(f"/api/messages/{mid}/webhook-events").get_json()["events"]
        self.assertEqual(ev, [])


class TestLabels(Base):
    def test_discover_assign_duplicate_remove(self):
        c = make_client()
        submit(c, {"channel": "email", "destination": "Alex@Example.com", "body": "hi"})
        submit(c, {"channel": "email", "destination": "other@example.com", "body": "hi"})
        ds = c.get("/api/destinations").get_json()["destinations"]
        self.assertTrue(any(d["normalized_destination"] == "alex@example.com" for d in ds))
        r = c.put("/api/destinations/label",
                  json={"channel": "email", "destination": "alex@example.com", "label": "Alex — Client"})
        self.assertEqual(r.status_code, 200)
        r2 = c.put("/api/destinations/label",
                   json={"channel": "email", "destination": "other@example.com", "label": "Alex — Client"})
        self.assertEqual(r2.status_code, 409)
        # rename ok
        r3 = c.put("/api/destinations/label",
                   json={"channel": "email", "destination": "alex@example.com", "label": "Alex VIP"})
        self.assertEqual(r3.status_code, 200)
        # reuse after new message
        submit(c, {"channel": "email", "destination": "alex@example.com", "body": "again"})
        ds2 = c.get("/api/destinations").get_json()["destinations"]
        alex = [d for d in ds2 if d["normalized_destination"] == "alex@example.com"][0]
        self.assertEqual(alex["label"], "Alex VIP")
        self.assertEqual(alex["message_count"], 2)
        # remove keeps messages
        self.assertEqual(c.delete("/api/destinations/label?channel=email&destination=alex@example.com").status_code, 200)
        total = c.get("/api/messages?destination=alex").get_json()["total"]
        self.assertEqual(total, 2)
        # empty label rejected
        self.assertEqual(c.put("/api/destinations/label",
                               json={"channel": "email", "destination": "a@b.com", "label": "  "}).status_code, 400)


class TestSurface(unittest.TestCase):
    def test_health_info_docs_openapi(self):
        c = make_client()
        self.assertEqual(c.get("/api/health").status_code, 200)
        info = c.get("/api/info").get_json()
        self.assertIn("max_attachment_bytes", info["config"])
        self.assertNotIn("DATA_DIR", json.dumps(info))
        spec = c.get("/openapi.json").get_json()
        self.assertTrue(spec["openapi"].startswith("3."))
        self.assertIn("/api/messages", spec["paths"])
        docs = c.get("/api/docs")
        self.assertEqual(docs.status_code, 200)
        self.assertIn(b"/api/messages", docs.data)
        spa = c.get("/")
        self.assertEqual(spa.status_code, 200)
        self.assertIn(b"Built 2026", spa.data)


if __name__ == "__main__":
    unittest.main()
