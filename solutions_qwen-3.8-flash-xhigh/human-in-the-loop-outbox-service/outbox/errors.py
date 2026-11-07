"""Error model shared by the domain layer and the HTTP layer.

``ApiError`` carries an HTTP status, a machine-readable ``code``, a human
message, and optional extra ``details`` (e.g. ``current_status`` and
``allowed_actions`` on a 409). The Flask layer renders every error as:

    {"error": <code>, "message": <human message>, ...details}
"""
from __future__ import annotations

from typing import Any, Optional


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str,
                 details: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}

    def to_body(self) -> dict[str, Any]:
        body: dict[str, Any] = {"error": self.code, "message": self.message}
        body.update(self.details)
        return body


def bad_request(message: str, **details: Any) -> ApiError:
    return ApiError(400, "bad_request", message, details or None)


def unsupported_media(message: str, **details: Any) -> ApiError:
    return ApiError(415, "unsupported_media_type", message, details or None)


def not_found(message: str, **details: Any) -> ApiError:
    return ApiError(404, "not_found", message, details or None)


def conflict(message: str, *, current_status: Optional[str] = None,
             allowed_actions: Optional[list[str]] = None, **details: Any) -> ApiError:
    payload: dict[str, Any] = dict(details)
    if current_status is not None:
        payload["current_status"] = current_status
    if allowed_actions is not None:
        payload["allowed_actions"] = allowed_actions
    return ApiError(409, "conflict", message, payload or None)


def too_large(message: str, **details: Any) -> ApiError:
    return ApiError(413, "payload_too_large", message, details or None)
