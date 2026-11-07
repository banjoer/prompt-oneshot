"""Outbound URL validation and safe HTTP fetching.

The only outbound requests the service ever makes are (a) attachment
``url_download`` fetches and (b) webhook POSTs, both to caller-supplied URLs.
Every request passes the SSRF guard here, and redirect targets are
revalidated hop by hop.

Default policy blocks: non-http(s) schemes, URLs with credentials, hosts that
fail DNS, and any resolved address that is loopback, private, link-local,
multicast, reserved, or unspecified — including cloud metadata endpoints.
``ALLOW_PRIVATE_URLS=1`` (documented local-testing override) additionally
permits loopback/private addresses, but link-local/metadata ranges
(169.254.0.0/16, 100.100.100.200, fc00::/7 sites-local style) stay blocked.
"""
from __future__ import annotations

import ipaddress
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from .errors import bad_request

ALLOWED_SCHEMES = {"http", "https"}

# Ranges that are NEVER reachable, even with ALLOW_PRIVATE_URLS=1.
ALWAYS_BLOCKED_NETWORKS = [
    ipaddress.ip_network("169.254.0.0/16"),      # link-local incl. cloud metadata
    ipaddress.ip_network("100.100.100.200/32"),  # Alibaba Cloud metadata
    ipaddress.ip_network("fd00::/8"),            # IPv6 unique-local
]


