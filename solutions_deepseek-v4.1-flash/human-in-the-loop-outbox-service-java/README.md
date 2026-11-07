# Human-in-the-Loop Outbox Service

**Local review-and-handoff outbox for email, WhatsApp and Telegram messages.** Producers submit
messages over a REST API, a human reviews them in a Svelte dashboard, and the human sends them
through their own email/WhatsApp/Telegram client using prepared handoff links.

The service **never integrates with provider APIs and never sends anything by itself**.

> **Built 2026-11-07 01:20 UTC by DeepSeek V4.1 Flash** (Java 21 / Spring Boot 3.5 + Svelte 5).

---

## 1. What it does

- Accepts messages from AI agents or internal tools over JSON or multipart HTTP.
- Stores everything locally in SQLite plus a local attachment directory.
- Shows a review queue with status, channel, destination/label, content, expiry, revision and attachments.
- Enforces an explicit human lifecycle: `pending → approved → sent`, or `rejected`, `cancelled`, `stale`.
- Prepares honest channel handoffs (`mailto:`, `wa.me`, `t.me`) and states exactly what can and cannot
  be prefilled.
- Keeps a complete audit trail: every revision, status transition, webhook event and delivery attempt.
- Expires due messages transactionally and refuses approval/handoff/mark-sent for expired messages.
- Protects against SSRF, path traversal, unsafe filenames, unsafe MIME types and oversized uploads.

There is no authentication, user management, multi-tenancy, OAuth, external database, broker,
cloud storage or provider integration. It is a loopback, single-user local service.

---

## 2. Stack and repository layout

| Layer | Technology |
|---|---|
| HTTP API | Java 21, Spring Boot 3.5, Spring MVC |
| Domain | Plain Java services and Spring `TransactionTemplate` |
| Persistence | SQLite via `sqlite-jdbc`, JDBC (`JdbcTemplate`), WAL mode, foreign keys |
| Frontend | Svelte 5 + Vite, compiled to static assets (no runtime CDN) |
| Tests | JUnit 5, Spring Boot test, loopback HTTP fixtures |
| Build | Maven (wrapper included) |

```
human-in-the-loop-outbox-service-java/
├── pom.xml / mvnw / mvnw.cmd / .mvn
├── src/main/java/dev/oneshot/outbox/
│   ├── OutboxApplication.java        # entry point + sign-off header
│   ├── config/                       # properties, DataSource, migrations, scheduler
│   ├── model/                        # records/enums
│   ├── repo/                         # JDBC repositories
│   ├── service/                      # domain logic, lifecycle, expiry, webhooks, handoff
│   ├── channel/                      # email / WhatsApp / Telegram adapters
│   ├── attachments/                   # storage interface, local storage, URL downloader
│   ├── security/                     # SSRF URL guard
│   ├── util/                         # UTC timestamps, IDs, filename/MIME hardening, encoding
│   └── web/                          # controllers, error handling, request mapping, docs
├── src/main/resources/
│   ├── application.yml
│   ├── static/                       # compiled Svelte SPA (committed)
│   └── public/openapi.json           # OpenAPI 3.0.3 document
├── frontend/                         # Svelte source, Vite config, package.json
├── src/test/java/dev/oneshot/outbox/ # integration + unit tests
├── fixtures/                         # sample attachment, JSON payloads, webhook sink
└── README.md
```

The compiled frontend is committed under `src/main/resources/static/`, so **running the service does
not require Node.js**. Node is only needed if you change the Svelte UI.

---

## 3. Quick start

### Prerequisites

- **JDK 21+**
- **Maven 3.9+** (or use the included `./mvnw`, which downloads Maven on first use)

### Run

```bash
cd human-in-the-loop-outbox-service-java
./mvnw spring-boot:run
# or: mvn spring-boot:run
```

Open <http://127.0.0.1:8000>.

The same process serves the REST API, `/openapi.json`, `/api/docs` and the SPA at `/`.

To use a different loopback port or a temporary data directory:

```bash
PORT=8001 DATA_DIR=/tmp/outbox-data ATTACHMENT_DIR=/tmp/outbox-data/attachments ./mvnw spring-boot:run
```

The service binds to `127.0.0.1` deliberately. There is no way to expose it publicly without changing
`server.address` yourself.

### Run the packaged jar

```bash
./mvnw clean package
java -jar target/human-in-the-loop-outbox-1.0.0.jar
```

### Run the tests

```bash
./mvnw test
```

Current suite: **41 tests, 0 failures, 0 errors, 0 skipped** across:
`OutboxCoreIntegrationTest` (14), `OutboxReliabilityIntegrationTest` (16), `OutboxSsrfIntegrationTest` (3),
`UrlGuardTest` (3), `FilenamesTest` (3), `PercentTest` (2).

### Rebuild the Svelte frontend (optional)

```bash
cd frontend
npm install
npm run build      # writes ../src/main/resources/static
```

`npm run dev` starts Vite on `5173` and proxies `/api` and `/openapi.json` to `127.0.0.1:8000`.

---

## 4. Configuration

All settings are environment variables with safe defaults.

