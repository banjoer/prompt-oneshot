# Build: Human-in-the-Loop Outbox Service

## 1. Objective

Build a lightweight, self-contained outbound messaging service that exposes a REST API for AI agents, LLMs, and other applications to submit messages for human review and delivery.

The service acts as a generic messaging outbox, decoupling message producers from communication platforms.

Message producers should not need direct access to email accounts, WhatsApp accounts, or Telegram accounts.

Instead, they submit messages to this service, which:
1. Receives and persists the message.
2. Stores its attachments.
3. Prepares channel-specific delivery instructions and handoff links.
4. Presents messages in a web-based review interface.
5. Allows a human to approve, reject, or cancel messages.
6. Allows the human to open the appropriate external application, copy message content, download attachments, and manually send the message.
7. Reports status changes and rejection feedback to the original caller.

The service must NOT require direct integration with email, WhatsApp, or Telegram APIs for its initial implementation.

The core delivery mechanism is human-operated handoff through existing applications.

The result should be a practical, minimal, reliable service rather than a general-purpose messaging platform.

---

## 2. Product principles

Follow these principles throughout the implementation:

- Simple REST API.
- Single-page web application.
- No authentication or user management.
- Single-user, single-instance deployment.
- Multiple outgoing destinations and accounts.
- Agents can submit messages to arbitrary destinations.
- Destinations can optionally be labeled and reused through the UI.
- All messages are persisted.
- Human approval is required before delivery.
- Sending is always performed manually through external applications.
- Marking a message as sent requires explicit human confirmation.
- Rejection must include an actionable reason.
- Revisions modify the original message rather than creating new messages.
- Messages can optionally expire.
- No expiration is applied by default.
- Attachments are stored locally.
- Preserve message and revision history.
- Avoid unnecessary infrastructure and abstractions.

Do not introduce authentication, multi-tenancy, user roles, OAuth, or unnecessary enterprise features.

---

## 3. Architecture

Implement three main components:

### 3.1 Backend

A lightweight REST API responsible for:
- Message submission.
- Message retrieval.
- Message updates and revisions.
- Cancellation.
- Message status management.
- Destination management.
- Attachment handling.
- Webhook notifications.
- Expiration processing.
- Persistence.

### 3.2 Frontend

A single-page web application responsible for:
- Reviewing messages.
- Inspecting message details.
- Managing the outgoing destination catalogue.
- Approving and rejecting messages.
- Preparing channel-specific handoffs.
- Copying message content.
- Downloading attachments.
- Opening external applications.
- Explicitly marking messages as sent.

### 3.3 Storage

Use:
- SQLite for application data.
- Local filesystem storage for attachments.

Do not require PostgreSQL, Redis, message brokers, cloud storage, or other external infrastructure.

Use database migrations or an equivalent reliable schema initialization mechanism.

The application should be easy to run locally or deploy as a single service.

---

## 4. Messaging channels

Support three initial channel types:

1. Email
2. WhatsApp
3. Telegram

The architecture should use a small channel adapter abstraction to isolate channel-specific destination validation, formatting, and handoff URL generation.

Do not implement actual delivery integrations.

### 4.1 Multiple outgoing destinations

The service must support multiple configured outgoing accounts/destinations per channel.

Examples:

- Personal email account.
- Work email account.
- Personal WhatsApp number.
- Business WhatsApp number.
- Telegram account.
- Telegram groups.

A message identifies its intended channel and destination.

The system must not assume there is only one outgoing account per channel.

### 4.2 Email handoff

For email messages:

- Generate a `mailto:` link.
- Prepopulate the recipient.
- Include the subject when provided.
- Support message body preparation.
- Provide a copy-body button.
- Provide individual attachment download links.
- Make it easy for the reviewer to open their configured email application.

Do not assume that mailto links support attachments.

The UI must explicitly instruct the reviewer to download and attach files manually.

If a body or subject exceeds practical mailto URL limits, provide a fallback that opens the mail application where possible and exposes copy controls.

### 4.3 WhatsApp handoff

For WhatsApp messages:

