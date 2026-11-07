# Human-in-the-Loop Outbox Service

Built **2026-11-07 00:09 UTC** by **DeepSeek V4.1 Flash**.

A local, single-user outbox for messages drafted by AI agents or internal tools. Producers submit email, WhatsApp and Telegram messages over a REST API. A human reviews each message in a local web app, opens a prepared handoff link in their own app, sends it themselves, and only then explicitly marks it sent.

The service **never sends messages**, **never calls provider APIs**, and has no SMTP, Gmail, WhatsApp Business or Telegram Bot integration. It records every review decision, revision, attachment and webhook attempt so the outbox is auditable.

---

## 1. Requirements and startup

- Python 3.11 or newer
- Flask (the only runtime dependency)
- SQLite, `urllib`, `ipaddress`, `mimetypes`, `threading`, `unittest` from the standard library

```bash
cd human-in-the-loop-outbox-service
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python3 app.py
```

Open <http://127.0.0.1:8000>. The same process serves the SPA, REST API, OpenAPI document and documentation.

Quick checks:

```bash
curl -sS http://127.0.0.1:8000/api/health
curl -sS http://127.0.0.1:8000/api/info
curl -sS http://127.0.0.1:8000/openapi.json | head
```

The first start creates `./data`, `./data/attachments` and `./data/outbox.sqlite3` (or the configured equivalents). Startup is idempotent; existing data is never reset.

### Run tests

```bash
python3 -m unittest discover -s tests -v
```

All tests are offline. A loopback HTTP fixture is used for attachment downloads and real webhook delivery/timeout tests; ordinary webhook tests inject a fake sender through the dispatcher. No headless browser is required.

---

## 2. Configuration

All settings come from environment variables. Paths are resolved relative to the current working directory.

| Variable | Default | Meaning |
|---|---|---|
| `DATA_DIR` | `./data` | Data directory; contains the SQLite database |
| `ATTACHMENT_DIR` | `./data/attachments` | Attachment blob directory |
| `MAX_ATTACHMENT_BYTES` | `10485760` (10 MiB) | Per-file limit |
| `MAX_MESSAGE_ATTACHMENT_BYTES` | `26214400` (25 MiB) | Per-message total attachment limit |
| `EXPIRATION_INTERVAL_SECONDS` | `30` | Background expiration sweep interval |
| `WEBHOOK_TIMEOUT_SECONDS` | `5` | Per-attempt webhook timeout |
| `WEBHOOK_MAX_ATTEMPTS` | `3` | Maximum delivery attempts per event |
| `WEBHOOK_BACKOFF_BASE_SECONDS` | `1` | Base for bounded exponential backoff |
| `DOWNLOAD_TIMEOUT_SECONDS` | `10` | Attachment download timeout |
| `MAX_REDIRECTS` | `3` | Maximum validated download redirects |
| `ALLOW_PRIVATE_URLS` | `0` | **Local-testing only** override for SSRF blocking |
| `PORT` | `8000` | HTTP port |
| `HOST` | `127.0.0.1` | Bind address (leave loopback for normal use) |

Example:

```bash
DATA_DIR=/srv/outbox/data \
ATTACHMENT_DIR=/srv/outbox/data/attachments \
WEBHOOK_MAX_ATTEMPTS=4 \
PORT=8000 \
python3 app.py
```

`GET /api/info` exposes the non-sensitive effective configuration. `ALLOW_PRIVATE_URLS=1` disables loopback/private-address blocking for attachment downloads and webhooks, and should only be used for documented local fixtures.

---

## 3. Architecture

```
app.py                    entry point, real build sign-off, host/port wiring
outbox/
  api.py                  Flask factory, HTTP parsing, error mapping, docs/SPA
  service.py              domain logic: lifecycle, revisions, expiry, destinations
  channels.py             channel adapters: validation, normalization, handoff
  storage.py              sanitized filenames and attachment blob storage
  net.py                  SSRF validation, safe downloads, webhook POST
  webhooks.py             async delivery, retries, attempt persistence
  db.py                   SQLite connections, WAL/foreign keys, migrations
  config.py               environment configuration
  timeutil.py             fixed-width UTC ISO-8601 helpers
  errors.py               typed API errors
static/index.html         complete vanilla HTML/CSS/JS SPA (no build step)
tests/test_app.py         unittest + Flask test client suite
openapi.json              OpenAPI 3.1 specification
fixtures/                 sample.txt and optional webhook sink
docs/manual-ui-test.md    manual frontend test script
```