| Variable | Default | Meaning |
|---|---|---|
| `DATA_DIR` | `./data` | Directory containing `outbox.db` (created on startup) |
| `ATTACHMENT_DIR` | `./data/attachments` | Directory for stored attachment bytes (created on startup) |
| `MAX_ATTACHMENT_BYTES` | `10485760` (10 MB) | Per-file limit for multipart and URL downloads |
| `MAX_MESSAGE_ATTACHMENT_BYTES` | `26214400` (25 MB) | Total active attachment bytes per message |
| `EXPIRATION_INTERVAL_SECONDS` | `30` | Background expiration worker interval |
| `WEBHOOK_TIMEOUT_SECONDS` | `5` | Per-attempt HTTP timeout |
| `WEBHOOK_MAX_ATTEMPTS` | `3` | Maximum delivery attempts per event |
| `WEBHOOK_BACKOFF_BASE_SECONDS` | `1` | Exponential backoff base (attempt 1 waits base, attempt 2 waits 2×base, …) |
| `DOWNLOAD_TIMEOUT_SECONDS` | `10` | Attachment-download request timeout |
| `MAX_REDIRECTS` | `3` | Maximum redirects for attachment downloads (every hop revalidated) |
| `ALLOW_PRIVATE_URLS` | `0` | **Local testing only.** `1` allows loopback/private/metadata URLs |
| `PORT` | `8000` | Server port |
| `HANDOFF_URL_MAX_CHARS` | `1800` | Maximum practical handoff URL length |
| `WEBHOOK_WORKER_INTERVAL_MS` | `300` | Webhook polling interval |
| `BUILT_AT` | build stamp in `application.yml` | Sign-off timestamp shown in `/api/info` and the SPA footer |
| `BUILT_BY` | `DeepSeek V4.1 Flash` | Sign-off author/model |

Non-sensitive values are exposed at `GET /api/info`. Private directories, limits, timeouts, the
`allow_private_urls` flag, schema version and build sign-off are included.

`ALLOW_PRIVATE_URLS=1` is required for the local webhook sink and local download fixture shown in the
examples. **Never enable it for normal use.**

---

## 5. Architecture overview

```
                 ┌───────────────────────────────────────────────────────┐
 Browser SPA ───▶│  Spring MVC controllers (/api/...)                    │
                 │    MessageController, DestinationController,         │
                 │    SystemController, DocsController                  │
                 └───────────────┬───────────────────────────────────────┘
                                 │
                 ┌───────────────▼───────────────────────────────────────┐
                 │ Domain services                                       │
                 │  MessageService · HandoffService · DestinationService │
                 │  ExpirationService · WebhookService · AttachmentService│
                 │  ChannelRegistry → Email / WhatsApp / Telegram adapters│
                 └───────────────┬───────────────────────────────────────┘
                                 │
        ┌────────────────────────┼─────────────────────────────┐
        │                        │                             │
┌───────▼────────┐     ┌─────────▼──────────┐        ┌─────────▼──────────┐
│ JDBC repos     │     │ LocalAttachment-   │        │ Outbound HTTP      │
│ SQLite (WAL)   │     │ Storage (UUID files)│       │ UrlDownloader +    │
│                │     │                    │        │ webhook delivery   │
└────────────────┘     └────────────────────┘        └────────────────────┘
```

Design rules:

- **Domain logic is separate from HTTP handlers.** Controllers parse/validate request shape and call
  services; services own transitions, revisions and audit rows.
- **Channel-specific URL construction lives only in channel adapters.** The SPA consumes structured
  handoff data; it never builds `mailto:`, `wa.me` or `t.me` URLs.
- **Attachment persistence is behind `AttachmentStorage`** with one local implementation.
- **Transactions cover every state change**, including the status-history row and the webhook event row.
- **SQLite uses one connection** (`Hikari maximumPoolSize=1`) to keep its single-writer semantics
  predictable; WAL mode and `busy_timeout=5000` are enabled. This is appropriate for the local
  single-user deployment.
- **Two scheduler threads**: expiration must not be delayed by a slow webhook HTTP call.

---

## 6. Database schema and migrations

SQLite file: `<DATA_DIR>/outbox.db`.

Startup runs idempotent, forward-only migrations recorded in `schema_migrations`. The current schema
version is **1**. Migrations only add tables/indexes; no automatic deletion of messages or history.

| Table | Purpose |
|---|---|
| `messages` | Active message state: id, channel, destination + normalized address, label snapshot, subject, body, status, created/updated/expiry, webhook URL, rejection, revision, source, metadata |
| `message_revisions` | Complete content snapshot for every revision, including rejection data preserved at that revision |
| `revision_attachments` | Ordered attachment set per revision |
| `revision_references` | Ordered external URL references per revision (stored only, never fetched) |
| `attachments` | Unique attachment ID, sanitized original filename, MIME type, size, generated storage name, timestamp, source type (`multipart` / `url_download`), source URL |
| `status_history` | from/to status, reason, revision number, UTC timestamp |
| `destination_labels` | channel + normalized destination → reviewer label, unique per channel |
| `webhook_events` | Event type, revision, JSON payload, created/delivered timestamps, attempt count, next attempt, last error; unique `(message_id, event, revision_number)` |
| `webhook_attempts` | Per-attempt status, HTTP status, error, started/finished timestamps |

