#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
#  Habit Streak Calendar — streak.py
#  A frictionless terminal streak tracker: record "I did it today" and watch
#  your momentum accumulate in a GitHub-style 7×12-week calendar grid.
#
#  Sign-off: produced 2026-10-30 00:08:01 (local time) by
#  Qwen3.8 Flash (xhigh reasoning) via OpenCode.
#  The same sign-off is printed by `python3 streak.py about`.
#
#  Python 3 standard library only. All data lives in `streaks.json` next to
#  this script — plain JSON, fully owned by you, safe to hand-edit.
# ─────────────────────────────────────────────────────────────────────────────
"""Terminal habit streak tracker with a week-aligned calendar and streak stats.

Commands
    add    "<habit>"                    create a new habit
    check  "<habit>" [--date YYYY-MM-DD] record a completion (default: today)
    show   "<habit>"                   print the last 12 weeks + streak stats
    list                                every habit with its current streak
    remove "<habit>" [--yes]           delete a habit (asks for confirmation)
    about                               sign-off and file locations

Storage (created on first write, next to this script):
    {"habits": {"Read 10 pages": ["2026-10-17", "2026-10-18"]}}
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

# ── sign-off ────────────────────────────────────────────────────────────────
PRODUCED_AT = "2026-10-30 00:08:01"  # local time this file was produced
PRODUCER = "Qwen3.8 Flash (xhigh reasoning) via OpenCode"

# ── constants ───────────────────────────────────────────────────────────────
DATA_FILE = Path(__file__).resolve().parent / "streaks.json"
WEEKS = 12
DAY_LABELS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
GLYPH_DONE = "■"   # completed day
GLYPH_EMPTY = "·"  # no check-in that day; days after today render blank

USE_COLOR = False  # decided in main(), after argparse


# ── tiny output helpers ─────────────────────────────────────────────────────
def _paint(code: str, text: str) -> str:
    return f"\x1b[{code}m{text}\x1b[0m" if USE_COLOR else text


def green(text: str) -> str:
    return _paint("32", text)


def dim(text: str) -> str:
    return _paint("2", text)


def bold(text: str) -> str:
    return _paint("1", text)


def ok(msg: str) -> None:
    print(f"{green('✔')} {msg}")


def fail(msg: str) -> None:
    print(f"{dim('✖')} {msg}", file=sys.stderr)


def plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


# ── data file: load / save ──────────────────────────────────────────────────
class DataError(Exception):
    """The data file exists but cannot be trusted (bad JSON or structure).

    When raised, the file must be left exactly as it is — never overwritten.
    """


def load_habits() -> dict[str, list[date]] | None:
    """Return habits as {name: [sorted unique dates]}, or None if the file is
    missing or empty (those states are handled gracefully by the commands)."""
    if not DATA_FILE.exists():
        return None
    try:
        raw = DATA_FILE.read_text(encoding="utf-8")
    except OSError as exc:
        raise DataError(f"cannot read {DATA_FILE} ({exc})")
    if not raw.strip():
        return None  # empty file behaves like no data yet
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DataError(
            f"{DATA_FILE} contains invalid JSON (line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}). Repair it by hand or delete it "
            "to start fresh — nothing has been overwritten."
        )
    if not isinstance(doc, dict) or not isinstance(doc.get("habits"), dict):
        raise DataError(
            f'{DATA_FILE} does not look like a streaks file '
            f'(expected an object with a "habits" object). '
            "Nothing has been overwritten."
        )
    habits: dict[str, list[date]] = {}
    for name, entries in doc["habits"].items():
        if not isinstance(name, str) or not isinstance(entries, list):
            raise DataError(
                f"{DATA_FILE} has a malformed habits entry — expected names "
                "mapping to lists of \"YYYY-MM-DD\" strings. Nothing has "
                "been overwritten."
            )
        days: list[date] = []
        for entry in entries:
            parsed = try_parse_date(entry) if isinstance(entry, str) else None
            if parsed is None:
                raise DataError(
                    f"{DATA_FILE}: {name!r} contains a bad date {entry!r} "
                    "(want \"YYYY-MM-DD\"). Nothing has been overwritten."
                )
            days.append(parsed)
        habits[name] = sorted(set(days))
    return habits


def save_habits(habits: dict[str, list[date]]) -> None:
    """Write the data file as pretty, hand-editable JSON (temp file + rename)."""
    doc = {
        "habits": {
            name: [d.isoformat() for d in days] for name, days in habits.items()
        }
    }
    tmp = DATA_FILE.with_name(DATA_FILE.name + ".tmp")
    try:
        tmp.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
        os.replace(tmp, DATA_FILE)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise DataError(f"could not write {DATA_FILE} ({exc})") from exc


def try_parse_date(text: str) -> date | None:
    """Parse a strict YYYY-MM-DD calendar date; None if it doesn't fit."""
    parts = text.split("-")
    if len(parts) != 3 or not (len(parts[0]) == 4 and len(parts[1]) == 2
                               and len(parts[2]) == 2):
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def habit_not_found(name: str, habits: dict) -> str:
    msg = f"no such habit: {name!r}. Run: python3 streak.py list"
    near = [h for h in habits if h.lower() == name.lower()]
    if near:
        msg = f"no such habit: {name!r} (did you mean {near[0]!r}?)"
    return msg