Domain logic is independent of HTTP handlers. Channel formatting lives inside adapters. Attachment persistence is behind `AttachmentStore`. Background processing is used only for expiration sweeps and webhook delivery/retries.

Every request gets its own SQLite connection; all writes use explicit transactions. Transitions use `BEGIN IMMEDIATE` plus compare-and-set `UPDATE ... WHERE id = ? AND status = ?` so duplicate or concurrent requests cannot both succeed. SQLite foreign keys are enabled and WAL mode is used.

---

## 4. Database schema and migrations

`schema_migrations(version, applied_at)` records applied versions. `Database.initialize()` creates missing tables and indexes inside a versioned migration and is safe to run on every start. Current schema version: **1**.

Core tables:

| Table | Purpose |
|---|---|
| `messages` | Active message snapshot, status, expiry, revision number, rejection, webhook URL |
| `message_revisions` | Full content snapshot per revision (channel, destination, subject, body, expiry, metadata, rejection data) |
| `attachments` | Immutable blobs: original filename, MIME, size, storage name, upload time, source type/URL |
| `revision_attachments` | Which attachments belong to each revision |
| `message_references` | External URL references per revision (`reference` or `attachment_reference`) |
| `status_history` | Every status transition with reason, revision and timestamp |
| `destinations` | Discovered destinations plus optional unique label per channel |
| `webhook_events` | Idempotent event records keyed by `(message_id, event, revision_number)` |
| `webhook_attempts` | One row per delivery attempt with HTTP status, timestamps and error |

Timestamps are stored and exchanged as UTC ISO-8601 with a `Z` suffix and millisecond precision, e.g. `2026-11-07T00:09:15.580Z`. `created_at` never changes; message IDs are stable across revisions. Nothing is deleted automatically: rejected, stale and cancelled messages retain content, attachments and history.

Inspect the schema:

```bash
sqlite3 data/outbox.sqlite3 '.schema'
sqlite3 data/outbox.sqlite3 'SELECT version, applied_at FROM schema_migrations;'
```

---

## 5. Message lifecycle

Statuses: `pending`, `approved`, `sent`, `rejected`, `stale`, `cancelled`.

Allowed transitions:

| From | To | How |
|---|---|---|
| `pending` | `approved` | `POST /approve` |
| `pending` | `rejected` | `POST /reject` with non-empty reason |
| `pending` | `cancelled` | `POST /cancel` |
| `pending` | `stale` | Expiration check or worker |
| `rejected` | `pending` | `PATCH` revision only |
| `rejected` | `cancelled` | `POST /cancel` |
| `approved` | `sent` | `POST /mark-sent` only |
| `approved` | `cancelled` | `POST /cancel` |
| `approved` | `stale` | Expiration check or worker |
| `sent`, `stale`, `cancelled` | — | Terminal and immutable |

There is no generic status editing. A `status` field in PATCH returns `400`. Invalid transitions return `409` with `current_status` and `allowed_actions`; a missing message returns `404`.

Expiration applies only to `pending` and `approved`. It is checked before listing, retrieval, approval, rejection, cancellation, mark-sent, handoff preparation and revision, and also by a periodic worker. Expiration and approval are transactional, so an expired message can never become approved. Approving does not send anything; it only unlocks the handoff. Opening a link or downloading an attachment never changes status. Only the explicit `mark-sent` call does, normally after the UI's second confirmation.

### Revisions

`PATCH /api/messages/{id}` is allowed only while the message is `pending` or `rejected`. It:

- keeps the same message ID and original `created_at`;
- snapshots the complete new content, attachments and references as a new revision;
- increments `revision_number`;
- preserves the previous revision and its rejection data;
- returns a `rejected` message to `pending` and clears the active rejection reason;
- emits `message.revised`.

