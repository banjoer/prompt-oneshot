"""Channel adapters: destination validation/normalization, handoff URLs,
capabilities, limitations, and required manual actions.

All channel-specific knowledge lives here; the HTTP layer and the SPA only
consume the structured handoff objects produced by these adapters.
"""
from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Optional

from .errors import bad_request


@dataclass
class Destination:
    raw: str                  # as submitted
    normalized: str           # canonical form used for matching/labels
    kind: str                 # 'individual' | 'group' | 'invite'
    display_name: Optional[str] = None  # group name etc., shown to the reviewer


@dataclass
class HandoffRequest:
    destination: Destination
    subject: Optional[str]
    body: str
    max_url_length: int


@dataclass
class HandoffResult:
    handoff_url: str
    capabilities: dict[str, bool]
    manual_actions: list[str]
    warnings: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)


EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
GROUP_PREFIX = "group:"


class ChannelAdapter:
    channel: str = ""
    supports_subject: bool = False

    def validate_destination(self, raw: str) -> Destination:
        raise NotImplementedError

    def normalize_destination(self, dest: Destination) -> str:
        return dest.normalized

    def build_handoff(self, req: HandoffRequest) -> HandoffResult:
        raise NotImplementedError

    def attachment_instructions(self) -> str:
        return (
            "Open the handoff link, then download each attachment from this "
            "page and attach it manually in the external application."
        )


def _parse_group(raw: str, channel: str) -> Optional[Destination]:
    if raw.lower().startswith(GROUP_PREFIX):
        name = raw[len(GROUP_PREFIX):].strip()
        if not name:
            raise bad_request(
                f"group destination for {channel} must name a group, e.g. 'group:Project Alpha'",
                field="destination")
        if len(name) > 120:
            raise bad_request("group name is too long (max 120 characters)", field="destination")
        return Destination(raw=raw, normalized=name.lower(), kind="group", display_name=name)
    return None


def _encode(text: str) -> str:
    # percent-encode everything outside unreserved chars: correct for UTF-8,
    # special characters, and newlines (%0A).
    return urllib.parse.quote(text, safe="")


