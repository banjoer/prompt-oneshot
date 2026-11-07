# Human-in-the-Loop Outbox Service

Local outbox: producers submit message drafts over a REST API; a human reviews them in a web UI and sends them through their own apps via prepared handoff links. **The service never sends anything itself** — no SMTP, Gmail API, WhatsApp Business API, or Telegram Bot API.

`Built 2026-11-06 23:33 UTC by muse-spark-1.3-contributor (Muse Spark 1.3 Contributor)`

## Installation / startup

```bash
pip install -r requirements.txt
python3 app.py
# open http://127.0.0.1:8000
python3 -m unittest discover -s tests -v
```

Only runtime dependency is Flask. Python 3.11+ (tested on 3.12). Single process serves API + SPA on `127.0.0.1:8000` by default.

## Environment variables

| Name | Default | Meaning |
|---|---|---|
| `DATA_DIR` | `./data` | SQLite DB directory |
| `ATTACHMENT_DIR` | `./data/attachments` | attachment bytes |
| `MAX_ATTACHMENT_BYTES` | `10485760` | per-file limit |
| `MAX_MESSAGE_ATTACHMENT_BYTES` | `26214400` | per-message total |
| `EXPIRATION_INTERVAL_SECONDS` | `30` | background sweep cadence |
| `WEBHOOK_TIMEOUT_SECONDS` | `5` | per-attempt HTTP timeout |
| `WEBHOOK_MAX_ATTEMPTS` | `3` | delivery retries |
| `WEBHOOK_BACKOFF_BASE_SECONDS` | `1` | exponential backoff base |
| `DOWNLOAD_TIMEOUT_SECONDS` | `10` | attachment URL fetch timeout |
| `MAX_REDIRECTS` | `3` | max fetch redirect hops |
| `ALLOW_PRIVATE_URLS` | `0` | `1` = allow loopback/private (local testing only) |
| `PORT` | `8000` | listen port |

`GET /api/info` exposes the non-sensitive subset.

## Architecture

- `app.py` — everything: config, SQLite schema, channel adapters, attachment store, SSRF guard, expiration worker, webhook delivery, HTTP handlers, SPA route.
- `static/index.html` — vanilla SPA (no build, no CDN).
- `openapi.json` — OpenAPI 3.0.3; served at `/openapi.json`; `/api/docs` renders the endpoint list locally.
- SQLite with WAL + foreign keys; one transaction per state change; compare-and-set (`UPDATE … WHERE status=?`) so concurrent transitions have exactly one winner.
- Background thread only for expiration sweep + webhook retries. Webhook delivery never blocks the state change (commit first, deliver async).

## Database schema / migrations

`init_db()` runs idempotently on startup (`CREATE TABLE IF NOT EXISTS` + indexes):

- `messages(id, channel, destination, destination_norm, destination_label, subject, body, status, created_at, updated_at, expires_at, webhook_url, rejection_reason, rejection_at, revision_number, source, metadata)`
- `revisions(message_id, revision_number, …, refs, metadata, attachment_ids, rejection_reason, …)` — full snapshot per revision
- `status_history(message_id, from_status, to_status, reason, revision_number, created_at)`
- `attachments(id, message_id, revision_number, filename, mime, size, storage, uploaded_at, source_type, source_url)`
- `msg_refs(message_id, revision_number, url)` — external references + `url_reference` attachments
- `destination_labels(channel, norm, label, …)` — managed labels; unique label per channel enforced in code
- `webhook_events(message_id, event, status, revision_number, payload, …)` + `webhook_attempts(…)` — full delivery history; idempotency key `(message_id, event, revision_number)`

Timestamps are UTC ISO 8601 `Z`. Message IDs (`msg_*`) are stable across revisions; `created_at` never changes. Terminal/rejected/stale messages are never deleted.

## REST API summary

