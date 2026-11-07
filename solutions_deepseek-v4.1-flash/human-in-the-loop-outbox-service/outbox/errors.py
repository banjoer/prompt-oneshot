"""Typed API errors used across the domain and HTTP layers."""

from __future__ import annotations

from typing import Any


class ApiError(Exception):
    """An error that maps directly onto a JSON HTTP response."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }
        # Promote a few high-value details for convenient clients. They are
        # duplicated intentionally; the canonical location is error.details.
        for key in ("current_status", "allowed_actions", "message_id"):
            if key in self.details:
                payload[key] = self.details[key]
        if "current_status" in self.details:
            payload["status"] = self.details["current_status"]
        return payload


class ValidationError(ApiError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(400, "validation_error", message, details)


class NotFoundError(ApiError):
    def __init__(self, message: str = "Resource not found.", details: dict[str, Any] | None = None) -> None:
        super().__init__(404, "not_found", message, details)


class ConflictError(ApiError):
    def __init__(
        self,
        message: str,
        current_status: str | None = None,
        allowed_actions: list[str] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged = dict(details or {})
        if current_status is not None:
            merged["current_status"] = current_status
        if allowed_actions is not None:
            merged["allowed_actions"] = allowed_actions
        super().__init__(409, "invalid_transition", message, merged)


class TooLargeError(ApiError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(413, "payload_too_large", message, details)


class UnsupportedMediaTypeError(ApiError):
    def __init__(self, message: str = "Unsupported media type.") -> None:
        super().__init__(415, "unsupported_media_type", message)
