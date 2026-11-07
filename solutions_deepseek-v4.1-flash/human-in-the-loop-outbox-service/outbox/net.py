"""Outbound HTTP safety: SSRF validation, safe downloads and webhook POSTs."""

from __future__ import annotations

import ipaddress
import json
import mimetypes
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from .errors import ApiError, TooLargeError, ValidationError

USER_AGENT = "HumanInTheLoopOutbox/1.0 (+local; no telemetry)"
BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "metadata",
    "metadata.google.internal",
    "metadata.goog",
    "instance-data",
    "instance-data.ec2.internal",
}
METADATA_IPS = {
    "169.254.169.254",
    "100.100.100.200",
    "fd00:ec2::254",
}
MIME_RE = re.compile(r"^[A-Za-z0-9!#$&^_.+\-]+/[A-Za-z0-9!#$&^_.+\-]+$")


class OutboundUrlError(ValidationError):
    pass


class DownloadError(ApiError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(400, "download_failed", message, details)


def _ip_is_blocked(ip: ipaddress._BaseAddress) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if str(ip) in METADATA_IPS:
        return True
    if isinstance(ip, ipaddress.IPv4Address) and ip in ipaddress.ip_network("100.64.0.0/10"):
        return True
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
    )


def _resolve(host: str, port: int) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return []
    addresses: list[str] = []
    for info in infos:
        addr = info[4][0]
        # Strip IPv6 scope identifiers.
        if "%" in addr:
            addr = addr.split("%", 1)[0]
        addresses.append(addr)
    return sorted(set(addresses))


def validate_outbound_url(
    url: str,
    *,
    allow_private: bool = False,
    require_resolution: bool = False,
    field: str = "url",
    max_length: int = 2048,
) -> str:
    """Validate an outbound URL and block SSRF-prone targets.

    Resolution failures are rejected only when ``require_resolution`` is true.
    This lets producers register a webhook whose DNS is temporarily unavailable
    while still blocking literal private addresses and known metadata hosts.
    """
    if not isinstance(url, str):
        raise OutboundUrlError(f"{field} must be a string URL.")
    cleaned = url.strip()
    if not cleaned:
        raise OutboundUrlError(f"{field} must not be empty.")
    if len(cleaned) > max_length:
        raise OutboundUrlError(f"{field} is too long (maximum {max_length} characters).")
    parsed = urllib.parse.urlsplit(cleaned)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise OutboundUrlError(f"{field} must use http or https.")
    if not parsed.netloc or not parsed.hostname:
        raise OutboundUrlError(f"{field} must be an absolute http(s) URL.")
    if parsed.username or parsed.password:
        raise OutboundUrlError(f"{field} must not contain credentials.")
    try:
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    except ValueError as exc:
        raise OutboundUrlError(f"{field} has an invalid port.") from exc
    host = parsed.hostname.strip().lower().rstrip(".")
    if not host:
        raise OutboundUrlError(f"{field} has no host.")
    if host in BLOCKED_HOSTNAMES or host.endswith(".localhost") or host.endswith(".local"):
        if not allow_private:
            raise OutboundUrlError(f"{field} targets a local or metadata host, which is blocked.")
    if allow_private:
        return cleaned

    # Literal IPs are always checked without DNS.
    literal: ipaddress._BaseAddress | None = None
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if _ip_is_blocked(literal):
            raise OutboundUrlError(
                f"{field} targets a private, loopback, link-local, reserved or metadata address, which is blocked."
            )
        return cleaned

    addresses = _resolve(host, port)
    if not addresses:
        if require_resolution:
            raise OutboundUrlError(f"{field} host could not be resolved.")
        return cleaned
    for addr in addresses:
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if _ip_is_blocked(ip):
            raise OutboundUrlError(
                f"{field} resolves to a private, loopback, link-local, reserved or metadata address, which is blocked."
            )
    return cleaned


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


@dataclass
class DownloadResult:
    data: bytes
    filename: str
    mime_type: str
    final_url: str


def _safe_mime(value: str | None, filename: str) -> str:
    if value:
        candidate = value.split(";", 1)[0].strip().lower()
        if MIME_RE.match(candidate):
            return candidate
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