- `POST /api/messages` (JSON or multipart) → `201 {id, status, created_at, revision_number}`
- `GET /api/messages?status=&channel=&destination=&created_from=&created_to=&expires_from=&expires_to=&limit=&offset=&sort=newest|oldest|expires_soon|expires_late` → `{items, total, limit, offset}`
- `GET /api/messages/{id}`, `PATCH /api/messages/{id}` (pending/rejected only; `status` field rejected with 400)
- `POST /api/messages/{id}/approve|reject|cancel|mark-sent` (`reject` needs non-empty `reason`)
- `GET /api/messages/{id}/history`, `/handoff` (approved only), `/attachments`, `/attachments/{aid}`, `/attachments.zip`, `/webhook-events`
- `GET /api/destinations`, `PUT /api/destinations/label`, `DELETE /api/destinations/label?channel=&destination=`
- `GET /api/health`, `/api/info`, `/api/docs`, `/openapi.json`, `/`

Error shape: `{"error": {"code": "...", "message": "...", "status"?/ "allowed"?}}` with `400/404/409/413/415`.

## Message lifecycle

`pending → approved → sent`, `pending → rejected → pending (via PATCH only)`, `pending/rejected/approved → cancelled`, `pending/approved → stale` (expiry only). `sent/stale/cancelled` terminal and immutable. `mark-sent` only from `approved` and only via explicit call; opening handoff links or downloading files never changes status. Expiration checked on read/list/approve/handoff + periodic sweep; approval and expiry are transactional so an expired message can never become approved.

## Attachments

Multipart field `attachments` (repeatable), JSON `{"kind":"url_reference"|"url_download","url":…}` (references stored, never fetched; downloads fetched and stored), and `references: [...]` URL strings. Filenames sanitized (no paths/control chars/reserved names), storage names are `att_*` + safe name, traversal-guarded, `Content-Disposition: attachment` + `nosniff` on download. Missing files → `404`. ZIP action at `…/attachments.zip`.

## Channel handoff limitations (honest)

- **Email**: `mailto:` with recipient/subject/body URL-encoded; attachments can never ride along — reviewer downloads and attaches manually. Bodies pushing the URL past ~1800 chars fall back to recipient+subject with a warning + copy controls.
- **WhatsApp individual**: `https://wa.me/<digits>?text=…`. **Groups** (`group:Name`): no preselect/prefill exists — fallback opens WhatsApp + shows group name + copy/download controls.
- **Telegram individual** (`@user`/`t.me/…`): `t.me/<user>` deep link; text cannot be prefilled — copy/paste is a required manual step. **Groups/private invites**: documented manual fallback, no username assumed.

Frontend consumes structured handoff JSON (never builds URLs itself).

## Security notes

- SSRF: attachment downloads + webhooks validate scheme/host, resolve DNS, block loopback/private/link-local/multicast/unspecified/reserved + `169.254.169.254`, revalidate every redirect hop. `ALLOW_PRIVATE_URLS=1` is a documented local-testing override only.
- Uploads never execute; MIME sniffed via `mimetypes`; traversal impossible (storage prefix + `send_file` guard).
- `413` on over-limit, `415` on wrong media, mandatory rejection reasons, terminal immutability, webhook failures never roll back state.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Covers submission (JSON/multipart), validation, listing/filter/pagination/sort, retrieval, approval/rejection/cancel/mark-sent, invalid transitions, revision history + stable IDs, labels, upload/download/URL-ref/URL-download (local fixture server), TTL + absolute expiry, pending/approved expiry, approval-vs-expiry race, webhook payloads/success/failure/retries/no-duplicates/no-rollback, adapter URLs/fallbacks/encoding/long bodies, SSRF blocks, traversal, unsafe names, size limits, malformed payloads, invalid webhooks. No network required (loopback fixtures only; `ALLOW_PRIVATE_URLS=1` in tests).

Manual frontend script: open `/`, submit the email sample below, see it in pending, open detail, Approve, Prepare handoff (open app link), Copy body, download attachment, Mark sent (check the confirmation box), filter by sent, assign a destination label under “Destination labels”, remove it again.

## curl examples

