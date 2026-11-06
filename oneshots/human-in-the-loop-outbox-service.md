# Human-in-the-Loop Outbox Service

**Difficulty:** Extreme  |  **Stack:** Python 3.11+ (Flask + SQLite) + vanilla HTML/CSS/JS SPA  |  **Estimated time:** 10–20 hours

## The Problem

AI agents and internal tools can draft email, WhatsApp, and Telegram messages, but giving them direct access to accounts is dangerous, and fully automatic delivery removes human judgment. The missing layer is a local outbox: producers submit messages over a REST API, a human reviews them in a web UI, and the human sends them through their own apps using prepared handoff links. Build that service — persistent, auditable, channel-aware, and honest about what each platform can and cannot prefill. It never integrates with provider APIs and never sends anything by itself.

## Requirements

1. **Runnable local service.** Build a single-process service on Python 3.11+ using Flask (the only runtime dependency) and SQLite via the standard library. The same process serves the REST API and a single-page web app. Bind to `127.0.0.1:8000` by default. A fresh checkout must start with `pip install -r requirements.txt` and `python3 app.py`. There is no authentication, user management, multi-tenancy, OAuth, external database, message broker, cloud storage, or provider API integration (no SMTP, Gmail API, WhatsApp Business API, or Telegram Bot API).

2. **Configuration.** Read settings from environment variables with sensible defaults: `DATA_DIR=./data`, `ATTACHMENT_DIR=./data/attachments`, `MAX_ATTACHMENT_BYTES=10485760`, `MAX_MESSAGE_ATTACHMENT_BYTES=26214400`, `EXPIRATION_INTERVAL_SECONDS=30`, `WEBHOOK_TIMEOUT_SECONDS=5`, `WEBHOOK_MAX_ATTEMPTS=3`, `WEBHOOK_BACKOFF_BASE_SECONDS=1`, `DOWNLOAD_TIMEOUT_SECONDS=10`, `MAX_REDIRECTS=3`, `ALLOW_PRIVATE_URLS=0`, `PORT=8000`. Create the data and attachment directories and initialize the database schema idempotently on startup. Expose non-sensitive configuration through `GET /api/info`.

3. **Persistence and data model.** Use SQLite with a reliable schema initialization/migration mechanism. The schema must persist at least: messages (`id`, `channel`, `destination`, optional `destination_label`, optional `subject`, `body`, `status`, `created_at`, `updated_at`, optional `expires_at`, optional `webhook_url`, optional `rejection_reason`, optional `rejection_at`, `revision_number`, optional `source`, optional `metadata`); message revisions (a complete content snapshot per revision, including attachment references); status history (`from_status`, `to_status`, reason, revision number, timestamp); attachments (unique ID, original filename, MIME type, byte size, storage reference, upload timestamp, source type `multipart` or `url_download`, optional source URL); optional external URL references; destination labels (channel, normalized destination, label, timestamps); and webhook events/delivery attempts. Store timestamps as UTC ISO 8601 with `Z`. Message IDs are stable across revisions, and `created_at` never changes. Never delete rejected, stale, or cancelled messages or their history automatically. Use transactions for every state change and enable SQLite foreign keys and WAL mode.

4. **Message submission.** `POST /api/messages` accepts both `application/json` and `multipart/form-data`. Accept `channel` (`email`, `whatsapp`, `telegram`), `destination`, optional `subject`, `body`, optional `expires_at` or `ttl_seconds`, optional `webhook_url`, optional `source`, optional JSON-object `metadata`, optional `destination_label` snapshot, optional `references` (external URL strings), and attachments. In JSON, `attachments` is a list of objects with `kind` equal to `url_reference` or `url_download` plus a `url`; `url_reference` entries must not be downloaded, while `url_download` entries are fetched and stored locally. In multipart, repeated file parts use the field name `attachments`. Validate the channel, destination, body, JSON shapes, and expiry: `expires_at` and `ttl_seconds` are mutually exclusive, `ttl_seconds` must be a positive integer, and an absolute `expires_at` must be in the future. Reject invalid destinations with a useful message. Return `201` with the stable message ID, current status, creation timestamp, and revision number.

