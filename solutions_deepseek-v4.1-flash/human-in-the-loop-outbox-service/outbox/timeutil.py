"""UTC timestamp helpers. Everything internal is fixed-width UTC ISO-8601."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from .errors import ValidationError

ISO_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc)
    # Fixed millisecond precision keeps lexicographic sorting/comparison sane.
    return value.strftime("%Y-%m-%dT%H:%M:%S.") + f"{value.microsecond // 1000:03d}Z"


def now_iso() -> str:
    return to_iso(utcnow())


def parse_iso(value: str, field: str = "timestamp") -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} must be an ISO 8601 timestamp string.")
    raw = value.strip()
    candidate = raw
    if candidate.endswith("Z") or candidate.endswith("z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValidationError(f"{field} must be a valid ISO 8601 timestamp.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_future_iso(value: str, field: str = "expires_at") -> str:
    parsed = parse_iso(value, field)
    if parsed <= utcnow():
        raise ValidationError(f"{field} must be in the future.")
    return to_iso(parsed)


def parse_filter_bound(value: str, field: str, end_of_day: bool = False) -> str:
    """Parse an ISO timestamp or date used by list filters into canonical form."""
    raw = value.strip()
    try:
        if len(raw) == 10:
            d = date.fromisoformat(raw)
            t = time(23, 59, 59, 999000) if end_of_day else time(0, 0, 0, 0)
            return to_iso(datetime.combine(d, t, tzinfo=timezone.utc))
    except ValueError as exc:
        raise ValidationError(f"{field} must be a valid ISO date or timestamp.") from exc
    return to_iso(parse_iso(raw, field))


def expires_at_from_ttl(ttl_seconds: int) -> str:
    try:
        return to_iso(utcnow() + timedelta(seconds=ttl_seconds))
    except (OverflowError, ValueError) as exc:
        raise ValidationError("ttl_seconds is too large to represent.") from exc
