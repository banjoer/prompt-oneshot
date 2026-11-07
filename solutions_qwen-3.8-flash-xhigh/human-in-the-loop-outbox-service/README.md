# Human-in-the-Loop Outbox Service

A local, single-process service that gives AI agents and internal tools a **safe outbox**
for drafted email, WhatsApp, and Telegram messages. Producers submit over a REST API, a
human reviews in a web UI, and the human sends through their own apps using **prepared
handoff links**. The service never integrates with provider APIs and **never sends
anything by itself**.

> Built 2026-11-06 23:42 UTC by **Qwen3.8 Flash** (see the sign-off header in `app.py`
> and the footer of the SPA).

**Stack:** Python 3.11+ · Flask (only runtime dependency) · SQLite (stdlib) · vanilla
HTML/CSS/JS SPA, no build step, no CDN.

---

## Quick start

```bash
pip install -r requirements.txt
python3 app.py
```

Open <http://127.0.0.1:8000>. The API is at `/api/...`, docs at `/api/docs`, the
machine-readable spec at `/openapi.json`.

Run the tests (no external network needed; loopback fixtures only):

```bash
python3 -m unittest discover -s tests -v
```

## Configuration (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `DATA_DIR` | `./data` | SQLite database directory |
| `ATTACHMENT_DIR` | `./data/attachments` | Attachment bytes |
| `MAX_ATTACHMENT_BYTES` | `10485760` | Per-file size cap (10 MiB) |
| `MAX_MESSAGE_ATTACHMENT_BYTES` | `26214400` | Per-message total cap (25 MiB) |
| `EXPIRATION_INTERVAL_SECONDS` | `30` | Background expiration sweep period |
| `WEBHOOK_TIMEOUT_SECONDS` | `5` | Per-attempt webhook timeout |
| `WEBHOOK_MAX_ATTEMPTS` | `3` | Bounded delivery attempts |
| `WEBHOOK_BACKOFF_BASE_SECONDS` | `1` | Exponential backoff base (`base × 2^(n-1)`) |
| `DOWNLOAD_TIMEOUT_SECONDS` | `10` | Attachment URL download timeout |
| `MAX_REDIRECTS` | `3` | Redirect hops followed for downloads (each revalidated) |
| `ALLOW_PRIVATE_URLS` | `0` | **Local-testing override only** — permits loopback/private webhook & download URLs. Cloud-metadata/link-local ranges stay blocked even with this set. |
| `PORT` | `8000` | Listen port (always bound to `127.0.0.1`) |
| `MAX_HANDOFF_URL_LENGTH` | `1800` | Practical URL budget before handoff fallbacks kick in |

The service binds to **loopback only**. It has no authentication, users, or
multi-tenancy by design — it is a local, single-user tool.

## Architecture

```
app.py                  Flask entry point, routes, request parsing, error envelope
outbox/
  config.py             Env-config + /api/info payload
  db.py                 Schema, idempotent migrations (PRAGMA user_version),
                        WAL + foreign keys + BEGIN IMMEDIATE transactions
  timeutil.py           UTC ISO 8601 (ms, "Z") parse/format helpers
  errors.py             ApiError + 400/404/409/413/415 constructors
  service.py            Domain logic: submission, listing, lifecycle CAS, revisions,
                        expiration, handoff preparation, destinations, events
  channels.py           Channel adapters (email/whatsapp/telegram): destination
                        validation/normalization, handoff URLs, capabilities, warnings
  storage.py            Attachment store: filename sanitizing, generated storage names,
                        MIME sniffing, path-traversal-proof lookups
  netguard.py           SSRF guard, redirect revalidation, safe GET, webhook POST
  webhooks.py           Async delivery worker + expiration worker threads
  openapi_spec.py       OpenAPI 3.0 document (source of openapi.json)
static/                 SPA: index.html, styles.css, app.js
tests/                  unittest suite + loopback fixtures helpers
fixtures/               sample.txt + webhook_sink.py (manual test helpers)
```

Design rules: domain logic lives in `outbox/service.py`, never in route handlers;
channel-specific formatting is entirely inside `outbox/channels.py`; attachment bytes go
through the `AttachmentStore` interface; the SPA builds **no** channel URLs itself — it
renders the structured `/handoff` response.

## Database schema / migrations

All tables are created idempotently at startup; migration steps bump
`PRAGMA user_version` and are replayed safely if interrupted (v1 → all tables below):