5. **Listing and retrieval.** `GET /api/messages` supports status, channel, destination (case-insensitive match on destination or label), creation-date range, and expiration-date range filters; pagination via `limit` (default 20, maximum 100) and `offset`; and sorting via `sort=newest|oldest|expires_soon|expires_late`, defaulting to newest first. Messages without an expiration sort last for both expiration orders. Return a consistent envelope with `items`, `total`, `limit`, and `offset`. `GET /api/messages/{id}` returns the complete active message, its attachments, references, rejection reason when present, revision number, and expiration. Missing messages return `404`. `GET /api/messages/{id}/history` returns all revisions and status transitions in chronological order, including the content and attachments preserved for each revision. Run expiration checks before reading, as described in requirement 8.

6. **Lifecycle and transitions.** Implement exactly these statuses: `pending`, `approved`, `sent`, `rejected`, `stale`, `cancelled`. Allow only these transitions: pending → approved, pending → rejected, pending → cancelled, pending → stale, rejected → pending (only through a PATCH revision), rejected → cancelled, approved → sent, approved → cancelled, approved → stale. `sent`, `stale`, and `cancelled` are terminal. Provide explicit operations: `POST /api/messages/{id}/approve`, `/reject`, `/cancel`, and `/mark-sent`. Do not allow generic status changes through PATCH; a `status` field in a PATCH body must be rejected. Invalid or missing transitions return `409` (or `404` for a missing message) with the current status and allowed actions. Implement transitions with transactional compare-and-set semantics so duplicate or concurrent requests cannot both succeed; exactly one wins and one status-history row is written. `mark-sent` is allowed only from `approved`, and only an explicit call to that operation (normally the UI confirmation) may mark a message sent — opening a handoff link or downloading an attachment must never do so.

7. **Rejection and revision.** Rejection requires a non-empty reason; otherwise return `400`. Record the reason and rejection timestamp, move the message to `rejected`, append status history, and emit a `message.rejected` webhook. `PATCH /api/messages/{id}` is allowed only for `pending` and `rejected` messages and may update channel, destination, subject, body, expiration, references, metadata, and attachments; omitted fields stay unchanged. PATCH uses the same mutually exclusive `expires_at`/`ttl_seconds` rules as submission, and a null `expires_at` clears expiration. A PATCH on a rejected message creates a new revision, preserves the previous revision and its rejection data in history, clears the active rejection reason, increments `revision_number`, returns the message to `pending`, keeps the same message ID and original `created_at`, and emits `message.revised`. A PATCH on a pending message creates a new revision, increments the revision number, and leaves it pending. A PATCH on an approved, sent, stale, or cancelled message returns `409` and must never silently modify it.

8. **Expiration.** Messages have no expiration by default. Support either absolute `expires_at` or relative `ttl_seconds`, but not both in one request. Expiration applies only to pending and approved messages. When a message expires, set it to `stale`, remove it from active review and sending queues, refuse approval/handoff/mark-sent with `409`, retain all content, attachments, and history, and emit `message.stale`. Check expiration during message retrieval/listing, before approval, before handoff preparation, and through a periodic background worker using `EXPIRATION_INTERVAL_SECONDS`; never rely only on the background worker. Approval and expiration must be transactional so an expired message can never become approved. Messages without expiration remain active indefinitely. Allow the reviewer to sort by expiration date, with no-expiration messages last.

