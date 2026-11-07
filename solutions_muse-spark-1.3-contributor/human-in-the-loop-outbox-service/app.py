# Built 2026-11-06 23:33 UTC by muse-spark-1.3-contributor (Muse Spark 1.3 Contributor)
"""Human-in-the-Loop Outbox Service.

Single-process Flask + SQLite service. Serves REST API and vanilla SPA.
No provider API integration; handoff links only. Never sends anything itself.
"""
import ipaddress
import json
import mimetypes
import os
import re
import secrets
import socket
import sqlite3
import threading
import time
import urllib.parse
import urllib.request
import uuid
import zipfile
from datetime import datetime, timezone, timedelta
from html import escape
from io import BytesIO

from flask import Flask, jsonify, request, send_file, Response, g

# ---------------------------------------------------------------- config

def _int_env(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default

def load_config():
    return {
        "DATA_DIR": os.environ.get("DATA_DIR", "./data"),
        "ATTACHMENT_DIR": os.environ.get("ATTACHMENT_DIR", "./data/attachments"),
        "MAX_ATTACHMENT_BYTES": _int_env("MAX_ATTACHMENT_BYTES", 10 * 1024 * 1024),
        "MAX_MESSAGE_ATTACHMENT_BYTES": _int_env("MAX_MESSAGE_ATTACHMENT_BYTES", 25 * 1024 * 1024),
        "EXPIRATION_INTERVAL_SECONDS": _int_env("EXPIRATION_INTERVAL_SECONDS", 30),
        "WEBHOOK_TIMEOUT_SECONDS": _int_env("WEBHOOK_TIMEOUT_SECONDS", 5),
        "WEBHOOK_MAX_ATTEMPTS": _int_env("WEBHOOK_MAX_ATTEMPTS", 3),
        "WEBHOOK_BACKOFF_BASE_SECONDS": _int_env("WEBHOOK_BACKOFF_BASE_SECONDS", 1),
        "DOWNLOAD_TIMEOUT_SECONDS": _int_env("DOWNLOAD_TIMEOUT_SECONDS", 10),
        "MAX_REDIRECTS": _int_env("MAX_REDIRECTS", 3),
        "ALLOW_PRIVATE_URLS": os.environ.get("ALLOW_PRIVATE_URLS", "0") == "1",
        "PORT": _int_env("PORT", 8000),
    }

CONFIG = load_config()

def refresh_config():
    global CONFIG
    CONFIG = load_config()
    return CONFIG

VALID_CHANNELS = ("email", "whatsapp", "telegram")
VALID_STATUSES = ("pending", "approved", "sent", "rejected", "stale", "cancelled")
# allowed explicit transitions via operations (stale only via expiration)
ALLOWED = {
    "pending": {"approved", "rejected", "cancelled", "stale"},
    "rejected": {"pending", "cancelled"},  # pending only via PATCH revision
    "approved": {"sent", "cancelled", "stale"},
    "sent": set(),
    "stale": set(),
    "cancelled": set(),
}
TERMINAL = ("sent", "stale", "cancelled")
MAILTO_LIMIT = 1800

# ---------------------------------------------------------------- helpers

def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def parse_iso(s):
    if not isinstance(s, str):
        return None
    t = s.strip()
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(t)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def to_iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

def new_msg_id():
    return "msg_" + secrets.token_hex(6)

def new_att_id():
    return "att_" + secrets.token_hex(6)

def db_path():
    return os.path.join(CONFIG["DATA_DIR"], "outbox.db")

def get_db():
    conn = sqlite3.connect(db_path(), timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn

def init_db():
    os.makedirs(CONFIG["DATA_DIR"], exist_ok=True)
    os.makedirs(CONFIG["ATTACHMENT_DIR"], exist_ok=True)
    conn = get_db()
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            channel TEXT NOT NULL,
            destination TEXT NOT NULL,
            destination_norm TEXT NOT NULL,
            destination_label TEXT,
            subject TEXT,
            body TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            expires_at TEXT,
            webhook_url TEXT,
            rejection_reason TEXT,
            rejection_at TEXT,
            revision_number INTEGER NOT NULL DEFAULT 1,
            source TEXT,
            metadata TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status);
        CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel);
        CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);
        CREATE INDEX IF NOT EXISTS idx_messages_expires ON messages(expires_at);
        CREATE TABLE IF NOT EXISTS revisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
            revision_number INTEGER NOT NULL,
            channel TEXT NOT NULL,
            destination TEXT NOT NULL,
            subject TEXT,
            body TEXT NOT NULL,
            expires_at TEXT,
            refs TEXT,
            metadata TEXT,
            attachment_ids TEXT,
            rejection_reason TEXT,
            rejection_at TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(message_id, revision_number)
        );
        CREATE TABLE IF NOT EXISTS status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
            from_status TEXT NOT NULL,
            to_status TEXT NOT NULL,
            reason TEXT,
            revision_number INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_history_msg ON status_history(message_id);
        CREATE TABLE IF NOT EXISTS attachments (
            id TEXT PRIMARY KEY,
            message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
            revision_number INTEGER NOT NULL DEFAULT 1,
            filename TEXT NOT NULL,
            mime TEXT NOT NULL,
            size INTEGER NOT NULL,
            storage TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            source_type TEXT NOT NULL DEFAULT 'multipart',
            source_url TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_att_msg ON attachments(message_id);
        CREATE TABLE IF NOT EXISTS msg_refs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
            revision_number INTEGER NOT NULL DEFAULT 1,
            url TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS destination_labels (
            channel TEXT NOT NULL,
            norm TEXT NOT NULL,
            label TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (channel, norm)
        );
        CREATE TABLE IF NOT EXISTS webhook_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
            event TEXT NOT NULL,
            status TEXT NOT NULL,
            revision_number INTEGER NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(message_id, event, revision_number)
        );
        CREATE TABLE IF NOT EXISTS webhook_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL REFERENCES webhook_events(id) ON DELETE CASCADE,
            attempt_number INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            success INTEGER NOT NULL DEFAULT 0,
            http_status INTEGER,
            error TEXT
        );
        """)
        conn.commit()
    finally:
        conn.close()

# ---------------------------------------------------------------- errors

def err(message, code="bad_request", http=400, extra=None):
    body = {"error": {"code": code, "message": message}}
    if extra:
        body["error"].update(extra)
    return jsonify(body), http

# ---------------------------------------------------------------- channel adapters

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def normalize_destination(channel, dest):
    dest = (dest or "").strip()
    if channel == "email":
        return dest.lower()
    if channel == "whatsapp":
        d = dest.strip()
        if d.lower().startswith("group:"):
            name = d.split(":", 1)[1].strip()
            return "group:" + re.sub(r"\s+", " ", name).lower()
        digits = re.sub(r"\D", "", d)
        if d.startswith("+"):
            return "+" + digits
        return digits
    if channel == "telegram":
        d = dest.strip()
        if d.lower().startswith("group:"):
            name = d.split(":", 1)[1].strip()
            return "group:" + re.sub(r"\s+", " ", name).lower()
        # t.me links / invite links
        m = re.match(r"^(?:https?://)?(?:www\.)?t\.me/(.+?)\s*$", d, re.I)
        if m:
            rest = m.group(1).strip().strip("/")
            if rest.startswith("+") or rest.startswith("joinchat/"):
                return "tme-invite:" + rest.lower()
            uname = rest.split("/")[0].split("?")[0]
            if uname.startswith("@"):
                uname = uname[1:]
            return "@" + uname.lower()
        if d.startswith("@"):
            return "@" + d[1:].strip().lower()
        return d.lower()
    return dest

def validate_destination(channel, dest):
    if not dest or not str(dest).strip():
        return False, "", "destination is required"
    d = str(dest).strip()
    if channel == "email":
        if not EMAIL_RE.match(d):
            return False, "", "invalid email destination (expected name@example.com)"
        return True, d.lower(), ""
    if channel == "whatsapp":
        if d.lower().startswith("group:"):
            name = d.split(":", 1)[1].strip()
            if not name:
                return False, "", "invalid WhatsApp group destination (expected 'group:Name')"
            if len(name) > 200:
                return False, "", "WhatsApp group name too long"
            return True, "group:" + re.sub(r"\s+", " ", name).lower(), ""
        digits = re.sub(r"\D", "", d)
        if len(digits) < 7 or len(digits) > 15:
            return False, "", "invalid WhatsApp destination (expected international phone digits or 'group:Name')"
        norm = ("+" + digits) if d.strip().startswith("+") else digits
        return True, norm, ""
    if channel == "telegram":
        if d.lower().startswith("group:"):
            name = d.split(":", 1)[1].strip()
            if not name:
                return False, "", "invalid Telegram group destination"
            return True, "group:" + re.sub(r"\s+", " ", name).lower(), ""
        m = re.match(r"^(?:https?://)?(?:www\.)?t\.me/(.+?)\s*$", d, re.I)
        if m:
            return True, normalize_destination(channel, d), ""
        if re.match(r"^@[A-Za-z0-9_]{5,64}$", d):
            return True, "@" + d[1:].lower(), ""
        # invite links passed raw
        if "joinchat" in d or d.strip().startswith("https://t.me/+"):
            return True, normalize_destination(channel, d), ""
        return False, "", "invalid Telegram destination (expected @username, t.me/ link, or 'group:Name')"
    return False, "", "unknown channel"

def build_handoff(msg):
    """msg: dict-like row. Returns handoff dict. Never mutates state."""
    channel = msg["channel"]
    dest = msg["destination"]
    norm = msg.get("destination_norm") or normalize_destination(channel, dest)
    subject = msg.get("subject") or ""
    body = msg.get("body") or ""
    atts = msg.get("_attachments") or []
    has_atts = len(atts) > 0
    if channel == "email":
        base = "mailto:" + urllib.parse.quote(dest.strip(), safe="@._-+")
        params = []
        if subject:
            params.append("subject=" + urllib.parse.quote(subject, safe=""))
        if body:
            params.append("body=" + urllib.parse.quote(body, safe=""))
        full = base + ("?" + "&".join(params) if params else "")
        warnings = []
        handoff_url = full
        if len(full) > MAILTO_LIMIT:
            short = base + (("?subject=" + urllib.parse.quote(subject, safe="")) if subject else "")
            handoff_url = short
            warnings.append(f"Body too long for a mailto: link ({len(full)} chars exceeds ~{MAILTO_LIMIT}). Opened link includes recipient and subject only; copy the body from the app.")
        caps = {"prefill_recipient": True, "prefill_subject": True, "prefill_body": len(full) <= MAILTO_LIMIT, "attachments_supported": False}
        manual = ["Click the handoff link to open your mail app with recipient/subject/body prefilled."]
        if has_atts:
            manual.append("Download each attachment below and attach the files to the email manually — mailto: links cannot carry attachments.")
        manual += ["Copy subject/body with the copy buttons if needed, then send from your own mail app."]
        return {"channel": channel, "destination": dest, "normalized_destination": norm,
                "handoff_url": handoff_url, "full_url_length": len(full),
                "capabilities": caps, "manual_actions": manual, "warnings": warnings,
                "subject": subject, "body": body,
                "subject_available": bool(subject), "body_available": True}
    if channel == "whatsapp":
        if norm.startswith("group:"):
            gname = dest.split(":", 1)[1].strip() if ":" in dest else dest
            text = urllib.parse.quote(body, safe="")
            url = "https://web.whatsapp.com/"
            return {"channel": channel, "destination": dest, "normalized_destination": norm,
                    "handoff_url": url, "group": gname,
                    "capabilities": {"prefill_recipient": False, "prefill_subject": False, "prefill_body": False, "attachments_supported": False},
                    "manual_actions": [f"Open WhatsApp and navigate to the group \u201c{gname}\u201d manually.",
                                       "Copy the message body with the copy button and paste it into the group chat.",
                                       "Download attachments below and share them into the group manually as documents/photos."],
                    "warnings": ["WhatsApp has no URL mechanism to preselect a group or prefill a group message. This fallback only opens WhatsApp; group selection and paste are manual."],
                    "subject": subject, "body": body, "body_available": True}
        digits = re.sub(r"\D", "", norm)
        url = "https://wa.me/" + digits + "?text=" + urllib.parse.quote(body, safe="")
        warnings = []
        if len(url) > 4000:
            warnings.append("Message is very long; if WhatsApp truncates it, copy the body from the app instead.")
        manual = ["Click the handoff link to open a chat with the number and prefilled text."]
        if has_atts:
            manual.append("Download attachments below and share them into the chat manually.")
        manual.append("Press send inside WhatsApp yourself.")
        return {"channel": channel, "destination": dest, "normalized_destination": norm,
                "handoff_url": url,
                "capabilities": {"prefill_recipient": True, "prefill_subject": False, "prefill_body": True, "attachments_supported": False},
                "manual_actions": manual, "warnings": warnings,
                "subject": subject, "body": body, "body_available": True}
    # telegram
    if norm.startswith("group:"):
        gname = dest.split(":", 1)[1].strip() if ":" in dest else dest
        return {"channel": channel, "destination": dest, "normalized_destination": norm,
                "handoff_url": "https://web.telegram.org/",
                "group": gname,
                "capabilities": {"prefill_recipient": False, "prefill_subject": False, "prefill_body": False, "attachments_supported": False},
                "manual_actions": [f"Open Telegram and navigate to the group \u201c{gname}\u201d manually.",
                                   "Copy the message body with the copy button and paste it into the group.",
                                   "Download attachments below and share them into the group manually."],
                "warnings": ["Telegram has no URL mechanism to preselect an arbitrary group or prefill its input. This fallback only opens Telegram Web; group selection and paste are manual. No public username is assumed."],
                "subject": subject, "body": body, "body_available": True}
    if norm.startswith("tme-invite:"):
        return {"channel": channel, "destination": dest, "normalized_destination": norm,
                "handoff_url": "https://web.telegram.org/",
                "capabilities": {"prefill_recipient": False, "prefill_subject": False, "prefill_body": False, "attachments_supported": False},
                "manual_actions": ["Open the invite link from your own Telegram app to reach the private chat/group.",
                                   "Copy the message body with the copy button and paste it manually.",
                                   "Download attachments below and share them manually."],
                "warnings": ["Private invite destinations cannot be preselected or prefilled via URL. Join via your Telegram app first, then paste manually."],
                "subject": subject, "body": body, "body_available": True}
    uname = norm[1:] if norm.startswith("@") else norm
    url = "https://t.me/" + uname
    if body:
        # t.me direct chat links do not support prefilled text; offer share fallback info
        url_with_text = "https://t.me/share/url?url=&text=" + urllib.parse.quote(body, safe="")
        return {"channel": channel, "destination": dest, "normalized_destination": norm,
                "handoff_url": url,
                "share_url": url_with_text,
                "capabilities": {"prefill_recipient": True, "prefill_subject": False, "prefill_body": False, "attachments_supported": False},
                "manual_actions": [f"Click the handoff link to open the chat with @{uname} in Telegram.",
                                   "Copy the message body with the copy button and paste it into the chat (direct t.me links cannot prefill message text).",
                                   "Download attachments below and share them into the chat manually."],
                "warnings": ["Telegram direct-chat links open the conversation but cannot prefill message text. Pasting the body is a required manual step."],
                "subject": subject, "body": body, "body_available": True}
    return {"channel": channel, "destination": dest, "normalized_destination": norm,
            "handoff_url": url,
            "capabilities": {"prefill_recipient": True, "prefill_subject": False, "prefill_body": False, "attachments_supported": False},
            "manual_actions": ["Open the chat link, then paste the body manually."],
            "warnings": [], "subject": subject, "body": body, "body_available": True}

# ---------------------------------------------------------------- SSRF / urls

CLOUD_METADATA_IPS = {"169.254.169.254"}

def _host_blocked(host):
    if not host:
        return True
    h = host.strip().lower().strip("[]")
    if h in ("localhost",):
        return True
    if CLOUD_METADATA_IPS and h in CLOUD_METADATA_IPS:
        return True
    try:
        ip = ipaddress.ip_address(h)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(h, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM)
    except Exception:
        return True  # unresolvable -> block
    addrs = set()
    for _fam, _typ, _proto, _canon, sockaddr in infos:
        addrs.add(sockaddr[0])
    if not addrs:
        return True
    for a in addrs:
        a0 = a.strip("[]")
        if a0 in CLOUD_METADATA_IPS:
            return True
        try:
            ip = ipaddress.ip_address(a0)
        except ValueError:
            return True
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved:
            return True
    return False

def validate_outbound_url(url):
    if not url or not isinstance(url, str):
        return False, "URL is required"
    u = url.strip()
    try:
        p = urllib.parse.urlparse(u)
    except Exception:
        return False, "malformed URL"
    if p.scheme not in ("http", "https"):
        return False, "URL must use http(s)"
    if not p.hostname:
        return False, "URL must include a host"
    if not CONFIG["ALLOW_PRIVATE_URLS"]:
        if _host_blocked(p.hostname):
            return False, "URL target is blocked (loopback/private/link-local/metadata). Set ALLOW_PRIVATE_URLS=1 only for local testing."
    return True, ""

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def fetch_url_bytes(url, timeout, max_redirects, max_bytes):
    current = url
    for _i in range(max_redirects + 1):
        ok, why = validate_outbound_url(current)
        if not ok:
            raise ValueError(why)
        req = urllib.request.Request(current, headers={"User-Agent": "outbox-service/1.0"})
        opener = urllib.request.build_opener(_NoRedirect)
        try:
            resp = opener.open(req, timeout=timeout)
            status = getattr(resp, "status", 200) or 200
            data = resp.read(max_bytes + 1)
            ctype = resp.headers.get("Content-Type", "application/octet-stream").split(";")[0].strip() or "application/octet-stream"
            if len(data) > max_bytes:
                raise ValueError("downloaded file exceeds per-file size limit")
            return bytes(data), ctype
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308):
                loc = e.headers.get("Location")
                if not loc:
                    raise ValueError("redirect without Location")
                current = urllib.parse.urljoin(current, loc)
                continue
            raise ValueError(f"download failed with HTTP {e.code}")
    raise ValueError("too many redirects")

# ---------------------------------------------------------------- attachments

WINDOWS_RESERVED = {"con", "prn", "aux", "nul", "com1", "com2", "com3", "com4", "com5",
                    "com6", "com7", "com8", "com9", "lpt1", "lpt2", "lpt3", "lpt4",
                    "lpt5", "lpt6", "lpt7", "lpt8", "lpt9"}

def sanitize_filename(name):
    if not name:
        return "file"
    base = os.path.basename(str(name).replace("\\", "/"))
    base = re.sub(r"[\x00-\x1f\x7f]", "", base)
    base = base.strip().strip(".")
    if not base:
        base = "file"
    if base.lower() in WINDOWS_RESERVED or base.lower().split(".")[0] in WINDOWS_RESERVED:
        base = "_" + base
    base = base[:200] or "file"
    return base

def guess_mime(filename, declared=None):
    if declared and declared != "application/octet-stream":
        return declared
    g, _ = mimetypes.guess_type(filename)
    return g or declared or "application/octet-stream"

def store_attachment_bytes(conn, message_id, revision_number, original_name, data, mime, source_type, source_url=None):
    if len(data) > CONFIG["MAX_ATTACHMENT_BYTES"]:
        raise ValueError("attachment exceeds per-file size limit")
    safe = sanitize_filename(original_name)
    att_id = new_att_id()
    stored = att_id + "_" + safe
    # never use client filename as storage path; prefix with id
    full = os.path.join(CONFIG["ATTACHMENT_DIR"], stored)
    # traversal guard
    if os.path.commonpath([os.path.abspath(full), os.path.abspath(CONFIG["ATTACHMENT_DIR"])]) != os.path.abspath(CONFIG["ATTACHMENT_DIR"]):
        raise ValueError("unsafe storage path")
    with open(full, "wb") as f:
        f.write(data)
    conn.execute("""INSERT INTO attachments (id, message_id, revision_number, filename, mime, size, storage, uploaded_at, source_type, source_url)
                    VALUES (?,?,?,?,?,?,?,?,?,?)""",
                 (att_id, message_id, revision_number, safe, mime or "application/octet-stream",
                  len(data), stored, now_iso(), source_type, source_url))
    return att_id

def message_total_bytes(conn, message_id):
    r = conn.execute("SELECT COALESCE(SUM(size),0) AS s FROM attachments WHERE message_id=?", (message_id,)).fetchone()
    return int(r["s"] or 0)

# ---------------------------------------------------------------- serialization

def row_to_dict(r):
    d = dict(r)
    return d

def get_attachments(conn, message_id):
    rows = conn.execute("SELECT * FROM attachments WHERE message_id=? ORDER BY uploaded_at ASC", (message_id,)).fetchall()
    return [dict(x) for x in rows]

def get_refs(conn, message_id):
    rows = conn.execute("SELECT url FROM msg_refs WHERE message_id=? ORDER BY id ASC", (message_id,)).fetchall()
    return [x["url"] for x in rows]

def serialize_message(conn, msg_row, include_full=True):
    m = dict(msg_row)
    atts = get_attachments(conn, m["id"])
    refs = get_refs(conn, m["id"])
    md = None
    if m.get("metadata"):
        try:
            md = json.loads(m["metadata"])
        except Exception:
            md = None
    # managed label lookup
    label_row = conn.execute("SELECT label FROM destination_labels WHERE channel=? AND norm=?",
                             (m["channel"], m["destination_norm"])).fetchone()
    managed = label_row["label"] if label_row else None
    out = {
        "id": m["id"], "channel": m["channel"], "destination": m["destination"],
        "destination_norm": m["destination_norm"],
        "destination_label": m.get("destination_label"),
        "label": managed, "managed_label": managed,
        "subject": m.get("subject"), "body": m["body"], "status": m["status"],
        "created_at": m["created_at"], "updated_at": m["updated_at"],
        "expires_at": m.get("expires_at"), "webhook_url": m.get("webhook_url"),
        "rejection_reason": m.get("rejection_reason"), "rejection_at": m.get("rejection_at"),
        "revision_number": m["revision_number"], "source": m.get("source"),
        "metadata": md, "references": refs,
        "attachment_count": len(atts),
    }
    if include_full:
        out["attachments"] = [{"id": a["id"], "filename": a["filename"], "mime": a["mime"],
                               "size": a["size"], "uploaded_at": a["uploaded_at"],
                               "source_type": a["source_type"], "source_url": a.get("source_url")} for a in atts]
    return out

# ---------------------------------------------------------------- expiration + webhooks

def _insert_status_history(conn, message_id, frm, to, reason, rev):
    conn.execute("""INSERT INTO status_history (message_id, from_status, to_status, reason, revision_number, created_at)
                    VALUES (?,?,?,?,?,?)""", (message_id, frm, to, reason, rev, now_iso()))

def queue_webhook_event(conn, message_id, event, status, revision_number, extra=None):
    row = conn.execute("SELECT webhook_url FROM messages WHERE id=?", (message_id,)).fetchone()
    url = (row["webhook_url"] if row and row["webhook_url"] else None)
    if extra is None:
        extra = {}
    payload = {"event": event, "message_id": message_id, "status": status,
               "revision_number": revision_number, "timestamp": now_iso()}
    payload.update(extra)
    if not url:
        # still record? spec says persist every event; but without URL there is no delivery.
        # Record nothing when no webhook configured (API remains usable).
        return None
    ok, why = validate_outbound_url(url)
    if not ok:
        # record event with failed validation so UI can show it
        try:
            cur = conn.execute("""INSERT OR IGNORE INTO webhook_events (message_id, event, status, revision_number, payload, created_at)
                                  VALUES (?,?,?,?,?,?)""",
                               (message_id, event, status, revision_number, json.dumps(payload), now_iso()))
            eid = cur.lastrowid
            if eid:
                conn.execute("""INSERT INTO webhook_attempts (event_id, attempt_number, started_at, finished_at, success, error)
                                VALUES (?,?,?,?,?,?)""", (eid, 1, now_iso(), now_iso(), 0, "invalid webhook URL: " + why))
            return eid
        except Exception:
            return None
    cur = conn.execute("""INSERT OR IGNORE INTO webhook_events (message_id, event, status, revision_number, payload, created_at)
                          VALUES (?,?,?,?,?,?)""",
                       (message_id, event, status, revision_number, json.dumps(payload), now_iso()))
    if cur.rowcount == 0:
        return None  # duplicate (idempotency)
    eid = cur.lastrowid
    return eid

def _deliver_event(event_id):
    conn = get_db()
    try:
        ev = conn.execute("SELECT * FROM webhook_events WHERE id=?", (event_id,)).fetchone()
        if not ev:
            return
        msg = conn.execute("SELECT webhook_url FROM messages WHERE id=?", (ev["message_id"],)).fetchone()
        url = msg["webhook_url"] if msg and msg["webhook_url"] else None
        if not url:
            return
        ok, why = validate_outbound_url(url)
        if not ok:
            conn.execute("""INSERT INTO webhook_attempts (event_id, attempt_number, started_at, finished_at, success, error)
                            VALUES (?,?,?,?,?,?)""", (event_id, 1, now_iso(), now_iso(), 0, "invalid webhook URL: " + why))
            conn.commit()
            return
        payload = ev["payload"].encode("utf-8")
        max_attempts = CONFIG["WEBHOOK_MAX_ATTEMPTS"]
        base = CONFIG["WEBHOOK_BACKOFF_BASE_SECONDS"]
        timeout = CONFIG["WEBHOOK_TIMEOUT_SECONDS"]
        n_prev = conn.execute("SELECT COUNT(*) AS c FROM webhook_attempts WHERE event_id=?", (event_id,)).fetchone()["c"]
        for i in range(n_prev + 1, max_attempts + 1):
            started = now_iso()
            try:
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "User-Agent": "outbox-service/1.0"})
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    code = getattr(resp, "status", 200) or 200
                conn.execute("""INSERT INTO webhook_attempts (event_id, attempt_number, started_at, finished_at, success, http_status)
                                VALUES (?,?,?,?,?,?)""", (event_id, i, started, now_iso(), 1, code))
                conn.commit()
                return
            except Exception as e:
                conn.execute("""INSERT INTO webhook_attempts (event_id, attempt_number, started_at, finished_at, success, error)
                                VALUES (?,?,?,?,?,?)""", (event_id, i, started, now_iso(), 0, str(e)[:500]))
                conn.commit()
                if i < max_attempts:
                    time.sleep(min(base * (2 ** (i - 1)), 10))
    finally:
        try:
            conn.close()
        except Exception:
            pass

def deliver_event_async(event_id):
    if not event_id:
        return
    t = threading.Thread(target=_deliver_event, args=(event_id,), daemon=True)
    t.start()

def expire_message_if_needed(conn, msg_row):
    """Assumes caller holds transaction. Returns True if transitioned to stale."""
    m = dict(msg_row)
    if m["status"] not in ("pending", "approved"):
        return False
    if not m.get("expires_at"):
        return False
    exp = parse_iso(m["expires_at"])
    if not exp:
        return False
    if datetime.now(timezone.utc) < exp:
        return False
    now = now_iso()
    cur = conn.execute("UPDATE messages SET status='stale', updated_at=? WHERE id=? AND status IN ('pending','approved')",
                       (now, m["id"]))
    if cur.rowcount == 0:
        return False
    _insert_status_history(conn, m["id"], m["status"], "stale", "expired", m["revision_number"])
    queue_webhook_event(conn, m["id"], "message.stale", "stale", m["revision_number"], {"reason": "expired", "expires_at": m["expires_at"]})
    return True

def run_expiration_sweep():
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM messages WHERE status IN ('pending','approved') AND expires_at IS NOT NULL").fetchall()
        changed = []
        for r in rows:
            try:
                if expire_message_if_needed(conn, r):
                    ev = conn.execute("SELECT id FROM webhook_events WHERE message_id=? AND event='message.stale' AND revision_number=?",
                                      (r["id"], r["revision_number"])).fetchone()
                    changed.append((r["id"], ev["id"] if ev else None))
            except Exception:
                continue
        conn.commit()
        for _mid, eid in changed:
            if eid:
                deliver_event_async(eid)
    finally:
        conn.close()

def expiration_loop():
    while True:
        try:
            time.sleep(max(CONFIG["EXPIRATION_INTERVAL_SECONDS"], 1))
            run_expiration_sweep()
        except Exception:
            continue

# ---------------------------------------------------------------- flask app

app = Flask(__name__, static_folder=None)

@app.before_request
def _open_db():
    g.db = get_db()

@app.teardown_request
def _close_db(exc):
    d = getattr(g, "db", None)
    if d is not None:
        try:
            d.close()
        except Exception:
            pass

def _expire_on_read(message_id):
    """Re-read + expire single message; returns fresh row or None. Commits if expired."""
    conn = g.db
    row = conn.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
    if not row:
        return None
    if expire_message_if_needed(conn, row):
        conn.commit()
        eid = conn.execute("SELECT id FROM webhook_events WHERE message_id=? AND event='message.stale' AND revision_number=?",
                           (row["id"], row["revision_number"])).fetchone()
        if eid:
            deliver_event_async(eid["id"])
        row = conn.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
    return row

def _sweep_visible(conn):
    rows = conn.execute("SELECT * FROM messages WHERE status IN ('pending','approved') AND expires_at IS NOT NULL").fetchall()
    fired = []
    for r in rows:
        if expire_message_if_needed(conn, r):
            ev = conn.execute("SELECT id FROM webhook_events WHERE message_id=? AND event='message.stale' AND revision_number=?",
                              (r["id"], r["revision_number"])).fetchone()
            fired.append(ev["id"] if ev else None)
    if fired:
        conn.commit()
    for eid in fired:
        if eid:
            deliver_event_async(eid)

def _parse_expiry(data, for_patch=False):
    has_abs = "expires_at" in data and data["expires_at"] is not None
    has_ttl = "ttl_seconds" in data and data["ttl_seconds"] is not None
    if ("expires_at" in data and "ttl_seconds" in data and data["expires_at"] is not None and data["ttl_seconds"] is not None):
        return None, err("expires_at and ttl_seconds are mutually exclusive", http=400)
    if has_ttl:
        ttl = data["ttl_seconds"]
        if isinstance(ttl, bool) or not isinstance(ttl, int) or ttl <= 0:
            try:
                ttl = int(ttl)
            except Exception:
                return None, err("ttl_seconds must be a positive integer", http=400)
            if ttl <= 0:
                return None, err("ttl_seconds must be a positive integer", http=400)
        exp = datetime.now(timezone.utc) + timedelta(seconds=ttl)
        return to_iso(exp), None
    if "expires_at" in data:
        v = data["expires_at"]
        if v is None:
            return None, None  # cleared (PATCH) / none
        if not isinstance(v, str):
            return None, err("expires_at must be an ISO 8601 string", http=400)
        dt = parse_iso(v)
        if not dt:
            return None, err("expires_at must be a valid ISO 8601 timestamp", http=400)
        if dt <= datetime.now(timezone.utc):
            return None, err("expires_at must be in the future", http=400)
        return to_iso(dt), None
    return "UNCHANGED", None

def _extract_submit_fields():
    """Returns (data_dict, files_list, error_response)."""
    ctype = request.content_type or ""
    if "multipart/form-data" in ctype:
        f = request.form
        data = {
            "channel": f.get("channel"),
            "destination": f.get("destination"),
            "subject": f.get("subject"),
            "body": f.get("body"),
            "expires_at": f.get("expires_at"),
            "source": f.get("source"),
            "destination_label": f.get("destination_label"),
            "webhook_url": f.get("webhook_url"),
        }
        # ttl_seconds
        if f.get("ttl_seconds") not in (None, ""):
            try:
                data["ttl_seconds"] = int(f.get("ttl_seconds"))
            except ValueError:
                data["ttl_seconds"] = f.get("ttl_seconds")
        # metadata may be JSON string
        if f.get("metadata") not in (None, ""):
            try:
                data["metadata"] = json.loads(f.get("metadata"))
            except Exception:
                return None, None, err("metadata must be a JSON object", http=400)
        # references may be repeated or JSON
        refs = f.getlist("references")
        if len(refs) == 1 and refs[0].strip().startswith("["):
            try:
                data["references"] = json.loads(refs[0])
            except Exception:
                data["references"] = refs
        elif refs:
            data["references"] = refs
        # drop Nones
        data = {k: v for k, v in data.items() if v is not None}
        # normalize empty-string expires_at to None (clear)
        files = request.files.getlist("attachments")
        return data, files, None
    if request.data and not request.is_json and ctype and "json" not in ctype and ctype.startswith("text/"):
        return None, None, err("unsupported media type: use application/json or multipart/form-data", code="unsupported_media", http=415)
    try:
        data = request.get_json(force=False, silent=False) if request.data else {}
    except Exception:
        return None, None, err("malformed JSON body", http=400)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        return None, None, err("JSON body must be an object", http=400)
    if "status" in data:
        pass  # only PATCH rejects status; submit ignores? reject to be safe? spec only says PATCH. Allow ignore.
    return data, [], None

# ---------------- health/info/docs

@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "time": now_iso()})

@app.get("/api/info")
def info():
    return jsonify({"config": {
        "max_attachment_bytes": CONFIG["MAX_ATTACHMENT_BYTES"],
        "max_message_attachment_bytes": CONFIG["MAX_MESSAGE_ATTACHMENT_BYTES"],
        "expiration_interval_seconds": CONFIG["EXPIRATION_INTERVAL_SECONDS"],
        "webhook_timeout_seconds": CONFIG["WEBHOOK_TIMEOUT_SECONDS"],
        "webhook_max_attempts": CONFIG["WEBHOOK_MAX_ATTEMPTS"],
        "webhook_backoff_base_seconds": CONFIG["WEBHOOK_BACKOFF_BASE_SECONDS"],
        "download_timeout_seconds": CONFIG["DOWNLOAD_TIMEOUT_SECONDS"],
        "max_redirects": CONFIG["MAX_REDIRECTS"],
        "allow_private_urls": CONFIG["ALLOW_PRIVATE_URLS"],
        "port": CONFIG["PORT"],
        "channels": list(VALID_CHANNELS),
        "statuses": list(VALID_STATUSES),
    }})

@app.get("/openapi.json")
def openapi_json():
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "openapi.json"), "r", encoding="utf-8") as f:
            return Response(f.read(), mimetype="application/json")
    except FileNotFoundError:
        return err("openapi.json not found", code="not_found", http=404)

@app.get("/api/docs")
def api_docs():
    try:
        base = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(base, "openapi.json"), "r", encoding="utf-8") as f:
            spec = json.load(f)
    except Exception:
        spec = {}
    paths = spec.get("paths", {}) if isinstance(spec, dict) else {}
    rows = []
    for p, ops in sorted(paths.items()):
        if not isinstance(ops, dict):
            continue
        for method, op in ops.items():
            summary = ""
            if isinstance(op, dict):
                summary = op.get("summary", "")
            rows.append(f"<tr><td><code>{escape(method.upper())}</code></td><td><code>{escape(p)}</code></td><td>{escape(str(summary))}</td></tr>")
    html = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Outbox API Docs</title><style>body{font-family:system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:.4rem .6rem;text-align:left;font-size:.9rem}code{background:#f4f4f4;padding:.1rem .3rem}</style></head>
<body><h1>Human-in-the-Loop Outbox — API Docs</h1>
<p>Rendered locally from <a href="/openapi.json">/openapi.json</a>. No external assets. The service never sends messages itself; reviewers send via handoff links.</p>
<table><thead><tr><th>Method</th><th>Path</th><th>Summary</th></tr></thead><tbody>""" + "\n".join(rows) + """</tbody></table>
<p><a href="/">Back to dashboard</a></p></body></html>"""
    return Response(html, mimetype="text/html")

