# Habit Streak Calendar

**Difficulty:** Easy  |  **Stack:** Python  |  **Estimated time:** 30–60 minutes

## The Problem
Consistency beats intensity, but motivation fades when progress is invisible. People building habits — reading, exercise, coding practice — need a frictionless way to record "I did it today" and *see* their momentum accumulate. A terminal-based streak tracker gives instant visual feedback (a GitHub-style calendar of filled squares) without opening an app, creating an account, or syncing anything to the cloud. The data lives in a plain local JSON file the user fully owns and can even edit by hand.

## Requirements
1. The app is a single Python file, `streak.py`, runnable with the system Python 3. It manages habits persisted in a local JSON file (e.g. `streaks.json`), created next to the script on first write.
2. `python streak.py add "<habit name>"` creates a new habit. Adding a duplicate name prints a friendly message and changes nothing.
3. `python streak.py check "<habit name>"` records today (local calendar date) as completed. Checking in twice on the same day is idempotent — one entry per day, no duplicates. Checking a non-existent habit prints a clear error.
4. `python streak.py show "<habit name>"` prints a streak calendar for the habit: the most recent 12 weeks rendered as a terminal grid of 7 rows (Mon–Sun) × 12 week columns, with a filled glyph (e.g. `■`) on completed days, an empty glyph (e.g. `·`) on days with no check-in, and blank padding for future days in the current week. Days must be aligned into correct calendar weeks (Monday-start).
5. Below the calendar, `show` prints stats: total check-ins, **current streak** (consecutive days ending today or yesterday), and **longest streak**.
6. `python streak.py list` prints every habit with its current streak, so all progress is visible at a glance.
7. If the JSON file is missing or empty, data-dependent commands behave gracefully (helpful message, no traceback). If the file contains invalid JSON, print a clear error and do **not** overwrite the file.
8. **Sign-off:** the finished solution must display, somewhere easy to spot, the date and time it was produced and the model/author that produced it (e.g. printed by a `python streak.py about` command or as a header line in `show`), plus a header comment in the source.

## Constraints
- Python 3 standard library only (`json`, `datetime`, `sys`, `argparse`, …). No third-party packages, no pip install.
- Local storage only: a single JSON file. No network calls, no external services, no environment variables required.
- All habit dates are local calendar dates in `YYYY-MM-DD` form; no timezone or timestamp logic is needed (beyond the sign-off).
- One source file: `streak.py`. The JSON data file is created by the program, not shipped with it.

## Sample Data / Inputs
Example session (run on 2026-10-29):

```
$ python streak.py add "Read 10 pages"
✔ Habit "Read 10 pages" created.
$ python streak.py check "Read 10 pages"
✔ Checked in "Read 10 pages" for 2026-10-29. Current streak: 1 day.
$ python streak.py show "Read 10 pages"
```

Sketch of the `show` output shape (glyphs may vary; week alignment must not):

```
Read 10 pages — last 12 weeks
Mon  · · · · · · · · · · · ■
Tue  · · · · · · · · · · · ·
Wed  · · · ■ · · · · · · · ■
Thu  · · · · · · · · · · ·
Fri  · · · · · ■ · · · · ■ ■
Sat  · · · · · · · · · · ·
Sun  · · · · · · · · · · ·

Total: 5 check-ins   Current streak: 1 day   Longest streak: 2 days
```

Suggested JSON file shape (implementation may vary, but it must round-trip):

```json
{
  "habits": {
    "Read 10 pages": ["2026-10-17", "2026-10-18", "2026-10-29"]
  }
}
```

## Deliverable
- `streak.py` — the only source file.
- Run commands:
  - `python streak.py add "<habit>"`
  - `python streak.py check "<habit>"`
  - `python streak.py show "<habit>"`
  - `python streak.py list`
  - `python streak.py about` (sign-off)

## Done When
- [ ] `add` → `check` → `show` works end-to-end without ever hand-editing the JSON file.
- [ ] `show` prints a 7-row × 12-column, week-aligned calendar where checked days are visibly distinct from unchecked days, and future days are blank.
- [ ] Current and longest streak figures are correct for a hand-verifiable set of dates (e.g. the sample JSON above: current 1, longest 2 when "today" is 2026-10-29).
- [ ] Running `check` twice on the same day does not create duplicate entries.
- [ ] Running `list` or `show` with no data file yet prints a friendly message, not a traceback.
- [ ] The sign-off (date/time produced + model/author) is visible in the CLI output and in a source header comment.

## Stretch Goals (optional)
- Support `python streak.py check "<habit>" --date 2026-10-25` to backfill a missed day.
- Color the calendar with ANSI escape codes (green filled squares, dim empty ones).
- Add `python streak.py remove "<habit>"` with a confirmation prompt.