9. **Channel adapters and handoff.** Implement a small channel-adapter abstraction responsible for destination validation/normalization, content formatting, handoff URL generation, capabilities, limitations, and required manual actions. The frontend must consume structured handoff data from the API rather than building channel-specific URLs itself. Provide `GET /api/messages/{id}/handoff`, allowed only for approved messages and only after an expiration check, returning at least: channel, destination, normalized destination, handoff URL, capabilities (`prefill_recipient`, `prefill_subject`, `prefill_body`, `attachments_supported`), manual actions, warnings, and the subject/body values available for copying. Email must generate a `mailto:` link with the recipient, subject, and body URL-encoded; provide copy-body and copy-subject controls; provide individual attachment downloads; explicitly instruct the reviewer to download and attach files manually because `mailto:` does not carry attachments. If the encoded URL exceeds a practical limit (default about 1800 characters), return a shorter valid `mailto:` (for example recipient and subject only) plus a warning and copy controls. WhatsApp individual destinations must normalize international phone numbers and produce `https://wa.me/<digits>?text=<encoded>`; WhatsApp group destinations (for example `group:Project Alpha`) must use an honest fallback that opens WhatsApp, displays the intended group clearly, provides copy controls and attachment downloads, and never claims direct preselection or prefill. Telegram individual destinations (`@username` or `t.me/...`) must produce an appropriate `t.me` deep link with text where supported; groups and private invite destinations must use a documented manual fallback that displays the group, provides copy controls and attachment downloads, and never assumes a public username or preselection. All encoding must handle UTF-8, special characters, and newlines correctly.

10. **Destination labels.** Agents may submit to arbitrary destinations without prior registration. Do not assume one account per channel: multiple email addresses, WhatsApp numbers, Telegram accounts, and groups must coexist, distinguished by destination and label. Discover destinations automatically from submitted messages and expose them through `GET /api/destinations`, including channel, destination, normalized destination, optional label, message count, and last-used timestamp. Provide UI-oriented label operations: `PUT /api/destinations/label` with `{channel, destination, label}` to assign or rename, and `DELETE /api/destinations/label?channel=...&destination=...` to remove. Labels must be non-empty, reasonably bounded, and unique per channel; duplicate labels in the same channel return `409`. Removing a label must never delete or modify historical messages. Previously labeled destinations remain available for reuse whenever the same channel and normalized destination appears in a new message.

11. **Attachments and references.** Support three mechanisms: multipart uploads, external URL references (stored as references, never fetched), and URL downloads (fetched and stored as real attachments). Each attachment must expose its unique ID, original filename, MIME type, size, storage reference, upload timestamp, and source type. Enforce per-file and per-message size limits from configuration. Sanitize filenames (strip paths, control characters, and unsafe reserved names), generate collision-free storage names, and never use the client filename as the storage path. Prevent path traversal on both storage and download. Detect MIME types reasonably; validate downloaded content; apply `DOWNLOAD_TIMEOUT_SECONDS` and `MAX_REDIRECTS`; block localhost, loopback, private, link-local, multicast, unspecified, and cloud-metadata destinations in URLs; revalidate redirect targets. Do not execute uploaded or downloaded files. Serve downloads with `Content-Disposition: attachment`, `X-Content-Type-Options: nosniff`, and a safe encoded filename. Missing files return clear `404`s. The UI must list attachments with individual download buttons and, optionally, a download-all ZIP action; the reviewer must be able to download attachments before opening the external application.

12. **Webhooks.** Each message may include one `webhook_url`. On real events only, send an HTTP POST with `event`, `message_id`, `status`, `revision_number`, a UTC timestamp, and relevant details such as `rejection_reason` for `message.rejected`. At minimum support `message.approved`, `message.rejected`, `message.sent`, `message.cancelled`, `message.stale`, and `message.revised`. Validate webhook URLs and apply the same SSRF protections as attachment downloads, revalidating before each attempt. Delivery must not block the state transition: commit the message change first, then deliver asynchronously with `WEBHOOK_TIMEOUT_SECONDS`, bounded exponential backoff starting at `WEBHOOK_BACKOFF_BASE_SECONDS`, and at most `WEBHOOK_MAX_ATTEMPTS` attempts. Persist every event and attempt, including status, attempt count, timestamps, and last error. Use an idempotency key such as `(message_id, event, revision_number)` to avoid duplicate event processing. Webhook failures must never roll back a successful state change, and the REST API must remain fully usable when no webhook is configured or delivery fails. Expose delivery history through the API and review UI for debugging.