* **messages** — id, channel, destination, normalized_destination, destination_kind,
  destination_label (snapshot), subject, body, status, created_at, updated_at,
  expires_at, webhook_url, rejection_reason, rejection_at, revision_number, source,
  metadata_json. Message IDs are stable across revisions; `created_at` never changes.
* **message_revisions** — full content snapshot per revision, including the attachment-id
  list and reference URLs of that revision, plus the rejection reason/timestamp the
  revision died with (captured when the next revision is created).
* **status_history** — from_status, to_status, reason, revision_number, timestamp.
  One row per accepted transition — always.
* **attachments** — id, filename (sanitized), stored_name (server-generated), MIME type,
  size, upload timestamp, source type (`multipart`/`url_download`), source URL.
* **external_references** — per-revision reference URLs (never fetched).
* **destination_labels** — (channel, normalized_destination) PK; unique label per channel.
* **webhook_events** — idempotency key `(message_id, event, revision_number)` is UNIQUE;
  state machine `queued → delivering → delivered/failed`, attempts, last error/code,
  next_attempt_at. **webhook_attempts** — one row per try with timing and result.

Rejected, stale, and cancelled messages are **never** deleted automatically. Nothing in
this service deletes message history.

## REST API summary

| Method & path | Purpose |
|---|---|
| `POST /api/messages` | Submit (JSON or multipart with `attachments` file parts) → `201 {id, status, created_at, revision_number}` |
| `GET /api/messages` | List with `status` (comma list ok), `channel`, `destination` (case-insensitive on destination or label), `created_from/to`, `expires_from/to`, `limit` (≤100), `offset`, `sort=newest\|oldest\|expires_soon\|expires_late` (no-expiry last). Envelope `{items,total,limit,offset}` |
| `GET /api/messages/{id}` | Full active message incl. attachments/references/label |
| `PATCH /api/messages/{id}` | Revise pending/rejected only → new revision, same id, back to `pending`. `status` in body = 400; terminal = 409 |
| `POST /api/messages/{id}/approve\|reject\|cancel\|mark-sent` | Lifecycle ops (reject requires non-empty reason) |
| `GET /api/messages/{id}/history` | All revisions + transitions chronologically, incl. webhook events |
| `GET /api/messages/{id}/handoff` | Approved-only structured handoff (URL, capabilities, warnings, manual actions, copy values) |
| `GET /api/messages/{id}/attachments[/{attachment_id}]` | List / download (`Content-Disposition: attachment`, `nosniff`) |
| `GET /api/messages/{id}/attachments.zip` | Download-all ZIP (stretch) |
| `GET /api/messages/{id}/webhook-events` | Delivery history for debugging |
| `GET /api/destinations` · `PUT/DELETE /api/destinations/label` | Discovered destinations and label CRUD |
| `GET /api/health` · `/api/info` · `/api/docs` · `/openapi.json` | System |

Errors are always `{"error": <code>, "message": <human>, ...context}` with proper status:
**400** validation, **404** missing, **409** invalid transition/conflict (includes
`current_status` and `allowed_actions`), **413** too large, **415** unsupported media.

## Message lifecycle

```
                 ┌──────────── approve ────────────┐
             pending ── reject ──► rejected ── PATCH ──┘   approved ── mark-sent ──► sent
                 │  ▲                                 │
             cancel│  └──── PATCH (new revision) ─────┤
                 ▼                                   ▼
             cancelled ◄── cancel ──── approved    stale ◄── expiration (pending or approved)
```

* Statuses: `pending, approved, sent, rejected, stale, cancelled`. `sent`, `stale`,
  `cancelled` are terminal and immutable.
* Every transition is a **compare-and-set** inside a write transaction: duplicate or
  concurrent requests cannot both succeed; exactly one wins and one history row is
  written.
* **Expiration** (`expires_at` XOR `ttl_seconds`, pending/approved only) is enforced
  lazily on every list/read/approve/handoff **and** by the background worker. An expired
  message can never become approved or handed off (409), and keeps all content/history.
* `mark-sent` happens **only** when the reviewer explicitly calls it (the UI requires a
  second confirmation with an explicit statement). Opening a handoff link or downloading
  an attachment never changes status.

## Attachments

Three mechanisms: multipart uploads, external **URL references** (stored, never
fetched), and **URL downloads** (fetched with the SSRF guard, redirect revalidation,
size caps, timeout, then stored as real attachments).