Timestamps are stored as UTC ISO-8601 with `Z`, truncated to whole seconds. The UI renders local time
and labels the timezone. Message IDs (`msg_…`), attachment IDs (`att_…`) and event IDs (`wh_…`) are
stable and random.

Foreign keys and WAL are enabled on every connection. Data directories are created at startup.

---

## 7. REST API summary

Everything is relative to `http://127.0.0.1:8000`. Errors use a consistent shape:

```json
{
  "error": {
    "code": "invalid_transition",
    "message": "Only pending messages can be approved. Current status: sent.",
    "current_status": "sent",
    "allowed_actions": []
  }
}
```

Codes: `400 validation_error` / `malformed_request` / `unsafe_url`, `404 not_found`,
`405 method_not_allowed`, `409 invalid_transition` / `conflict`, `413 payload_too_large`,
`415 unsupported_media_type`.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/messages` | Submit JSON or multipart message |
| `GET` | `/api/messages` | List/filter/paginate/sort |
| `GET` | `/api/messages/{id}` | Active message detail |
| `PATCH` | `/api/messages/{id}` | Revise a pending/rejected message (JSON or multipart) |
| `POST` | `/api/messages/{id}/approve` | `pending → approved` |
| `POST` | `/api/messages/{id}/reject` | `pending → rejected`, mandatory reason |
| `POST` | `/api/messages/{id}/cancel` | `pending/approved/rejected → cancelled` |
| `POST` | `/api/messages/{id}/mark-sent` | `approved → sent`, explicit confirmation only |
| `GET` | `/api/messages/{id}/history` | All revisions + status transitions |
| `GET` | `/api/messages/{id}/handoff` | Structured handoff, approved only |
| `GET` | `/api/messages/{id}/attachments` | Active attachment list |
| `GET` | `/api/messages/{id}/attachments/{attachment_id}` | Download one file |
| `GET` | `/api/messages/{id}/attachments.zip` | Download all active files as ZIP |
| `GET` | `/api/messages/{id}/webhook-events` | Delivery events and attempts |
| `GET` | `/api/destinations` | Discovered destinations + labels |
| `PUT` | `/api/destinations/label` | Assign/rename a label |
| `DELETE` | `/api/destinations/label?channel=…&destination=…` | Remove a label |
| `GET` | `/api/health` | Health and database status |
| `GET` | `/api/info` | Non-sensitive configuration |
| `GET` | `/api/docs` | Human-readable docs rendered from OpenAPI |
| `GET` | `/openapi.json` | OpenAPI 3.0.3 document |

### Listing parameters

`status` (single, comma-separated, `active`/`non_terminal`, or `all`), `channel`, `destination`
(case-insensitive substring on destination, normalized destination or label), `created_after`,
`created_before`, `expires_after`, `expires_before`, `sort` (`newest` default, `oldest`,
`expires_soon`, `expires_late`, plus SPA-focused `review`), `limit` (default 20, max 100), `offset`.

Messages without expiration sort **last** for both expiration orders. The envelope is always:

```json
{"items": [], "total": 0, "limit": 20, "offset": 0, "sort": "newest"}
```

### Submission shape

JSON:

```json
{
  "channel": "email | whatsapp | telegram",
  "destination": "alex@example.com",
  "subject": "optional single line",
  "body": "required",
  "expires_at": "2030-01-01T00:00:00Z",
  "ttl_seconds": 3600,
  "webhook_url": "http://127.0.0.1:9002/hooks/outbox",
  "source": "report-agent",
  "destination_label": "Alex — Client",
  "metadata": {"ticket": "OPS-142"},
  "references": ["https://example.com/spec"],
  "attachments": [
    {"kind": "url_reference", "url": "https://example.com/reference"},
    {"kind": "url_download", "url": "http://127.0.0.1:9001/sample.txt", "filename": "sample.txt"}
  ]
}
```

- `expires_at` and `ttl_seconds` are **mutually exclusive**; TTL must be a positive integer and an
  absolute expiry must be in the future.
- `metadata` must be a JSON object (max 20,000 serialized characters).
- `references` and `url_reference` entries are stored only and **never fetched**.
- `url_download` entries are fetched, SSRF-checked and stored as real attachments.
- Multipart uses the repeated form field name `attachments` for files; scalar fields are normal form
  fields; `metadata` is a JSON string.

PATCH accepts the same content/expiry/reference/attachment fields. Omitted fields are unchanged.
`expires_at: null` clears expiration. New attachments are **appended**; supplying `references` replaces
the active reference set. A `status` field is rejected with 400. Only pending and rejected messages
may be patched.

---

## 8. Message lifecycle

```
              approve                 mark-sent
  pending ─────────────▶ approved ─────────────▶ sent        (terminal)
     │  │                    │  │
     │  │ reject             │  │ cancel
     │  └────────▶ rejected ─┼──┴─────────────▶ cancelled    (terminal)
     │               │       │
     │  PATCH        │       │ expire
     └───────────────┘       ▼
        (new revision)     stale                              (terminal)

  pending / approved / rejected ──cancel──▶ cancelled
  rejected ──PATCH (new revision)──▶ pending
