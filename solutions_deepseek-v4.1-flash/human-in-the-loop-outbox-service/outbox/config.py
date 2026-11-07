"""Environment-driven configuration for the outbox service."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise SystemExit(f"{name} must be an integer, got {raw!r}") from exc
    if value < 0:
        raise SystemExit(f"{name} must not be negative")
    return value


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise SystemExit(f"{name} must be a number, got {raw!r}") from exc
    if value < 0:
        raise SystemExit(f"{name} must not be negative")
    return value


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


@dataclass
class Config:
    data_dir: Path
    attachment_dir: Path
    database_path: Path
    max_attachment_bytes: int = 10 * 1024 * 1024
    max_message_attachment_bytes: int = 25 * 1024 * 1024
    expiration_interval_seconds: float = 30.0
    webhook_timeout_seconds: float = 5.0
    webhook_max_attempts: int = 3
    webhook_backoff_base_seconds: float = 1.0
    download_timeout_seconds: float = 10.0
    max_redirects: int = 3
    allow_private_urls: bool = False
    port: int = 8000
    host: str = "127.0.0.1"
    static_dir: Path | None = None
    openapi_path: Path | None = None
    start_workers: bool = True
    webhook_async: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_env(
        cls,
        base_dir: str | os.PathLike[str] | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> "Config":
        base = Path(base_dir or os.getcwd()).resolve()
        if overrides is None:
            overrides = {}
        elif isinstance(overrides, (str, os.PathLike)):
            overrides = {
                "data_dir": str(overrides),
                "attachment_dir": str(Path(overrides) / "attachments"),
            }
        else:
            # Accept both Python-style lowercase keys and env-style uppercase keys.
            overrides = {str(key).lower(): value for key, value in dict(overrides).items()}
        data_raw = overrides.pop("data_dir", os.environ.get("DATA_DIR", "./data"))
        attach_raw = overrides.pop(
            "attachment_dir", os.environ.get("ATTACHMENT_DIR", str(Path(str(data_raw)) / "attachments"))
        )
        data_dir = Path(data_raw)
        if not data_dir.is_absolute():
            data_dir = (base / data_dir).resolve()
        attachment_dir = Path(attach_raw)
        if not attachment_dir.is_absolute():
            attachment_dir = (base / attachment_dir).resolve()
        database_path = Path(overrides.pop("database_path", data_dir / "outbox.sqlite3"))
        if not database_path.is_absolute():
            database_path = (base / database_path).resolve()
        static_dir = Path(
            overrides.pop(
                "static_dir", os.environ.get("STATIC_DIR", str(Path(__file__).resolve().parent.parent / "static"))
            )
        )
        openapi_path = Path(
            overrides.pop(
                "openapi_path", os.environ.get("OPENAPI_PATH", str(Path(__file__).resolve().parent.parent / "openapi.json"))
            )
        )
        if not static_dir.is_absolute():
            static_dir = (base / static_dir).resolve()
        if not openapi_path.is_absolute():
            openapi_path = (base / openapi_path).resolve()
        cfg = cls(
            data_dir=data_dir,
            attachment_dir=attachment_dir,
            database_path=database_path,
            max_attachment_bytes=overrides.pop(
                "max_attachment_bytes", _env_int("MAX_ATTACHMENT_BYTES", 10485760)
            ),
            max_message_attachment_bytes=overrides.pop(
                "max_message_attachment_bytes",
                _env_int("MAX_MESSAGE_ATTACHMENT_BYTES", 26214400),
            ),
            expiration_interval_seconds=overrides.pop(
                "expiration_interval_seconds", _env_float("EXPIRATION_INTERVAL_SECONDS", 30.0)
            ),
            webhook_timeout_seconds=overrides.pop(
                "webhook_timeout_seconds", _env_float("WEBHOOK_TIMEOUT_SECONDS", 5.0)
            ),
            webhook_max_attempts=overrides.pop(
                "webhook_max_attempts", _env_int("WEBHOOK_MAX_ATTEMPTS", 3)
            ),
            webhook_backoff_base_seconds=overrides.pop(
                "webhook_backoff_base_seconds",
                _env_float("WEBHOOK_BACKOFF_BASE_SECONDS", 1.0),
            ),
            download_timeout_seconds=overrides.pop(
                "download_timeout_seconds", _env_float("DOWNLOAD_TIMEOUT_SECONDS", 10.0)
            ),
            max_redirects=overrides.pop("max_redirects", _env_int("MAX_REDIRECTS", 3)),
            allow_private_urls=overrides.pop(
                "allow_private_urls", _env_bool("ALLOW_PRIVATE_URLS", False)
            ),
            port=overrides.pop("port", _env_int("PORT", 8000)),
            host=overrides.pop("host", os.environ.get("HOST", "127.0.0.1")),
            static_dir=static_dir,
            openapi_path=openapi_path,
            start_workers=overrides.pop("start_workers", True),
            webhook_async=overrides.pop("webhook_async", True),
            extra=overrides,
        )
        # Coerce programmatic overrides that arrive as environment-style strings.
        cfg.max_attachment_bytes = int(cfg.max_attachment_bytes)
        cfg.max_message_attachment_bytes = int(cfg.max_message_attachment_bytes)
        cfg.expiration_interval_seconds = float(cfg.expiration_interval_seconds)
        cfg.webhook_timeout_seconds = float(cfg.webhook_timeout_seconds)
        cfg.webhook_max_attempts = int(cfg.webhook_max_attempts)
        cfg.webhook_backoff_base_seconds = float(cfg.webhook_backoff_base_seconds)
        cfg.download_timeout_seconds = float(cfg.download_timeout_seconds)
        cfg.max_redirects = int(cfg.max_redirects)
        cfg.port = int(cfg.port)
        cfg.allow_private_urls = _coerce_bool(cfg.allow_private_urls)
        cfg.start_workers = _coerce_bool(cfg.start_workers)
        cfg.webhook_async = _coerce_bool(cfg.webhook_async)
        return cfg

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.attachment_dir.mkdir(parents=True, exist_ok=True)

    def public_info(self) -> dict[str, Any]:
        return {
            "data_dir": str(self.data_dir),
            "attachment_dir": str(self.attachment_dir),
            "database": str(self.database_path),
            "max_attachment_bytes": self.max_attachment_bytes,
            "max_message_attachment_bytes": self.max_message_attachment_bytes,
            "expiration_interval_seconds": self.expiration_interval_seconds,
            "webhook_timeout_seconds": self.webhook_timeout_seconds,
            "webhook_max_attempts": self.webhook_max_attempts,
            "webhook_backoff_base_seconds": self.webhook_backoff_base_seconds,
            "download_timeout_seconds": self.download_timeout_seconds,
            "max_redirects": self.max_redirects,
            "allow_private_urls": self.allow_private_urls,
            "port": self.port,
            "host": self.host,
        }