PATCH on approved, sent, stale or cancelled messages returns `409` and modifies nothing.

---

## 6. REST API summary

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/messages` | Submit JSON or multipart message |
| `GET` | `/api/messages` | Filter, paginate, sort |
| `GET` | `/api/messages/{id}` | Full active message |
| `PATCH` | `/api/messages/{id}` | Revise pending/rejected |
| `POST` | `/api/messages/{id}/approve` | Pending → approved |
| `POST` | `/api/messages/{id}/reject` | Pending → rejected |
| `POST` | `/api/messages/{id}/cancel` | Pending/approved/rejected → cancelled |
| `POST` | `/api/messages/{id}/mark-sent` | Approved → sent |
| `GET` | `/api/messages/{id}/history` | Revisions and status history |
| `GET` | `/api/messages/{id}/handoff` | Approved handoff data |
| `GET` | `/api/messages/{id}/attachments` | Active attachment list |
| `GET` | `/api/messages/{id}/attachments/{attachment_id}` | Download one attachment |
| `GET` | `/api/messages/{id}/attachments.zip` | Download all active attachments |
| `GET` | `/api/messages/{id}/webhook-events` | Events and attempts |
| `GET` | `/api/destinations` | Discovered destinations |
| `PUT` | `/api/destinations/label` | Assign/rename label |
| `DELETE` | `/api/destinations/label` | Remove label |
| `GET` | `/api/health` | Health |
| `GET` | `/api/info` | Non-sensitive configuration |
| `GET` | `/api/docs` | Self-contained API docs |
| `GET` | `/openapi.json` | OpenAPI 3.1 document |

Errors are consistent:

```json
{
  "error": {
    "code": "invalid_transition",
    "message": "Cannot approve a message in status 'sent'.",
    "details": {
      "current_status": "sent",
      "allowed_actions": []
    }
  },
  "current_status": "sent",
  "allowed_actions": []
}
```

Statuses: `400` validation, `404` missing, `409` invalid transition/conflict, `413` too large, `415` unsupported media type.

Listing supports `status` (single or comma-separated), `channel`, `destination` (case-insensitive on destination or labels), `created_from`, `created_to`, `expires_from`, `expires_to`, `limit` (default 20, max 100), `offset`, and `sort=newest|oldest|expires_soon|expires_late`. The envelope is `{items,total,limit,offset}`. No-expiration messages sort last for both expiration orders.

---

## 7. curl examples

### Email submission with expiry and webhook

```bash
cat > email.json <<'JSON'
{
  "channel": "email",
  "destination": "alex@example.com",
  "subject": "Q4 report draft",
  "body": "Hi Alex,\n\nPlease review the attached Q4 report before Friday.\n\nThanks,\nSam",
  "expires_at": "2030-01-01T00:00:00Z",
  "webhook_url": "http://127.0.0.1:9002/hooks/outbox",
  "source": "report-agent",
  "metadata": {"ticket": "OPS-142"}
}
JSON

curl -sS -X POST http://127.0.0.1:8000/api/messages \
  -H 'Content-Type: application/json' \
  --data @email.json
```

With `webhook_url` pointing at loopback, start the service with `ALLOW_PRIVATE_URLS=1` for the local sink. Otherwise omit the webhook.

### Multipart email with a file

```bash
curl -sS -X POST http://127.0.0.1:8000/api/messages \
  -F channel=email \
  -F destination=alex@example.com \
  -F subject='Q4 report draft' \
  -F body='Hi Alex, please review the attached Q4 report.' \
  -F expires_at=2030-01-01T00:00:00Z \
  -F source=report-agent \
  -F attachments=@fixtures/sample.txt
```

### WhatsApp individual and group

```bash
curl -sS -X POST http://127.0.0.1:8000/api/messages \
  -H 'Content-Type: application/json' \
  -d '{"channel":"whatsapp","destination":"+1 (415) 555-0123","body":"Your appointment is confirmed for 3 PM."}'