class EmailAdapter(ChannelAdapter):
    channel = "email"
    supports_subject = True

    def validate_destination(self, raw: str) -> Destination:
        value = raw.strip()
        if not EMAIL_RE.match(value):
            raise bad_request(
                f"'{raw}' is not a valid email address (expected local@domain.tld)",
                field="destination")
        local, _, domain = value.partition("@")
        # Assumption: the whole address is treated case-insensitively for
        # normalization, matching common provider behavior and label reuse.
        normalized = value.lower()
        return Destination(raw=raw, normalized=normalized, kind="individual")

    def build_handoff(self, req: HandoffRequest) -> HandoffResult:
        to = urllib.parse.quote(req.destination.normalized, safe="@")
        caps = {"prefill_recipient": True, "prefill_subject": True,
                "prefill_body": True, "attachments_supported": False}
        manual = [
            "Open your mail client (triggered by the mailto: link).",
            "Download every attachment from this page and attach them manually — "
            "mailto: links cannot carry attachments.",
            "Verify the recipient, subject, and body before sending.",
            "Press send in your mail client. This service never sends anything.",
        ]
        warnings = [
            "mailto: cannot prefill attachments; download and attach them manually.",
        ]
        url_full = f"mailto:{to}"
        if req.subject:
            url_full += "?subject=" + _encode(req.subject)
        body_sep = "&" if req.subject else "?"
        with_body = f"{url_full}{body_sep}body={_encode(req.body)}" if req.body else url_full
        if len(with_body) <= req.max_url_length:
            return HandoffResult(with_body, caps, manual, warnings)
        # Long-body fallback: recipient + subject only.
        fallback = url_full
        if len(fallback) > req.max_url_length and req.subject:
            # subject alone is oversized: truncate it for the link, body/subject
            # remain available through copy controls.
            budget = req.max_url_length - len(f"mailto:{to}?subject=")
            fallback = f"mailto:{to}?subject=" + _encode(req.subject[:max(20, budget // 3)]) if budget > 24 else f"mailto:{to}"
        warnings = warnings + [
            f"The full body exceeds the practical URL limit ({req.max_url_length} chars), "
            "so it is not prefilled in the link. Use 'Copy body' and paste it into the email.",
        ]
        caps = dict(caps, prefill_body=False)
        if len(fallback) > req.max_url_length:
            fallback = f"mailto:{to}"
            caps = dict(caps, prefill_subject=False)
            warnings.append("The subject was also too long to prefill; use 'Copy subject'.")
        return HandoffResult(fallback, caps, manual, warnings)


class WhatsAppAdapter(ChannelAdapter):
    channel = "whatsapp"

    def validate_destination(self, raw: str) -> Destination:
        group = _parse_group(raw, "whatsapp")
        if group:
            return group
        value = raw.strip()
        if not value.startswith("+"):
            raise bad_request(
                "WhatsApp individual destinations must be international phone numbers "
                "in E.164 form, e.g. '+14155550123' (or 'group:<name>' for groups)",
                field="destination")
        digits = re.sub(r"[\s().\-]", "", value)
        if digits != "+" + digits[1:].lstrip("+") or not re.fullmatch(r"\+\d{8,15}", digits):
            raise bad_request(
                f"'{raw}' is not a valid international WhatsApp number "
                "(expected '+' followed by 8-15 digits, e.g. +14155550123)",
                field="destination")
        return Destination(raw=raw, normalized=digits, kind="individual")

    def build_handoff(self, req: HandoffRequest) -> HandoffResult:
        dest = req.destination
        manual_common = [
            "Download every attachment from this page — WhatsApp handoff cannot attach files.",
            "Press send inside WhatsApp. This service never sends anything.",
        ]
        if dest.kind == "group":
            return HandoffResult(
                handoff_url="https://wa.me/",
                capabilities={"prefill_recipient": False, "prefill_subject": False,
                              "prefill_body": False, "attachments_supported": False},
                manual_actions=[
                    f"Open WhatsApp and find the group '{dest.display_name}' yourself.",
                    "Paste the message body (use Copy body).",
                    *manual_common,
                ],
                warnings=[
                    f"WhatsApp has no URL scheme to preselect a group ('{dest.display_name}'). "
                    "The link only opens WhatsApp; recipient and content are NOT prefilled.",
                ],
                extra={"group_name": dest.display_name},
            )
        digits = dest.normalized.lstrip("+")
        url = f"https://wa.me/{digits}?text={_encode(req.body)}"
        caps = {"prefill_recipient": True, "prefill_subject": False,
                "prefill_body": True, "attachments_supported": False}
        warnings = ["WhatsApp handoff cannot prefill attachments."]
        if len(url) > req.max_url_length:
            url = f"https://wa.me/{digits}"
            caps = dict(caps, prefill_body=False)
            warnings.append(
                f"The body exceeds the practical URL limit ({req.max_url_length} chars), "
                "so it is not prefilled. Use 'Copy body' and paste it into WhatsApp.")
        return HandoffResult(url, caps, [
            "Confirm the chat and recipient in WhatsApp.",
            "Paste the body if it was not prefilled (Copy body).",
            *manual_common,
        ], warnings)


class TelegramAdapter(ChannelAdapter):
    channel = "telegram"

    def validate_destination(self, raw: str) -> Destination:
        group = _parse_group(raw, "telegram")
        if group:
            return group
        value = raw.strip()
        # t.me deep links
        m = re.fullmatch(r"(?:https?://)?t\.me/(\+[A-Za-z0-9_\-]{5,64}|[A-Za-z][A-Za-z0-9_]{4,31})", value,
                         re.IGNORECASE)
        if m:
            value = "@" + m.group(1) if not m.group(1).startswith("+") else m.group(1)
        if value.startswith("+") and re.fullmatch(r"\+[A-Za-z0-9_\-]{5,64}", value):
            return Destination(raw=raw, normalized=value, kind="invite")
        if value.startswith("@") and re.fullmatch(r"@[A-Za-z][A-Za-z0-9_]{4,31}", value):
            return Destination(raw=raw, normalized=value.lower(), kind="individual")
        raise bad_request(
            f"'{raw}' is not a valid Telegram destination. Use @username (5-32 chars), "
            "a t.me/... link, an invite code (+XXXXXX), or 'group:<name>'",
            field="destination")

    def build_handoff(self, req: HandoffRequest) -> HandoffResult:
        dest = req.destination
        manual_common = [
            "Download every attachment from this page — the handoff link cannot attach files.",
            "Press send inside Telegram. This service never sends anything.",
        ]
        if dest.kind == "individual":
            username = dest.normalized.lstrip("@")
            url = f"https://t.me/{username}?text={_encode(req.body)}"
            caps = {"prefill_recipient": True, "prefill_subject": False,
                    "prefill_body": True, "attachments_supported": False}
            warnings = ["Telegram deep links cannot prefill attachments."]
            if len(url) > req.max_url_length:
                url = f"https://t.me/{username}"
                caps = dict(caps, prefill_body=False)
                warnings.append(
                    f"The body exceeds the practical URL limit ({req.max_url_length} chars), "
                    "so it is not prefilled. Use 'Copy body' and paste it into Telegram.")
            return HandoffResult(url, caps, [
                "Confirm the chat opened for @" + username + ".",
                "Paste the body if it was not prefilled (Copy body).",
                *manual_common,
            ], warnings)
        if dest.kind == "invite":
            invite_url = "https://t.me/" + urllib.parse.quote(dest.normalized, safe="+")
            return HandoffResult(
                handoff_url=invite_url,
                capabilities={"prefill_recipient": False, "prefill_subject": False,
                              "prefill_body": False, "attachments_supported": False},
                manual_actions=[
                    f"Open the invite link and join the chat ({dest.normalized}).",
                    "Paste the message body (use Copy body).",
                    *manual_common,
                ],
                warnings=[
                    "Private invite links open a join dialog; Telegram does not allow "
                    "prefilling text into them. Nothing is sent until you confirm in-app.",
                ],
                extra={"invite_code": dest.normalized},
            )
        # group
        return HandoffResult(
            handoff_url="https://web.telegram.org/",
            capabilities={"prefill_recipient": False, "prefill_subject": False,
                          "prefill_body": False, "attachments_supported": False},
            manual_actions=[
                f"Open Telegram and find the group '{dest.display_name}' yourself.",
                "Paste the message body (use Copy body).",
                *manual_common,
            ],
            warnings=[
                f"Telegram groups have no public deep link unless the group has a public "
                f"username. Group '{dest.display_name}' is shown here but cannot be "
                "preselected or prefilled by this service.",
            ],
            extra={"group_name": dest.display_name},
        )


_REGISTRY: dict[str, ChannelAdapter] = {
    "email": EmailAdapter(),
    "whatsapp": WhatsAppAdapter(),
    "telegram": TelegramAdapter(),
}


def adapter_for(channel: str) -> ChannelAdapter:
    adapter = _REGISTRY.get(channel)
    if adapter is None:
        raise bad_request(
            f"unknown channel {channel!r}; expected one of email, whatsapp, telegram",
            field="channel", allowed=["email", "whatsapp", "telegram"])
    return adapter


def allowed_channels() -> list[str]:
    return sorted(_REGISTRY)
