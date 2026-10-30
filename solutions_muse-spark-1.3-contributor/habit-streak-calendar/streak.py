#!/usr/bin/env python3
"""Habit Streak Calendar — terminal-based streak tracker with GitHub-style calendar.

Produced: 2026-10-29 22:24:56 UTC (2026-10-29 23:24:56 CET local)
Author/Model: Muse Spark 1.3 Contributor (via OpenCode)

Usage:
    python streak.py add "<habit name>"
    python streak.py check "<habit name>" [--date YYYY-MM-DD]
    python streak.py show "<habit name>"
    python streak.py list
    python streak.py remove "<habit name>" [--yes]
    python streak.py about

Data is stored in a plain local JSON file (streaks.json) next to this script:
    {"habits": {"Read 10 pages": ["2026-10-17", "2026-10-18", ...]}}

Standard library only. No network, no third-party packages.
"""

import argparse
import datetime
import json
import os
import sys

DATA_FILENAME = "streaks.json"
FILLED_GLYPH = "\u25a0"  # ■
EMPTY_GLYPH = "\u00b7"   # ·
WEEKS_SHOWN = 12

PRODUCED_AT = "2026-10-29 22:24:56 UTC"
PRODUCED_BY = "Muse Spark 1.3 Contributor (via OpenCode)"


