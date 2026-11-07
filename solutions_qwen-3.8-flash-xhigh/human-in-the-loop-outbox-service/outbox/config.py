"""Configuration for the outbox service, loaded from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "")
    if raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from None
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer, got {value}")
    return value


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Config:
    data_dir: Path = field(default_factory=lambda: Path("./data"))
    attachment_dir: Path = field(default_factory=lambda: Path("./data/attachments"))
    max_attachment_bytes: int = 10 * 1024 * 1024          # per file (10 MiB)
    max_message_attachment_bytes: int = 25 * 1024 * 1024  # per message (25 MiB)
    expiration_interval_seconds: int = 30
    webhook_timeout_seconds: float = 5.0
    webhook_max_attempts: int = 3
    webhook_backoff_base_seconds: float = 1.0
    download_timeout_seconds: float = 10.0
    max_redirects: int = 3
    allow_private_urls: bool = False
    port: int = 8000
    max_handoff_url_length: int = 1800
    host: str = "127.0.0.1"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "outbox.db"

    @classmethod
    def from_env(cls) -> "Config":
        data_dir = Path(os.environ.get("DATA_DIR", "./data"))
        attachment_dir = Path(os.environ.get("ATTACHMENT_DIR", str(data_dir / "attachments")))
        return cls(
            data_dir=data_dir,
            attachment_dir=attachment_dir,
            max_attachment_bytes=_env_int("MAX_ATTACHMENT_BYTES", 10 * 1024 * 1024),
            max_message_attachment_bytes=_env_int("MAX_MESSAGE_ATTACHMENT_BYTES", 25 * 1024 * 1024),
            expiration_interval_seconds=_env_int("EXPIRATION_INTERVAL_SECONDS", 30),
            webhook_timeout_seconds=float(_env_int("WEBHOOK_TIMEOUT_SECONDS", 5)),
            webhook_max_attempts=_env_int("WEBHOOK_MAX_ATTEMPTS", 3),
            webhook_backoff_base_seconds=float(_env_int("WEBHOOK_BACKOFF_BASE_SECONDS", 1)),
            download_timeout_seconds=float(_env_int("DOWNLOAD_TIMEOUT_SECONDS", 10)),
            max_redirects=_env_int("MAX_REDIRECTS", 3),
            allow_private_urls=_env_bool("ALLOW_PRIVATE_URLS", False),
            port=_env_int("PORT", 8000),
            max_handoff_url_length=_env_int("MAX_HANDOFF_URL_LENGTH", 1800),
        )

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.attachment_dir.mkdir(parents=True, exist_ok=True)

    def public_info(self) -> dict:
        """Non-sensitive configuration exposed via GET /api/info."""
        return {
            "service": "human-in-the-loop-outbox",
            "version": VERSION,
            "built_at": BUILT_AT,
            "author": AUTHOR,
            "data_dir": str(self.data_dir),
            "attachment_dir": str(self.attachment_dir),
            "host": self.host,
            "port": self.port,
            "max_attachment_bytes": self.max_attachment_bytes,
            "max_message_attachment_bytes": self.max_message_attachment_bytes,
            "expiration_interval_seconds": self.expiration_interval_seconds,
            "webhook_timeout_seconds": self.webhook_timeout_seconds,
            "webhook_max_attempts": self.webhook_max_attempts,
            "webhook_backoff_base_seconds": self.webhook_backoff_base_seconds,
            "download_timeout_seconds": self.download_timeout_seconds,
            "max_redirects": self.max_redirects,
            "allow_private_urls": self.allow_private_urls,
            "max_handoff_url_length": self.max_handoff_url_length,
            "channels": ["email", "whatsapp", "telegram"],
        }


VERSION = "1.0.0"
BUILT_AT = "2026-11-06T23:42:00Z"
AUTHOR = "Qwen3.8 Flash"