curl -sS -X POST http://127.0.0.1:8000/api/messages \
  -H 'Content-Type: application/json' \
  -d '{"channel":"whatsapp","destination":"group:Project Alpha","body":"Standup moved to 10:00."}'
```

### Telegram individual and group

```bash
curl -sS -X POST http://127.0.0.1:8000/api/messages \
  -H 'Content-Type: application/json' \
  -d '{"channel":"telegram","destination":"@alex_example","body":"Build finished successfully."}'

curl -sS -X POST http://127.0.0.1:8000/api/messages \
  -H 'Content-Type: application/json' \
  -d '{"channel":"telegram","destination":"group:Ops Room","body":"Deploy is live."}'
```

### External reference and downloaded attachment

Start the local fixture server in another terminal:

```bash
python3 -m http.server 9001 --directory fixtures
```

Then start the service with `ALLOW_PRIVATE_URLS=1` and submit:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/messages \
  -H 'Content-Type: application/json' \
  -d '{
    "channel": "email",
    "destination": "alex@example.com",
    "subject": "Reference and file",
    "body": "See the external reference and the attached file.",
    "references": ["https://example.com/spec"],
    "attachments": [
      {"kind": "url_download", "url": "http://127.0.0.1:9001/sample.txt", "filename": "sample.txt"}
    ]
  }'
```

`https://example.com/spec` is stored as a reference and is **never fetched**. `url_download` is fetched with SSRF checks and stored as a real attachment. To store a reference without downloading, use `{"kind":"url_reference","url":"https://example.com/other"}`.

### Expiration

```bash
# Relative TTL
curl -sS -X POST http://127.0.0.1:8000/api/messages \
  -H 'Content-Type: application/json' \
  -d '{"channel":"email","destination":"a@example.com","body":"Expires soon","ttl_seconds":120}'

# Absolute expiry (must be in the future)
curl -sS -X POST http://127.0.0.1:8000/api/messages \
  -H 'Content-Type: application/json' \
  -d '{"channel":"email","destination":"a@example.com","body":"Long lived","expires_at":"2030-01-01T00:00:00Z"}'
```

Sending both in one request returns `400`. `PATCH { "expires_at": null }` clears expiration.

### Webhook sink

```bash
python3 fixtures/webhook_sink.py
```

Run the service with `ALLOW_PRIVATE_URLS=1` when submitting the loopback webhook URL shown above. Events are delivered asynchronously with bounded retries; inspect delivery attempts with:

```bash
curl -sS http://127.0.0.1:8000/api/messages/msg_REPLACE/webhook-events
```

### Review journey

```bash
# Poll status
curl -sS http://127.0.0.1:8000/api/messages/msg_REPLACE

# Reject (reason mandatory)
curl -sS -X POST http://127.0.0.1:8000/api/messages/msg_REPLACE/reject \
  -H 'Content-Type: application/json' \
  -d '{"reason":"The recipient name is wrong. Address it to Alex Smith, not Alex Doe."}'

# Revise the rejected message; same ID, revision 2, back to pending
curl -sS -X PATCH http://127.0.0.1:8000/api/messages/msg_REPLACE \
  -H 'Content-Type: application/json' \
  -d '{"subject":"Q4 report draft — revised","body":"Hi Alex Smith,\n\nPlease review the attached Q4 report before Friday.\n\nThanks,\nSam"}'

# Approve and prepare handoff
curl -sS -X POST http://127.0.0.1:8000/api/messages/msg_REPLACE/approve
curl -sS http://127.0.0.1:8000/api/messages/msg_REPLACE/handoff

# After you actually sent it in your own app:
curl -sS -X POST http://127.0.0.1:8000/api/messages/msg_REPLACE/mark-sent

# Cancel instead
curl -sS -X POST http://127.0.0.1:8000/api/messages/msg_REPLACE/cancel \
  -H 'Content-Type: application/json' \
  -d '{"reason":"Superseded by a newer draft."}'

# History and attachments
curl -sS http://127.0.0.1:8000/api/messages/msg_REPLACE/history
curl -sS http://127.0.0.1:8000/api/messages/msg_REPLACE/attachments
curl -sS -OJ http://127.0.0.1:8000/api/messages/msg_REPLACE/attachments/att_REPLACE
```