Storage rules: filenames are sanitized (paths stripped, control characters removed,
Windows reserved names neutralized); storage names are server-generated
(`att_<hex>_<safe-name>`), so the client filename is never a path and traversal is
impossible on both write and read. Downloads are `Content-Disposition: attachment` +
`X-Content-Type-Options: nosniff` with RFC 5987 filenames. Files are never executed.
Revised-away attachments remain on disk and in the old revision's history.

## Channel handoff: what can and cannot be prefilled

| Channel | Individual | Group / invite |
|---|---|---|
| Email | `mailto:` with recipient, subject, body URL-encoded | — |
| WhatsApp | `https://wa.me/<digits>?text=<encoded>` (E.164 `+…`, normalized) | `group:<Name>` → opens `https://wa.me/`, **no preselection/prefill claimed**; group name shown for manual pickup; copy controls provided |
| Telegram | `@username` or `t.me/…` → `https://t.me/<username>?text=<encoded>` | `group:<Name>` → `https://web.telegram.org/` fallback, manual find + paste; `+invite` → `https://t.me/+code` (join dialog opens; text cannot be prefilled) |

Honest limitations (also returned in the API `warnings`/`capabilities` so the UI can show
them):

* `mailto:` cannot carry attachments — the UI shows download buttons and instructs manual
  attaching.
* If the encoded URL would exceed `MAX_HANDOFF_URL_LENGTH` (≈1800), the service returns a
  shorter valid URL (recipient + subject, then recipient only) and flags
  `prefill_body=false`; copy controls remain available. Long bodies never produce broken
  or oversized links.
* All values are percent-encoded for UTF-8, special characters, and newlines.

## Webhooks

Optional `webhook_url` per message. On real events the service POSTs
`{event, message_id, status, revision_number, timestamp, …details}` — for
`message.rejected` the payload includes `rejection_reason`. Events: `message.approved`,
`message.rejected`, `message.sent`, `message.cancelled`, `message.stale`,
`message.revised`.

* The event row is committed **with** the state change; delivery runs **afterwards** in a
  background worker — it can never block or roll back a transition.
* Bounded retries: `WEBHOOK_MAX_ATTEMPTS` with exponential backoff
  (`WEBHOOK_BACKOFF_BASE_SECONDS × 2^(n-1)`); every attempt persisted with status/error.
* `(message_id, event, revision_number)` is a unique idempotency key — no duplicate
  events per revision.
* URLs are revalidated against the SSRF guard before **each** attempt.
* Delivery history is visible via `GET /api/messages/{id}/webhook-events` and in the UI.

## Security notes

* **SSRF**: outbound HTTP exists only for caller-supplied download/webhook URLs. Blocked
  by default: non-http(s), credential-bearing URLs, and hosts resolving to loopback,
  private, link-local, multicast, reserved, or unspecified addresses — including cloud
  metadata (169.254.169.254, 100.100.100.200, IPv6 ULA). `ALLOW_PRIVATE_URLS=1` is a
  documented local-testing override; link-local/metadata stay blocked even then. Redirect
  targets are revalidated hop by hop, hops capped by `MAX_REDIRECTS`.
* **Path traversal**: storage names match `^att_[hex]_[safe]$`-style server patterns and
  are re-resolved under the attachment dir on every read; `../` inputs can't reach the
  filesystem.
* **Execution**: uploaded/downloaded bytes are never run, served inline, or
  content-sniffed by the browser (`nosniff` + attachment disposition).
* **Race safety**: all transitions are `BEGIN IMMEDIATE` + CAS; approval vs. expiration
  is serialized the same way.
* No auth exists — that is why the default bind is `127.0.0.1`. Do not expose this to
  untrusted networks.

## curl walkthrough

Start the helpers in separate terminals when you want webhooks/downloads:

```bash
python3 fixtures/webhook_sink.py              # prints webhook POST bodies, port 9002
python3 -m http.server 9001 --directory fixtures   # serves sample.txt for url_download
ALLOW_PRIVATE_URLS=1 python3 app.py           # required for the two loopback helpers
```

