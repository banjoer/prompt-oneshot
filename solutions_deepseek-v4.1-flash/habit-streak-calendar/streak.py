#!/usr/bin/env python3
"""
Habit Streak Calendar
=====================
A single-file, standard-library-only habit tracker for the terminal. Check in
once a day, then see the last 12 weeks as a week-aligned GitHub-style grid.

Produced: 2026-10-29 22:55 CET
Author:   DeepSeek V4.1 Flash (opencode)

Usage:
    python streak.py add "Read 10 pages"
    python streak.py check "Read 10 pages"
    python streak.py check "Read 10 pages" --date 2026-10-25
    python streak.py show "Read 10 pages"
    python streak.py list
    python streak.py remove "Read 10 pages"
    python streak.py about

Data lives in streaks.json next to this script (override with --file PATH).
The file is created on the first write; nothing is sent over the network.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Sign-off / identity
# ---------------------------------------------------------------------------
APP_NAME = "Habit Streak Calendar"
PRODUCED_AT = "2026-10-29 22:55 CET"
AUTHOR = "DeepSeek V4.1 Flash (opencode)"

# ---------------------------------------------------------------------------
# Layout & glyphs
# ---------------------------------------------------------------------------
DATA_FILENAME = "streaks.json"
WEEKS = 12
FILLED = "■"
EMPTY = "·"
LABEL_WIDTH = 5  # "Mon" plus two spaces
DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MONTH_NAMES = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

DIM = "\x1b[2m"
GREEN = "\x1b[32m"
RESET = "\x1b[0m"


class DataError(Exception):
    """A readable problem with the data file (never overwrite in this case)."""


# ---------------------------------------------------------------------------
# Data file handling
# ---------------------------------------------------------------------------
def data_path(explicit: str | None = None) -> Path:
    """Return the JSON path, defaulting to the directory holding this script."""
    if explicit:
        return Path(explicit).expanduser()
    return Path(__file__).resolve().parent / DATA_FILENAME


def load_habits(path: Path) -> dict[str, set[date]]:
    """Load and validate the JSON file.

    A missing or empty file yields an empty habit map. Malformed content raises
    DataError so callers can refuse to write anything over the user's data.
    """
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DataError(f"could not read {path}: {exc.strerror or exc}") from exc

    if not raw.strip():
        return {}

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DataError(
            f"{path} is not valid JSON (line {exc.lineno}, column {exc.colno}: "
            f"{exc.msg}). The file has been left untouched."
        ) from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("habits"), dict):
        if payload == {}:
            # A bare "{}" is an empty file in spirit; treat it as no habits.
            return {}
        raise DataError(
            f'{path} does not look like a streak file: expected an object with a '
            f'"habits" object. The file has been left untouched.'
        )

    habits: dict[str, set[date]] = {}
    for name, entries in payload["habits"].items():
        if not isinstance(name, str) or not isinstance(entries, list):
            raise DataError(
                f'Oops: habit "{name}" in {path} is not stored as a list of dates. '
                f"The file has been left untouched."
            )
        days: set[date] = set()
        for value in entries:
            if not isinstance(value, str) or not _looks_like_date(value):
                raise DataError(
                    f'Oops: habit "{name}" in {path} contains an invalid date '
                    f"({value!r}). Expected YYYY-MM-DD. The file has been left untouched."
                )
            try:
                days.add(date.fromisoformat(value))
            except ValueError as exc:
                raise DataError(
                    f'Oops: habit "{name}" in {path} contains an invalid calendar '
                    f"date ({value!r}). The file has been left untouched."
                ) from exc
        habits[name] = days
    return habits


def save_habits(path: Path, habits: dict[str, set[date]]) -> None:
    """Atomically write the habit map as pretty-printed JSON."""
    payload = {
        "habits": {
            name: sorted(day.isoformat() for day in days)
            for name, days in sorted(habits.items())
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        prefix=".streaks-", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Dates & statistics
# ---------------------------------------------------------------------------
def _looks_like_date(value: str) -> bool:
    return bool(ISO_DATE_RE.match(value))


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" + ("" if count == 1 else "s")


def _days(count: int) -> str:
    return _plural(count, "day")


def stats_for(days: set[date], today: date) -> tuple[int, int, int]:
    """Return (total, current streak, longest streak).

    The current streak may end today or yesterday, so a habit checked in
    yesterday but not yet today still shows its live streak.
    """
    total = len(days)

    anchor: date | None = None
    if today in days:
        anchor = today
    elif (today - timedelta(days=1)) in days:
        anchor = today - timedelta(days=1)

    current = 0
    while anchor is not None and anchor in days:
        current += 1
        anchor -= timedelta(days=1)

    longest = 0
    run = 0
    previous: date | None = None
    for day in sorted(days):
        run = run + 1 if previous is not None and day == previous + timedelta(days=1) else 1
        if run > longest:
            longest = run
        previous = day
    return total, current, longest


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def _paint(text: str, code: str, enabled: bool) -> str:
    return f"{code}{text}{RESET}" if enabled else text


def _color_enabled(stream) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


def _month_row(first_monday: date) -> str:
    """Tiny month axis above the columns; one label per month change."""
    cells = [" "] * (LABEL_WIDTH + WEEKS * 2 + 3)
    previous_month: int | None = None
    for column in range(WEEKS):
        monday = first_monday + timedelta(weeks=column)
        if monday.month != previous_month:
            label = MONTH_NAMES[monday.month - 1]
            start = LABEL_WIDTH + column * 2
            cells[start:start + len(label)] = label
            previous_month = monday.month
    return "".join(cells).rstrip()


def calendar_for(
    name: str, days: set[date], today: date, color: bool = False
) -> str:
    """Build the 7-row x 12-column Monday-start calendar plus stats."""
    current_monday = today - timedelta(days=today.weekday())
    first_monday = current_monday - timedelta(weeks=WEEKS - 1)

    lines = [f"{name} — last {WEEKS} weeks", _month_row(first_monday)]

    for row in range(7):
        cells = []
        for column in range(WEEKS):
            day = first_monday + timedelta(days=column * 7 + row)
            if day > today:
                cells.append(" ")  # blank padding for the future
            elif day in days:
                cells.append(_paint(FILLED, GREEN, color))
            else:
                cells.append(_paint(EMPTY, DIM, color))
        # Keep all 12 cells, including trailing blanks for the future, so
        # every row lines up to the same width.
        lines.append(f"{DAY_NAMES[row]:<3}  " + " ".join(cells))

    total, current, longest = stats_for(days, today)
    lines.append("")
    lines.append(
        f"Total: {_plural(total, 'check-in')}   "
        f"Current streak: {_days(current)}   "
        f"Longest streak: {_days(longest)}"
    )
    lines.append(_paint(f"Produced {PRODUCED_AT} by {AUTHOR}", DIM, color))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------
def _clean_name(raw: str) -> str | None:
    name = raw.strip()
    return name or None


def _empty_hint() -> str:
    return (
        "No habits yet. Create one with:\n"
        '  python streak.py add "<habit name>"'
    )


def _parse_check_date(raw: str | None) -> date:
    if raw is None:
        return date.today()
    if not _looks_like_date(raw):
        raise ValueError(f'"{raw}" is not a date in YYYY-MM-DD form.')
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f'"{raw}" is not a real calendar date.') from exc


def cmd_add(args, path: Path, habits: dict[str, set[date]]) -> int:
    name = _clean_name(args.habit)
    if name is None:
        print("Error: the habit name cannot be empty.", file=sys.stderr)
        return 1
    if name in habits:
        print(f'ℹ Habit "{name}" already exists — nothing changed.')
        return 0

    habits[name] = set()
    try:
        save_habits(path, habits)
    except OSError as exc:
        print(f"Error: could not write {path}: {exc.strerror or exc}", file=sys.stderr)
        return 1
    print(f'✔ Habit "{name}" created.')
    return 0


def cmd_check(args, path: Path, habits: dict[str, set[date]]) -> int:
    name = _clean_name(args.habit)
    if name is None:
        print("Error: the habit name cannot be empty.", file=sys.stderr)
        return 1
    if name not in habits:
        print(f'Error: habit "{name}" not found.', file=sys.stderr)
        if habits:
            print("Run `python streak.py list` to see your habits.", file=sys.stderr)
        else:
            print(_empty_hint(), file=sys.stderr)
        return 1

    try:
        target = _parse_check_date(args.date)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if target > date.today():
        print("Error: you cannot check in for a future date.", file=sys.stderr)
        return 1

    days = habits[name]
    if target in days:
        _, current, _ = stats_for(days, date.today())
        print(
            f'✔ Already checked in "{name}" for {target.isoformat()} — '
            f"no duplicate added. Current streak: {_days(current)}."
        )
        return 0

    days.add(target)
    try:
        save_habits(path, habits)
    except OSError as exc:
        print(f"Error: could not write {path}: {exc.strerror or exc}", file=sys.stderr)
        return 1
    _, current, _ = stats_for(days, date.today())
    print(
        f'✔ Checked in "{name}" for {target.isoformat()}. '
        f"Current streak: {_days(current)}."
    )
    return 0


def cmd_show(args, path: Path, habits: dict[str, set[date]]) -> int:
    name = _clean_name(args.habit)
    if name is None:
        print("Error: the habit name cannot be empty.", file=sys.stderr)
        return 1
    if name not in habits:
        print(f'Error: habit "{name}" not found.', file=sys.stderr)
        if habits:
            print("Run `python streak.py list` to see your habits.", file=sys.stderr)
        else:
            print(_empty_hint(), file=sys.stderr)
        return 1

    print(calendar_for(name, habits[name], date.today(), _color_enabled(sys.stdout)))
    return 0


def cmd_list(args, path: Path, habits: dict[str, set[date]]) -> int:
    if not habits:
        print(_empty_hint())
        return 0

    today = date.today()
    names = sorted(habits, key=str.casefold)
    name_width = max(len(name) for name in names)
    color = _color_enabled(sys.stdout)

    print(f"Habits — {today.isoformat()}")
    print()
    for name in names:
        total, current, _ = stats_for(habits[name], today)
        # Pad before colouring: ANSI escapes would otherwise count as width.
        streak = _paint(f"{_days(current):<7}", GREEN, color and current > 0)
        print(
            f"  {name:<{name_width}}   current streak: {streak} "
            f"({_plural(total, 'check-in')})"
        )
    return 0


def cmd_remove(args, path: Path, habits: dict[str, set[date]]) -> int:
    name = _clean_name(args.habit)
    if name is None:
        print("Error: the habit name cannot be empty.", file=sys.stderr)
        return 1
    if name not in habits:
        print(f'Error: habit "{name}" not found.', file=sys.stderr)
        return 1

    count = len(habits[name])
    if not args.yes:
        try:
            answer = input(
                f'Remove "{name}" and {_plural(count, "check-in")}? [y/N] '
            )
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled — nothing changed.")
            return 0
        if answer.strip().lower() not in ("y", "yes"):
            print("Cancelled — nothing changed.")
            return 0

    del habits[name]
    try:
        save_habits(path, habits)
    except OSError as exc:
        print(f"Error: could not write {path}: {exc.strerror or exc}", file=sys.stderr)
        return 1
    print(f'✔ Removed "{name}".')
    return 0


def cmd_about(args, path: Path) -> int:
    print(APP_NAME)
    print("-" * len(APP_NAME))
    print(f"Produced:  {PRODUCED_AT}")
    print(f"Author:    {AUTHOR}")
    print(f"Data file: {path}")
    print(f"Python:    {sys.version.split()[0]}")
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="streak.py",
        description="Track daily habits and see a 12-week calendar in your terminal.",
    )
    parser.add_argument(
        "--file",
        metavar="PATH",
        help=f"JSON data file to use (default: {DATA_FILENAME} next to streak.py)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="create a new habit")
    add.add_argument("habit", help="habit name")

    check = sub.add_parser("check", help="record today as completed")
    check.add_argument("habit", help="habit name")
    check.add_argument(
        "--date",
        metavar="YYYY-MM-DD",
        help="backfill a past date instead of today",
    )

    show = sub.add_parser("show", help="print the 12-week calendar")
    show.add_argument("habit", help="habit name")

    sub.add_parser("list", help="list habits and current streaks")

    remove = sub.add_parser("remove", help="delete a habit")
    remove.add_argument("habit", help="habit name")
    remove.add_argument(
        "-y", "--yes", action="store_true", help="skip the confirmation prompt"
    )

    sub.add_parser("about", help="show build sign-off")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    path = data_path(args.file)

    if args.command == "about":
        return cmd_about(args, path)

    try:
        habits = load_habits(path)
    except DataError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    handlers = {
        "add": cmd_add,
        "check": cmd_check,
        "show": cmd_show,
        "list": cmd_list,
        "remove": cmd_remove,
    }
    return handlers[args.command](args, path, habits)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        # Piping into `head` should not dump a traceback.
        try:
            sys.stdout.close()
        finally:
            raise SystemExit(0)