```

Allowed transitions:

| From | To | Operation |
|---|---|---|
| `pending` | `approved` | `POST /approve` |
| `pending` | `rejected` | `POST /reject` (reason required) |
| `pending` | `cancelled` | `POST /cancel` |
| `pending` | `stale` | automatic expiration |
| `rejected` | `pending` | `PATCH` (new revision only) |
| `rejected` | `cancelled` | `POST /cancel` |
| `approved` | `sent` | `POST /mark-sent` (explicit human confirmation) |
| `approved` | `cancelled` | `POST /cancel` |
| `approved` | `stale` | automatic expiration |

`sent`, `stale` and `cancelled` are terminal and immutable. Transitions are compare-and-set inside a
transaction; a duplicate/concurrent request gets `409` with `current_status` and `allowed_actions`.
Exactly one status-history row is written.

**Important:** opening a handoff link, copying text or downloading an attachment can never change
status. Only `POST /mark-sent` sets `sent`, and the UI requires a second explicit confirmation.

### Rejection and revision

- Rejection requires a non-empty reason; it is stored on the message and current revision, recorded in
  status history, and emitted as `message.rejected`.
- `PATCH` on a rejected message creates a **new revision** with the same message ID and original
  `created_at`, clears the active rejection fields, increments `revision_number`, returns it to
  `pending`, and emits `message.revised`.
- The old revision keeps its full content, attachments, references and rejection data.
- `PATCH` on an approved/sent/stale/cancelled message returns `409`.

---

## 9. Expiration

- No expiration by default.
- Absolute `expires_at` or relative `ttl_seconds`, never both.
- Applies only to `pending` and `approved`.
- Expiration is checked:
  - before every list/detail/history/attachment/handoff read,
  - before approval, rejection, cancellation and mark-sent,
  - by a periodic worker (`EXPIRATION_INTERVAL_SECONDS`).
- Expiry CAS and approval CAS are mutually exclusive: an expired message can never become approved.
- Expired messages become `stale`, leave active queues, refuse approval/handoff/mark-sent with `409`,
  and retain all content, attachments and history. Nothing is deleted.
- Messages without expiration remain active indefinitely and sort last in expiration orderings.

---

## 10. Channel handoff behavior and limitations

The API returns structured handoff data:

```json
{
  "channel": "whatsapp",
  "destination": "+1 (415) 555-0123",
  "normalized_destination": "14155550123",
  "handoff_url": "https://wa.me/14155550123?text=…",
  "capabilities": {
    "prefill_recipient": true,
    "prefill_subject": false,
    "prefill_body": true,
    "attachments_supported": false
  },
  "manual_actions": ["…"],
  "warnings": ["…"],
  "copy": {"subject": null, "body": "…"},
  "attachments": [{"download_url": "/api/messages/…/attachments/att_…"}]
}
```

| Channel / destination | Link | What is prefilled | Manual work |
|---|---|---|---|
| Email individual | `mailto:addr?subject=…&body=…` | recipient, subject, body | Download and attach files manually; send in email client |
| Email over ~1800 chars | `mailto:addr?subject=…` or recipient only | recipient + maybe subject | Copy body; attach files; send manually |
| WhatsApp individual | `https://wa.me/<digits>?text=…` | recipient and body | Press send; attach files manually |
| WhatsApp group (`group:Name`) | `https://web.whatsapp.com/` | **nothing** | Open WhatsApp, select the named group, paste body, attach files, send |
| Telegram individual (`@user`, `t.me/user`) | `https://t.me/user?text=…` | recipient; body where the client supports `?text=` | Some clients ignore text prefill; use Copy body; attach files manually |
| Telegram group (`group:Name`) | `https://web.telegram.org/` | **nothing** | Open Telegram, select the named group, paste body, attach files, send |
| Telegram private invite (`t.me/+hash`) | `https://t.me/+hash` | **nothing** | Open/join the private chat, paste body, attach files, send |

Encoding is strict UTF-8 percent-encoding: spaces become `%20`, newlines `%0A`, `&` `%26`, `+` `%2B`,
accented characters and emoji are byte-encoded. Long bodies are never allowed to break the link:
the API drops the body (and then the subject, for email) and warns the reviewer, while copy controls
still expose the complete original content.

WhatsApp numbers are normalized by removing spaces, dots, parentheses and hyphens, removing a leading
`00`, and requiring 7–15 digits. This is intentionally simple and does not use libphonenumber.

---

## 11. Attachments and references

Three mechanisms:

1. **Multipart upload** — repeated `attachments` file parts. Stored under a generated UUID name;
   the client filename is never used as a path.
2. **URL reference** (`kind: url_reference` or `references[]`) — stored as a reference only. It is
   never fetched and is exempt from SSRF checks because the service does not connect to it.
