# Habit Streak Calendar — solution

**Prompt:** [`oneshots/habit-streak-calendar.md`](../../oneshots/habit-streak-calendar.md)
**Stack:** Python 3 standard library only · single file `streak.py` · local `streaks.json`

> **Sign-off:** produced **2026-10-30 00:08:01** (local time) by **Qwen3.8 Flash
> (xhigh reasoning) via OpenCode**. The sign-off is a header comment in
> `streak.py` **and** visible in CLI output: via `python3 streak.py about`, as a
> footer line under `show`, and in the `--help` epilog.

## Run it

No dependencies — no pip install, no venv. On this machine `python` isn't on
the PATH, so `python3` everywhere (swap in `python` if your system has it).

```
python3 streak.py add "Read 10 pages"
python3 streak.py check "Read 10 pages"                  # records today
python3 streak.py check "Read 10 pages" --date 2026-10-28  # backfill (stretch)
python3 streak.py show "Read 10 pages"                   # 12-week calendar + stats
python3 streak.py list                                   # all habits at a glance
python3 streak.py remove "Read 10 pages"                 # asks [y/N] first (stretch)
python3 streak.py about                                  # sign-off
```

Habit names with spaces work as normal quoted arguments.

## How it works

- **Storage** — `streaks.json` is created *next to the script* on first write
  (not next to the current working directory), pretty-printed, deduplicated and
  sorted on every save, and safe to hand-edit. Writes go through a temp file +
  `os.replace` so a crash can never leave a half-written file.
- **Calendar** — `show` renders 7 rows (Mon–Sun) × the 12 most recent
  Monday-start week columns. Each row is exactly 28 characters, cells column-
  aligned by construction: `■` completed day, `·` missed day, blank padding for
  days still in the future this week (past weeks are never blank).
- **Streaks** — *current streak* counts consecutive days ending today **or
  yesterday** (forgetting to log today doesn't break the streak until tomorrow);
  *longest streak* is the best run of consecutive days ever recorded. Every
  date-dependent function takes `today` as a parameter, so the spec's
  hand-verifiable example (dates `10-17, 10-18, 10-29`, today `2026-10-29` →
  current 1, longest 2) was tested directly.
- **Failure modes** — missing/empty data file → friendly message, exit 0 (for
  `list`/`show`) or exit 1 (for `check`, which needs an existing habit);
  unknown habit → clear error + `list` hint (+ "did you mean" on case mismatch);
  invalid JSON or unexpected structure → clear error and the file is **never
  overwritten**.
- **Colors (stretch)** — ANSI green `■` / dim `·` are used only when stdout is
  a TTY, and are disabled by `--no-color` or the `NO_COLOR` env var, so piped
  and scripted output stays plain text.

## Example session (verified, run 2026-10-30)

```
$ python3 streak.py add "Read 10 pages"
✔ Habit "Read 10 pages" created. Check in with: python3 streak.py check "Read 10 pages"
$ python3 streak.py check "Read 10 pages"
✔ Checked in "Read 10 pages" for 2026-10-30. Current streak: 1 day.
$ python3 streak.py check "Read 10 pages"          # same day again
✔ "Read 10 pages" was already checked in for 2026-10-30 (one entry per day, no duplicates added).
$ python3 streak.py check "Read 10 pages" --date 2026-10-26   # …and 27, 28, 29, 17, 18
✔ Backfilled "Read 10 pages" for 2026-10-26. Current streak: 1 day.
…
✔ Backfilled "Read 10 pages" for 2026-10-29. Current streak: 5 days.
$ python3 streak.py show "Read 10 pages"
Read 10 pages — last 12 weeks
Mon  · · · · · · · · · · · ■
Tue  · · · · · · · · · · · ■
Wed  · · · · · · · · · · · ■
Thu  · · · · · · · · · · · ■
Fri  · · · · · · · · · · · ■
Sat  · · · · · · · · · ■ ·
Sun  · · · · · · · · · ■ ·
  legend: ■ checked in   · missed day   (blank) upcoming

Total: 7 check-ins   Current streak: 5 days   Longest streak: 5 days
streak.py · produced 2026-10-30 00:08:01 by Qwen3.8 Flash (xhigh reasoning) via OpenCode · data: ./streaks.json
$ python3 streak.py list
3 habits:
  Read 10 pages   current streak: 5 days   total: 7 check-ins
  Exercise        current streak: 1 day   total: 1 check-in
  Meditate        current streak: 0 days   total: 0 check-ins
$ python3 streak.py about
Habit Streak Calendar — streak.py
  produced   : 2026-10-30 00:08:01 (local time)
  model      : Qwen3.8 Flash (xhigh reasoning) via OpenCode
  data file  : /path/to/streaks.json
  commands   : add · check · show · list · remove · about (see --help)
```

Oct 17/18 are Sat/Sun, and the `■`s land in that weekend exactly two columns
before the last one (week of Oct 12); the current week's Fri–Sun padding is
blank because 2026-10-30 is a Friday. Week alignment holds by construction.

## Done-When checklist — all verified

| Check | Result |
| --- | --- |
| `add` → `check` → `show` end-to-end without hand-editing JSON | ✔ ran in isolated temp dirs; data file created next to script, even when invoked from another CWD |
| 7×12 week-aligned calendar, filled vs empty distinct, future blank | ✔ 28-char rows, `■`/`·`/blank placement asserted positionally for Thu 2026-10-29 and Mon 2026-11-02 "today"s |
| Current/longest streaks correct for hand-verifiable dates | ✔ spec example `{10-17, 10-18, 10-29}`, today=2026-10-29 → current **1**, longest **2**; plus streak-through-yesterday and gap cases |
| `check` twice same day → no duplicates | ✔ second run prints "already checked in", file holds one entry |
| `list`/`show` with no data file → friendly, no traceback | ✔ (and `check`/`remove` too) |
| Invalid JSON → clear error, file untouched | ✔ byte-identical after failed `add`/`check`/`show`/`list`; empty file behaves like "no data" |
| Sign-off visible in CLI output **and** source header | ✔ `about`, `show` footer, `--help` epilog, top-of-file comment |

Extra tests: duplicate `add` leaves file untouched; unknown habit errors with
hint; `--date` rejects malformed and future dates; JSON round-trips the spec's
suggested shape; `remove` cancels on `n`/EOF, deletes on `y`/`--yes`. **57/57
checks pass.**

## Stretch goals — all implemented

1. `check --date YYYY-MM-DD` backfill (future dates rejected).
2. ANSI colors (green `■`, dim `·`) on TTYs, with `--no-color` and `NO_COLOR`
   escape hatches.
3. `remove "<habit>"` with a `[y/N]` confirmation prompt (`--yes` to skip).

## Files

- `streak.py` — the entire program (~430 lines, stdlib only).
- `README.md` — this document.

`streaks.json` is generated by the program on first write; it is not shipped.