- Generate the appropriate WhatsApp deep link.
- Prepopulate the recipient phone number where supported.
- Prepopulate the message text where supported.
- Support opening WhatsApp Web or the installed application.
- Provide an explicit copy-message button.
- Provide attachment download controls.

Use supported URL formats, such as `https://wa.me/`.

Handle international phone number formatting.

WhatsApp group handoff must be handled honestly: do not assume that a group can be selected or a message preloaded through the same mechanism as an individual recipient.

Where direct group preselection is not supported, provide an appropriate fallback:
- Open WhatsApp.
- Copy the message.
- Display the intended group clearly.
- Provide attachment downloads.

### 4.4 Telegram handoff

For Telegram:

- Support individual recipients and groups.
- Generate appropriate Telegram deep links where supported.
- Prepopulate message text when possible.
- Provide copy-message controls.
- Provide attachment download controls.

Do not assume that every Telegram group has a publicly accessible username or supports direct handoff.

For unsupported destinations, provide a practical manual handoff fallback.

### 4.5 Channel adapter interface

Define a small interface responsible for:

- Validating a destination.
- Formatting message content.
- Generating handoff URLs.
- Returning handoff capabilities and limitations.
- Identifying required manual actions.

The frontend should consume structured handoff information rather than implementing channel-specific URL logic independently.

---

## 5. Destination management

Agents must be able to submit messages to arbitrary destinations without registering them beforehand.

A destination can be:
- An email address.
- A WhatsApp phone number.
- A Telegram username, identifier, or group destination.

The destination is accompanied by the channel type.

### 5.1 Destination labels

Destination labeling is managed exclusively through the web UI.

The API must not require destination registration or destination labels.

The UI should allow the reviewer to:

- See destinations used by previous messages.
- Assign a human-readable label.
- Rename labels.
- Remove labels.
- Reuse previously labeled destinations.

Examples:

- John - Client
- Finance Team
- Project Alpha Group
- Personal Email

A destination can be recognized by its channel and normalized address.

Labels should be unique within their appropriate namespace.

Removing a label must not delete historical messages.

The API can optionally expose read-only destination lookup if useful, but destination creation and labeling remain UI responsibilities.

---

## 6. Message data model

Every message must have a stable, unique ID.

A message should contain at least:

- `id`
- `channel`
- `destination`
- `destination_label` (optional descriptive snapshot)
- `subject` (optional, primarily for email)
- `body`
- `attachments`
- `status`
- `created_at`
- `updated_at`
- `expires_at` (optional)
- `webhook_url` (optional)
- `rejection_reason` (optional)
- `revision_number`
- `revision_history`
- `source` (optional caller identification)
- `metadata` (optional JSON object)

The message should preserve its original creation timestamp across revisions.

The latest revision should be the active message content.

Keep a full revision history so that previous content remains available for inspection.

### 6.1 Message immutability in the UI

The reviewer must not edit the message body, destination, subject, or attachments through the review interface.

If a message needs correction:
1. Reject it with an explanation.
2. The originating agent receives the rejection.
3. The agent submits a PATCH request to update the same message.
4. The revised message returns to the pending review queue.

This provides a clear separation between the message producer and the human reviewer.

---

## 7. Message lifecycle

Implement the following states:

### pending

The message has been received and is awaiting human review.

### approved

The reviewer has approved the message.

It is ready for manual handoff.

### sent

The reviewer explicitly confirmed that the message was sent.

Opening a handoff link must NEVER automatically change a message to sent.

Downloading attachments must NEVER automatically change a message to sent.

Only an explicit UI action can mark a message as sent.

### rejected

The reviewer rejected the message.

A rejection reason is mandatory.

The message remains available for inspection and revision.

### stale

The message expired before being sent.

Stale messages must not appear in the active sending queue.

### cancelled

The originating caller explicitly cancelled the message, or the reviewer cancelled it.

Cancelled messages must not be available for delivery.

### 7.1 State transitions

Implement and validate the following transitions:

- pending → approved
- pending → rejected
- pending → cancelled
- pending → stale
- rejected → pending (through PATCH revision)
- rejected → cancelled
- approved → sent
- approved → cancelled
- approved → stale

Sent, stale, and cancelled are terminal states.

Do not allow arbitrary status changes through generic PATCH requests.