3. **URL download** (`kind: url_download`) — fetched with timeout, redirect limit, size cap and SSRF
   checks on every hop, then stored as a normal attachment with `source_type=url_download` and its URL.

Limits and safety:

- Per-file limit `MAX_ATTACHMENT_BYTES`; total active set limit `MAX_MESSAGE_ATTACHMENT_BYTES`.
  Violations return `413` before any message is committed.
- Spring's multipart container limit is deliberately high (1 GB) so the application's configurable
  limits produce the meaningful error; do not treat the container value as the security limit.
- Filenames are stripped of paths, control characters and Windows reserved names, bounded to 180 chars,
  and stored with a generated collision-free name such as `att_<uuid>.pdf`.
- MIME types are sanitized to a valid `type/subtype`; invalid/malformed values fall back to
  `application/octet-stream`.
- Downloads revalidate SSRF on every redirect; redirects that produce a blocked address are refused.
- Path traversal is prevented both when resolving storage names and when serving downloads.
- Download responses use `Content-Disposition: attachment`, `X-Content-Type-Options: nosniff` and a
  safe encoded filename (including `filename*`). Files are never executed.
- Missing records or missing bytes return a clear `404`; attachment records are retained for audit.
- The optional ZIP action (`attachments.zip`) builds a fresh archive from the local store with unique
  sanitized entry names and returns `404` if any referenced file is missing.
- Downloading or listing attachments never changes message status.

References are replaced when a PATCH supplies `references`; otherwise they stay unchanged. New
attachments are appended on PATCH and are linked to the new revision; previous revisions keep their
own attachment references.

---

## 12. Destination labels

- Destinations are discovered automatically from submitted messages; no registration.
- The canonical key is `(channel, normalized destination)`, so multiple accounts, numbers and groups
  coexist independently.
- `GET /api/destinations` returns channel, destination spelling, normalized address, label, message
  count and last-used timestamp. Label-only entries can have `message_count: 0`.
- Labels are 1–80 characters, control-character free, and unique per channel (case-insensitive via a
  lower-case unique index). Duplicates return `409`.
- Renaming updates the managed label; the message's original `destination_label` snapshot is preserved
  separately.
- Removing a label deletes only that label row. Messages, snapshots and history are untouched.
- A previously labelled destination automatically shows its label again when a new message uses the
  same channel + normalized destination (unless the label was removed).

---

## 13. Webhooks

A message may carry one `webhook_url`. The service emits events only for real state changes:

`message.approved`, `message.rejected`, `message.sent`, `message.cancelled`, `message.stale`,
`message.revised`.

Example payload:

```json
{
  "event": "message.rejected",
  "message_id": "msg_8f2c1a4b9d30",
  "status": "rejected",
  "revision_number": 1,
  "timestamp": "2026-11-06T20:00:00Z",
  "channel": "email",
  "destination": "alex@example.com",
  "rejection_reason": "The recipient name is wrong. Address it to Alex Smith, not Alex Doe.",
  "previous_status": "pending"
}
```

Delivery semantics:

- The event row is inserted **in the same transaction as the state change**.
- Delivery happens asynchronously after commit. A slow or failing webhook never blocks or rolls back
  the transition.
- Attempts use `WEBHOOK_TIMEOUT_SECONDS`, bounded exponential backoff starting at
  `WEBHOOK_BACKOFF_BASE_SECONDS`, and at most `WEBHOOK_MAX_ATTEMPTS`.
- Every event and every attempt is persisted with status, HTTP status, timestamps and last error.
  `GET /api/messages/{id}/webhook-events` exposes the history; the SPA shows it in the detail panel.
- The unique key `(message_id, event, revision_number)` prevents duplicate event rows, and the
  `Idempotency-Key` header (`message_id:event:revision`) lets receivers deduplicate at-least-once
  retries after a crash between POST and local acknowledgement.
- Webhook URLs are SSRF-checked at submission and **revalidated before every attempt**. Redirects are
  not followed for webhooks.
- Failures are recorded, never rolled back. With no webhook URL configured, no event row is created.
- Events for `message.stale` are emitted by the expiration worker, including when expiration is
  triggered by a read.

Outbound HTTP is limited to caller-supplied attachment-download URLs and webhook URLs. There are no
third-party integrations, telemetry or analytics.

---

## 14. Security notes

- **SSRF:** by default, URLs resolving to loopback, private, link-local, multicast, unspecified,
  carrier-grade-NAT, benchmarking, documentation/reserved ranges, IPv6 unique-local space, cloud
  metadata names and `.internal` hosts are blocked. Addresses are resolved and checked; every redirect
  hop is rechecked. `ALLOW_PRIVATE_URLS=1` is an explicit local-testing override and is reported by
  `/api/info`. Note: the JDK HTTP client resolves the hostname again at connect time, so DNS-rebinding
  protection is best-effort; run only on a trusted local network.
- **Path traversal:** storage names are generated UUIDs; any supplied storage reference containing
  separators, `..`, absolute paths or leading dots is rejected. Downloads resolve inside the configured
  root only.