# ---------------- messages: create

@app.post("/api/messages")
def create_message():
    data, files, e = _extract_submit_fields()
    if e:
        return e
    channel = (data.get("channel") or "").strip().lower()
    if channel not in VALID_CHANNELS:
        return err("channel must be one of email, whatsapp, telegram", http=400)
    dest = data.get("destination", "")
    if not isinstance(dest, str):
        return err("destination must be a string", http=400)
    ok, norm, why = validate_destination(channel, dest)
    if not ok:
        return err(why, http=400)
    subject = data.get("subject")
    if subject is not None and not isinstance(subject, str):
        return err("subject must be a string", http=400)
    body = data.get("body", "")
    if not isinstance(body, str) or not body.strip():
        return err("body is required and must be non-empty", http=400)
    if len(body) > 200000:
        return err("body too long", http=413)
    # metadata
    metadata = data.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        return err("metadata must be a JSON object", http=400)
    # references
    refs = data.get("references", [])
    if refs is None:
        refs = []
    if not isinstance(refs, list) or any(not isinstance(x, str) for x in refs):
        return err("references must be a list of URL strings", http=400)
    # webhook
    webhook_url = data.get("webhook_url")
    if webhook_url is not None:
        if not isinstance(webhook_url, str) or not webhook_url.strip():
            return err("webhook_url must be a non-empty string", http=400)
        okw, whyw = validate_outbound_url(webhook_url.strip())
        if not okw:
            return err("invalid webhook_url: " + whyw, http=400)
        webhook_url = webhook_url.strip()
    # source / label
    source = data.get("source")
    if source is not None and not isinstance(source, str):
        return err("source must be a string", http=400)
    dlabel = data.get("destination_label")
    if dlabel is not None and not isinstance(dlabel, str):
        return err("destination_label must be a string", http=400)
    # expiry
    exp_val, ee = _parse_expiry(data)
    if ee:
        return ee
    expires_at = None if exp_val in (None, "UNCHANGED") else exp_val
    # json attachments (url kinds)
    json_atts = data.get("attachments", [])
    if json_atts is None:
        json_atts = []
    ctype = request.content_type or ""
    if "multipart" not in ctype and json_atts is not None and not isinstance(json_atts, list):
        return err("attachments must be a list", http=400)
    for a in (json_atts or []):
        if not isinstance(a, dict) or a.get("kind") not in ("url_reference", "url_download") or not isinstance(a.get("url"), str):
            return err("each attachment must have kind url_reference|url_download and a url", http=400)

    conn = g.db
    mid = new_msg_id()
    now = now_iso()
    try:
        conn.execute("""INSERT INTO messages (id, channel, destination, destination_norm, destination_label, subject, body, status, created_at, updated_at, expires_at, webhook_url, revision_number, source, metadata)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                     (mid, channel, dest.strip(), norm, (dlabel.strip() if isinstance(dlabel, str) and dlabel.strip() else None),
                      subject, body, "pending", now, now, expires_at, webhook_url, 1, source,
                      json.dumps(metadata) if metadata is not None else None))
        # refs
        for u in refs:
            conn.execute("INSERT INTO msg_refs (message_id, revision_number, url) VALUES (?,?,?)", (mid, 1, u))
        # json attachments
        for a in (json_atts or []):
            kind = a["kind"]; url = a["url"].strip()
            if kind == "url_reference":
                conn.execute("INSERT INTO msg_refs (message_id, revision_number, url) VALUES (?,?,?)", (mid, 1, url))
            else:
                try:
                    blob, ctype2 = fetch_url_bytes(url, CONFIG["DOWNLOAD_TIMEOUT_SECONDS"], CONFIG["MAX_REDIRECTS"], CONFIG["MAX_ATTACHMENT_BYTES"])
                except ValueError as ve:
                    msg_low = str(ve).lower()
                    conn.rollback()
                    if "exceeds" in msg_low or "too large" in msg_low:
                        return err(str(ve), http=413)
                    if "blocked" in msg_low:
                        return err(str(ve), http=400)
                    return err("failed to download attachment: " + str(ve), http=400)
                fname = a.get("filename") or os.path.basename(urllib.parse.urlparse(url).path) or "download"
                if message_total_bytes(conn, mid) + len(blob) > CONFIG["MAX_MESSAGE_ATTACHMENT_BYTES"]:
                    conn.rollback()
                    return err("message attachment total exceeds limit", http=413)
                store_attachment_bytes(conn, mid, 1, fname, blob, guess_mime(fname, ctype2), "url_download", url)
        # multipart files
        for fs in (files or []):
            if not fs or not fs.filename:
                continue
            blob = fs.read(CONFIG["MAX_ATTACHMENT_BYTES"] + 1)
            if len(blob) > CONFIG["MAX_ATTACHMENT_BYTES"]:
                conn.rollback()
                return err(f"attachment {fs.filename} exceeds per-file size limit", http=413)
            if message_total_bytes(conn, mid) + len(blob) > CONFIG["MAX_MESSAGE_ATTACHMENT_BYTES"]:
                conn.rollback()
                return err("message attachment total exceeds limit", http=413)
            store_attachment_bytes(conn, mid, 1, fs.filename, blob, guess_mime(fs.filename, fs.mimetype), "multipart", None)
        # revision snapshot
        att_ids = [r["id"] for r in conn.execute("SELECT id FROM attachments WHERE message_id=?", (mid,)).fetchall()]
        conn.execute("""INSERT INTO revisions (message_id, revision_number, channel, destination, subject, body, expires_at, refs, metadata, attachment_ids, created_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                     (mid, 1, channel, dest.strip(), subject, body, expires_at, json.dumps(refs),
                      json.dumps(metadata) if metadata is not None else None, json.dumps(att_ids), now))
        _insert_status_history(conn, mid, "pending", "pending", "created", 1)
        conn.commit()
    except Exception as ex:
        try:
            conn.rollback()
        except Exception:
            pass
        return err("failed to create message: " + str(ex)[:300], http=500)
    row = conn.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()
    return jsonify({"id": mid, "status": "pending", "created_at": row["created_at"], "revision_number": 1}), 201

# ---------------- list / get

@app.get("/api/messages")
def list_messages():
    conn = g.db
    _sweep_visible(conn)
    q = request.args
    status = q.get("status")
    channel = q.get("channel")
    destf = q.get("destination")
    sort = q.get("sort", "newest")
    try:
        limit = int(q.get("limit", "20"))
    except ValueError:
        return err("limit must be an integer", http=400)
    try:
        offset = int(q.get("offset", "0"))
    except ValueError:
        return err("offset must be an integer", http=400)
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    where = []
    params = []
    if status and status != "all":
        if status not in VALID_STATUSES:
            return err("invalid status filter", http=400)
        where.append("m.status = ?"); params.append(status)
    if channel:
        if channel not in VALID_CHANNELS:
            return err("invalid channel filter", http=400)
        where.append("m.channel = ?"); params.append(channel)
    if destf:
        where.append("(LOWER(m.destination) LIKE ? OR LOWER(COALESCE(m.destination_label,'')) LIKE ? OR LOWER(COALESCE(l.label,'')) LIKE ?)")
        like = "%" + destf.lower() + "%"
        params += [like, like, like]
    def _date_param(*names):
        for n in names:
            v = q.get(n)
            if v:
                return v
        return None
    cf = _date_param("created_from", "created_after", "created_since")
    ct = _date_param("created_to", "created_before", "created_until")
    ef = _date_param("expires_from", "expires_after", "expires_since")
    et = _date_param("expires_to", "expires_before", "expires_until")
    for v, col, op in ((cf, "m.created_at", ">="), (ct, "m.created_at", "<="), (ef, "m.expires_at", ">="), (et, "m.expires_at", "<=")):
        if v:
            if not parse_iso(v):
                return err(f"invalid date filter value: {v}", http=400)
            where.append(f"{col} {op} ?"); params.append(v)
    join = "LEFT JOIN destination_labels l ON l.channel = m.channel AND l.norm = m.destination_norm"
    wsql = ("WHERE " + " AND ".join(where)) if where else ""
    total = conn.execute(f"SELECT COUNT(*) AS c FROM messages m {join} {wsql}", params).fetchone()["c"]
    if sort == "oldest":
        order = "m.created_at ASC"
    elif sort == "expires_soon":
        order = "CASE WHEN m.expires_at IS NULL THEN 1 ELSE 0 END, m.expires_at ASC, m.created_at DESC"
    elif sort == "expires_late":
        order = "CASE WHEN m.expires_at IS NULL THEN 1 ELSE 0 END, m.expires_at DESC, m.created_at DESC"
    else:
        order = "m.created_at DESC"
    rows = conn.execute(f"SELECT m.* FROM messages m {join} {wsql} ORDER BY {order} LIMIT ? OFFSET ?", (*params, limit, offset)).fetchall()
    items = []
    for r in rows:
        s = serialize_message(conn, r, include_full=False)
        items.append(s)
    return jsonify({"items": items, "total": total, "limit": limit, "offset": offset})

@app.get("/api/messages/<mid>")
def get_message(mid):
    row = _expire_on_read(mid)
    if not row:
        return err("message not found", code="not_found", http=404)
    return jsonify(serialize_message(g.db, row, include_full=True))

@app.get("/api/messages/<mid>/history")
def get_history(mid):
    conn = g.db
    row = _expire_on_read(mid)
    if not row:
        return err("message not found", code="not_found", http=404)
    revs = conn.execute("SELECT * FROM revisions WHERE message_id=? ORDER BY revision_number ASC", (mid,)).fetchall()
    hist = conn.execute("SELECT * FROM status_history WHERE message_id=? ORDER BY id ASC", (mid,)).fetchall()
    out_revs = []
    for r in revs:
        d = dict(r)
        for k in ("refs", "metadata", "attachment_ids"):
            try:
                d[k] = json.loads(d[k]) if d[k] else ([] if k != "metadata" else None)
            except Exception:
                pass
        out_revs.append(d)
    return jsonify({"message_id": mid, "revisions": out_revs,
                    "transitions": [dict(h) for h in hist]})

# ---------------- lifecycle ops

def _transition(mid, to_status, reason=None, event=None, extra=None):
    conn = g.db
    row = _expire_on_read(mid)
    if not row:
        return err("message not found", code="not_found", http=404), None
    cur = dict(row)
    frm = cur["status"]
    if to_status not in ALLOWED.get(frm, set()):
        allowed = sorted(ALLOWED.get(frm, set()))
        return err(f"invalid transition from {frm} to {to_status}", code="conflict", http=409,
                   extra={"status": frm, "allowed": allowed}), None
    now = now_iso()
    upd = conn.execute("UPDATE messages SET status=?, updated_at=? WHERE id=? AND status=?", (to_status, now, mid, frm))
    if upd.rowcount == 0:
        fresh = conn.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()
        fs = fresh["status"] if fresh else frm
        return err(f"conflicting transition (current status: {fs})", code="conflict", http=409,
                   extra={"status": fs, "allowed": sorted(ALLOWED.get(fs, set()))}), None
    if to_status == "rejected":
        conn.execute("UPDATE messages SET rejection_reason=?, rejection_at=? WHERE id=?", (reason, now, mid))
    if to_status in ("approved", "sent", "cancelled"):
        pass
    _insert_status_history(conn, mid, frm, to_status, reason, cur["revision_number"])
    eid = None
    if event:
        eid = queue_webhook_event(conn, mid, event, to_status, cur["revision_number"], extra or {})
    conn.commit()
    if eid:
        deliver_event_async(eid)
    fresh = conn.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()
    return None, fresh

@app.post("/api/messages/<mid>/approve")
def approve(mid):
    e, fresh = _transition(mid, "approved", reason="approved", event="message.approved")
    if e:
        return e
    return jsonify(serialize_message(g.db, fresh))

@app.post("/api/messages/<mid>/reject")
def reject(mid):
    try:
        data = request.get_json(force=False, silent=True) or {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        return err("malformed JSON body", http=400)
    # also accept form-encoded reason
    reason = data.get("reason") if isinstance(data, dict) else None
    if reason is None and request.form:
        reason = request.form.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        return err("rejection reason is required", http=400)
    e, fresh = _transition(mid, "rejected", reason=reason.strip(), event="message.rejected",
                           extra={"rejection_reason": reason.strip()})
    if e:
        return e
    return jsonify(serialize_message(g.db, fresh))

@app.post("/api/messages/<mid>/cancel")
def cancel(mid):
    try:
        data = request.get_json(force=False, silent=True) or {}
    except Exception:
        data = {}
    reason = data.get("reason") if isinstance(data, dict) else None
    e, fresh = _transition(mid, "cancelled", reason=reason if isinstance(reason, str) else "cancelled",
                           event="message.cancelled")
    if e:
        return e
    return jsonify(serialize_message(g.db, fresh))

@app.post("/api/messages/<mid>/mark-sent")
def mark_sent(mid):
    e, fresh = _transition(mid, "sent", reason="marked sent by reviewer", event="message.sent")
    if e:
        return e
    return jsonify(serialize_message(g.db, fresh))

# ---------------- PATCH revision

@app.patch("/api/messages/<mid>")
def patch_message(mid):
    conn = g.db
    row = _expire_on_read(mid)
    if not row:
        return err("message not found", code="not_found", http=404)
    cur = dict(row)
    if cur["status"] not in ("pending", "rejected"):
        return err(f"message is {cur['status']} and cannot be revised", code="conflict", http=409,
                   extra={"status": cur["status"]})
    ctype = request.content_type or ""
    if "multipart/form-data" in ctype:
        data, files, e = _extract_submit_fields()
        if e:
            return e
    else:
        try:
            data = request.get_json(force=False, silent=False) if request.data else {}
        except Exception:
            return err("malformed JSON body", http=400)
        if data is None:
            data = {}
        if not isinstance(data, dict):
            return err("JSON body must be an object", http=400)
        files = []
    if "status" in data:
        return err("status cannot be changed via PATCH", http=400)
    was_rejected = cur["status"] == "rejected"
    # channel/destination
    new_channel = cur["channel"]
    new_dest = cur["destination"]
    new_norm = cur["destination_norm"]
    if "channel" in data or "destination" in data:
        nc = str(data.get("channel", cur["channel"])).strip().lower()
        nd = str(data.get("destination", cur["destination"]))
        if nc not in VALID_CHANNELS:
            return err("channel must be one of email, whatsapp, telegram", http=400)
        ok, nnorm, why = validate_destination(nc, nd)
        if not ok:
            return err(why, http=400)
        new_channel, new_dest, new_norm = nc, nd.strip(), nnorm
    # subject/body
    new_subject = data.get("subject", cur["subject"])
    if new_subject is not None and not isinstance(new_subject, str):
        return err("subject must be a string", http=400)
    new_body = data.get("body", cur["body"])
    if new_body is not None and (not isinstance(new_body, str) or not new_body.strip()):
        return err("body must be non-empty", http=400)
    # metadata
    if "metadata" in data:
        md = data["metadata"]
        if md is not None and not isinstance(md, dict):
            return err("metadata must be a JSON object", http=400)
        new_metadata = json.dumps(md) if md is not None else None
    else:
        new_metadata = cur["metadata"]
    # source
    new_source = data.get("source", cur["source"])
    if new_source is not None and not isinstance(new_source, str):
        return err("source must be a string", http=400)
    # destination_label snapshot
    if "destination_label" in data:
        dl = data["destination_label"]
        if dl is not None and not isinstance(dl, str):
            return err("destination_label must be a string", http=400)
        new_dlabel = dl.strip() if isinstance(dl, str) and dl.strip() else None
    else:
        new_dlabel = cur["destination_label"]
    # expiry
    if "expires_at" in data or "ttl_seconds" in data:
        exp_val, ee = _parse_expiry(data, for_patch=True)
        if ee:
            return ee
        new_expires = exp_val  # None clears
    else:
        new_expires = cur["expires_at"]
    # references
    if "references" in data:
        refs = data["references"]
        if refs is None:
            refs = []
        if not isinstance(refs, list) or any(not isinstance(x, str) for x in refs):
            return err("references must be a list of URL strings", http=400)
        new_refs = refs
    else:
        new_refs = get_refs(conn, mid)
    # webhook_url
    if "webhook_url" in data:
        wu = data["webhook_url"]
        if wu is not None:
            if not isinstance(wu, str) or not wu.strip():
                return err("webhook_url must be a non-empty string", http=400)
            okw, whyw = validate_outbound_url(wu.strip())
            if not okw:
                return err("invalid webhook_url: " + whyw, http=400)
            new_webhook = wu.strip()
        else:
            new_webhook = None
    else:
        new_webhook = cur["webhook_url"]
    # attachments handling: if key present, replace set? Spec: may update attachments; omitted stays.
    replace_atts = ("attachments" in data) or (files is not None and len(files) > 0)
    try:
        new_rev = cur["revision_number"] + 1
        now = now_iso()
        # verify still in editable state (compare-and-set guard)
        conn.execute("""UPDATE messages SET channel=?, destination=?, destination_norm=?, destination_label=?,
                        subject=?, body=?, expires_at=?, webhook_url=?, source=?, metadata=?,
                        rejection_reason=NULL, rejection_at=NULL,
                        revision_number=?, updated_at=?, status=?
                        WHERE id=? AND status=?""",
                     (new_channel, new_dest, new_norm, new_dlabel, new_subject, new_body, new_expires,
                      new_webhook, new_source, new_metadata, new_rev, now,
                      "pending", mid, cur["status"]))
        # rowcount check
        if conn.execute("SELECT changes() AS c").fetchone()["c"] == 0:
            conn.rollback()
            fresh = conn.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()
            fs = fresh["status"] if fresh else cur["status"]
            return err(f"message changed concurrently (status: {fs})", code="conflict", http=409,
                       extra={"status": fs})
        # refs replace
        conn.execute("DELETE FROM msg_refs WHERE message_id=?", (mid,))
        for u in new_refs:
            conn.execute("INSERT INTO msg_refs (message_id, revision_number, url) VALUES (?,?,?)", (mid, new_rev, u))
        # attachments
        if replace_atts:
            # remove old files from disk
            old = conn.execute("SELECT * FROM attachments WHERE message_id=?", (mid,)).fetchall()
            for a in old:
                try:
                    p = os.path.join(CONFIG["ATTACHMENT_DIR"], a["storage"])
                    if os.path.commonpath([os.path.abspath(p), os.path.abspath(CONFIG["ATTACHMENT_DIR"])]) == os.path.abspath(CONFIG["ATTACHMENT_DIR"]) and os.path.isfile(p):
                        os.remove(p)
                except Exception:
                    pass
            conn.execute("DELETE FROM attachments WHERE message_id=?", (mid,))
            # json url kinds
            for a in (data.get("attachments") or []):
                if not isinstance(a, dict):
                    continue
                kind = a.get("kind"); url = (a.get("url") or "").strip()
                if kind not in ("url_reference", "url_download") or not url:
                    conn.rollback()
                    return err("each attachment must have kind url_reference|url_download and a url", http=400)
                if kind == "url_reference":
                    conn.execute("INSERT INTO msg_refs (message_id, revision_number, url) VALUES (?,?,?)", (mid, new_rev, url))
                else:
                    try:
                        blob, ct2 = fetch_url_bytes(url, CONFIG["DOWNLOAD_TIMEOUT_SECONDS"], CONFIG["MAX_REDIRECTS"], CONFIG["MAX_ATTACHMENT_BYTES"])
                    except ValueError as ve:
                        conn.rollback()
                        ml = str(ve).lower()
                        if "exceeds" in ml:
                            return err(str(ve), http=413)
                        return err("failed to download attachment: " + str(ve), http=400)
                    fname = a.get("filename") or os.path.basename(urllib.parse.urlparse(url).path) or "download"
                    if message_total_bytes(conn, mid) + len(blob) > CONFIG["MAX_MESSAGE_ATTACHMENT_BYTES"]:
                        conn.rollback()
                        return err("message attachment total exceeds limit", http=413)
                    store_attachment_bytes(conn, mid, new_rev, fname, blob, guess_mime(fname, ct2), "url_download", url)
            for fs in (files or []):
                if not fs or not fs.filename:
                    continue
                blob = fs.read(CONFIG["MAX_ATTACHMENT_BYTES"] + 1)
                if len(blob) > CONFIG["MAX_ATTACHMENT_BYTES"]:
                    conn.rollback()
                    return err(f"attachment {fs.filename} exceeds per-file size limit", http=413)
                if message_total_bytes(conn, mid) + len(blob) > CONFIG["MAX_MESSAGE_ATTACHMENT_BYTES"]:
                    conn.rollback()
                    return err("message attachment total exceeds limit", http=413)
                store_attachment_bytes(conn, mid, new_rev, fs.filename, blob, guess_mime(fs.filename, fs.mimetype), "multipart", None)
        else:
            conn.execute("UPDATE attachments SET revision_number=? WHERE message_id=?", (new_rev, mid))
        att_ids = [r["id"] for r in conn.execute("SELECT id FROM attachments WHERE message_id=?", (mid,)).fetchall()]
        # preserve previous revision rejection data already in revisions? update current revision row for old rev with rejection info
        if was_rejected:
            conn.execute("UPDATE revisions SET rejection_reason=?, rejection_at=? WHERE message_id=? AND revision_number=?",
                         (cur["rejection_reason"], cur["rejection_at"], mid, cur["revision_number"]))
        conn.execute("""INSERT INTO revisions (message_id, revision_number, channel, destination, subject, body, expires_at, refs, metadata, attachment_ids, created_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                     (mid, new_rev, new_channel, new_dest, new_subject, new_body, new_expires, json.dumps(new_refs),
                      new_metadata, json.dumps(att_ids), now))
        if was_rejected:
            _insert_status_history(conn, mid, "rejected", "pending", "revised", new_rev)
        else:
            _insert_status_history(conn, mid, "pending", "pending", "revised", new_rev)
        eid = queue_webhook_event(conn, mid, "message.revised", "pending", new_rev, {})
        conn.commit()
        if eid:
            deliver_event_async(eid)
    except Exception as ex:
        try:
            conn.rollback()
        except Exception:
            pass
        s = str(ex)
        if "exceeds" in s.lower():
            return err(s, http=413)
        return err("revision failed: " + s[:300], http=500)
    fresh = conn.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()
    return jsonify(serialize_message(conn, fresh))

# ---------------- handoff

@app.get("/api/messages/<mid>/handoff")
def handoff(mid):
    conn = g.db
    row = _expire_on_read(mid)
    if not row:
        return err("message not found", code="not_found", http=404)
    m = dict(row)
    if m["status"] != "approved":
        return err(f"handoff requires approved status (current: {m['status']})", code="conflict", http=409,
                   extra={"status": m["status"]})
    atts = get_attachments(conn, mid)
    m["_attachments"] = atts
    h = build_handoff(m)
    h["attachments"] = [{"id": a["id"], "filename": a["filename"], "size": a["size"], "mime": a["mime"]} for a in atts]
    h["status"] = m["status"]
    h["message_id"] = mid
    return jsonify(h)

# ---------------- attachments

@app.get("/api/messages/<mid>/attachments")
def list_attachments(mid):
    conn = g.db
    row = conn.execute("SELECT id FROM messages WHERE id=?", (mid,)).fetchone()
    if not row:
        return err("message not found", code="not_found", http=404)
    atts = get_attachments(conn, mid)
    refs = get_refs(conn, mid)
    return jsonify({"attachments": [{k: a[k] for k in ("id", "filename", "mime", "size", "uploaded_at", "source_type", "source_url") if k in a} for a in atts],
                    "references": refs})

@app.get("/api/messages/<mid>/attachments/<aid>")
def download_attachment(mid, aid):
    conn = g.db
    if ".." in aid or "/" in aid or "\\" in aid:
        return err("invalid attachment id", http=400)
    row = conn.execute("SELECT id FROM messages WHERE id=?", (mid,)).fetchone()
    if not row:
        return err("message not found", code="not_found", http=404)
    a = conn.execute("SELECT * FROM attachments WHERE id=? AND message_id=?", (aid, mid)).fetchone()
    if not a:
        return err("attachment not found", code="not_found", http=404)
    full = os.path.join(CONFIG["ATTACHMENT_DIR"], a["storage"])
    if os.path.commonpath([os.path.abspath(full), os.path.abspath(CONFIG["ATTACHMENT_DIR"])]) != os.path.abspath(CONFIG["ATTACHMENT_DIR"]):
        return err("unsafe attachment path", http=400)
    if not os.path.isfile(full):
        return err("attachment file missing from store", code="not_found", http=404)
    safe = sanitize_filename(a["filename"])
    q = urllib.parse.quote(safe)
    resp = send_file(full, mimetype=a["mime"] or "application/octet-stream", as_attachment=True, download_name=safe)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Content-Disposition"] = f"attachment; filename=\"{safe}\"; filename*=UTF-8''{q}"
    return resp

@app.get("/api/messages/<mid>/attachments.zip")
def download_all_zip(mid):
    conn = g.db
    row = conn.execute("SELECT id FROM messages WHERE id=?", (mid,)).fetchone()
    if not row:
        return err("message not found", code="not_found", http=404)
    atts = get_attachments(conn, mid)
    if not atts:
        return err("no attachments", code="not_found", http=404)
    buf = BytesIO()
    total = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        used = set()
        for a in atts:
            full = os.path.join(CONFIG["ATTACHMENT_DIR"], a["storage"])
            if os.path.commonpath([os.path.abspath(full), os.path.abspath(CONFIG["ATTACHMENT_DIR"])]) != os.path.abspath(CONFIG["ATTACHMENT_DIR"]):
                continue
            if not os.path.isfile(full):
                continue
            name = sanitize_filename(a["filename"])
            if name in used:
                base, dot, ext = name.partition(".")
                name = f"{base}_{a['id'][:6]}.{ext}" if dot else f"{name}_{a['id'][:6]}"
            used.add(name)
            with open(full, "rb") as f:
                data = f.read(CONFIG["MAX_MESSAGE_ATTACHMENT_BYTES"] + 1)
            total += len(data)
            if total > CONFIG["MAX_MESSAGE_ATTACHMENT_BYTES"] * 2:
                return err("archive too large", http=413)
            zf.writestr(name, data)
    buf.seek(0)
    resp = send_file(buf, mimetype="application/zip", as_attachment=True, download_name=f"{mid}_attachments.zip")
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp

# ---------------- webhooks history

@app.get("/api/messages/<mid>/webhook-events")
def webhook_events(mid):
    conn = g.db
    row = conn.execute("SELECT id FROM messages WHERE id=?", (mid,)).fetchone()
    if not row:
        return err("message not found", code="not_found", http=404)
    evs = conn.execute("SELECT * FROM webhook_events WHERE message_id=? ORDER BY id ASC", (mid,)).fetchall()
    out = []
    for ev in evs:
        d = dict(ev)
        try:
            d["payload"] = json.loads(d["payload"])
        except Exception:
            pass
        atts = conn.execute("SELECT * FROM webhook_attempts WHERE event_id=? ORDER BY attempt_number ASC", (ev["id"],)).fetchall()
        d["attempts"] = [dict(a) for a in atts]
        d["attempt_count"] = len(atts)
        out.append(d)
    return jsonify({"events": out})

# ---------------- destinations

def _discover_destinations(conn):
    rows = conn.execute("""SELECT channel, destination_norm AS norm, MIN(destination) AS sample,
                           COUNT(*) AS message_count, MAX(created_at) AS last_used
                           FROM messages GROUP BY channel, destination_norm""").fetchall()
    labels = {(r["channel"], r["norm"]): dict(r2) for r2 in
              (conn.execute("SELECT * FROM destination_labels").fetchall()) for r in [r2]}
    out = []
    for r in rows:
        key = (r["channel"], r["norm"])
        lab = labels.get(key)
        out.append({"channel": r["channel"], "destination": r["sample"], "normalized_destination": r["norm"],
                    "label": lab["label"] if lab else None,
                    "message_count": r["message_count"], "last_used": r["last_used"]})
    out.sort(key=lambda x: (x["channel"], x["normalized_destination"]))
    return out

@app.get("/api/destinations")
def list_destinations():
    return jsonify({"destinations": _discover_destinations(g.db)})

@app.put("/api/destinations/label")
def put_label():
    try:
        data = request.get_json(force=True, silent=False)
    except Exception:
        return err("malformed JSON body", http=400)
    if not isinstance(data, dict):
        return err("JSON body must be an object", http=400)
    channel = str(data.get("channel", "")).strip().lower()
    dest = str(data.get("destination", ""))
    label = data.get("label")
    if channel not in VALID_CHANNELS:
        return err("channel must be one of email, whatsapp, telegram", http=400)
    ok, norm, why = validate_destination(channel, dest)
    if not ok:
        return err(why, http=400)
    if not isinstance(label, str) or not label.strip():
        return err("label must be a non-empty string", http=400)
    label = label.strip()
    if len(label) > 100:
        return err("label too long (max 100 chars)", http=400)
    conn = g.db
    dup = conn.execute("SELECT norm FROM destination_labels WHERE channel=? AND label=? AND norm != ?",
                       (channel, label, norm)).fetchone()
    if dup:
        return err(f"label '{label}' already used in channel {channel}", code="conflict", http=409)
    now = now_iso()
    conn.execute("""INSERT INTO destination_labels (channel, norm, label, created_at, updated_at) VALUES (?,?,?,?,?)
                    ON CONFLICT(channel, norm) DO UPDATE SET label=excluded.label, updated_at=excluded.updated_at""",
                 (channel, norm, label, now, now))
    conn.commit()
    return jsonify({"channel": channel, "normalized_destination": norm, "label": label})

@app.delete("/api/destinations/label")
def delete_label():
    channel = (request.args.get("channel") or "").strip().lower()
    dest = request.args.get("destination") or ""
    if channel not in VALID_CHANNELS:
        return err("channel query param required (email|whatsapp|telegram)", http=400)
    ok, norm, why = validate_destination(channel, dest)
    if not ok:
        return err(why, http=400)
    conn = g.db
    cur = conn.execute("DELETE FROM destination_labels WHERE channel=? AND norm=?", (channel, norm))
    conn.commit()
    if cur.rowcount == 0:
        return err("label not found", code="not_found", http=404)
    return jsonify({"ok": True})

# ---------------- SPA

@app.get("/")
def spa():
    base = os.path.dirname(os.path.abspath(__file__))
    idx = os.path.join(base, "static", "index.html")
    try:
        with open(idx, "r", encoding="utf-8") as f:
            return Response(f.read(), mimetype="text/html")
    except FileNotFoundError:
        return Response("<h1>Outbox</h1><p>static/index.html missing</p>", mimetype="text/html")

# ---------------- main

def _start_worker_once():
    t = threading.Thread(target=expiration_loop, daemon=True)
    t.start()

if __name__ == "__main__":
    refresh_config()
    init_db()
    _start_worker_once()
    port = CONFIG["PORT"]
    import sys
    if "--seed-demo" in sys.argv:
        print("seed-demo not required for normal use; skipping (no demo data inserted).")
    app.run(host="127.0.0.1", port=port, threaded=True)
else:
    # import time (tests / wsgi): ensure schema exists lazily
    try:
        if not os.path.exists(db_path()):
            init_db()
        else:
            init_db()
    except Exception:
        pass
    try:
        _start_worker_once()
    except Exception:
        pass