### Destination labels

```bash
curl -sS http://127.0.0.1:8000/api/destinations

curl -sS -X PUT http://127.0.0.1:8000/api/destinations/label \
  -H 'Content-Type: application/json' \
  -d '{"channel":"email","destination":"alex@example.com","label":"Alex — Client"}'

curl -sS -X DELETE \
  'http://127.0.0.1:8000/api/destinations/label?channel=email&destination=alex@example.com'
```

Labels are non-empty, at most 120 characters, and unique within a channel (case-insensitive). Removing a label never modifies or deletes messages.

---

## 8. Channel adapters and handoff limitations

The API returns structured handoff data; the SPA never constructs channel URLs itself. Every response includes `channel`, `destination`, `normalized_destination`, `handoff_url`, `mode`, `capabilities`, `manual_actions`, `warnings`, `subject`, `body`, `copy`, and attachment download links. `attachments_supported` is always false because none of these handoff mechanisms can carry files.

| Channel / destination | Handoff | Honest limitation |
|---|---|---|
| Email | `mailto:` with recipient, subject and body | Attachments cannot travel in `mailto:`; reviewer must download and attach manually |
| Email, very long content | Shorter valid `mailto:` (recipient+subject, or recipient only) plus warning | Body is copied manually; UI exposes full copy value |
| WhatsApp individual | `https://wa.me/<digits>?text=<encoded>` | No subject line; attachments manual; overlong bodies fall back to opening the chat without text |
| WhatsApp group (`group:Name`) | Opens `https://wa.me/` | Groups cannot be preselected or prefilled; reviewer selects the named group, pastes and attaches manually |
| Telegram individual (`@user`, `t.me/user`) | `https://t.me/<user>?text=<encoded>` | Text prefill depends on the installed client; attachments manual; overlong bodies fall back to the chat without text |
| Telegram group (`group:Name`) | Opens `https://t.me/` | No public group username is assumed; reviewer selects the named group and pastes manually |
| Telegram private invite (`t.me/+…`, `t.me/joinchat/…`) | Opens the invite link | Invite links cannot preselect the chat or prefill; reviewer joins/selects and pastes manually |

Encoding uses UTF-8 percent-encoding and handles newlines, `&`, `+`, emoji and other special characters. The practical handoff URL limit is about 1800 characters.

Approval is required before handoff. Handoff preparation re-checks expiration first. Opening a link or downloading a file is a plain browser action and never calls `mark-sent`.

---

## 9. Attachments and references

Three mechanisms are supported:

1. **Multipart upload** — repeated file parts named `attachments`.
2. **External reference** — stored as a URL string, never fetched (`references`, or `attachments[].kind = "url_reference"`).
3. **URL download** — fetched over HTTP(S), validated, bounded, stored as a real attachment (`attachments[].kind = "url_download"`).

Stored attachments expose ID, original filename, MIME type, size, storage reference, upload timestamp, source type (`multipart` or `url_download`) and source URL. Filenames are sanitized: path components, control characters and reserved Windows names are removed or rewritten; the storage name is a random UUID plus a short safe extension, never the client filename. Reads and writes are confined to the attachment directory with resolved-path checks; traversal cannot escape it.

Downloads are served with `Content-Disposition: attachment`, `X-Content-Type-Options: nosniff`, `Cache-Control: no-store`, and both ASCII and RFC 5987 encoded filenames. Missing records or missing blobs return clear `404`s. Files are never executed. A ZIP download of the active revision is available at `/attachments.zip`.

SSRF protections for URL downloads and webhooks:

- only `http` and `https`;
- no URL credentials;
- block `localhost`, `.localhost`, `.local`, known metadata hostnames and cloud-metadata addresses;
- resolve hostnames and reject loopback, private, link-local, multicast, unspecified, reserved and IPv4-mapped private addresses;
- revalidate every redirect target and the final response URL;
- cap redirects (`MAX_REDIRECTS`), timeout (`DOWNLOAD_TIMEOUT_SECONDS`) and byte count while streaming;
- webhooks do not follow redirects, and every retry revalidates the URL;
- `ALLOW_PRIVATE_URLS=1` is the explicit local-testing override.

---

## 10. Webhooks

A message may have one `webhook_url`. Real events only:

- `message.approved`
- `message.rejected`
- `message.sent`
- `message.cancelled`
- `message.stale`
- `message.revised`

Payload example:

```json
{
  "event": "message.rejected",
  "message_id": "msg_8f2c1a4b9d30",
  "status": "rejected",
  "revision_number": 1,
  "rejection_reason": "The recipient name is wrong. Address it to Alex Smith, not Alex Doe.",
  "timestamp": "2026-11-06T20:00:00.000Z"
}
```

The state transition commits first; delivery then runs asynchronously in a daemon thread. Failures never roll back the message change. Delivery uses `WEBHOOK_TIMEOUT_SECONDS`, at most `WEBHOOK_MAX_ATTEMPTS`, and bounded exponential backoff starting at `WEBHOOK_BACKOFF_BASE_SECONDS` (1s, 2s, 4s, …). Every event and attempt is persisted, with status, attempt count, HTTP status, timestamps, last error and a short response body. Events are idempotent on `(message_id, event, revision_number)`. With no webhook configured, the API and UI work normally and no event rows are created.

Inspect history:

```bash
curl -sS http://127.0.0.1:8000/api/messages/msg_REPLACE/webhook-events
```

The message detail view shows the same events and attempts.

---

## 11. Security and reliability notes

- Local single-user service, binds to `127.0.0.1` by default, no authentication by design.
- No provider APIs, telemetry, analytics, CDN assets or external storage.
- SQLite foreign keys on, WAL mode, `busy_timeout`, explicit transactions and compare-and-set transitions.
- Exactly one of two concurrent approvals wins; the loser gets `409`.
- Expiration and approval share a transaction; expired messages can never be approved or handed off.
- Terminal messages are immutable. Rejected messages can only move back to pending through PATCH revision.
- Rejection reasons are mandatory.
- Message IDs and `created_at` are stable across revisions; previous content and attachments remain in history.
- Filenames are sanitized and storage names randomized; traversal is blocked on storage and downloads.
- Uploaded/downloaded bytes are never executed, only offered as attachments with `nosniff`.
- Oversized uploads return `413`; malformed payloads `400`; wrong media types `415`.
- Webhook failures and timeouts never undo state changes.
- Timestamps are UTC internally; the UI formats local time with an explicit timezone label.

---

## 12. Manual frontend test script

A detailed step-by-step script is in [`docs/manual-ui-test.md`](docs/manual-ui-test.md). At a minimum, verify these journeys at 1440×900 and 390×844:

1. Submit a pending email and a multipart attachment; refresh the queue.
2. Filter by status/channel/destination/date and change sort order; confirm no horizontal overflow.
3. Open the detail drawer; inspect body, metadata, references, attachments and histories.
4. Approve; confirm the handoff panel appears with prefilled capability labels, warnings and manual steps.
5. Copy subject/body; open the handoff link; download an attachment. Re-check the status stayed `approved`.
6. Mark as sent through the second-confirmation modal with the required checkbox.
7. Reject another message with a mandatory reason; confirm blank reason is blocked.
8. Revise the rejected message through the API; refresh and inspect revision 2 with revision 1 in history.
9. Let a short-TTL message expire; confirm it leaves active queues and cannot be approved or handed off.
10. Assign, rename, conflict-test and remove a destination label; confirm messages remain unchanged.

Keyboard checks: Tab through controls, visible focus, Enter/Space activates cards, Escape closes the drawer/modal, focus returns to the trigger. Enable `prefers-reduced-motion` and confirm animations are disabled.

---

## 13. Troubleshooting

**Port already in use** — set `PORT=8001` or stop the other process.