```bash
# email (webhook needs ALLOW_PRIVATE_URLS=1 + sink on 9002)
curl -sS -X POST http://127.0.0.1:8000/api/messages -H 'Content-Type: application/json' --data @email.json
# multipart attachment
curl -sS -X POST http://127.0.0.1:8000/api/messages -F channel=email -F destination=alex@example.com -F subject='Q4 report draft' -F body='Hi Alex, please review.' -F attachments=@fixtures/sample.txt
# whatsapp / telegram
curl -sS -X POST http://127.0.0.1:8000/api/messages -H 'Content-Type: application/json' -d '{"channel":"whatsapp","destination":"+1 (415) 555-0123","body":"Your appointment is confirmed for 3 PM."}'
curl -sS -X POST http://127.0.0.1:8000/api/messages -H 'Content-Type: application/json' -d '{"channel":"whatsapp","destination":"group:Project Alpha","body":"Standup moved to 10:00."}'
curl -sS -X POST http://127.0.0.1:8000/api/messages -H 'Content-Type: application/json' -d '{"channel":"telegram","destination":"@alex_example","body":"Build finished successfully."}'
curl -sS -X POST http://127.0.0.1:8000/api/messages -H 'Content-Type: application/json' -d '{"channel":"telegram","destination":"group:Ops Room","body":"Deploy is live."}'
# reference + download (fixture server: python3 -m http.server 9001 --directory fixtures)
curl -sS -X POST http://127.0.0.1:8000/api/messages -H 'Content-Type: application/json' -d '{"channel":"email","destination":"alex@example.com","subject":"Reference and file","body":"See reference and file.","references":["https://example.com/spec"],"attachments":[{"kind":"url_download","url":"http://127.0.0.1:9001/sample.txt","filename":"sample.txt"}]}'
# TTL expiry + webhook
curl -sS -X POST http://127.0.0.1:8000/api/messages -H 'Content-Type: application/json' -d '{"channel":"email","destination":"a@b.com","body":"x","ttl_seconds":120,"webhook_url":"http://127.0.0.1:9002/hooks/outbox"}'
# poll / reject / revise / approve / handoff / cancel
curl -sS 'http://127.0.0.1:8000/api/messages?status=pending&sort=newest&limit=20' | head -c 500
curl -sS -X POST http://127.0.0.1:8000/api/messages/ID/reject -H 'Content-Type: application/json' -d '{"reason":"The recipient name is wrong."}'
curl -sS -X PATCH http://127.0.0.1:8000/api/messages/ID -H 'Content-Type: application/json' -d '{"subject":"Q4 report draft — revised","body":"Hi Alex Smith,\n\nPlease review."}'
curl -sS -X POST http://127.0.0.1:8000/api/messages/ID/approve
curl -sS http://127.0.0.1:8000/api/messages/ID/handoff
curl -sS -X POST http://127.0.0.1:8000/api/messages/ID/mark-sent
curl -sS -X POST http://127.0.0.1:8000/api/messages/ID/cancel -H 'Content-Type: application/json' -d '{}'
```

`email.json` and the sink/server commands are in the task spec; `fixtures/sample.txt` and `fixtures/webhook_sink.py` are included here.

## Backup / restore

- DB: `cp data/outbox.db backup/outbox-$(date +%F).db` (or `sqlite3 data/outbox.db ".backup 'backup/outbox.db'"` for online backup).
- Attachments: `tar -czf backup/attachments-$(date +%F).tar.gz -C data attachments`.
- Restore: stop the service, copy both back to `DATA_DIR`/`ATTACHMENT_DIR`, restart (schema init is idempotent; files are matched to rows by stored names — restore both together).

## Assumptions

- Single-user loopback deployment; no auth by design.
- `mailto:` practical limit ≈ 1800 chars; WhatsApp `wa.me` text not length-capped but very long bodies get a truncation warning.
- Telegram direct links cannot prefill text; group preselection is impossible on all chat platforms — the UI says so explicitly.
- Webhook endpoints must return any 2xx; anything else (or timeout/DNS/SSRF) counts as failure with bounded retries.
