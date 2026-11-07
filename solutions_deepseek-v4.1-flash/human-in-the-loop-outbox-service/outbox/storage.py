"""Attachment storage behind a tiny interface, with traversal-proof paths."""

from __future__ import annotations

import os
import re
import unicodedata
import uuid
from pathlib import Path
from typing import Any

from .errors import ValidationError

RESERVED_NAMES = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}
STORAGE_NAME_RE = re.compile(r"^[0-9a-f]{32}(?:\.[A-Za-z0-9]{1,16})?$")
UNSAFE_CHARS_RE = re.compile(r'[\x00-\x1f\x7f/\\:*?"<>|]')
WHITESPACE_RE = re.compile(r"\s+")


def sanitize_filename(raw: str | None, fallback: str = "attachment") -> str:
    """Return a safe display filename (never a path) preserving the extension."""
    name = raw if isinstance(raw, str) else ""
    # Normalise unicode and remove any directory components from Windows and POSIX paths.
    name = unicodedata.normalize("NFKC", name)
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C")
    name = UNSAFE_CHARS_RE.sub("_", name)
    name = WHITESPACE_RE.sub(" ", name).strip().strip(".")
    if not name or name in {".", ".."}:
        name = fallback
    stem, ext = os.path.splitext(name)
    stem = stem.strip().strip(".")
    if not stem:
        stem = fallback
    if stem.lower() in RESERVED_NAMES:
        stem = f"_{stem}"
    ext = ext[:17]
    max_stem = max(1, 180 - len(ext))
    stem = stem[:max_stem]
    result = stem + ext
    if len(result) > 180:
        result = result[:180]
    return result or fallback


def safe_extension(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if re.fullmatch(r"\.[a-z0-9]{1,16}", ext):
        return ext
    return ""


class AttachmentStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def new_storage_name(self, filename: str) -> str:
        return uuid.uuid4().hex + safe_extension(filename)

    def path_for(self, storage_name: str) -> Path:
        if not STORAGE_NAME_RE.fullmatch(storage_name or ""):
            raise ValidationError("Invalid attachment storage reference.")
        candidate = (self.root / storage_name).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValidationError("Invalid attachment storage reference.") from exc
        return candidate

    def save_bytes(
        self,
        *,
        filename: str,
        mime_type: str,
        data: bytes,
        source_type: str,
        source_url: str | None,
    ) -> dict[str, Any]:
        safe_name = sanitize_filename(filename)
        storage_name = self.new_storage_name(safe_name)
        path = self.path_for(storage_name)
        # Exclusive create prevents accidental overwrite of an existing blob.
        with open(path, "xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(path, 0o600)
        except OSError:  # pragma: no cover - platform dependent
            pass
        return {
            "original_filename": safe_name,
            "mime_type": mime_type or "application/octet-stream",
            "size_bytes": len(data),
            "storage_name": storage_name,
            "source_type": source_type,
            "source_url": source_url,
        }

    def read_bytes(self, storage_name: str) -> bytes:
        path = self.path_for(storage_name)
        try:
            with open(path, "rb") as handle:
                return handle.read()
        except FileNotFoundError as exc:
            raise FileNotFoundError(storage_name) from exc

    def exists(self, storage_name: str) -> bool:
        return self.path_for(storage_name).is_file()