def _filename_from_url(url: str) -> str:
    path = urllib.parse.urlsplit(url).path
    name = urllib.parse.unquote(path.rsplit("/", 1)[-1])
    return name or "download"


def safe_download(
    url: str,
    *,
    max_bytes: int,
    timeout: float,
    max_redirects: int,
    allow_private: bool,
    override_filename: str | None = None,
) -> DownloadResult:
    """Download bounded bytes from a validated URL, validating every redirect."""
    current = url
    opener = urllib.request.build_opener(_NoRedirect())
    for redirect_count in range(max_redirects + 1):
        try:
            validate_outbound_url(
                current,
                allow_private=allow_private,
                require_resolution=True,
                field="attachment URL",
            )
        except ValidationError:
            raise
        request = urllib.request.Request(
            current,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "*/*",
                "Accept-Encoding": "identity",
            },
            method="GET",
        )
        try:
            response = opener.open(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            location = exc.headers.get("Location") if exc.headers else None
            if exc.code in {301, 302, 303, 307, 308} and location:
                if redirect_count >= max_redirects:
                    raise DownloadError(
                        f"Attachment download exceeded the maximum of {max_redirects} redirects."
                    )
                current = urllib.parse.urljoin(current, location)
                continue
            raise DownloadError(
                f"Attachment download failed with HTTP {exc.code}.",
                {"http_status": exc.code},
            ) from exc
        except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
            raise DownloadError(f"Attachment download failed: {exc}") from exc

        final_url = response.geturl()
        try:
            validate_outbound_url(
                final_url,
                allow_private=allow_private,
                require_resolution=True,
                field="attachment URL",
            )
        except ValidationError:
            response.close()
            raise
        content_length = response.headers.get("Content-Length")
        if content_length:
            try:
                declared = int(content_length)
            except ValueError:
                declared = None
            if declared is not None and declared > max_bytes:
                response.close()
                raise TooLargeError(
                    f"Attachment exceeds the maximum size of {max_bytes} bytes.",
                    {"max_bytes": max_bytes, "declared_bytes": declared},
                )
        chunks: list[bytes] = []
        total = 0
        try:
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise TooLargeError(
                        f"Attachment exceeds the maximum size of {max_bytes} bytes.",
                        {"max_bytes": max_bytes},
                    )
                chunks.append(chunk)
        except (TimeoutError, socket.timeout, OSError) as exc:
            raise DownloadError(f"Attachment download failed while reading: {exc}") from exc
        finally:
            response.close()

        filename = override_filename.strip() if override_filename else ""
        if not filename:
            filename = _filename_from_url(final_url)
        mime_type = _safe_mime(response.headers.get("Content-Type"), filename)
        return DownloadResult(
            data=b"".join(chunks),
            filename=filename,
            mime_type=mime_type,
            final_url=final_url,
        )
    raise DownloadError("Attachment download exceeded the maximum number of redirects.")


def post_webhook(
    url: str,
    payload: dict[str, Any],
    *,
    timeout: float,
    allow_private: bool,
) -> tuple[bool, int | None, str | None, str | None]:
    """Deliver one webhook attempt. Returns (ok, http_status, error, response_body)."""
    try:
        validate_outbound_url(
            url,
            allow_private=allow_private,
            require_resolution=True,
            field="webhook_url",
        )
    except ValidationError as exc:
        return False, None, str(exc), None
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": USER_AGENT,
            "Accept": "application/json, */*",
        },
        method="POST",
    )
    try:
        # Webhooks intentionally do not follow redirects: a redirect could
        # silently move delivery to a different target after validation.
        opener = urllib.request.build_opener(_NoRedirect())
        response = opener.open(request, timeout=timeout)
        body = response.read(2048).decode("utf-8", "replace")
        status = response.status
        response.close()
        if 200 <= status < 300:
            return True, status, None, body
        return False, status, f"HTTP {status}", body
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read(2048).decode("utf-8", "replace")
        except Exception:  # pragma: no cover - defensive
            body = None
        if 200 <= exc.code < 300:
            return True, exc.code, None, body
        return False, exc.code, f"HTTP {exc.code}", body
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
        return False, None, str(exc), None