```bash
# Email (JSON) with absolute expiry + webhook — save the spec's JSON as email.json
curl -sS -X POST http://127.0.0.1:8000/api/messages \
  -H 'Content-Type: application/json' --data @email.json
# → {"id":"msg_…","status":"pending","created_at":"…Z","revision_number":1}

# Multipart attachment
curl -sS -X POST http://127.0.0.1:8000/api/messages \
  -F channel=email -F destination=alex@example.com \
  -F subject='Q4 report draft' -F 'body=Hi Alex, please review the attached Q4 report.' \
  -F expires_at=2030-01-01T00:00:00Z -F source=report-agent \
  -F attachments=@fixtures/sample.txt

# WhatsApp individual / group; Telegram individual / group
curl -sS -X POST http://127.0.0.1:8000/api/messages -H 'Content-Type: application/json' \
  -d '{"channel":"whatsapp","destination":"+1 (415) 555-0123","body":"Your appointment is confirmed for 3 PM."}'
curl -sS -X POST http://127.0.0.1:8000/api/messages -H 'Content-Type: application/json' \
  -d '{"channel":"whatsapp","destination":"group:Project Alpha","body":"Standup moved to 10:00."}'
curl -sS -X POST http://127.0.0.1:8000/api/messages -H 'Content-Type: application/json' \
  -d '{"channel":"telegram","destination":"@alex_example","body":"Build finished successfully."}'
curl -sS -X POST http://127.0.0.1:8000/api/messages -H 'Content-Type: application/json' \
  -d '{"channel":"telegram","destination":"group:Ops Room","body":"Deploy is live."}'

# URL reference (never fetched) + URL download (fetched and stored)
curl -sS -X POST http://127.0.0.1:8000/api/messages -H 'Content-Type: application/json' -d '{
  "channel":"email","destination":"alex@example.com","subject":"Reference and file",
  "body":"See the external reference and the attached file.",
  "references":["https://example.com/spec"],
  "attachments":[{"kind":"url_download","url":"http://127.0.0.1:9001/sample.txt","filename":"sample.txt"}]}'

# TTL-based expiry / relative submission
curl -sS -X POST http://127.0.0.1:8000/api/messages -H 'Content-Type: application/json' \
  -d '{"channel":"email","destination":"a@b.co","body":"Quick one","ttl_seconds":3600}'

# Poll status / list the queue
curl -sS 'http://127.0.0.1:8000/api/messages?status=pending,approved,rejected&sort=expires_soon'
curl -sS http://127.0.0.1:8000/api/messages/msg_REPLACE

# Reject (reason mandatory) — visible in the sink, if running
curl -sS -X POST http://127.0.0.1:8000/api/messages/msg_REPLACE/reject \
  -H 'Content-Type: application/json' \
  -d '{"reason":"The recipient name is wrong. Address it to Alex Smith, not Alex Doe."}'

# Revise the rejected message (same id, revision 2, back to pending)
curl -sS -X PATCH http://127.0.0.1:8000/api/messages/msg_REPLACE \
  -H 'Content-Type: application/json' \
  -d '{"subject":"Q4 report draft — revised","body":"Hi Alex Smith,\n\nPlease review the attached Q4 report before Friday.\n\nThanks,\nSam"}'

# Approve, inspect the handoff, download attachments
curl -sS -X POST http://127.0.0.1:8000/api/messages/msg_REPLACE/approve
curl -sS http://127.0.0.1:8000/api/messages/msg_REPLACE/handoff
curl -sS -OJ http://127.0.0.1:8000/api/messages/msg_REPLACE/attachments/att_REPLACE
curl -sS -o bundle.zip http://127.0.0.1:8000/api/messages/msg_REPLACE/attachments.zip

# Mark sent (only this explicit call marks the message sent)
curl -sS -X POST http://127.0.0.1:8000/api/messages/msg_REPLACE/mark-sent

# Cancel
curl -sS -X POST http://127.0.0.1:8000/api/messages/msg_REPLACE/cancel

# Destinations and labels
curl -sS http://127.0.0.1:8000/api/destinations
curl -sS -X PUT http://127.0.0.1:8000/api/destinations/label \
  -H 'Content-Type: application/json' \
  -d '{"channel":"email","destination":"alex@example.com","label":"Alex — Client"}'
curl -sS -X DELETE 'http://127.0.0.1:8000/api/destinations/label?channel=email&destination=alex@example.com'
```

## Manual frontend test script

Primary journeys at desktop (1440×900) and phone width (390×844):

1. **Submit a pending email** via the JSON curl above; click ↻ Refresh in the SPA.
   Expect: a card in the review queue with channel chip, destination, subject, preview,
   created time, expiry countdown, rev 1, attachment count.
2. **Open the detail** by clicking the card. Expect: full body, metadata, timestamps with
   the local timezone label, and Approve / Reject with reason / Cancel buttons. On phone
   width the detail is a full-height sheet; ✕ or Escape closes it.