**`413` when uploading** — the per-file or per-message limit was exceeded, or Flask rejected the total request size. Raise `MAX_ATTACHMENT_BYTES` / `MAX_MESSAGE_ATTACHMENT_BYTES` and restart.

**Webhook never arrives** — confirm `ALLOW_PRIVATE_URLS=1` for a loopback sink, check the message's webhook event history for attempts/errors, and ensure the sink is listening. DNS failures are recorded; use a reachable URL.

**URL download blocked** — private/loopback/link-local/metadata targets are blocked by default. Use a real public URL, or `ALLOW_PRIVATE_URLS=1` only for local fixtures.

**`database is locked`** — avoid running long write transactions externally; the service sets a 15-second busy timeout. Keep `DATA_DIR` on a local filesystem.

**SPA opens but data is empty** — check `GET /api/health`, then `GET /api/messages`. The SPA's default filter shows pending/approved/rejected only; choose “All statuses” to see terminal messages.

**Tests fail importing `outbox`** — run them from the solution directory: `python3 -m unittest discover -s tests -v`.

---

## 14. Backup and restore

Stop the service for a simple, consistent backup. Back up **both** the database and the attachment directory; attachment records point at blobs.

### Backup (offline)

```bash
DATA_DIR=./data
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p backups
cp -a "$DATA_DIR/outbox.sqlite3" "backups/outbox-$STAMP.sqlite3"
cp -a "$DATA_DIR/attachments" "backups/attachments-$STAMP"
# Also copy WAL/SHM if they exist after an unclean stop:
[ -f "$DATA_DIR/outbox.sqlite3-wal" ] && cp -a "$DATA_DIR/outbox.sqlite3-wal" "backups/"
[ -f "$DATA_DIR/outbox.sqlite3-shm" ] && cp -a "$DATA_DIR/outbox.sqlite3-shm" "backups/"
tar -czf "backups/attachments-$STAMP.tar.gz" -C backups "attachments-$STAMP"
```

### Backup (online SQLite snapshot)

```bash
DATA_DIR=./data
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
sqlite3 "$DATA_DIR/outbox.sqlite3" ".backup 'backups/outbox-$STAMP.sqlite3'"
cp -a "$DATA_DIR/attachments" "backups/attachments-$STAMP"
```

The SQLite online backup is transactionally consistent. Copy attachments immediately after; for strict consistency, stop the service.

### Restore

```bash
DATA_DIR=./data
cp "backups/outbox-20260101T000000Z.sqlite3" "$DATA_DIR/outbox.sqlite3"
rm -f "$DATA_DIR/outbox.sqlite3-wal" "$DATA_DIR/outbox.sqlite3-shm"
rm -rf "$DATA_DIR/attachments"
cp -a "backups/attachments-20260101T000000Z" "$DATA_DIR/attachments"
python3 app.py
```

Verify with `GET /api/health`, `GET /api/info` and a spot-check of a message, its attachments and `/api/messages/{id}/history`.

If the database and attachment directory are restored from different points in time, message history stays consistent but an attachment blob may be missing; downloads return a clear `404` rather than incorrect bytes.

---

## 15. Assumptions

- Single reviewer, single machine, loopback-only deployment; there is no authentication, authorization or multi-tenancy.
- Producers and the reviewer trust each other and the local filesystem.
- Email/WhatsApp/Telegram prefilling depends on the installed client and OS; links are best-effort and every unsupported feature is surfaced with manual instructions.
- Attachments are always manual for all three channels.
- `created_at` is immutable and revisions keep the original ID.
- Absolute expiry values are UTC instants; naive timestamps are interpreted as UTC.
- A rejected message's expiry does not mark it stale (expiration applies only to pending/approved); revision back to pending can therefore produce a pending message whose stored expiry is already past, which the next read will mark stale. Producers should set a fresh `ttl_seconds`/`expires_at` when revising such a message.
- Webhook delivery is at-least-once with in-process threads and persisted attempts; a process crash can leave an event recorded as pending. Restart does not automatically replay old events.
- `ALLOW_PRIVATE_URLS=1` weakens SSRF protections and must not be used outside local testing.