class UrlBlockedError(Exception):
    """Raised when an outbound URL fails the SSRF guard or cannot be fetched."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _ip_is_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
                   allow_private: bool) -> Optional[str]:
    for net in ALWAYS_BLOCKED_NETWORKS:
        if ip.version == net.version and ip in net:
            return f"blocked address range (cloud metadata / unique-local): {ip}"
    if ip.is_link_local:
        return f"link-local address: {ip}"
    if ip.is_multicast:
        return f"multicast address: {ip}"
    if ip.is_reserved:
        return f"reserved address: {ip}"
    if ip.is_unspecified:
        return f"unspecified address: {ip}"
    if not allow_private:
        if ip.is_loopback:
            return f"loopback address: {ip}"
        if ip.is_private:
            return f"private address: {ip}"
    # With allow_private (documented local-testing override), loopback and
    # private ranges are permitted; everything else was handled above.
    return None


def validate_url(url: str, *, field: str, allow_private: bool) -> str:
    """Validate scheme/host and resolved addresses. Returns the canonical URL.

    Raises UrlBlockedError for anything forbidden; the API layer converts
    that into a 400.
    """
    if not isinstance(url, str) or not url.strip():
        raise UrlBlockedError(f"{field} must be a non-empty URL string")
    url = url.strip()
    if len(url) > 2048:
        raise UrlBlockedError(f"{field} URL is too long (max 2048 characters)")
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise UrlBlockedError(f"{field} must use the http or https scheme, got {parsed.scheme or 'none'!r}")
    if not parsed.hostname:
        raise UrlBlockedError(f"{field} must include a host")
    if parsed.username or parsed.password:
        raise UrlBlockedError(f"{field} must not contain embedded credentials")
    host = parsed.hostname
    if host.strip("[]").lower() in {"localhost", "localhost.localdomain"}:
        if not allow_private:
            raise UrlBlockedError(f"{field} resolves to a loopback address (localhost is blocked by default)")
        return url
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80),
                                   type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UrlBlockedError(f"{field} host {host!r} could not be resolved: {exc}") from None
    if not infos:
        raise UrlBlockedError(f"{field} host {host!r} resolved to no addresses")
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            raise UrlBlockedError(f"{field} resolved to an unusable address: {addr}") from None
        reason = _ip_is_blocked(ip, allow_private)
        if reason:
            raise UrlBlockedError(f"{field} resolves to a blocked destination — {reason}")
    return url


class _NoRedirectPolicy(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102 - we block all auto-redirects
        return None


_OPENER = urllib.request.build_opener(_NoRedirectPolicy)


def http_get(url: str, *, allow_private: bool, timeout: float, max_bytes: int,
             max_redirects: int) -> tuple[bytes, Optional[str], Optional[str]]:
    """GET a caller URL with revalidated redirects and a hard size cap.

    Returns ``(body, content_type, suggested_filename)``.
    """
    current = url
    redirects = 0
    while True:
        checked = validate_url(current, field="attachment url", allow_private=allow_private)
        request = urllib.request.Request(checked, method="GET",
                                         headers={"User-Agent": "outbox-service/1.0"})
        try:
            response = _OPENER.open(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            if exc.code in (301, 302, 303, 307, 308):
                location = exc.headers.get("Location")
                if not location:
                    raise UrlBlockedError(f"download redirect #{redirects} had no Location header") from None
                if redirects >= max_redirects:
                    raise UrlBlockedError(
                        f"download exceeded {max_redirects} redirects") from None
                current = urllib.parse.urljoin(checked, location.strip())
                redirects += 1
                continue
            raise UrlBlockedError(f"download failed with HTTP status {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise UrlBlockedError(f"download failed: {exc.reason}") from exc
        except Exception as exc:  # socket timeouts etc.
            raise UrlBlockedError(
                f"download failed: {type(exc).__name__}: {exc}") from None
        try:
            status = getattr(response, "status", None) or response.getcode()
            if status is not None and status >= 300:
                location = response.headers.get("Location")
                if location and redirects < max_redirects and status in (301, 302, 303, 307, 308):
                    current = urllib.parse.urljoin(checked, location.strip())
                    redirects += 1
                    response.close()
                    continue
                raise UrlBlockedError(f"download returned unexpected HTTP status {status}")
            declared = response.headers.get("Content-Length")
            if declared:
                try:
                    if int(declared) > max_bytes:
                        raise UrlBlockedError(
                            f"download is too large: {declared} bytes exceeds limit of {max_bytes}")
                except ValueError:
                    pass
            content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower() or None
            filename = _filename_from_content_disposition(response.headers.get("Content-Disposition"))
            data = response.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise UrlBlockedError(f"download exceeded the size limit of {max_bytes} bytes")
            return data, content_type, filename
        finally:
            response.close()


def http_post_json(url: str, payload: dict, *, allow_private: bool,
                   timeout: float) -> int:
    """POST JSON to a webhook URL, revalidating first. Returns HTTP status."""
    checked = validate_url(url, field="webhook_url", allow_private=allow_private)
    body = __import__("json").dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        checked, data=body, method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "outbox-webhook/1.0"},
    )
    try:
        response = _OPENER.open(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        # Treat HTTP-level errors as delivery failures but surface the status.
        if exc.code in (301, 302, 303, 307, 308):
            raise UrlBlockedError("webhook endpoint returned a redirect; POST targets must not redirect") from None
        raise UrlBlockedError(f"webhook returned HTTP status {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise UrlBlockedError(f"webhook delivery failed: {exc.reason}") from exc
    except Exception as exc:
        raise UrlBlockedError(
            f"webhook delivery failed: {type(exc).__name__}: {exc}") from None
    try:
        code = response.getcode()
    finally:
        response.close()
    return code


def _filename_from_content_disposition(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    for segment in value.split(";"):
        segment = segment.strip()
        if segment.lower().startswith("filename*="):
            raw = segment.split("=", 1)[1].strip()
            if "'" in raw:
                bits = raw.split("'", 2)
                if len(bits) == 3:
                    try:
                        return urllib.parse.unquote(bits[2], encoding=bits[0] or "utf-8")
                    except (LookupError, UnicodeDecodeError):
                        return None
            return None
        if segment.lower().startswith("filename="):
            raw = segment.split("=", 1)[1].strip().strip('"')
            return urllib.parse.unquote(raw)
    return None
