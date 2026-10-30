# Habit Streak Calendar

A terminal habit tracker in a single Python file. Check in once a day, then see
the last 12 weeks as a GitHub-style grid with current and longest streak stats.
Standard library only, local JSON only, no account and no network.

```bash
python3 streak.py add "Read 10 pages"
python3 streak.py check "Read 10 pages"
python3 streak.py show "Read 10 pages"
python3 streak.py list
```

On the first write the program creates `streaks.json` next to `streak.py`. The
file is yours: pretty-printed, sorted, and easy to edit by hand.

## Commands

| Command | What it does |
|---------|--------------|
| `add "<habit>"` | Create a habit. A duplicate name prints a note and changes nothing. |
| `check "<habit>"` | Record today (local calendar date). Running it twice the same day is a no-op. |
| `check "<habit>" --date YYYY-MM-DD` | Backfill an earlier day (future dates are refused). |
| `show "<habit>"` | Print the 12-week calendar, total, current streak, longest streak. |
| `list` | Every habit with its current streak and check-in count. |
| `remove "<habit>"` | Delete a habit after a `y/N` prompt; `--yes` skips the prompt. |
| `about` | Print the build sign-off (produced date/time and author). |
| `--file PATH` | Use a different JSON file (must come before the subcommand). |

## Example session

Captured on 2026-10-29 with Python 3.12.3:

```text
$ python3 streak.py add "Read 10 pages"
✔ Habit "Read 10 pages" created.
$ python3 streak.py check "Read 10 pages"
✔ Checked in "Read 10 pages" for 2026-10-29. Current streak: 1 day.
$ python3 streak.py check "Read 10 pages"
✔ Already checked in "Read 10 pages" for 2026-10-29 — no duplicate added. Current streak: 1 day.
$ python3 streak.py show "Read 10 pages"
Read 10 pages — last 12 weeks
     Aug     Sep     Oct
Mon  · · · · · · · · · · · ·
Tue  · · · · · · · · · · · ·
Wed  · · · · · · · · · · · ·
Thu  · · · · · · · · · · · ■
Fri  · · · · · · · · · · ·
Sat  · · · · · · · · · · ·
Sun  · · · · · · · · · · ·

Total: 1 check-in   Current streak: 1 day   Longest streak: 1 day
Produced 2026-10-29 22:55 CET by DeepSeek V4.1 Flash (opencode)
```

With the challenge's sample file
(`2026-10-17`, `2026-10-18`, `2026-10-29`) the calendar and stats read:

```text
Total: 3 check-ins   Current streak: 1 day   Longest streak: 2 days
```

And a two-habit overview:

```text
Habits — 2026-10-29

  Morning run     current streak: 2 days  (2 check-ins)
  Read 10 pages   current streak: 2 days  (4 check-ins)
```

## Calendar layout

- **12 columns** are the 12 most recent Monday-start weeks, ending with the
  week that contains today.
- **7 rows** are Mon–Sun. The month labels above the columns help with
  orientation.
- `■` is a checked day, `·` is an unchecked day, and a **blank** cell is a day
  in the future. Trailing blanks are kept so all 84 positions line up.
- Grouping and glyphs are plain text by default when stdout is not a
  terminal. On a TTY the filled squares are green and empty ones are dim;
  `NO_COLOR=1` disables that.

## How streaks are counted

All dates are local calendar dates (`YYYY-MM-DD`), one entry per day at most.

- **Total**: number of distinct recorded dates.
- **Current streak**: consecutive days ending today *or* yesterday, so a
  check-in yesterday still shows a live streak before today's check-in.
- **Longest streak**: the longest run of consecutive days ever recorded.

## Data format

```json
{
  "habits": {
    "Read 10 pages": [
      "2026-10-17",
      "2026-10-18",
      "2026-10-29"
    ]
  }
}
```

Writes go through a temporary file in the same directory followed by an atomic
replace, so an interrupted save cannot leave half a JSON document behind. A
file with duplicate or unsorted dates is normalized on the next save.

If the file is missing or empty, `list`/`show` print a friendly hint instead of
a traceback. If it contains invalid JSON or an invalid date, the command exits
with a clear error and **leaves the file byte-for-byte untouched** — nothing is
ever overwritten on a parse failure.

## Verification

From this directory:

```bash
python3 - <<'EOF'
import streak
from datetime import date, timedelta

today = date(2026, 10, 29)

# Challenge sample: current 1, longest 2.
sample = {date(2026, 10, 17), date(2026, 10, 18), today}
assert streak.stats_for(sample, today) == (3, 1, 2)

# A streak ending yesterday still counts as current.
assert streak.stats_for({today - timedelta(days=1), today - timedelta(days=2)}, today) == (2, 2, 2)

# Empty habit.
assert streak.stats_for(set(), today) == (0, 0, 0)

# 7 rows x 12 Monday-start columns; future cells are blank.
text = streak.calendar_for("Read 10 pages", sample, today, color=False)
rows = [line for line in text.splitlines() if line[:3] in streak.DAY_NAMES]
assert len(rows) == 7
assert all(len(row[5::2]) == 12 for row in rows)
assert rows[3][5::2][-1] == streak.FILLED  # today (Thu) is in the last column
assert rows[4][5::2][-1] == " "            # tomorrow (Fri) is blank

print("all checks passed")
EOF
```

A quick end-to-end smoke test that never touches the shipped directory:

```bash
tmp="$(mktemp -d)"
python3 streak.py --file "$tmp/s.json" add "Test"
python3 streak.py --file "$tmp/s.json" check "Test"
python3 streak.py --file "$tmp/s.json" check "Test"   # idempotent
python3 streak.py --file "$tmp/s.json" show "Test"
python3 streak.py --file "$tmp/s.json" list
rm -rf "$tmp"
```

## Sign-off

- **Produced:** 2026-10-29 22:55 CET
- **Author:** DeepSeek V4.1 Flash (opencode)

The same sign-off is in the header comment of `streak.py`, in `show`'s footer,
and via `python3 streak.py about`.
