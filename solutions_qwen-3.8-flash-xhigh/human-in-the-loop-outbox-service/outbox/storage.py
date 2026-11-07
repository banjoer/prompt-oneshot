"""Attachment persistence behind a small storage interface.

Rules enforced here:

* Client filenames are *never* used as storage paths. Storage names are
  generated from the server-side attachment id plus a sanitized basename,
  so path traversal and collisions are structurally impossible.
* Filenames are sanitized: paths stripped, control characters removed,
  unsafe reserved names (CON, NUL, COM1...) neutralized, length bounded.
* Bytes are written under the configured attachment directory only; reads
  re-check that the resolved path stays inside it.
* Uploaded/downloaded files are never executed; downloads are served with
  ``Content-Disposition: attachment`` and ``nosniff`` by the HTTP layer.
"""
from __future__ import annotations

import mimetypes
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from .config import Config
from .errors import bad_request
from .ids import new_attachment_id
from .timeutil import now_iso

RESERVED_NAMES = re.compile(
    r"^(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(\..*)?$", re.IGNORECASE
)
MAX_FILENAME_LEN = 150
CHUNK = 64 * 1024


@dataclass
class StoredAttachment:
    id: str
    filename: str          # sanitized original name (shown to users)
    stored_name: str       # server-generated file name on disk
    mime_type: str
    size_bytes: int
    source_type: str       # 'multipart' | 'url_download'
    source_url: Optional[str]
    uploaded_at: str


def sanitize_filename(raw: Optional[str]) -> str:
    """Turn any client-supplied name into a safe display filename."""
    name = (raw or "").strip()
    # Strip Windows/Unix path components and percent-encoded separators.
    name = name.replace("%2f", "/").replace("%5c", "\\")
    name = name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    # Normalize unicode, then drop control characters and characters that
    # break Content-Disposition headers.
    name = unicodedata.normalize("NFC", name)
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C" and ch not in '"\'<>|:;')
    name = name.strip(" .")  # no leading/trailing dots or spaces
    if RESERVED_NAMES.match(name):
        name = "_" + name
    if not name:
        name = "attachment"
    if len(name) > MAX_FILENAME_LEN:
        stem, dot, ext = name.rpartition(".")
        if dot and len(ext) <= 12:
            name = stem[: MAX_FILENAME_LEN - len(ext) - 1] + dot + ext
        else:
            name = name[:MAX_FILENAME_LEN]
    return name


def guess_mime(filename: str, data: bytes) -> str:
    guessed, _ = mimetypes.guess_type(filename)
    if guessed:
        return guessed
    # Small magic sniffing, then text-vs-binary heuristic.
    signatures = {
        b"%PDF": "application/pdf",
        b"PK\x03\x04": "application/zip",
        b"\x89PNG\r\n\x1a\n": "image/png",
        b"GIF87a": "image/gif",
        b"GIF89a": "image/gif",
        b"\xff\xd8\xff": "image/jpeg",
        b"ID3": "audio/mpeg",
        b"\x1f\x8b": "application/gzip",
        b"Rar!": "application/vnd.rar",
        b"7z\xbc\xaf\x27\x1c": "application/x-7z-compressed",
    }
    for magic, mime in signatures.items():
        if data.startswith(magic):
            return mime
    if data:
        head = data[:1024]
        try:
            head.decode("utf-8")
            printable = sum(1 for b in head if 32 <= b < 127 or b in (9, 10, 13))
            if printable / max(1, len(head)) > 0.90:
                return "text/plain"
        except UnicodeDecodeError:
            pass
    return "application/octet-stream"