3. **Reject with empty reason**: open Reject, submit with the textarea empty → inline
   error "non-empty reason is required". Now type a real reason and confirm → status
   becomes ✕ Rejected, the reason callout shows it, history lists the transition, and the
   webhook event appears (delivery queued/delivered) if a webhook was set.
4. **Revise via PATCH** (curl above) and refresh → same id, rev 2, back in the queue as
   Pending; the detail's revision history still shows rev 1 with its rejection.
5. **Approve** → handoff panel appears with the `mailto:` link, capability chips
   (✓ recipient/subject/body, ✗ attachments), manual action checklist, copy-subject and
   copy-body buttons (clipboard permission required), attachment rows with ⬇ Download and
   ⬇ Download all (ZIP).
6. **Download attachments first** (as instructed), **then open the handoff link**. Watch
   the status chip: it must stay ✓ Approved through link opens and downloads.
7. **Mark as sent**: click → modal requires the explicit "I actually sent it" checkbox →
   confirm → status → Sent. Revisit via the History tab: Sent is terminal, no delivery
   actions, full history intact.
8. **Filtering/sorting**: switch status/channel/sort selects, type a destination or label
   substring, toggle Date ranges; empty/loading states appear where expected. The
   Destinations tab lists discovered addresses with counts and last use; assign, rename,
   remove a label — duplicate labels in one channel must show a clear conflict error.
9. **Expiration**: submit with `ttl_seconds: 2`, wait, press Refresh → the card is gone
   from the review queue (stale), visible under status Stale in History, and approve/
   handoff return 409.
10. **Keyboard/AX**: tab through the whole review flow; focus is always visible; Escape
    closes modals and the mobile sheet; destructive actions all confirm; no console errors.

## Troubleshooting

* **Port in use** — set `PORT=8001 python3 app.py`.
* **`400 invalid webhook_url`/`url_download failed` for a localhost URL** — expected;
  loopback is blocked by default. Start with `ALLOW_PRIVATE_URLS=1` for local testing only.
* **`409 conflict` on an action** — the message already moved (someone else approved it, or
  it expired). The response includes `current_status` and `allowed_actions`; refresh.
* **Attachment download 404 "attachment file is missing on disk"** — the DB row survived
  but the file didn't; restore the attachment directory from backup (see below) or PATCH
  a fresh attachment.
* **Webhooks stuck in `queued`/`failed`** — inspect `GET /api/messages/{id}/webhook-events`
  (each attempt with HTTP status/error is stored). The REST API stays fully usable
  regardless of webhook health.
* **Stale messages "not expiring"** — expiration is also checked on every read; if a card
  looks stale, press Refresh. The background sweep uses `EXPIRATION_INTERVAL_SECONDS`.

## Backup / restore

All state is two things: the SQLite database and the attachment directory.

**Backup** (service stopped, or momentarily for a consistent pair):

```bash
sqlite3 data/outbox.db "VACUUM INTO 'backup/outbox-$(date +%F).db'"   # online-safe copy
tar czf backup/attachments-$(date +%F).tgz -C data attachments
```

**Restore:**

```bash
cp backup/outbox-YYYY-MM-DD.db data/outbox.db
tar xzf backup/attachments-YYYY-MM-DD.tgz -C data
rm -f data/outbox.db-wal data/outbox.db-shm   # only when restoring a stopped instance
```

Keep the DB and the attachments archive from the **same moment** — attachment rows
reference files by generated name.

## Assumptions that materially affect behavior

* Email destinations are treated case-insensitively (normalized to lowercase) so labels
  and matching behave like real providers.
* WhatsApp numbers require `+`-prefixed E.164 after stripping ` ()-.`; 8–15 digits.
* Telegram supports `@username` (5–32 chars), `t.me/…` links, `+invite` codes, and
  `group:<name>`; nothing guesses a group's public username.
* A PATCH that provides new attachments **replaces** the active set (the old set stays in
  the previous revision and on disk); omitting `attachments` keeps them.
* `expires_at` in a PATCH may be set to a past instant (immediate expiry on next
  check); submissions require the future.
* Failed uploads that were rolled back can leave orphaned bytes in the attachment
  directory; they are unreachable from any revision and safe to delete manually.
* Webhook non-2xx responses count as failures; redirects for POST targets are rejected.
* Timestamps are stored/exchanged as UTC ISO 8601 with milliseconds and `Z`; the UI
  renders local time with an explicit timezone label.