- **Filenames/MIME:** path components and control characters stripped, reserved names prefixed, length
  bounded; MIME sanitized; served as attachment with `nosniff`.
- **Size:** per-file and per-message limits enforced in code with `413`; oversized requests never commit
  a message.
- **No execution:** uploaded/downloaded files are inert; nothing is launched or interpreted.
- **No auth:** do not expose this service beyond loopback. It has no authentication by design.
- **SQL:** all queries use parameter binding; no string interpolation of user values.
- **CSRF:** there is no cookie auth/session, and the API is same-origin; destructive actions are
  explicit POSTs.

---

## 15. Automated tests

```bash
./mvnw test
```

The suite uses temporary SQLite/attachment directories and loopback HTTP fixtures. It does **not**
use external network resources; loopback fixtures are allowed by the explicit testing override.

Coverage includes:

- JSON and multipart submission; field/shape validation; malformed JSON; unsupported media (`415`).
- Listing filters, pagination, newest/oldest/expiration sorts, null-expiration-last and default order.
- Retrieval and `404`s; complete detail; metadata.
- Approve, reject (empty and valid reason), cancel from every allowed status, mark-sent, invalid
  transitions and terminal immutability.
- Rejection followed by revision(s): stable ID, original `created_at`, revision 2, preserved previous
  revision and rejection data, cleared active rejection, `message.revised`.
- Concurrent approvals: exactly one `200`, one `409`, one status-history row.
- Expiration via TTL and absolute timestamps for pending and approved messages, background worker,
  retention of content/attachments/history, blocked approval/handoff, and approval-vs-expiry race.
- Destination discovery, labels, renames, removal without message changes, duplicate-label conflicts.
- Multipart files, sanitized traversal filenames, individual downloads, ZIP, missing physical files,
  `413` per-file and per-message limits.
- URL references (never fetched) and URL downloads through a local fixture server, redirects,
  redirect-loop rejection and invalid schemes.
- Webhooks: all event types, payloads, async success, retries with backoff, permanent failure
  (no rollback), timeout behaviour, no duplicate events, delivery history.
- Channel adapter URLs and fallbacks: mailto encoding, long-body fallback, WhatsApp individual/group,
  Telegram individual/group/private invite, UTF-8 and newlines.
- SSRF blocks for loopback/private/link-local/metadata in both webhooks and downloads, with the
  private-URL override off; unit tests for `UrlGuard`, filename sanitization and percent encoding.
- Health/info/docs/OpenAPI presence and required paths.

### Manual frontend test script

1. Start the service with local fixtures enabled:
   ```bash
   ALLOW_PRIVATE_URLS=1 ./mvnw spring-boot:run
   python3 fixtures/webhook_sink.py          # separate terminal
   python3 -m http.server 9001 --directory fixtures   # separate terminal
   ```
2. Open <http://127.0.0.1:8000>. Confirm the footer shows the build timestamp and author/model.
3. Submit the email example:
   ```bash
   curl -sS -X POST http://127.0.0.1:8000/api/messages \
     -H 'Content-Type: application/json' --data @fixtures/email.json
   ```
   Refresh the queue. The message appears as **Pending** with destination, subject, expiry, revision 1,
   attachment count 0. The queue should put pending above approved/rejected.
4. Open the message. Verify full body, metadata, timestamps, source, status history and the empty
   webhook history.
5. Click **Reject…**, try to submit with an empty reason (button disabled / error), then enter a reason.
   Confirm the message becomes **Rejected**, the reason is visible, and the sink prints
   `message.rejected`.
6. Using curl, PATCH the rejected message with a revised subject/body. Refresh the detail/queue:
   status returns to **Pending**, revision 2, same message ID and created time, and history shows both
   revisions with the old rejection preserved.
7. Approve the message. The handoff panel appears; verify the `mailto:` link, capabilities, warnings
   and manual attachment instructions. Click **Open in Email** and **Copy body**. The status must
   remain **Approved**.
8. Download the attachment (or upload one first) from the detail panel. Confirm status remains
   **Approved** and the file downloads with its original name.
9. Click **Mark as sent…**, try to confirm without checking the acknowledgment (button disabled), then
   check the explicit statement and confirm. Status becomes **Sent**; the sink prints
   `message.sent`; the message moves to the terminal filters.
10. Use the status chips, channel/destination/date filters and sorting controls. Verify **All** shows
    actionable messages first and terminal messages under a separate divider, and that default sorting
    is pending → approved → rejected.
11. Submit WhatsApp/Telegram individual and `group:` messages and inspect their handoffs:
    `wa.me` and `t.me` links for individuals; manual group fallback with copy controls and target name
    for groups; private Telegram invite fallback.
12. Open **Destinations**. Assign a label, rename it, try assigning the same label to another
    destination in the same channel (clear 409 error), then remove it. Confirm messages and their
    snapshot labels remain untouched.
13. Submit a message with `ttl_seconds: 2`, wait, refresh: it becomes **Stale**, leaves actionable
    filters, retains content/attachments, and Approve/Handoff return 409.