13. **REST surface and OpenAPI.** Implement at least these endpoints: `POST /api/messages`; `GET /api/messages`; `GET /api/messages/{id}`; `PATCH /api/messages/{id}`; `POST /api/messages/{id}/approve`; `POST /api/messages/{id}/reject`; `POST /api/messages/{id}/cancel`; `POST /api/messages/{id}/mark-sent`; `GET /api/messages/{id}/history`; `GET /api/messages/{id}/handoff`; `GET /api/messages/{id}/attachments`; `GET /api/messages/{id}/attachments/{attachment_id}`; `GET /api/messages/{id}/webhook-events`; `GET /api/destinations`; `PUT /api/destinations/label`; `DELETE /api/destinations/label`; `GET /api/health`; `GET /api/info`; `GET /api/docs`; and `GET /openapi.json`. Use consistent JSON responses and error shapes with meaningful status codes (`400` validation, `404` missing, `409` invalid transition/conflict, `413` too large, `415` unsupported media). Publish a valid OpenAPI 3.x document covering every endpoint, request schema, response schema, error shape, and representative examples. Serve a simple human-readable `/api/docs` page that renders the endpoint list from the spec without any CDN or network dependency.

14. **SPA dashboard.** Serve the single-page app at `/`. Provide a queue/dashboard showing each message's channel, destination, destination label when available, subject when applicable, body preview, creation timestamp, expiration timestamp and time remaining, status, revision number, and attachment count. Default to non-terminal messages with pending first, then approved, then rejected. Provide filters for pending, approved, rejected, sent, stale, cancelled, all, plus channel, destination, and date ranges; terminal messages are reachable through history. Provide sorting by newest, oldest, expiring soonest, and expiring latest. Provide a refresh control and loading/empty/error states. Terminal messages must be reachable through history but clearly separated from actionable work.