Status transitions must be performed through explicit operations.

---

## 8. Rejection and revision workflow

Rejection is an essential feature.

When rejecting a message, the reviewer must provide a reason explaining what needs to change.

Example:

"The recipient name is incorrect. Please address the message to John Smith instead of John Doe."

The service must:
- Record the rejection reason.
- Record the rejection timestamp.
- Preserve the rejected revision.
- Notify the caller through its configured webhook.
- Expose the rejection information through the status API.

### 8.1 Revision through PATCH

Resubmission must update the original message.

Do not create a new message ID.

The caller uses:

`PATCH /messages/{id}`

The PATCH request may update:
- Destination.
- Channel.
- Subject.
- Body.
- Attachments.
- Expiration.

A PATCH to a rejected message:
- Creates a new revision.
- Preserves the previous revision.
- Clears the current rejection reason from the active revision.
- Increments the revision number.
- Returns the message to pending.
- Preserves the original message ID.
- Triggers a webhook notification for the status change.

The revision history must remain accessible.

A PATCH must not silently modify sent, cancelled, or stale messages.

Use appropriate validation and HTTP error codes.

---

## 9. Expiration

Messages have no expiration by default.

The caller can optionally provide either:

- `expires_at`: Absolute expiration timestamp.
- `ttl_seconds`: Relative time-to-live from submission.

Support both, but do not allow contradictory values in the same submission.

Expiration applies to messages that have not been sent, including approved messages.

When a message expires:
- Its status becomes stale.
- It disappears from the active review and sending queues.
- It cannot be approved or handed off.
- Its content and attachments remain available in historical records.
- The caller receives a webhook notification if configured.

Expiration must be checked:
- During message retrieval.
- Before approval.
- Before handoff preparation.
- During periodic background expiration processing.

Do not rely exclusively on a background scheduler for correctness.

Messages without expiration remain active indefinitely.

Allow the reviewer to sort messages by expiration date.

---

## 10. Attachment management

Support three attachment submission mechanisms.

### 10.1 Multipart uploads

Allow agents to upload files directly as part of the message submission request.

### 10.2 URL references

Allow agents to provide URLs that should be included in the message body or treated as external references.

These URLs must not automatically become downloaded attachments.

### 10.3 URL downloads

Allow agents to specify URLs from which the service downloads files and stores them locally.

The resulting files become regular message attachments.

### 10.4 Attachment metadata

Each attachment should include:

- Unique ID.
- Original filename.
- MIME type.
- File size.
- Storage reference.
- Upload timestamp.
- Source type (multipart or URL download).

### 10.5 Attachment security and validation

Implement reasonable protections:

- File size limits.
- Configurable maximum attachment size.
- MIME type detection.
- Safe filename handling.
- Prevent path traversal.
- Avoid overwriting existing files.
- Validate downloaded content.
- Apply download timeouts.
- Limit redirects.
- Prevent server-side request forgery (SSRF), including access to localhost, private IP ranges, link-local addresses, and cloud metadata endpoints.
- Do not execute uploaded files.

Attachments must be available through the review UI.

Provide individual download buttons and, optionally, a download-all ZIP action.

The reviewer must be able to download attachments before opening the target communication application.

---

## 11. Webhooks

Each submitted message may include a `webhook_url`.

The service sends HTTP POST notifications when relevant message events occur.

At minimum, support notifications for:

- message.approved
- message.rejected
- message.sent
- message.cancelled
- message.stale
- message.revised

Example payload:

{
  "event": "message.rejected",
  "message_id": "msg_123",
  "status": "rejected",
  "revision_number": 1,
  "rejection_reason": "Incorrect recipient name",
  "timestamp": "2026-11-06T20:00:00Z"
}

Webhook requests should contain:
- Event type.
- Message ID.
- Current status.
- Revision number.
- Event timestamp.
- Relevant event details.

Webhook behavior:
- Do not block message state changes while waiting for webhook delivery.
- Implement reasonable timeouts.
- Log delivery attempts and failures.
- Retry transient failures with bounded exponential backoff.
- Avoid duplicate event processing where possible.
- Keep webhook delivery history available for debugging.

Only notify events that actually occur.