def data_path():
    """JSON file lives next to this script (created on first write)."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, DATA_FILENAME)


def fail(message):
    """Print a clear error (to both streams for visibility) and exit non-zero."""
    text = "Error: {}".format(message)
    print(text, file=sys.stderr)
    # Also echo to stdout so output is easy to spot no matter which
    # stream the caller captures; combined captures will simply see it twice.
    if sys.stderr is not sys.stdout:
        print(text)
    sys.exit(1)


def info(message):
    print(message)


def load_data():
    """Load habit data. Missing/empty file -> empty dataset (graceful).

    Invalid JSON or corrupt structure -> clear error, exit(1), never overwrite.
    """
    path = data_path()
    if not os.path.exists(path):
        return {"habits": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
    except OSError as exc:
        fail("could not read {}: {}".format(path, exc))
    if raw.strip() == "":
        return {"habits": {}}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        fail("{} contains invalid JSON ({}). Fix or delete the file; "
             "it was NOT overwritten.".format(DATA_FILENAME, exc))
    if not isinstance(data, dict):
        fail("{} is corrupt: top-level JSON must be an object. "
             "File was NOT overwritten.".format(DATA_FILENAME))
    habits = data.get("habits", {})
    if not isinstance(habits, dict):
        fail("{} is corrupt: \"habits\" must be an object mapping "
             "habit names to date lists. File was NOT overwritten.".format(DATA_FILENAME))
    for name, dates in habits.items():
        if not isinstance(dates, list):
            fail("{} is corrupt: habit {!r} must map to a list of "
                 "YYYY-MM-DD strings. File was NOT overwritten.".format(
                     DATA_FILENAME, name))
    return {"habits": habits}


def save_data(data):
    path = data_path()
    tmp = path + ".tmp"
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def parse_iso_date(s):
    try:
        return datetime.date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def coerce_dates(dates_list):
    """Return (sorted_unique_dates, iso_set) skipping malformed entries."""
    seen = set()
    for item in dates_list:
        if not isinstance(item, str):
            continue
        d = parse_iso_date(item.strip())
        if d is not None:
            seen.add(d)
    ordered = sorted(seen)
    iso_set = set(d.isoformat() for d in seen)
    return ordered, iso_set


def compute_stats(dates_list, today=None):
    """Return (total, current_streak, longest_streak).

    current = consecutive days ending today or yesterday (0 if neither).
    longest = longest run of consecutive days anywhere in the data.
    """
    if today is None:
        today = datetime.date.today()
    ordered, iso_set_dates = coerce_dates(dates_list)
    date_set = set(ordered)
    total = len(ordered)
    if total == 0:
        return 0, 0, 0
    # Longest streak.
    longest = 1
    run = 1
    for prev, cur in zip(ordered, ordered[1:]):
        if (cur - prev).days == 1:
            run += 1
            longest = max(longest, run)
        else:
            run = 1
    # Current streak anchored at today, else yesterday.
    if today in date_set:
        cursor = today
    elif (today - datetime.timedelta(days=1)) in date_set:
        cursor = today - datetime.timedelta(days=1)
    else:
        return total, 0, longest
    current = 0
    while cursor in date_set:
        current += 1
        cursor -= datetime.timedelta(days=1)
    return total, current, longest


def plural(n, singular, plural_word=None):
    if plural_word is None:
        plural_word = singular + "s"
    return "{} {}".format(n, singular if n == 1 else plural_word)


def use_color():
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


def colorize(text, code, enabled):
    if not enabled:
        return text
    return "\033[{}m{}\033[0m".format(code, text)


def build_calendar_cells(iso_set, today):
    """Return (start_monday, grid) where grid[row][col] is the day or None.

    grid covers WEEKS_SHOWN Monday-start weeks ending with the current week.
    Days after today (future padding) map to None upstream; we keep the date
    here and let the renderer blank it.
    """
    monday_this_week = today - datetime.timedelta(days=today.weekday())
    start_monday = monday_this_week - datetime.timedelta(weeks=WEEKS_SHOWN - 1)
    return start_monday


def render_calendar(habit_name, dates_list, today=None):
    if today is None:
        today = datetime.date.today()
    _ordered, iso_set = coerce_dates(dates_list)
    start_monday = build_calendar_cells(iso_set, today)
    end_sunday = start_monday + datetime.timedelta(days=WEEKS_SHOWN * 7 - 1)
    colored = use_color()
    filled = colorize(FILLED_GLYPH, "32;1", colored)  # bright green
    empty = colorize(EMPTY_GLYPH, "2", colored)       # dim

    labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    lines = []
    lines.append("{} \u2014 last {} weeks".format(habit_name, WEEKS_SHOWN))
    lines.append("{} .. {} (today {})".format(
        start_monday.isoformat(), end_sunday.isoformat(), today.isoformat()))
    for row in range(7):
        cells = []
        for col in range(WEEKS_SHOWN):
            day = start_monday + datetime.timedelta(days=col * 7 + row)
            if day > today:
                cells.append(" ")
            elif day.isoformat() in iso_set:
                cells.append(filled)
            else:
                cells.append(empty)
        lines.append("{}  {}".format(labels[row], " ".join(cells)))
    lines.append("")
    lines.append("Legend: {} done   {} missed   (blank = future)".format(
        colorize(FILLED_GLYPH, "32;1", colored),
        colorize(EMPTY_GLYPH, "2", colored)))
    return "\n".join(lines)


# ------------------------------- commands -------------------------------

def cmd_add(name):
    name = (name or "").strip()
    if not name:
        fail("habit name must not be empty.")
    data = load_data()
    habits = data["habits"]
    if name in habits:
        info("Habit \"{}\" already exists \u2014 nothing changed.".format(name))
        return 0
    habits[name] = []
    save_data(data)
    info("\u2714 Habit \"{}\" created.".format(name))
    return 0


def cmd_check(name, date_str=None):
    name = (name or "").strip()
    if not name:
        fail("habit name must not be empty.")
    data = load_data()
    habits = data["habits"]
    if name not in habits:
        fail("habit \"{}\" does not exist. Create it first with: "
             "python streak.py add \"{}\"".format(name, name))
    if date_str is not None:
        target = parse_iso_date(date_str.strip())
        if target is None:
            fail("--date must be YYYY-MM-DD (got {!r}).".format(date_str))
        today = datetime.date.today()
        if target > today:
            fail("cannot check in for a future date ({} > today {}).".format(
                target.isoformat(), today.isoformat()))
    else:
        target = datetime.date.today()
    iso = target.isoformat()
    dates = habits[name]
    if iso in dates:
        total, current, _longest = compute_stats(dates, datetime.date.today())
        info("Already checked in \"{}\" for {} \u2014 no duplicate added. "
             "Current streak: {}.".format(name, iso, plural(current, "day")))
        return 0
    dates.append(iso)
    # Keep file tidy: sorted, de-duplicated.
    _ordered, iso_set = coerce_dates(dates)
    habits[name] = sorted(iso_set)
    save_data(data)
    total, current, _longest = compute_stats(habits[name], datetime.date.today())
    info("\u2714 Checked in \"{}\" for {}. Current streak: {}.".format(
        name, iso, plural(current, "day")))
    return 0


def cmd_show(name):
    name = (name or "").strip()
    if not name:
        fail("habit name must not be empty.")
    data = load_data()
    habits = data["habits"]
    if not habits:
        info("No habits yet. Create one with: python streak.py add \"<habit>\"")
        return 0
    if name not in habits:
        fail("habit \"{}\" does not exist. See all habits with: "
             "python streak.py list".format(name))
    today = datetime.date.today()
    dates = habits[name]
    print(render_calendar(name, dates, today))
    print("")
    total, current, longest = compute_stats(dates, today)
    total_word = "check-in" if total == 1 else "check-ins"
    print("Total: {} {}   Current streak: {}   Longest streak: {}".format(
        total, total_word, plural(current, "day"), plural(longest, "day")))
    return 0


def cmd_list():
    data = load_data()
    habits = data["habits"]
    if not habits:
        info("No habits yet. Create one with: python streak.py add \"<habit>\"")
        return 0
    today = datetime.date.today()
    info("Habits:")
    for name in sorted(habits):
        _total, current, _longest = compute_stats(habits[name], today)
        total = len(set(habits[name]))
        info("  - {}: current streak {} ({} total)".format(
            name, plural(current, "day"), plural(total, "check-in", "check-ins")))
    return 0


def cmd_remove(name, assume_yes=False):
    name = (name or "").strip()
    if not name:
        fail("habit name must not be empty.")
    data = load_data()
    habits = data["habits"]
    if name not in habits:
        fail("habit \"{}\" does not exist. Nothing removed.".format(name))
    if not assume_yes:
        try:
            answer = input("Remove habit \"{}\" ({} check-ins)? [y/N]: ".format(
                name, len(habits[name])))
        except (EOFError, KeyboardInterrupt):
            print("")
            info("Cancelled \u2014 nothing removed.")
            return 1
        if answer.strip().lower() not in ("y", "yes"):
            info("Cancelled \u2014 nothing removed.")
            return 1
    del habits[name]
    save_data(data)
    info("Removed habit \"{}\".".format(name))
    return 0


def cmd_about():
    info("Habit Streak Calendar")
    info("Produced: {} ".format(PRODUCED_AT))
    info("Author/model: {}".format(PRODUCED_BY))
    info("Storage: local JSON file {} next to streak.py (stdlib only).".format(DATA_FILENAME))
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        prog="streak.py",
        description="Terminal habit streak tracker (local JSON, stdlib only).")
    sub = p.add_subparsers(dest="command")

    a = sub.add_parser("add", help="create a new habit")
    a.add_argument("habit", help="habit name")

    c = sub.add_parser("check", help="record today (or --date) as completed")
    c.add_argument("habit", help="habit name")
    c.add_argument("--date", default=None,
                   help="backfill a date as YYYY-MM-DD (default: today)")

    s = sub.add_parser("show", help="show 12-week calendar + stats")
    s.add_argument("habit", help="habit name")

    sub.add_parser("list", help="list every habit with its current streak")

    r = sub.add_parser("remove", help="delete a habit (with confirmation)")
    r.add_argument("habit", help="habit name")
    r.add_argument("--yes", "-y", action="store_true",
                   help="skip confirmation prompt")

    sub.add_parser("about", help="show when/by whom this solution was produced")
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    if args.command == "add":
        return cmd_add(args.habit)
    if args.command == "check":
        return cmd_check(args.habit, args.date)
    if args.command == "show":
        return cmd_show(args.habit)
    if args.command == "list":
        return cmd_list()
    if args.command == "remove":
        return cmd_remove(args.habit, args.yes)
    if args.command == "about":
        return cmd_about()
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