# ── streak math (all date-dependent logic is injectable for easy testing) ───
def current_streak(days: set[date], today: date) -> int:
    """Consecutive check-ins ending today or yesterday (a day not yet checked
    in today has not broken the streak)."""
    if today in days:
        d = today
    elif (today - timedelta(days=1)) in days:
        d = today - timedelta(days=1)
    else:
        return 0
    streak = 0
    while d in days:
        streak += 1
        d -= timedelta(days=1)
    return streak


def longest_streak(days: set[date]) -> int:
    """Longest run of consecutive calendar days ever recorded."""
    best = run = 0
    prev: date | None = None
    for d in sorted(days):
        run = run + 1 if prev and d - prev == timedelta(days=1) else 1
        best = max(best, run)
        prev = d
    return best


# ── rendering ───────────────────────────────────────────────────────────────
def render_calendar(days: set[date], today: date, weeks: int = WEEKS) -> list[str]:
    """7 rows (Mon–Sun) × `weeks` columns, Monday-start, aligned to calendar
    weeks. Filled glyph on done days, empty glyph otherwise, blank padding for
    future days in the current week (and never for the past weeks)."""
    start = today - timedelta(days=today.weekday() + 7 * (weeks - 1))
    lines = []
    for offset, label in enumerate(DAY_LABELS):
        cells = []
        for w in range(weeks):
            d = start + timedelta(weeks=w, days=offset)
            if d > today:
                cells.append(" ")
            elif d in days:
                cells.append(green(GLYPH_DONE))
            else:
                cells.append(dim(GLYPH_EMPTY))
        lines.append(f"{label}  " + " ".join(cells))
    return lines


def stats_line(days: set[date], today: date) -> str:
    return (
        f"Total: {plural(len(days), 'check-in')}   "
        f"Current streak: {plural(current_streak(days, today), 'day')}   "
        f"Longest streak: {plural(longest_streak(days), 'day')}"
    )


# ── commands ────────────────────────────────────────────────────────────────
def cmd_add(name: str) -> int:
    habits = load_habits()
    if habits is None:
        habits = {}
    if name in habits:
        ok(f'Habit "{name}" already exists — nothing changed.')
        return 0
    habits[name] = []
    save_habits(habits)
    ok(f'Habit "{name}" created. Check in with: python3 streak.py check "{name}"')
    return 0


def cmd_check(name: str, explicit: str | None) -> int:
    habits = load_habits()
    if habits is None:
        fail(f"No data file yet. Create a habit first: python3 streak.py add \"{name}\"")
        return 1
    if name not in habits:
        fail(habit_not_found(name, habits))
        return 1
    today = date.today()
    if explicit is None:
        target = today
    else:
        target = try_parse_date(explicit)
        if target is None:
            fail(f"bad --date {explicit!r}: use YYYY-MM-DD, e.g. --date 2026-10-25")
            return 1
        if target > today:
            fail(f"--date {target.isoformat()} is in the future; "
                 "backfilling is for days you already missed.")
            return 1
    days = habits[name]
    if target in days:
        ok(f'"{name}" was already checked in for {target.isoformat()} '
           f"(one entry per day, no duplicates added).")
    else:
        days.append(target)
        days.sort()
        save_habits(habits)
        verb = "Checked in" if target == today else "Backfilled"
        ok(f'{verb} "{name}" for {target.isoformat()}. '
           f"Current streak: {plural(current_streak(set(days), today), 'day')}.")
    return 0


def cmd_show(name: str) -> int:
    habits = load_habits()
    if habits is None:
        ok(f"No data file yet ({DATA_FILE.name} doesn't exist or is empty). "
           f"Add a habit first: python3 streak.py add \"{name}\"")
        return 0
    if name not in habits:
        fail(habit_not_found(name, habits))
        return 1
    today = date.today()
    days = set(habits[name])
    print(bold(f"{name} — last {WEEKS} weeks"))
    print("\n".join(render_calendar(days, today)))
    print(dim(f"  legend: {GLYPH_DONE} checked in   {GLYPH_EMPTY} missed day"
              "   (blank) upcoming"))
    print()
    print(stats_line(days, today))
    print(dim(f"streak.py · produced {PRODUCED_AT} by {PRODUCER} · "
              f"data: {DATA_FILE}"))
    return 0