14. Resize to 390×844 and 1440×900. Confirm there is no horizontal page overflow, the detail becomes a
    full-width sheet, modals are usable, Escape closes the top modal, focus is visible, and controls
    disable while requests are in flight.

---

## 16. curl cookbook

Set a base URL:

```bash
BASE=http://127.0.0.1:8000
```

### Email JSON submission

```bash
curl -sS -X POST "$BASE/api/messages" \
  -H 'Content-Type: application/json' \
  --data @fixtures/email.json
```

### Multipart submission with an attachment

```bash
curl -sS -X POST "$BASE/api/messages" \
  -F channel=email \
  -F destination=alex@example.com \
  -F subject='Q4 report draft' \
  -F body='Hi Alex, please review the attached Q4 report.' \
  -F expires_at=2030-01-01T00:00:00Z \
  -F source=report-agent \
  -F attachments=@fixtures/sample.txt
```

### Relative TTL

```bash
curl -sS -X POST "$BASE/api/messages" \
  -H 'Content-Type: application/json' \
  -d '{"channel":"email","destination":"alex@example.com","subject":"Quick note","body":"Expires in two minutes.","ttl_seconds":120}'
```

### WhatsApp individual and group

```bash
curl -sS -X POST "$BASE/api/messages" -H 'Content-Type: application/json' \
  --data @fixtures/whatsapp.json

curl -sS -X POST "$BASE/api/messages" -H 'Content-Type: application/json' \
  --data @fixtures/whatsapp-group.json
```

### Telegram individual and group

```bash
curl -sS -X POST "$BASE/api/messages" -H 'Content-Type: application/json' \
  --data @fixtures/telegram.json

curl -sS -X POST "$BASE/api/messages" -H 'Content-Type: application/json' \
  --data @fixtures/telegram-group.json
```

### URL reference and URL download

Start `python3 -m http.server 9001 --directory fixtures` and run the service with
`ALLOW_PRIVATE_URLS=1`:

```bash
curl -sS -X POST "$BASE/api/messages" \
  -H 'Content-Type: application/json' \
  --data @fixtures/url-download.json
```

`https://example.com/spec` is stored as a reference and never fetched. The local URL is fetched and
stored as a real attachment.

### Configure a webhook

Start `python3 fixtures/webhook_sink.py` and use `ALLOW_PRIVATE_URLS=1`:

```bash
curl -sS -X POST "$BASE/api/messages" \
  -H 'Content-Type: application/json' \
  -d '{
    "channel": "email",
    "destination": "alex@example.com",
    "subject": "Webhook demo",
    "body": "Reject me to see a webhook.",
    "webhook_url": "http://127.0.0.1:9002/hooks/outbox",
    "source": "demo-agent"
  }'
```

### Reject, poll, revise, approve, hand off, cancel

```bash
MSG=msg_REPLACE

# Mandatory reason
curl -sS -X POST "$BASE/api/messages/$MSG/reject" \
  -H 'Content-Type: application/json' \
  -d '{"reason":"The recipient name is wrong. Address it to Alex Smith, not Alex Doe."}'

# Poll status
curl -sS "$BASE/api/messages/$MSG"

# Revise the rejected message (same ID, revision 2, back to pending)
curl -sS -X PATCH "$BASE/api/messages/$MSG" \
  -H 'Content-Type: application/json' \
  -d '{"subject":"Q4 report draft — revised","body":"Hi Alex Smith,\n\nPlease review the attached Q4 report before Friday.\n\nThanks,\nSam"}'

# Approve and prepare handoff
curl -sS -X POST "$BASE/api/messages/$MSG/approve"
curl -sS "$BASE/api/messages/$MSG/handoff"

# Mark sent only after you actually sent it in your own app
curl -sS -X POST "$BASE/api/messages/$MSG/mark-sent" \
  -H 'Content-Type: application/json' -d '{"confirmed":true}'

# Cancel (only while pending/approved/rejected)
curl -sS -X POST "$BASE/api/messages/$MSG/cancel" \
  -H 'Content-Type: application/json' -d '{"reason":"Superseded by a newer draft."}'
```

### Filter, paginate, sort

```bash
curl -sS "$BASE/api/messages?status=pending&channel=email&limit=20&offset=0&sort=newest"
curl -sS "$BASE/api/messages?status=sent&created_after=2026-01-01&created_before=2026-12-31"
curl -sS "$BASE/api/messages?sort=expires_soon&limit=50"
```

### Labels and destinations

```bash
curl -sS "$BASE/api/destinations"
curl -sS -X PUT "$BASE/api/destinations/label" \
  -H 'Content-Type: application/json' \
  -d '{"channel":"whatsapp","destination":"+1 (415) 555-0123","label":"Alex — Client"}'
curl -sS -X DELETE "$BASE/api/destinations/label?channel=whatsapp&destination=14155550123"
```

### Download attachments and webhook history

```bash
curl -sS "$BASE/api/messages/$MSG/attachments"
curl -sS -OJ "$BASE/api/messages/$MSG/attachments/att_REPLACE"
curl -sS -o attachments.zip "$BASE/api/messages/$MSG/attachments.zip"
curl -sS "$BASE/api/messages/$MSG/webhook-events"
```

