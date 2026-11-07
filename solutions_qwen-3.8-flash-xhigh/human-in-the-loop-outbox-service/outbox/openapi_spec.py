"""OpenAPI 3.0 document for the outbox REST API (single source of truth).

``python3 app.py`` serves this at /openapi.json; the /api/docs page renders
it without any CDN. The committed openapi.json at the repo root is generated
with:  python3 -m outbox.openapi_spec > openapi.json
"""
from __future__ import annotations

import json
from typing import Any

STATUS_ENUM = ["pending", "approved", "sent", "rejected", "stale", "cancelled"]
CHANNEL_ENUM = ["email", "whatsapp", "telegram"]

ERROR_SCHEMA = {
    "type": "object",
    "properties": {
        "error": {"type": "string", "description": "machine-readable error code"},
        "message": {"type": "string"},
    },
    "required": ["error", "message"],
}

CONFLICT_SCHEMA = {
    "allOf": [
        {"$ref": "#/components/schemas/Error"},
        {"type": "object", "properties": {
            "current_status": {"type": "string", "enum": STATUS_ENUM},
            "allowed_actions": {"type": "array", "items": {"type": "string"}},
        }},
    ]
}


def _resp(desc: str, schema: dict, headers: dict | None = None) -> dict:
    out = {"description": desc, "content": {"application/json": {"schema": schema}}}
    if headers:
        out["headers"] = headers
    return out


def _file_resp(desc: str) -> dict:
    return {"description": desc,
            "content": {"application/octet-stream": {"schema": {"type": "string",
                                                                "format": "binary"}}}}