class AttachmentStore:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        cfg.attachment_dir.mkdir(parents=True, exist_ok=True)

    # -- paths ---------------------------------------------------------------

    def _path_for(self, stored_name: str) -> Path:
        # Stored names are server-generated [A-Za-z0-9._-] only; anything
        # else (including traversal attempts) is refused outright.
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,255}", stored_name or ""):
            raise bad_request("invalid attachment storage reference")
        path = (self.cfg.attachment_dir / stored_name).resolve()
        root = self.cfg.attachment_dir.resolve()
        if not str(path).startswith(str(root) + "/") and path != root:
            raise bad_request("invalid attachment storage reference")
        return path

    def path_for(self, stored_name: str) -> Path:
        """Public lookup used by the download route; raises OSError-safe."""
        path = self._path_for(stored_name)
        if not path.is_file():
            from .errors import not_found
            raise not_found(
                "attachment file is missing on disk — restore it from backup "
                "or re-upload via PATCH", stored_name=stored_name)
        return path

    # -- writes --------------------------------------------------------------

    def save_bytes(self, data: bytes, *, original_filename: Optional[str],
                   source_type: str, source_url: Optional[str] = None,
                   declared_mime: Optional[str] = None) -> StoredAttachment:
        if len(data) == 0:
            raise bad_request("attachment data is empty", source_url=source_url)
        if len(data) > self.cfg.max_attachment_bytes:
            from .errors import too_large
            raise too_large(
                f"attachment is too large: {len(data)} bytes exceeds the per-file "
                f"limit of {self.cfg.max_attachment_bytes} bytes")
        att_id = new_attachment_id()
        filename = sanitize_filename(original_filename or _name_from_url(source_url))
        stored_name = f"{att_id}_{filename}"
        mime = (declared_mime or "").strip().lower() or None
        if mime and not re.fullmatch(r"[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+", mime):
            mime = None  # ignore bogus declared types and detect instead
        detected = guess_mime(filename, data)
        final_mime = mime if mime in _acceptable(mime, detected) else detected
        path = self._path_for(stored_name)
        tmp = path.with_suffix(path.suffix + ".part")
        try:
            with open(tmp, "wb") as fh:
                fh.write(data)
            tmp.replace(path)
        except OSError as exc:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            from .errors import ApiError
            raise ApiError(500, "storage_error", f"could not persist attachment: {exc}") from exc
        return StoredAttachment(
            id=att_id, filename=filename, stored_name=stored_name,
            mime_type=final_mime, size_bytes=len(data),
            source_type=source_type, source_url=source_url, uploaded_at=now_iso(),
        )

    def save_stream(self, stream, *, original_filename: Optional[str],
                    max_file_bytes: int) -> StoredAttachment:
        """Persist an upload stream while enforcing the per-file size cap.

        Cleans up its partial write and raises 413 when the cap is exceeded.
        """
        att_id = new_attachment_id()
        filename = sanitize_filename(original_filename)
        stored_name = f"{att_id}_{filename}"
        path = self._path_for(stored_name)
        total = 0
        head = bytearray()
        try:
            with open(path, "wb") as fh:
                while True:
                    chunk = stream.read(CHUNK)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_file_bytes:
                        raise _OverLimit()
                    if len(head) < 1024:
                        head.extend(chunk[: 1024 - len(head)])
                    fh.write(chunk)
        except _OverLimit:
            path.unlink(missing_ok=True)
            from .errors import too_large
            raise too_large(
                f"attachment {filename!r} exceeds the per-file limit of "
                f"{max_file_bytes} bytes") from None
        except OSError as exc:
            path.unlink(missing_ok=True)
            from .errors import ApiError
            raise ApiError(500, "storage_error", f"could not persist upload: {exc}") from exc
        if total == 0:
            path.unlink(missing_ok=True)
            raise bad_request(f"uploaded attachment {filename!r} is empty")
        mime = guess_mime(filename, bytes(head))
        return StoredAttachment(
            id=att_id, filename=filename, stored_name=stored_name,
            mime_type=mime, size_bytes=total,
            source_type="multipart", source_url=None, uploaded_at=now_iso(),
        )

    def delete_quietly(self, stored_names: Iterable[str]) -> None:
        for name in stored_names:
            try:
                self._path_for(name).unlink(missing_ok=True)
            except Exception:
                pass  # storage cleanup is best-effort; history is never destroyed


class _OverLimit(Exception):
    pass


def _name_from_url(url: Optional[str]) -> str:
    if not url:
        return "attachment"
    import urllib.parse
    tail = urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1]
    return urllib.parse.unquote(tail) or "attachment"


def _acceptable(mime: Optional[str], detected: str) -> set[str]:
    """Declared types that we are willing to trust for these bytes.

    A declared MIME type is honored only when it is compatible with the
    detected type — this stops a server or client from relabeling a .zip or
    an executable as ``text/plain``.
    """
    if not mime:
        return {detected}
    if mime == detected:
        return {mime}
    generic = {"application/octet-stream", "binary/octet-stream",
               "application/unknown", "application/download", "application/x-download"}
    if mime in generic:
        return {detected}
    if detected.startswith("text/") or mime.startswith("text/"):
        # text-vs-binary mismatches are never trusted.
        return {detected}
    if mime.split("/")[0] == detected.split("/")[0]:
        return {mime}
    return {detected}