---

## 17. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `Address already in use` | Set `PORT=8001` or stop the other process. |
| `SQLITE_BUSY` | Another process is writing the DB; this service uses one writer. Stop external writers or retry. |
| `unsafe_url` for a local webhook/download | Default SSRF protection blocks private/loopback. Use `ALLOW_PRIVATE_URLS=1` only for local testing. |
| `413 payload_too_large` | Increase `MAX_ATTACHMENT_BYTES` / `MAX_MESSAGE_ATTACHMENT_BYTES`, or reduce files. |
| Handoff has no body | The body exceeded `HANDOFF_URL_MAX_CHARS`; use **Copy body**. The full body is never truncated in storage. |
| Webhook shows failed attempts | Inspect `GET /api/messages/{id}/webhook-events`; check the sink, URL, timeout and SSRF rules. State changes remain committed. |
| SPA loads but API calls fail | Ensure you opened the same origin/port as the service; check the browser console and `/api/health`. |
| `401`/`403` from a provider | Expected: this service does not call providers. Handoff links open the user's own client. |
| Maven cannot download dependencies | First run needs network for Maven Central; afterwards `~/.m2` is warm. The running jar/SPA does not need network except caller-supplied webhook/download URLs. |
| Java version error | Use JDK 21+ (`java -version`), or set `JAVA_HOME` before `./mvnw`. |

---

## 18. Backup and restore

All state is in two places: `<DATA_DIR>/outbox.db` (plus `-wal`/`-shm` in WAL mode) and the whole
`<ATTACHMENT_DIR>` directory. Back up both together; attachment rows reference files in that directory.

### Consistent backup while stopped (simplest)

```bash
systemctl --user stop outbox 2>/dev/null || true   # or Ctrl-C the foreground process
mkdir -p backup/2026-11-07
cp -a data/outbox.db data/outbox.db-wal data/outbox.db-shm backup/2026-11-07/ 2>/dev/null || true
cp -a data/attachments backup/2026-11-07/
tar -czf backup/outbox-2026-11-07.tar.gz -C backup/2026-11-07 .
```

### Online SQLite backup while the service runs

```bash
mkdir -p backup
sqlite3 data/outbox.db ".backup 'backup/outbox-online.db'"
# Copy attachments at the same time; a message may reference a file uploaded moments later.
tar -czf backup/attachments-online.tar.gz -C data attachments
```

For a true point-in-time pair, briefly pause producers or stop the service before copying attachments.
The database `.backup` command is safe with WAL and does not need to stop the service.

### Restore

```bash
# Stop the service first.
rm -rf data/outbox.db data/outbox.db-wal data/outbox.db-shm
mkdir -p data/attachments
cp backup/2026-11-07/outbox.db data/outbox.db
cp -a backup/2026-11-07/attachments/. data/attachments/
chmod -R u+rwX data
./mvnw spring-boot:run
```

Verify with `GET /api/health` (schema version and WAL) and `GET /api/messages`.

---

## 19. Assumptions and deliberate limitations

- **Java/Spring instead of Flask:** the assignment requested a Java Spring backend and Svelte frontend.
  The domain model, endpoints, lifecycle and behavior follow the original requirements;
  `requirements.txt`/Flask are replaced by `pom.xml`/Spring Boot.
- **JUnit instead of `unittest`:** Python's `unittest` is not applicable to a Java service. The test
  suite is the equivalent JUnit 5 integration/unit suite and still runs entirely offline with loopback
  fixtures.
- Single local user, loopback bind, **no authentication or authorization**. Do not expose remotely.
- The service never sends and never calls provider APIs. Handoff links are the only delivery mechanism.
- Email destinations are a single address only (no display names, groups or lists).
- WhatsApp group destinations must use the explicit `group:<name>` form; no group discovery.
- Telegram group destinations use `group:<name>`; private invite links are a manual fallback. Usernames
  are not verified against Telegram.
- Attachments are not transferred by any handoff link; the reviewer downloads and attaches them
  manually. The API truthfully reports `attachments_supported: false`.
- PATCH appends new attachments rather than editing files in place; historical files remain for audit.
- Attachment bytes are not deduplicated; each upload/download creates a new stored file.
- Webhook delivery is at-least-once. Receivers should honor `Idempotency-Key`.
- DNS-rebinding resistance is best-effort (resolve, check, then connect by hostname) on a trusted
  local host.
- The frontend's built assets are committed. Node.js is only needed to rebuild the UI.
- No HMAC signatures, bulk operations, full-text search or demo seeding (these were optional stretch
  goals); the ZIP download and webhook history/attempt viewer are implemented.

---

## 20. Sign-off

**Built 2026-11-07 01:20 UTC by DeepSeek V4.1 Flash** (opencode-go / `deepseek-v4.1-flash`).

The same sign-off appears in the header of `src/main/java/dev/oneshot/outbox/OutboxApplication.java`,
in `/api/info` (`built_at`, `built_by`) and in the SPA footer/about dialog.