def cmd_list() -> int:
    habits = load_habits()
    if habits is None:
        ok(f"No data file yet ({DATA_FILE.name} doesn't exist or is empty). "
           "Add your first habit: python3 streak.py add \"Read 10 pages\"")
        return 0
    if not habits:
        ok("No habits yet. Add your first: python3 streak.py add \"Read 10 pages\"")
        return 0
    today = date.today()
    width = max(len(n) for n in habits)
    print(bold(f"{len(habits)} habit{'s' if len(habits) != 1 else ''}:"))
    for name in habits:
        days = set(habits[name])
        cur = current_streak(days, today)
        streak_txt = green(plural(cur, "day")) if cur else dim("0 days")
        print(f"  {name.ljust(width)}   current streak: {streak_txt}"
              f"   total: {plural(len(days), 'check-in')}")
    return 0


def cmd_remove(name: str, assume_yes: bool) -> int:
    habits = load_habits()
    if habits is None:
        fail("No data file yet — there is nothing to remove.")
        return 1
    if name not in habits:
        fail(habit_not_found(name, habits))
        return 1
    count = len(habits[name])
    if not assume_yes:
        prompt = f'Remove "{name}" and its {plural(count, "check-in")}? [y/N] '
        try:
            answer = input(prompt).strip().lower()
        except EOFError:
            answer = ""
        if answer not in ("y", "yes"):
            ok(f'Kept "{name}" — removal cancelled.')
            return 0
    del habits[name]
    save_habits(habits)
    ok(f'Removed "{name}" ({plural(count, "check-in")} deleted).')
    return 0


def cmd_about() -> int:
    print(f"{bold('Habit Streak Calendar')} — streak.py")
    print(f"  produced   : {PRODUCED_AT} (local time)")
    print(f"  model      : {PRODUCER}")
    print(f"  data file  : {DATA_FILE}"
          + (dim("  (not created yet)") if not DATA_FILE.exists() else ""))
    print('  commands   : add · check · show · list · remove · about '
          '(see --help)')
    return 0


# ── CLI ─────────────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="streak.py",
        description="Terminal habit streak tracker with a GitHub-style "
                    "12-week calendar. Data lives in streaks.json next to "
                    "this script.",
        epilog=f"Produced {PRODUCED_AT} by {PRODUCER}. See `about`.",
    )
    parser.add_argument("--no-color", action="store_true",
                        help="disable ANSI colors (colors are only used on a TTY)")
    sub = parser.add_subparsers(dest="command", metavar="command")

    p_add = sub.add_parser("add", help="create a new habit")
    p_add.add_argument("habit", help='habit name, e.g. "Read 10 pages"')

    p_check = sub.add_parser("check", help="record a completion (default: today)")
    p_check.add_argument("habit", help="habit name")
    p_check.add_argument("--date", metavar="YYYY-MM-DD",
                         help="backfill a missed day instead of today")

    p_show = sub.add_parser("show", help="print the last 12 weeks + streak stats")
    p_show.add_argument("habit", help="habit name")

    sub.add_parser("list", help="every habit with its current streak")

    p_remove = sub.add_parser("remove", help="delete a habit (asks to confirm)")
    p_remove.add_argument("habit", help="habit name")
    p_remove.add_argument("-y", "--yes", action="store_true",
                          help="skip the confirmation prompt")

    sub.add_parser("about", help="sign-off: when and by whom this was produced")
    return parser


def main(argv: list[str] | None = None) -> int:
    global USE_COLOR
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    name = getattr(args, "habit", None)
    if isinstance(name, str):
        name = name.strip()
        if not name:
            fail("habit name must not be empty")
            return 1

    USE_COLOR = (
        sys.stdout.isatty()
        and not args.no_color
        and not os.environ.get("NO_COLOR")
        and os.environ.get("TERM", "") != "dumb"
    )

    try:
        if args.command == "add":
            return cmd_add(name)
        if args.command == "check":
            return cmd_check(name, args.date)
        if args.command == "show":
            return cmd_show(name)
        if args.command == "list":
            return cmd_list()
        if args.command == "remove":
            return cmd_remove(name, args.yes)
        if args.command == "about":
            return cmd_about()
    except DataError as exc:
        fail(str(exc))
        return 1
    parser.error(f"unknown command {args.command!r}")  # unreachable
    return 2


if __name__ == "__main__":
    sys.exit(main())