The REST API must always remain available for polling, even when no webhook is configured or delivery fails.

Validate webhook destinations and apply SSRF protections.

---

## 12. REST API

Implement a documented REST API.

At minimum, provide the following endpoints.

### Messages

`POST /api/messages`

Submit a new message.

Accept:
- Channel.
- Destination.
- Subject.
- Body.
- Attachments.
- Expiration.
- Webhook URL.
- Optional source and metadata.

Return:
- Stable message ID.
- Current status.
- Creation timestamp.
- Revision number.

Use multipart/form-data when uploading files directly.

Support a JSON-based submission format for URL references and URL downloads.

`GET /api/messages`

List messages.

Support:
- Status filtering.
- Channel filtering.
- Destination filtering.
- Creation date filtering.
- Expiration date filtering.
- Pagination.
- Sorting.

Default sorting: newest messages first.

`GET /api/messages/{id}`

Retrieve the complete current message, including its status, rejection reason, expiration, attachments, and relevant history.

`PATCH /api/messages/{id}`

Update a rejected message and resubmit it for review.

Also support permitted updates to messages that are still pending, according to the lifecycle rules.

`POST /api/messages/{id}/approve`

Approve a pending message.

`POST /api/messages/{id}/reject`

Reject a pending message.

Require a non-empty rejection reason.

`POST /api/messages/{id}/cancel`

Cancel an eligible message.

`POST /api/messages/{id}/mark-sent`

Mark an approved message as sent.

This endpoint is primarily intended for the review UI.

`GET /api/messages/{id}/history`

Retrieve the message revision and status transition history.

### Attachments

`GET /api/messages/{id}/attachments`

List attachments.

`GET /api/messages/{id}/attachments/{attachment_id}`

Download an attachment.

### Destinations

Provide UI-oriented endpoints for:
- Listing previously used destinations.
- Assigning labels.
- Updating labels.
- Removing labels.

Do not require agents to register destinations.

### System

Provide:
- Health endpoint.
- Basic application information.
- Configuration visibility for non-sensitive settings.

Use consistent JSON responses and meaningful HTTP status codes.

Generate an OpenAPI specification and make it available through the application.

---

## 13. Web application

Build a clean, functional, responsive single-page web application.

The UI is the main human review surface.

Avoid unnecessary complexity and excessive navigation.

### 13.1 Main dashboard

Display the message queue.

Each message should show:
- Channel icon.
- Destination.
- Destination label, if available.
- Subject, when applicable.
- Message preview.
- Creation timestamp.
- Expiration timestamp, if present.
- Time remaining, if applicable.
- Current status.
- Revision number.
- Attachment count.

### 13.2 Sorting

Provide sorting options:

- Newest first (default).
- Oldest first.
- Expiring soonest.
- Expiring latest.

Messages without expiration should be handled separately in expiration sorting.

### 13.3 Filtering

Provide filters for:
- Pending.
- Approved.
- Rejected.
- Sent.
- Stale.
- Cancelled.
- Channel.
- Destination.
- Date ranges.

The default view should prioritize actionable messages, especially pending messages.

Terminal messages should be accessible through history.

### 13.4 Message details

Selecting a message opens a detail view.

Show:
- Complete message content.
- Destination.
- Destination label.
- Channel.
- Creation date.
- Expiration.
- Attachments.
- Revision history.
- Status history.
- Rejection reason, when applicable.

The reviewer must not be able to edit message content.

### 13.5 Review actions

For pending messages:

- Approve.
- Reject (with mandatory reason).
- Cancel.

For approved messages:

- Open destination application.
- Copy message body.
- Copy subject, when applicable.
- Download attachments.
- Download all attachments.
- Mark as sent.
- Cancel.

For rejected messages:

- Display rejection reason.
- Show revision history.
- Allow the reviewer to inspect the new revision when submitted.

For terminal messages:

- Display their final status and history.
- Do not offer delivery actions.

### 13.6 Destination management

Provide a simple UI section for managing destination labels.

Allow:
- Viewing known destinations.
- Assigning labels.
- Renaming labels.
- Removing labels.

Destinations should be automatically discovered from submitted messages.

### 13.7 User experience

