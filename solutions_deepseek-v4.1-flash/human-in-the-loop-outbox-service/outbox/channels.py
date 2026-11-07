"""Channel adapters: validation, normalization, capabilities and handoff URLs.

Adapters never send anything. They only generate links the human reviewer can
open in their own application, and they are explicit about every limitation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote, urlencode, urlparse

from .errors import ValidationError

EMAIL_RE = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)
PHONE_CHARS_RE = re.compile(r"^[+()\d\s.\-]+$")
TELEGRAM_USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")
TELEGRAM_GROUP_NAME_MAX = 160
DESTINATION_LABEL_MAX = 120
HANDOFF_URL_LIMIT = 1800


@dataclass
class NormalizedDestination:
    channel: str
    destination: str
    normalized: str
    kind: str  # individual | group | invite
    extra: dict[str, Any] = field(default_factory=dict)


class ChannelAdapter:
    channel = ""
    display_name = ""

    def normalize(self, destination: str) -> NormalizedDestination:  # pragma: no cover - interface
        raise NotImplementedError

    def handoff(self, message: dict[str, Any], attachments: list[dict[str, Any]]) -> dict[str, Any]:
        raise NotImplementedError

    def validate_label(self, label: str | None) -> str | None:
        if label is None:
            return None
        if not isinstance(label, str):
            raise ValidationError("destination_label must be a string.")
        cleaned = label.strip()
        if not cleaned:
            raise ValidationError("destination_label must not be empty.")
        if len(cleaned) > DESTINATION_LABEL_MAX:
            raise ValidationError(f"destination_label must be at most {DESTINATION_LABEL_MAX} characters.")
        return cleaned

    @staticmethod
    def _attachment_payload(message_id: str, attachments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "id": a["id"],
                "filename": a["original_filename"],
                "original_filename": a["original_filename"],
                "mime_type": a["mime_type"],
                "size_bytes": a["size_bytes"],
                "uploaded_at": a.get("uploaded_at"),
                "source_type": a.get("source_type"),
                "source_url": a.get("source_url"),
                "download_url": f"/api/messages/{message_id}/attachments/{a['id']}",
            }
            for a in attachments
        ]

    @staticmethod
    def _base_payload(
        message: dict[str, Any],
        normalized: NormalizedDestination,
        attachments: list[dict[str, Any]],
        *,
        handoff_url: str,
        mode: str,
        capabilities: dict[str, bool],
        manual_actions: list[str],
        warnings: list[str],
    ) -> dict[str, Any]:
        body = message.get("body") or ""
        subject = message.get("subject")
        return {
            "message_id": message["id"],
            "channel": message["channel"],
            "destination": message["destination"],
            "normalized_destination": normalized.normalized,
            "destination_kind": normalized.kind,
            "handoff_url": handoff_url,
            "url": handoff_url,
            "mode": mode,
            "capabilities": capabilities,
            "manual_actions": manual_actions,
            "warnings": warnings,
            "subject": subject,
            "body": body,
            "copy": {"subject": subject, "body": body},
            "attachments": ChannelAdapter._attachment_payload(message["id"], attachments),
            "attachments_supported": False,
        }


def _no_capabilities() -> dict[str, bool]:
    return {
        "prefill_recipient": False,
        "prefill_subject": False,
        "prefill_body": False,
        "attachments_supported": False,
    }


def _copy_actions(subject: str | None, body: str) -> list[str]:
    actions = ["Copy the message body."]
    if subject:
        actions.append("Copy the subject line.")
    return actions


class EmailAdapter(ChannelAdapter):
    channel = "email"
    display_name = "Email"

    def normalize(self, destination: str) -> NormalizedDestination:
        if not isinstance(destination, str):
            raise ValidationError("destination must be a string for email.")
        cleaned = destination.strip()
        if not cleaned:
            raise ValidationError("destination (email address) is required.")
        if len(cleaned) > 254:
            raise ValidationError("Email destination is too long (maximum 254 characters).")
        if not EMAIL_RE.match(cleaned):
            raise ValidationError(
                "Invalid email destination. Use a single address such as alex@example.com."
            )
        local, domain = cleaned.rsplit("@", 1)
        if len(local) > 64:
            raise ValidationError("Email local part is too long (maximum 64 characters).")
        normalized = f"{local.lower()}@{domain.lower()}"
        return NormalizedDestination(self.channel, cleaned, normalized, "individual")

    def handoff(self, message: dict[str, Any], attachments: list[dict[str, Any]]) -> dict[str, Any]:
        normalized = self.normalize(message["destination"])
        subject = message.get("subject") or ""
        body = message.get("body") or ""
        warnings: list[str] = []
        manual_actions = [
            "Open the prepared email in your email application.",
            "Review the recipient, subject and body before sending.",
            "Send the message yourself from your email application.",
        ]
        capabilities = {
            "prefill_recipient": True,
            "prefill_subject": bool(subject),
            "prefill_body": True,
            "attachments_supported": False,
        }

        def build(include_subject: bool, include_body: bool) -> str:
            params: list[tuple[str, str]] = []
            if include_subject and subject:
                params.append(("subject", subject))
            if include_body and body:
                params.append(("body", body))
            query = urlencode(params, quote_via=quote, safe="")
            return "mailto:" + quote(normalized.normalized, safe="@") + (f"?{query}" if query else "")

        handoff_url = build(True, True)
        mode = "prefill"
        if len(handoff_url) > HANDOFF_URL_LIMIT:
            warnings.append(
                "The message is too long for a reliable mailto: link. The prepared link "
                "contains the recipient and subject; copy the body manually."
            )
            handoff_url = build(True, False)
            mode = "prefill_trimmed"
            capabilities["prefill_body"] = False
        if len(handoff_url) > HANDOFF_URL_LIMIT:
            warnings.append("Even the subject is too long for the link; only the recipient is prefilled.")
            handoff_url = build(False, False)
            mode = "recipient_only"
            capabilities["prefill_subject"] = False
        if attachments:
            manual_actions.append(
                "Download each attachment below and attach it manually; mailto: links cannot carry attachments."
            )
            warnings.append("Email attachments are not included in the mailto: handoff and must be attached manually.")
        else:
            warnings.append("mailto: does not carry attachments; this message has none.")
        manual_actions.extend(_copy_actions(message.get("subject"), body))
        return self._base_payload(
            message,
            normalized,
            attachments,
            handoff_url=handoff_url,
            mode=mode,
            capabilities=capabilities,
            manual_actions=manual_actions,
            warnings=warnings,
        )


class WhatsAppAdapter(ChannelAdapter):
    channel = "whatsapp"
    display_name = "WhatsApp"

    def normalize(self, destination: str) -> NormalizedDestination:
        if not isinstance(destination, str):
            raise ValidationError("destination must be a string for WhatsApp.")
        cleaned = destination.strip()
        if not cleaned:
            raise ValidationError("destination is required for WhatsApp.")
        if cleaned.lower().startswith("group:"):
            name = cleaned.split(":", 1)[1].strip()
            if not name:
                raise ValidationError("WhatsApp group destination must include a group name, e.g. group:Project Alpha.")
            if len(name) > TELEGRAM_GROUP_NAME_MAX:
                raise ValidationError("WhatsApp group name is too long.")
            normalized = "group:" + " ".join(name.split()).lower()
            return NormalizedDestination(
                self.channel, cleaned, normalized, "group", {"group_name": name}
            )
        if not PHONE_CHARS_RE.match(cleaned):
            raise ValidationError(
                "Invalid WhatsApp destination. Use an international phone number such as "
                "+1 (415) 555-0123, or group:Name for a group."
            )
        digits = re.sub(r"\D", "", cleaned)
        if cleaned.startswith("00"):
            digits = digits[2:]
        if len(digits) < 7 or len(digits) > 15:
            raise ValidationError("WhatsApp phone number must contain 7 to 15 digits (international format).")
        return NormalizedDestination(
            self.channel, cleaned, "+" + digits, "individual", {"digits": digits}
        )

    def handoff(self, message: dict[str, Any], attachments: list[dict[str, Any]]) -> dict[str, Any]:
        normalized = self.normalize(message["destination"])
        body = message.get("body") or ""
        subject = message.get("subject")
        manual_actions: list[str] = []
        warnings: list[str] = []
        if normalized.kind == "group":
            group_name = normalized.extra["group_name"]
            handoff_url = "https://wa.me/"
            capabilities = _no_capabilities()
            warnings.append(
                "WhatsApp group chats cannot be preselected by a link. WhatsApp will open; "
                "you must choose the group and paste the message yourself."
            )
            manual_actions = [
                f"Open WhatsApp and select the group \"{group_name}\".",
                "Paste the copied message body into the group chat.",
                "Download and attach any files manually.",
                "Send the message yourself.",
            ]
            mode = "manual_fallback"
        else:
            digits = normalized.extra["digits"]
            handoff_url = f"https://wa.me/{digits}?text={quote(body, safe='')}"
            capabilities = {
                "prefill_recipient": True,
                "prefill_subject": False,
                "prefill_body": True,
                "attachments_supported": False,
            }
            mode = "prefill"
            if len(handoff_url) > HANDOFF_URL_LIMIT:
                handoff_url = f"https://wa.me/{digits}"
                mode = "manual_fallback"
                capabilities["prefill_body"] = False
                warnings.append(
                    "The body is too long for a reliable wa.me link. The chat opens with the "
                    "recipient selected; copy and paste the body manually."
                )
            manual_actions = [
                "Open WhatsApp with the prepared chat.",
                "Review the recipient before sending.",
                "Paste the copied body if it was not prefilled.",
                "Download and attach any files manually.",
                "Send the message yourself in WhatsApp.",
            ]
        if subject:
            warnings.append("WhatsApp does not support a separate subject line; copy it manually if needed.")
        if attachments:
            manual_actions.append("Download each attachment below and attach it manually in WhatsApp.")
        manual_actions.extend(_copy_actions(subject, body))
        return self._base_payload(
            message,
            normalized,
            attachments,
            handoff_url=handoff_url,
            mode=mode,
            capabilities=capabilities,
            manual_actions=manual_actions,
            warnings=warnings,
        )


class TelegramAdapter(ChannelAdapter):
    channel = "telegram"
    display_name = "Telegram"

    def normalize(self, destination: str) -> NormalizedDestination:
        if not isinstance(destination, str):
            raise ValidationError("destination must be a string for Telegram.")
        cleaned = destination.strip()
        if not cleaned:
            raise ValidationError("destination is required for Telegram.")
        if cleaned.lower().startswith("group:"):
            name = cleaned.split(":", 1)[1].strip()
            if not name:
                raise ValidationError("Telegram group destination must include a name, e.g. group:Ops Room.")
            if len(name) > TELEGRAM_GROUP_NAME_MAX:
                raise ValidationError("Telegram group name is too long.")
            normalized = "group:" + " ".join(name.split()).lower()
            return NormalizedDestination(
                self.channel, cleaned, normalized, "group", {"group_name": name}
            )

        # Accept t.me links (including private invites) and @usernames.
        raw = cleaned
        explicit_form = cleaned.startswith("@")
        if raw.lower().startswith("https://") or raw.lower().startswith("http://"):
            explicit_form = True
            parsed = urlparse(raw)
            host = (parsed.hostname or "").lower()
            if host not in {"t.me", "telegram.me", "www.t.me"}:
                raise ValidationError(
                    "Telegram destination URL must be on t.me or telegram.me."
                )
            path = parsed.path.strip("/")
            if not path:
                raise ValidationError("Telegram destination URL is missing a username or invite token.")
            raw = path
        elif raw.lower().startswith("t.me/"):
            explicit_form = True
            raw = raw[5:]

        if raw.startswith("+"):
            token = raw[1:].strip()
            if not re.match(r"^[A-Za-z0-9_-]{6,64}$", token):
                raise ValidationError("Invalid Telegram private invite token.")
            return NormalizedDestination(
                self.channel,
                cleaned,
                "invite:" + token.lower(),
                "invite",
                {"invite": token, "link": f"https://t.me/+{token}"},
            )
        if raw.lower().startswith("joinchat/"):
            token = raw.split("/", 1)[1].strip()
            if not re.match(r"^[A-Za-z0-9_-]{6,64}$", token):
                raise ValidationError("Invalid Telegram private invite token.")
            return NormalizedDestination(
                self.channel,
                cleaned,
                "invite:" + token.lower(),
                "invite",
                {"invite": token, "link": f"https://t.me/joinchat/{token}"},
            )

        username = raw.lstrip("@")
        if not explicit_form:
            raise ValidationError(
                "Invalid Telegram destination. Use @username, t.me/username, a t.me/+invite link, "
                "or group:Name for a group."
            )
        if not TELEGRAM_USERNAME_RE.match(username):
            raise ValidationError(
                "Invalid Telegram destination. Use @username, t.me/username, a t.me/+invite link, "
                "or group:Name for a group."
            )
        return NormalizedDestination(
            self.channel, cleaned, "@" + username.lower(), "individual", {"username": username}
        )

    def handoff(self, message: dict[str, Any], attachments: list[dict[str, Any]]) -> dict[str, Any]:
        normalized = self.normalize(message["destination"])
        body = message.get("body") or ""
        subject = message.get("subject")
        warnings: list[str] = []
        if normalized.kind == "individual":
            username = normalized.extra["username"]
            handoff_url = f"https://t.me/{username}?text={quote(body, safe='')}"
            capabilities = {
                "prefill_recipient": True,
                "prefill_subject": False,
                "prefill_body": True,
                "attachments_supported": False,
            }
            mode = "prefill"
            if len(handoff_url) > HANDOFF_URL_LIMIT:
                handoff_url = f"https://t.me/{username}"
                capabilities["prefill_body"] = False
                mode = "manual_fallback"
                warnings.append(
                    "The body is too long for a reliable t.me link. The chat opens with the "
                    "recipient selected; copy and paste the body manually."
                )
            warnings.append(
                "Telegram deep-link text prefill depends on the installed client; verify the "
                "message before sending. Links never carry attachments."
            )
            manual_actions = [
                "Open Telegram with the prepared chat.",
                "Review the recipient and prefilled text (if supported by your client).",
                "Paste the copied body if it was not prefilled.",
                "Download and attach any files manually.",
                "Send the message yourself in Telegram.",
            ]
        elif normalized.kind == "invite":
            invite = normalized.extra["invite"]
            if message["destination"].lower().startswith("http"):
                handoff_url = message["destination"].strip()
            else:
                handoff_url = normalized.extra.get("link") or f"https://t.me/+{invite}"
            capabilities = _no_capabilities()
            mode = "manual_fallback"
            warnings.append(
                "Private Telegram invite links cannot preselect a chat or prefill text. The "
                "invite opens; join the group and paste the message manually. No public "
                "username is assumed."
            )
            manual_actions = [
                "Open the private invite link and join the group if you are not already a member.",
                "Select the intended chat shown in this review.",
                "Paste the copied message body into the chat.",
                "Download and attach any files manually.",
                "Send the message yourself in Telegram.",
            ]
        else:
            group_name = normalized.extra["group_name"]
            handoff_url = "https://t.me/"
            capabilities = _no_capabilities()
            mode = "manual_fallback"
            warnings.append(
                "Telegram groups cannot be preselected by a public t.me link. Telegram opens; "
                "select the group and paste the message yourself. No public username is assumed."
            )
            manual_actions = [
                f"Open Telegram and select the group \"{group_name}\".",
                "Paste the copied message body into the group chat.",
                "Download and attach any files manually.",
                "Send the message yourself in Telegram.",
            ]
        if subject:
            warnings.append("Telegram does not support a separate subject line; copy it manually if needed.")
        if attachments:
            manual_actions.append("Download each attachment below and attach it manually in Telegram.")
        manual_actions.extend(_copy_actions(subject, body))
        return self._base_payload(
            message,
            normalized,
            attachments,
            handoff_url=handoff_url,
            mode=mode,
            capabilities=capabilities,
            manual_actions=manual_actions,
            warnings=warnings,
        )


ADAPTERS: dict[str, ChannelAdapter] = {
    "email": EmailAdapter(),
    "whatsapp": WhatsAppAdapter(),
    "telegram": TelegramAdapter(),
}

CHANNELS = tuple(ADAPTERS.keys())


def get_adapter(channel: str) -> ChannelAdapter:
    adapter = ADAPTERS.get(channel)
    if adapter is None:
        raise ValidationError(
            f"Unsupported channel {channel!r}. Expected one of: {', '.join(CHANNELS)}."
        )
    return adapter


def validate_url_reference(url: str) -> str:
    if not isinstance(url, str):
        raise ValidationError("references must be strings containing http(s) URLs.")
    cleaned = url.strip()
    if not cleaned:
        raise ValidationError("Reference URLs must not be empty.")
    if len(cleaned) > 2048:
        raise ValidationError("Reference URL is too long (maximum 2048 characters).")
    parsed = urlparse(cleaned)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ValidationError("Reference URLs must be absolute http(s) URLs.")
    return cleaned