15. **Message details and review actions.** Selecting a message opens a detail view showing the full body, destination, destination label (the managed label when present, otherwise the message's `destination_label` snapshot), channel, source, metadata, creation/update/expiration timestamps, attachments, external references, revision history, status history, rejection reason, and webhook delivery history. The reviewer must not be able to edit the body, destination, subject, or attachments in the UI. For pending messages, offer Approve, Reject with a mandatory reason modal, and Cancel. For approved messages, offer the prepared handoff (open the target application), copy subject, copy body, download individual attachments, optionally download all, mark as sent with an explicit second confirmation, and cancel. Show the adapter's manual actions and warnings; opening a link or downloading a file must not change status. For rejected messages, show the rejection reason and history, allow inspection of the new revision when it arrives, and allow cancel; do not offer delivery actions. For terminal messages, show the final status and full history with no delivery actions.

16. **Destination management UI.** Provide a section for known destinations discovered from messages, with channel, normalized address, label, message count, and last use. Let the reviewer assign, rename, remove, and reuse labels for matching destinations. Removing a label must leave messages intact. Labels must be unique within a channel and conflicts must show a clear error.

17. **UX and accessibility.** Make the app genuinely usable at 1440×900 and at 390×844 without horizontal page overflow; use drawers, sheets, or stacked layouts on narrow screens. Use clear text/icon distinctions for actionable versus terminal states, never color alone. Require confirmation dialogs for reject, cancel, and mark-sent, with mark-sent requiring an explicit statement that the message was actually sent. Disable controls while requests are in flight, show useful loading and error feedback, support keyboard navigation, visible focus, labelled controls, and Escape-to-close for modals. Respect `prefers-reduced-motion`. No dead buttons, placeholder controls, console errors, TODOs, or fake sending paths.

18. **Security and reliability invariants.** Guarantee and test: expired messages can never be handed off or approved; opening a handoff or downloading an attachment never marks a message sent; rejection reasons are mandatory; revisions preserve previous content and the original message ID; terminal messages are immutable; duplicate/concurrent transitions are safe; expiration and approval cannot race into an invalid state; webhook failures do not undo state changes; missing attachments produce clear errors; invalid destinations are rejected at submission; unsupported handoff features have explicit manual fallbacks; large bodies do not produce broken or oversized handoff URLs; timestamps are UTC internally; uploaded files cannot execute; unsafe filenames and path traversal are impossible; SSRF protections cover webhooks and URL downloads; oversized or invalid uploads return clear errors.

19. **Automated tests.** Use `unittest` (standard library) and Flask's test client. `python3 -m unittest discover -s tests -v` must pass from a clean checkout without external network access (loopback fixtures are allowed). Use temporary databases and attachment directories, and mock webhook delivery. Cover message submission (JSON and multipart), validation, listing/filtering/pagination/sorting, retrieval, approval, rejection, cancellation, mark-sent, invalid transitions, rejection followed by one or more revisions with preserved history and stable IDs, destination labels, attachment upload/download, URL references, URL downloads (with a local fixture or mock), expiration via TTL and absolute timestamps, pending and approved expiration, approval-versus-expiration races, webhook payloads/success/failure/timeout/retries/no-duplicate-events/no-rollback, channel adapter URLs and fallbacks, URL encoding, long bodies, SSRF blocks, path traversal, unsafe filenames, size limits, invalid MIME types, malformed payloads, and invalid webhook URLs. No required test may be skipped or mocked away. Document a manual frontend test script for the primary journeys: reviewing a pending message, approving, rejecting with a reason, copying content, downloading attachments, opening the prepared handoff, marking sent, sorting/filtering, and labeling a destination. A headless browser dependency is optional and must not be required to run the backend tests.

20. **Documentation.** Provide `README.md` with installation/startup, environment variables, architecture overview, database schema/migrations, REST API summary, message lifecycle, attachment handling, channel handoff limitations, security notes, test command, troubleshooting, and backup/restore instructions for both the SQLite database and the attachment directory. Include realistic `curl` examples for submitting email, WhatsApp, and Telegram messages; uploading attachments; downloading remote attachments; setting expiration; configuring a webhook; polling status; rejecting; revising a rejected message with PATCH; approving; preparing handoff; and cancelling. State assumptions that materially affect behavior.

21. **Sign-off:** the finished solution must display, somewhere easy to spot, the actual date and time it was produced and the model/author that produced it — both as a header comment at the top of `app.py` and as a visible footer/about line in the SPA (for example `Built 2026-11-06 23:30 by <model-name>`). Do not fabricate values.

## Constraints

- Python 3.11+; Flask is the only runtime dependency; SQLite, `urllib`, `ipaddress`, `mimetypes`, `threading`, and `unittest` come from the standard library. Do not add a second runtime framework or an ORM.
- One process serves the API and the SPA. The frontend is vanilla HTML/CSS/JavaScript with no build step, no CDN, and no external assets required to run.
- Local single-user deployment only. Bind to loopback by default. No authentication, roles, OAuth, multi-tenancy, external databases, brokers, cloud storage, or provider APIs.
- All application state lives in SQLite; all attachment bytes live under the local attachment directory. No external storage.
- The only outbound HTTP requests are to caller-supplied attachment-download URLs and webhook URLs. There are no third-party API integrations, telemetry, or analytics. `ALLOW_PRIVATE_URLS=1` may be used only as a documented local-testing override; the default must block loopback/private/link-local/metadata destinations.
- Keep domain logic separate from HTTP handlers, channel-specific formatting inside channel adapters, and attachment persistence behind a small storage interface. Use background processing only for expiration and webhook retries.
- Timestamps are stored and exchanged in UTC ISO 8601. The UI may render local time with an explicit timezone label.
- Do not stop at scaffolding. Deliver the complete working service, not a mock or a proof of concept. No TODO features, no fake send path, and no dead controls.

## Sample Data / Inputs

**Sample attachment** — create `fixtures/sample.txt`:

```text
Outbox attachment fixture.
This file is intentionally small.
```

**Email submission (JSON):** start the service with `ALLOW_PRIVATE_URLS=1` when using the local webhook sink shown below; otherwise omit `webhook_url`.

```json
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
```

Save the JSON block as `email.json`, then run:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/messages \
  -H 'Content-Type: application/json' \
  --data @email.json
```

**Email submission with a multipart attachment:**

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

**WhatsApp individual and group submissions:**

```json
{"channel": "whatsapp", "destination": "+1 (415) 555-0123", "body": "Your appointment is confirmed for 3 PM."}
```

```json
{"channel": "whatsapp", "destination": "group:Project Alpha", "body": "Standup moved to 10:00."}
```

**Telegram individual and group submissions:**

```json
{"channel": "telegram", "destination": "@alex_example", "body": "Build finished successfully."}
```

```json
{"channel": "telegram", "destination": "group:Ops Room", "body": "Deploy is live."}
```

**URL reference and URL download:**

```json
{
  "channel": "email",
  "destination": "alex@example.com",
  "subject": "Reference and file",
  "body": "See the external reference and the attached file.",
  "references": ["https://example.com/spec"],
  "attachments": [
    {"kind": "url_download", "url": "http://127.0.0.1:9001/sample.txt", "filename": "sample.txt"}
  ]
}
```

For the local download test, run `python3 -m http.server 9001 --directory fixtures` in another terminal and start the service with `ALLOW_PRIVATE_URLS=1`. The `https://example.com/spec` entry is stored as a reference and must not be fetched.

**Rejection with a mandatory reason:**

```bash
curl -sS -X POST http://127.0.0.1:8000/api/messages/msg_REPLACE/reject \
  -H 'Content-Type: application/json' \
  -d '{"reason":"The recipient name is wrong. Address it to Alex Smith, not Alex Doe."}'
```

**Revision of the rejected message (same ID):**

```bash
curl -sS -X PATCH http://127.0.0.1:8000/api/messages/msg_REPLACE \
  -H 'Content-Type: application/json' \
  -d '{"subject":"Q4 report draft — revised","body":"Hi Alex Smith,\n\nPlease review the attached Q4 report before Friday.\n\nThanks,\nSam"}'
```

**Example webhook payload:**

```json
{
  "event": "message.rejected",
  "message_id": "msg_8f2c1a4b9d30",
  "status": "rejected",
  "revision_number": 1,
  "rejection_reason": "The recipient name is wrong. Address it to Alex Smith, not Alex Doe.",
  "timestamp": "2026-11-06T20:00:00Z"
}
```

**Optional local webhook sink** — create `fixtures/webhook_sink.py`:

```python
# Manual test helper: prints each webhook POST body to stdout.
from http.server import BaseHTTPRequestHandler, HTTPServer

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        print(self.rfile.read(length).decode("utf-8"), flush=True)
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args):
        pass

HTTPServer(("127.0.0.1", 9002), Handler).serve_forever()
```

Run it with `python3 fixtures/webhook_sink.py`, then submit messages with the webhook URL shown above and `ALLOW_PRIVATE_URLS=1`.

**Example destination labels:** `Alex — Client`, `Finance Team`, `Project Alpha Group`, `Personal Email`.

## Deliverable

- `app.py` — Flask entry point and wiring; backend domain logic, channel adapters, attachment storage, expiration worker, and webhook delivery may live in `app.py` or a small `outbox/` package.
- `requirements.txt` — Flask only.
- `static/index.html` — complete SPA (CSS and JavaScript may be inline or in a minimal `static/` set; no build step).
- `tests/test_app.py` — automated tests (plus optional test helpers).
- `openapi.json` — valid OpenAPI 3.x specification.
- `README.md` — setup, architecture, API, lifecycle, security, backup/restore, and curl examples.
- Optional fixtures: `fixtures/sample.txt`, `fixtures/webhook_sink.py`.

Run:

```bash
pip install -r requirements.txt
python3 app.py
```

Open `http://127.0.0.1:8000`. Run the tests with:

```bash
python3 -m unittest discover -s tests -v
```

## Done When

- [ ] `pip install -r requirements.txt` and `python3 app.py` start cleanly; `GET /api/health` returns 200; `GET /api/info` shows non-sensitive configuration; `GET /openapi.json` is valid OpenAPI; `/` loads the SPA with no console errors.
- [ ] A JSON email submission with an absolute expiry and webhook returns 201 with a stable ID, status, creation timestamp, and revision number; the message appears in the pending queue with the correct destination, subject, expiry, and attachment count; the detail view shows its full content.
- [ ] A multipart submission with `fixtures/sample.txt` stores the file; the attachment downloads with its original name and correct size; a URL-reference submission stores no downloaded file; a URL-download submission through the local fixture server stores a real attachment.
- [ ] Rejecting with an empty reason returns 400; rejecting with a reason yields `rejected`, records the reason/timestamp/status history, and creates and attempts the `message.rejected` webhook (visible in delivery history and received by the sink when running).
- [ ] PATCH on the rejected message keeps the same ID, increments the revision to 2, returns it to `pending`, clears the active rejection reason, preserves the previous revision/history, and emits `message.revised`; PATCH on an approved, sent, stale, or cancelled message returns 409.
- [ ] Approving a pending message returns `approved`; the handoff response contains a `mailto:` URL with recipient/subject/body (or a documented long-body fallback) and explicit manual attachment instructions; opening the handoff or downloading attachments does not change status.
- [ ] `mark-sent` from approved, after the explicit UI confirmation, returns `sent` and emits `message.sent`; repeated or invalid transitions return 409; the UI never marks a message sent from a link open or download.
- [ ] WhatsApp individual handoff uses `https://wa.me/<digits>?text=...`; WhatsApp group handoff opens WhatsApp with copy controls and the group name, without claiming preselection or prefill; Telegram individual uses a `t.me` deep link; Telegram group/private destinations use a documented fallback; special characters and newlines are correctly encoded; overlong bodies use a safe fallback.
- [ ] Expiration works through both `ttl_seconds` and `expires_at` (both at once returns 400); a 2-second TTL becomes `stale` after refresh or the interval; stale messages disappear from active queues, cannot be approved or handed off (409), and retain content, attachments, and history; a message without expiration stays active; an approval-versus-expiration race never leaves an expired message approved.
- [ ] Listing supports status, channel, destination, creation-date, and expiration-date filters; pagination and newest/oldest/expiring-soon/expiring-late sorting work, with no-expiration messages last; the default order is newest first.
- [ ] Destinations are discovered from submitted messages without registration; the UI can assign, rename, remove, and reuse labels; duplicate labels in the same channel are rejected; removing a label leaves all messages intact.
- [ ] Security checks hold: a filename like `../../evil.txt` is stored and served safely; oversized uploads return 413; missing or invalid attachments give clear errors; webhook/download URLs pointing at loopback, private ranges, link-local, or metadata endpoints are blocked by default and allowed only with the explicit dev override; path traversal on attachment download is impossible; webhook failures do not roll back state.
- [ ] Invalid states, transitions, and malformed payloads return consistent JSON errors (400/404/409/413/415); concurrent approvals produce exactly one success and one 409, with one corresponding status-history entry.
- [ ] The SPA is usable at 1440×900 and 390×844: filters and sorting work, pending and approved actions are available, rejected and terminal messages show history without delivery actions, destructive actions require confirmation, and mark-sent requires an explicit second confirmation.
- [ ] `python3 -m unittest discover -s tests -v` passes; tests cover submission, listing, lifecycle, revisions, expiration, attachments, webhooks, channel adapters, labels, and security; no required test is skipped or mocked away.
- [ ] The sign-off (actual production date/time plus model/author) appears in the `app.py` header comment and visibly in the SPA footer/about line.
- [ ] No dead buttons, placeholder controls, console errors, TODOs, or fake sending paths remain; the README documents setup, configuration, API, lifecycle, handoff limitations, backup/restore, and curl examples.

## Stretch Goals (optional)

- Add a safe download-all ZIP action built from the attachment store, with path-traversal and size protections.
- Add HMAC-SHA256 webhook signatures with a timestamp header and document verification and replay protection.
- Add bulk approve/reject and full-text search across subject, body, destination, and labels.
- Add a `--seed-demo` command that inserts representative messages and attachments for a quick tour without becoming required for normal use.
- Add an online SQLite backup command that copies the database and creates a matching attachment archive with a documented restore procedure.
