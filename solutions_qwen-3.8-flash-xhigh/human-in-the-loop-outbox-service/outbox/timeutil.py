"""UTC ISO 8601 timestamp helpers.

All timestamps are stored and exchanged in UTC with a trailing ``Z`` and
millisecond precision, e.g. ``2026-11-06T23:42:01.234Z``. The canonical form
sorts lexicographically, which the service relies on for SQL comparisons.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone

from .errors import bad_request

CANONICAL_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    """Serialize an aware datetime to canonical UTC ISO 8601 with Z."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def now_iso() -> str:
    return iso(now_utc())


def parse_iso(value: str, *, field_name: str = "timestamp") -> datetime:
    """Parse ISO 8601 input. Bare dates become start-of-day UTC.

    Raises a 400-class ApiError for anything unparseable or naive.
    """
    if not isinstance(value, str) or not value.strip():
        raise bad_request(f"{field_name} must be a non-empty string", field=field_name)
    raw = value.strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            dt = datetime.combine(date.fromisoformat(raw), datetime.min.time(), tzinfo=timezone.utc)
            return dt
        candidate = raw
        if candidate.endswith("Z") or candidate.endswith("z"):
            candidate = candidate[:-1] + "+00:00"
        dt = datetime.fromisoformat(candidate)
    except ValueError:
        raise bad_request(
            f"{field_name} is not a valid ISO 8601 timestamp: {value!r}", field=field_name
        ) from None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_canonical(value: str, *, field_name: str = "timestamp") -> str:
    return iso(parse_iso(value, field_name=field_name))


def end_of_day_iso(value: str, *, field_name: str = "timestamp") -> str:
    """For a bare-date upper-bound filter, include the whole day."""
    dt = parse_iso(value, field_name=field_name)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
        dt = dt.replace(hour=23, minute=59, second=59, microsecond=999000)
    return iso(dt)