The interface should be:
- Simple.
- Responsive.
- Fast.
- Desktop-friendly.
- Easy to use for repeated message reviews.

Use clear visual distinctions between actionable and terminal states.

Provide confirmation dialogs for destructive actions.

Require an explicit confirmation before marking a message as sent.

Display useful error messages and loading states.

---

## 14. Persistence and history

Persist all message state in SQLite.

Use transactions for operations that change message state.

Maintain:
- Message records.
- Current message content.
- Revision history.
- Status transition history.
- Attachment metadata.
- Destination labels.
- Webhook event records and delivery attempts.

The original message ID must remain stable throughout revisions.

Do not delete rejected messages when they are revised.

Do not delete stale or cancelled messages automatically.

Keep historical information accessible through the API and UI.

Use safe local filesystem paths for attachments.

Provide a straightforward backup strategy covering both the SQLite database and attachment directory.

---

## 15. Technical implementation

Choose a pragmatic, maintainable technology stack.

Prefer a conventional stack with:
- A lightweight backend framework.
- SQLite.
- A local filesystem attachment store.
- A modern SPA frontend.
- TypeScript where appropriate.
- REST API documentation through OpenAPI.

Do not introduce unnecessary dependencies.

Keep backend business logic separate from HTTP handlers.

Keep channel-specific formatting isolated in channel adapters.

Keep attachment storage isolated behind a small storage abstraction.

Implement background processing only where necessary, such as expiration checks and webhook retries.

Do not introduce distributed systems infrastructure.

Use environment variables for configuration.

Provide sensible defaults for:
- Data directory.
- Attachment directory.
- Maximum upload size.
- HTTP request timeouts.
- Webhook retry behavior.
- Expiration processing interval.

The service should be runnable with a small number of commands.

---

## 16. Reliability and edge cases

Pay particular attention to the following:

1. A message must never be handed off after expiration.
2. A message must never be marked sent merely because a handoff link was opened.
3. Rejection reasons are mandatory.
4. Revisions must preserve previous content.
5. A revision must retain the original message ID.
6. Terminal states cannot be modified.
7. Duplicate or concurrent state transitions must be handled safely.
8. Expiration and approval must not race into an invalid state.
9. Webhook failures must not undo successful message state transitions.
10. Missing attachments must produce clear errors.
11. Invalid channel destinations must be rejected during submission.
12. Unsupported channel handoff features must have explicit manual fallbacks.
13. Large message bodies must not produce broken handoff URLs.
14. Timezones and timestamps must be handled consistently using UTC internally.
15. File downloads must use safe filenames and prevent unauthorized filesystem access.

---

## 17. Testing and evaluation

Implement automated tests for the core application behavior.

### API tests

Test:
- Message submission.
- Message retrieval.
- Message listing.
- Message updates.
- Approval.
- Rejection.
- Cancellation.
- Explicit sent confirmation.
- Invalid state transitions.
- Destination labeling.
- Attachment uploads.
- Attachment downloads.
- URL attachment downloads.
- Expiration.

### Lifecycle tests

Test all valid state transitions.

Test that invalid transitions return appropriate errors.

Test rejection followed by multiple revisions.

Verify that revision history is preserved and the message ID remains unchanged.

### Expiration tests

Test:
- Messages without expiration.
- Relative TTL.
- Absolute expiration.
- Expiration of pending messages.
- Expiration of approved messages.
- Expiration versus approval race conditions.
- Stale messages cannot be handed off.

### Webhook tests

Test:
- Successful delivery.
- Failed delivery.
- Timeout.
- Retry behavior.
- Event payload structure.
- No duplicate state transitions.

### Channel adapter tests

Test:
- Email mailto links.
- WhatsApp individual deep links.
- WhatsApp group fallback.
- Telegram individual links.
- Telegram group fallback.
- Special characters and URL encoding.
- Long message bodies.

### Frontend tests

Test the primary user journeys:
- Reviewing a pending message.
- Approving a message.
- Rejecting with a reason.
- Copying content.
- Downloading attachments.
- Opening external applications.
- Marking as sent.
- Sorting and filtering.
- Labeling a destination.

### Security tests