def build_spec() -> dict[str, Any]:
    attachment_schema = {
        "type": "object", "properties": {
            "id": {"type": "string", "example": "att_1a2b3c4d5e6f"},
            "filename": {"type": "string"},
            "mime_type": {"type": "string"},
            "size_bytes": {"type": "integer"},
            "storage_reference": {"type": "string",
                                  "description": "server-generated storage file name"},
            "uploaded_at": {"$ref": "#/components/schemas/DateTime"},
            "source_type": {"type": "string", "enum": ["multipart", "url_download"]},
            "source_url": {"type": "string", "nullable": True},
            "download_url": {"type": "string"},
        },
        "required": ["id", "filename", "mime_type", "size_bytes", "storage_reference",
                     "uploaded_at", "source_type", "download_url"],
    }
    message_summary = {
        "type": "object", "properties": {
            "id": {"type": "string"},
            "channel": {"type": "string", "enum": CHANNEL_ENUM},
            "destination": {"type": "string"},
            "normalized_destination": {"type": "string"},
            "destination_kind": {"type": "string", "enum": ["individual", "group", "invite"]},
            "destination_label": {"type": "string", "nullable": True,
                                  "description": "snapshot label submitted with the message"},
            "label": {"type": "string", "nullable": True,
                      "description": "managed label if set, else the snapshot"},
            "subject": {"type": "string", "nullable": True},
            "status": {"type": "string", "enum": STATUS_ENUM},
            "created_at": {"$ref": "#/components/schemas/DateTime"},
            "updated_at": {"$ref": "#/components/schemas/DateTime"},
            "expires_at": {"type": "string", "nullable": True},
            "revision_number": {"type": "integer"},
            "source": {"type": "string", "nullable": True},
            "webhook_url": {"type": "string", "nullable": True},
            "allowed_actions": {"type": "array", "items": {"type": "string"}},
            "body_preview": {"type": "string"},
            "attachment_count": {"type": "integer"},
        },
    }
    message_full = {
        "allOf": [message_summary, {"type": "object", "properties": {
            "body": {"type": "string"},
            "rejection_reason": {"type": "string", "nullable": True},
            "rejection_at": {"type": "string", "nullable": True},
            "metadata": {"type": "object", "nullable": True},
            "attachments": {"type": "array", "items": attachment_schema},
            "references": {"type": "array", "items": {"type": "string"}},
        }}],
    }
    submit_attachment_spec = {
        "type": "object", "properties": {
            "kind": {"type": "string", "enum": ["url_reference", "url_download"]},
            "url": {"type": "string", "format": "uri"},
            "filename": {"type": "string", "description": "optional override for downloads"},
        },
        "required": ["kind", "url"],
    }
    submit_body = {
        "type": "object",
        "properties": {
            "channel": {"type": "string", "enum": CHANNEL_ENUM},
            "destination": {"type": "string", "description":
                "email address, +E.164 number, 'group:<name>', @username, t.me link, or invite code"},
            "subject": {"type": "string"},
            "body": {"type": "string"},
            "expires_at": {"type": "string", "description": "absolute UTC ISO 8601, future; mutually exclusive with ttl_seconds"},
            "ttl_seconds": {"type": "integer", "minimum": 1, "description": "mutually exclusive with expires_at"},
            "webhook_url": {"type": "string", "format": "uri"},
            "source": {"type": "string"},
            "metadata": {"type": "object"},
            "destination_label": {"type": "string"},
            "references": {"type": "array", "items": {"type": "string", "format": "uri"},
                           "description": "external URLs, stored as references, never fetched"},
            "attachments": {"type": "array", "items": submit_attachment_spec},
        },
        "required": ["channel", "destination", "body"],
    }
    patch_body = {
        "type": "object",
        "properties": {k: v for k, v in submit_body["properties"].items()},
        "description": "omitted fields stay unchanged; expires_at=null clears expiration; 'status' is rejected with 400",
    }
    handoff_schema = {
        "type": "object", "properties": {
            "message_id": {"type": "string"},
            "channel": {"type": "string", "enum": CHANNEL_ENUM},
            "destination": {"type": "string"},
            "normalized_destination": {"type": "string"},
            "destination_kind": {"type": "string"},
            "group_name": {"type": "string", "nullable": True},
            "handoff_url": {"type": "string", "description":
                "mailto:/wa.me/t.me URL (or an honest app-open fallback)"},
            "capabilities": {"type": "object", "properties": {
                "prefill_recipient": {"type": "boolean"},
                "prefill_subject": {"type": "boolean"},
                "prefill_body": {"type": "boolean"},
                "attachments_supported": {"type": "boolean"},
            }},
            "manual_actions": {"type": "array", "items": {"type": "string"}},
            "warnings": {"type": "array", "items": {"type": "string"}},
            "attachment_instructions": {"type": "string"},
            "attachments": {"type": "array", "items": attachment_schema},
            "references": {"type": "array", "items": {"type": "string"}},
            "copy": {"type": "object", "properties":
                     {"subject": {"type": "string"}, "body": {"type": "string"}}},
            "revision_number": {"type": "integer"},
            "status": {"type": "string"},
        },
    }
    webhook_event_schema = {
        "type": "object", "properties": {
            "event": {"type": "string", "enum": ["message.approved", "message.rejected",
                                                 "message.sent", "message.cancelled",
                                                 "message.stale", "message.revised"]},
            "message_id": {"type": "string"},
            "revision_number": {"type": "integer"},
            "message_status": {"type": "string"},
            "state": {"type": "string", "enum": ["queued", "delivering", "delivered", "failed"]},
            "attempts": {"type": "integer"},
            "last_status_code": {"type": "integer", "nullable": True},
            "last_error": {"type": "string", "nullable": True},
            "created_at": {"$ref": "#/components/schemas/DateTime"},
            "next_attempt_at": {"type": "string", "nullable": True},
            "delivered_at": {"type": "string", "nullable": True},
            "payload": {"type": "object"},
            "attempt_history": {"type": "array", "items": {"type": "object"}},
        },
    }
    destination_item = {
        "type": "object", "properties": {
            "channel": {"type": "string"},
            "destination": {"type": "string"},
            "normalized_destination": {"type": "string"},
            "label": {"type": "string", "nullable": True},
            "message_count": {"type": "integer"},
            "last_used": {"$ref": "#/components/schemas/DateTime"},
        },
    }
    destination_list_schema = {
        "type": "object",
        "properties": {"items": {"type": "array", "items": destination_item}},
    }
    envelope = {
        "type": "object", "properties": {
            "items": {"type": "array", "items": message_summary},
            "total": {"type": "integer"}, "limit": {"type": "integer"},
            "offset": {"type": "integer"},
        },
        "required": ["items", "total", "limit", "offset"],
    }

    errors = {
        "400": _resp("Validation error", ERROR_SCHEMA),
        "404": _resp("Not found", ERROR_SCHEMA),
        "409": _resp("Invalid transition or conflict", CONFLICT_SCHEMA),
        "413": _resp("Payload too large", ERROR_SCHEMA),
        "415": _resp("Unsupported media type", ERROR_SCHEMA),
    }

    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Human-in-the-Loop Outbox Service",
            "version": "1.0.0",
            "description": (
                "Local outbox for AI-drafted email/WhatsApp/Telegram messages. "
                "Producers submit via this REST API; a human reviews in the SPA and sends "
                "through their own apps using prepared handoff links. The service never "
                "integrates with provider APIs and never sends anything itself. All state "
                "lives in local SQLite; there is no authentication (loopback single-user "
                "deployment)."
            ),
        },
        "servers": [{"url": "http://127.0.0.1:8000"}],
        "tags": [
            {"name": "messages", "description": "Submission, review queue, lifecycle"},
            {"name": "handoff", "description": "Prepared links for manual sending"},
            {"name": "attachments", "description": "Files and external references"},
            {"name": "destinations", "description": "Discovered destinations and labels"},
            {"name": "system", "description": "Health, info, docs"},
        ],
        "paths": {
            "/api/messages": {
                "post": {
                    "tags": ["messages"], "operationId": "createMessage",
                    "summary": "Submit a message (JSON or multipart/form-data)",
                    "description": "Multipart uses repeated file parts named 'attachments'. "
                                   "JSON attachments are objects {kind: url_reference|url_download, url}.",
                    "requestBody": {"required": True, "content": {
                        "application/json": {"schema": submit_body, "examples": {
                            "email": {"value": {
                                "channel": "email", "destination": "alex@example.com",
                                "subject": "Q4 report draft",
                                "body": "Hi Alex,\n\nPlease review the attached Q4 report.",
                                "expires_at": "2030-01-01T00:00:00Z",
                                "webhook_url": "http://127.0.0.1:9002/hooks/outbox",
                                "source": "report-agent", "metadata": {"ticket": "OPS-142"}}},
                            "whatsapp_group": {"value": {
                                "channel": "whatsapp", "destination": "group:Project Alpha",
                                "body": "Standup moved to 10:00."}},
                            "telegram": {"value": {
                                "channel": "telegram", "destination": "@alex_example",
                                "body": "Build finished successfully."}},
                            "reference_and_download": {"value": {
                                "channel": "email", "destination": "alex@example.com",
                                "subject": "Reference and file",
                                "body": "See the external reference and the attached file.",
                                "references": ["https://example.com/spec"],
                                "attachments": [{"kind": "url_download",
                                                 "url": "http://127.0.0.1:9001/sample.txt",
                                                 "filename": "sample.txt"}]}}}},
                        "multipart/form-data": {"schema": {
                            "type": "object", "properties": {
                                "channel": {"type": "string", "enum": CHANNEL_ENUM},
                                "destination": {"type": "string"},
                                "subject": {"type": "string"},
                                "body": {"type": "string"},
                                "expires_at": {"type": "string"},
                                "ttl_seconds": {"type": "integer"},
                                "webhook_url": {"type": "string"},
                                "source": {"type": "string"},
                                "metadata": {"type": "string", "description": "JSON object as string"},
                                "destination_label": {"type": "string"},
                                "references": {"type": "array", "items": {"type": "string"}},
                                "attachments": {"type": "array", "items": {"type": "string",
                                                                           "format": "binary"}}}}}}},
                    "responses": {
                        "201": _resp("Created", {
                            "type": "object", "properties": {
                                "id": {"type": "string"},
                                "status": {"type": "string", "enum": STATUS_ENUM},
                                "created_at": {"$ref": "#/components/schemas/DateTime"},
                                "revision_number": {"type": "integer"}}}),
                        "400": errors["400"], "413": errors["413"], "415": errors["415"],
                    },
                },
                "get": {
                    "tags": ["messages"], "operationId": "listMessages",
                    "summary": "List messages with filters, pagination, sorting",
                    "parameters": [
                        {"name": "status", "in": "query", "schema": {"type": "string"},
                         "description": "status or comma-separated statuses, e.g. pending,approved,rejected"},
                        {"name": "channel", "in": "query", "schema": {"type": "string",
                                                                       "enum": CHANNEL_ENUM}},
                        {"name": "destination", "in": "query", "schema": {"type": "string"},
                         "description": "case-insensitive substring of destination or label"},
                        {"name": "created_from", "in": "query", "schema": {"type": "string"}},
                        {"name": "created_to", "in": "query", "schema": {"type": "string"}},
                        {"name": "expires_from", "in": "query", "schema": {"type": "string"}},
                        {"name": "expires_to", "in": "query", "schema": {"type": "string"}},
                        {"name": "limit", "in": "query", "schema": {"type": "integer",
                                                                     "default": 20, "maximum": 100}},
                        {"name": "offset", "in": "query", "schema": {"type": "integer",
                                                                      "default": 0, "minimum": 0}},
                        {"name": "sort", "in": "query",
                         "schema": {"type": "string", "enum": ["newest", "oldest",
                                                               "expires_soon", "expires_late"],
                                    "default": "newest"}},
                    ],
                    "responses": {"200": _resp("Envelope", envelope),
                                  "400": errors["400"]},
                },
            },
            "/api/messages/{id}": {
                "get": {
                    "tags": ["messages"], "operationId": "getMessage",
                    "summary": "Retrieve the complete active message",
                    "parameters": [{"$ref": "#/components/parameters/MessageId"}],
                    "responses": {"200": _resp("Full message", message_full),
                                  "404": errors["404"]},
                },
                "patch": {
                    "tags": ["messages"], "operationId": "patchMessage",
                    "summary": "Revise a pending or rejected message (creates a new revision)",
                    "description": "409 on approved/sent/stale/cancelled. 'status' in the body is a 400. "
                                   "Same expires_at/ttl_seconds rules as submission; expires_at=null clears.",
                    "parameters": [{"$ref": "#/components/parameters/MessageId"}],
                    "requestBody": {"required": True, "content": {
                        "application/json": {"schema": patch_body},
                        "multipart/form-data": {"schema": {"type": "object", "properties": {
                            "subject": {"type": "string"}, "body": {"type": "string"},
                            "attachments": {"type": "array",
                                            "items": {"type": "string", "format": "binary"}}}}}}},
                    "responses": {"200": _resp("Revised message", message_full),
                                  "400": errors["400"], "404": errors["404"],
                                  "409": errors["409"], "413": errors["413"],
                                  "415": errors["415"]},
                },
            },
            "/api/messages/{id}/approve": {
                "post": {"tags": ["messages"], "operationId": "approveMessage",
                         "summary": "pending -> approved",
                         "parameters": [{"$ref": "#/components/parameters/MessageId"}],
                         "responses": {"200": _resp("Approved message", message_full),
                                       "404": errors["404"], "409": errors["409"]}}},
            "/api/messages/{id}/reject": {
                "post": {"tags": ["messages"], "operationId": "rejectMessage",
                         "summary": "pending -> rejected (non-empty reason required)",
                         "parameters": [{"$ref": "#/components/parameters/MessageId"}],
                         "requestBody": {"required": True, "content": {"application/json": {
                             "schema": {"type": "object", "properties": {
                                 "reason": {"type": "string", "minLength": 1}},
                                 "required": ["reason"]},
                             "examples": {"name": {"value": {"reason":
                                 "The recipient name is wrong. Address it to Alex Smith, not Alex Doe."}}}}}},
                         "responses": {"200": _resp("Rejected message", message_full),
                                       "400": errors["400"], "404": errors["404"],
                                       "409": errors["409"]}}},
            "/api/messages/{id}/cancel": {
                "post": {"tags": ["messages"], "operationId": "cancelMessage",
                         "summary": "pending/rejected/approved -> cancelled (terminal)",
                         "parameters": [{"$ref": "#/components/parameters/MessageId"}],
                         "requestBody": {"required": False, "content": {"application/json": {
                             "schema": {"type": "object", "properties": {
                                 "reason": {"type": "string"}}}}}},
                         "responses": {"200": _resp("Cancelled message", message_full),
                                       "404": errors["404"], "409": errors["409"]}}},
            "/api/messages/{id}/mark-sent": {
                "post": {"tags": ["messages"], "operationId": "markSent",
                         "summary": "approved -> sent (only via this explicit call)",
                         "description": "Opening a handoff link or downloading an attachment never marks sent.",
                         "parameters": [{"$ref": "#/components/parameters/MessageId"}],
                         "requestBody": {"required": False, "content": {"application/json": {
                             "schema": {"type": "object", "properties": {
                                 "note": {"type": "string"}}}}}},
                         "responses": {"200": _resp("Sent message", message_full),
                                       "404": errors["404"], "409": errors["409"]}}},
            "/api/messages/{id}/history": {
                "get": {"tags": ["messages"], "operationId": "messageHistory",
                        "summary": "All revisions and status transitions, chronological",
                        "parameters": [{"$ref": "#/components/parameters/MessageId"}],
                        "responses": {"200": _resp("History", {
                            "type": "object", "properties": {
                                "message_id": {"type": "string"},
                                "current_status": {"type": "string"},
                                "revision_number": {"type": "integer"},
                                "revisions": {"type": "array", "items": {"type": "object"}},
                                "transitions": {"type": "array", "items": {"type": "object"}},
                                "timeline": {"type": "array", "items": {"type": "object"}},
                                "webhook_events": {"type": "array", "items": {"type": "object"}}}}),
                            "404": errors["404"]}}},
            "/api/messages/{id}/handoff": {
                "get": {"tags": ["handoff"], "operationId": "getHandoff",
                        "summary": "Prepared handoff data (approved messages only)",
                        "parameters": [{"$ref": "#/components/parameters/MessageId"}],
                        "responses": {"200": _resp("Handoff", handoff_schema),
                                      "404": errors["404"], "409": errors["409"]}}},
            "/api/messages/{id}/attachments": {
                "get": {"tags": ["attachments"], "operationId": "listAttachments",
                        "summary": "Attachments of the current revision",
                        "parameters": [{"$ref": "#/components/parameters/MessageId"}],
                        "responses": {"200": _resp("Attachment list", {
                            "type": "object", "properties": {
                                "items": {"type": "array", "items": attachment_schema}}}),
                            "404": errors["404"]}}},
            "/api/messages/{id}/attachments/{attachment_id}": {
                "get": {"tags": ["attachments"], "operationId": "downloadAttachment",
                        "summary": "Download one attachment (never changes status)",
                        "parameters": [{"$ref": "#/components/parameters/MessageId"},
                                       {"name": "attachment_id", "in": "path", "required": True,
                                        "schema": {"type": "string"}}],
                        "responses": {"200": _file_resp("Attachment bytes with "
                                                        "Content-Disposition: attachment and nosniff"),
                                      "404": errors["404"]}}},
            "/api/messages/{id}/attachments.zip": {
                "get": {"tags": ["attachments"], "operationId": "downloadAllAttachments",
                        "summary": "All attachments as a ZIP (stretch feature)",
                        "parameters": [{"$ref": "#/components/parameters/MessageId"}],
                        "responses": {"200": {"description": "ZIP archive", "content": {
                            "application/zip": {"schema": {"type": "string",
                                                           "format": "binary"}}}},
                            "404": errors["404"]}}},
            "/api/messages/{id}/webhook-events": {
                "get": {"tags": ["messages"], "operationId": "listWebhookEvents",
                        "summary": "Webhook delivery history for debugging",
                        "parameters": [{"$ref": "#/components/parameters/MessageId"}],
                        "responses": {"200": _resp("Events", {
                            "type": "object", "properties": {
                                "items": {"type": "array", "items": webhook_event_schema}}}),
                            "404": errors["404"]}}},
            "/api/destinations": {
                "get": {"tags": ["destinations"], "operationId": "listDestinations",
                        "summary": "Destinations discovered from submitted messages",
                        "responses": {"200": _resp("Destinations", destination_list_schema)}}},
            "/api/destinations/label": {
                "put": {"tags": ["destinations"], "operationId": "setLabel",
                        "summary": "Assign or rename a destination label",
                        "requestBody": {"required": True, "content": {"application/json": {
                            "schema": {"type": "object", "properties": {
                                "channel": {"type": "string", "enum": CHANNEL_ENUM},
                                "destination": {"type": "string"},
                                "label": {"type": "string", "minLength": 1}},
                                "required": ["channel", "destination", "label"]},
                            "examples": {"finance": {"value": {
                                "channel": "email", "destination": "alex@example.com",
                                "label": "Alex — Client"}}}}}},
                        "responses": {"200": _resp("Label row", {
                            "type": "object", "properties": {
                                "channel": {"type": "string"},
                                "normalized_destination": {"type": "string"},
                                "label": {"type": "string"},
                                "created_at": {"type": "string"},
                                "updated_at": {"type": "string"}}}),
                            "400": errors["400"], "409": errors["409"]}},
                "delete": {"tags": ["destinations"], "operationId": "removeLabel",
                           "summary": "Remove a label (historical messages are untouched)",
                           "parameters": [
                               {"name": "channel", "in": "query", "required": True,
                                "schema": {"type": "string", "enum": CHANNEL_ENUM}},
                               {"name": "destination", "in": "query", "required": True,
                                "schema": {"type": "string"}}],
                           "responses": {"200": _resp("Removed", {
                               "type": "object", "properties": {
                                   "deleted": {"type": "boolean"},
                                   "channel": {"type": "string"},
                                   "normalized_destination": {"type": "string"}}}),
                               "400": errors["400"]}}},
            "/api/health": {
                "get": {"tags": ["system"], "operationId": "health",
                        "summary": "Liveness check",
                        "responses": {"200": _resp("OK", {
                            "type": "object", "properties": {
                                "status": {"type": "string", "example": "ok"},
                                "time": {"$ref": "#/components/schemas/DateTime"}}})}}},
            "/api/info": {
                "get": {"tags": ["system"], "operationId": "info",
                        "summary": "Non-sensitive configuration",
                        "responses": {"200": _resp("Config", {"type": "object"})}}},
            "/api/docs": {"get": {"tags": ["system"], "operationId": "docs",
                                  "summary": "Human-readable endpoint list rendered from the spec",
                                  "responses": {"200": {"description": "HTML page", "content": {
                                      "text/html": {"schema": {"type": "string"}}}}}}},
            "/openapi.json": {"get": {"tags": ["system"], "operationId": "openapi",
                                      "summary": "This document",
                                      "responses": {"200": _resp("OpenAPI 3.0",
                                                                 {"type": "object"})}}},
        },
        "components": {
            "parameters": {
                "MessageId": {"name": "id", "in": "path", "required": True,
                              "schema": {"type": "string"},
                              "example": "msg_8f2c1a4b9d30"},
            },
            "schemas": {
                "DateTime": {"type": "string", "format": "date-time",
                             "description": "UTC ISO 8601 with Z suffix",
                             "example": "2026-11-06T20:00:00.000Z"},
                "Error": ERROR_SCHEMA,
                "MessageSummary": message_summary,
                "Message": message_full,
                "Attachment": attachment_schema,
                "SubmitMessage": submit_body,
                "PatchMessage": patch_body,
                "Handoff": handoff_schema,
                "WebhookEvent": webhook_event_schema,
                "ListEnvelope": envelope,
            },
        },
    }


if __name__ == "__main__":
    print(json.dumps(build_spec(), indent=2, ensure_ascii=False))