Test:
- SSRF protections.
- File path traversal.
- Unsafe filenames.
- File size restrictions.
- Invalid MIME types.
- Malformed webhook URLs.
- Invalid API payloads.

---

## 18. Documentation

Provide:

1. README with installation and startup instructions.
2. Architecture overview.
3. REST API documentation.
4. OpenAPI specification.
5. Message lifecycle documentation.
6. Attachment handling documentation.
7. Channel handoff limitations.
8. Configuration reference.
9. Backup and restore instructions.
10. Example API requests using curl.

Include realistic examples for:
- Submitting an email.
- Submitting a WhatsApp message.
- Submitting a Telegram message.
- Uploading attachments.
- Downloading remote attachments.
- Setting expiration.
- Registering a webhook.
- Polling message status.
- Rejecting a message.
- Revising a rejected message through PATCH.
- Cancelling a message.

---

## 19. Implementation strategy

Implement the complete working application rather than producing only a design or prototype.

Recommended implementation order:

1. Establish project structure and development environment.
2. Implement database schema and migrations.
3. Implement message domain model and lifecycle validation.
4. Implement attachment storage.
5. Implement REST API.
6. Implement webhook processing.
7. Implement expiration processing.
8. Implement channel adapters and handoff generation.
9. Implement the single-page web application.
10. Integrate the frontend and backend.
11. Implement automated tests.
12. Write documentation.
13. Verify the complete application through end-to-end tests.

Do not stop after creating scaffolding.

Do not leave essential features as TODOs or mocked functionality.

Do not implement fake message sending.

---

## 20. Acceptance criteria

The implementation is complete only when the following end-to-end workflow works:

1. An external agent submits an email message with a destination, subject, body, attachment, and webhook URL.
2. The service returns a unique message ID.
3. The message appears in the web review queue.
4. The reviewer opens the message and inspects its content and attachment.
5. The reviewer rejects the message with an explanation.
6. The service records the rejection and notifies the webhook.
7. The agent retrieves the rejection reason through the REST API.
8. The agent PATCHes the original message with corrected content.
9. The same message ID is retained and its revision number increments.
10. The revised message reappears in the pending queue.
11. The reviewer approves it.
12. The reviewer opens the prepared email handoff.
13. The reviewer copies the message body and downloads the attachment.
14. The reviewer sends the email using their own email application.
15. The reviewer explicitly clicks Mark as sent.
16. The service records the sent status and sends a webhook notification.
17. The complete message and revision history remain accessible.

Repeat equivalent end-to-end tests for WhatsApp and Telegram, including their respective handoff limitations.

Also verify that:
- Messages without expiration remain active.
- Expired messages become stale.
- Stale messages cannot be sent.
- Messages can be sorted by creation and expiration dates.
- Agents can submit messages to new destinations without prior registration.
- The UI can label and reuse destinations.

---

## 21. Scope boundaries

Explicitly out of scope for the initial implementation:

- Direct SMTP delivery.
- Gmail API integration.
- WhatsApp Business API integration.
- Telegram Bot API delivery.
- Automatic message sending.
- OAuth or account authentication.
- User management.
- Multi-tenancy.
- Complex workflow engines.
- External message brokers.
- Cloud-based attachment storage.
- AI-generated message content.
- AI-based automatic approval or rejection.

Keep the architecture extensible enough to support actual delivery adapters in the future, but do not implement them now.

---

## 22. Final instructions to the coding agents

Before implementing, inspect the existing repository and understand its conventions and existing infrastructure.

Preserve useful existing components rather than replacing them unnecessarily.

Make reasonable implementation decisions where details are unspecified.

Prioritize simplicity, correctness, maintainability, and a complete working experience.

Do not introduce unnecessary abstractions or dependencies.

Document assumptions that materially affect behavior.

If multiple implementation approaches are possible, choose the simplest approach that satisfies the requirements.

Deliver:
- Complete source code.
- Database schema and migrations.
- Working REST API.
- Working single-page web UI.
- Attachment storage.
- Channel-specific handoff functionality.
- Webhook processing.
- Expiration handling.
- Automated tests.
- OpenAPI specification.
- Setup and operational documentation.

The final result must be a runnable, usable service, not merely a proof of concept.