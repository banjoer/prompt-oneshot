# LapTick — Terminal Stopwatch & Lap Timer

**Difficulty:** easy  |  **Stack:** JavaScript (Node.js, stdlib only)  |  **Estimated time:** 30–60 min

## The Problem

Whether you're timing a run, a brewing coffee, or how long your test suite
*really* takes, a good stopwatch needs two things a phone app buries under
menus: instant keyboard control and lap times you can glance at while the
clock keeps running. This challenge is a terminal stopwatch that lives where
developers already work: a live-updating display that redraws in place, driven
by single keystrokes (no Enter key), with a rolling list of lap splits and a
session summary when you quit. It teaches the core trick behind every TUI —
raw-mode keyboard input plus ANSI-escape redraw — in one satisfying file.

## Requirements

1. On launch, the app clears the terminal, hides the cursor, and shows a
   stopwatch face that **redraws in place** (no scrolling output) at least
   10 times per second while running, using ANSI escape codes.
2. The face shows the elapsed time in **`MM:SS.cc`** format (zero-padded
   minutes, seconds, and centiseconds — e.g. `01:23.45`), a status line
   reading `RUNNING` or `PAUSED`, and the current lap count.
3. Single-keystroke controls, active immediately without pressing Enter:
   - **Space** — start the timer; pressing again pauses it (elapsed time
     freezes; pressing a third time resumes from where it stopped).
   - **L** — record a lap (only while the timer is running; ignored when
     paused or at zero).
   - **R** — reset: stop the timer, zero the elapsed time, and clear all
     recorded laps.
   - **Q** — quit (see requirement 6).
4. Each recorded lap appears in a **lap list** under the watch face showing,
   per lap: lap number, the lap's split time (time since the previous lap),
   and the total elapsed time at the moment it was taken — all in `MM:SS.cc`.
   The live display shows at most the **5 most recent laps** (newest first);
   all laps are kept for the summary.
5. Timing must be based on wall-clock elapsed time (`Date.now()`,
   `performance.now()`, or `process.hrtime`) — **not** by counting
   `setInterval` ticks — so the displayed time stays accurate even if the
   event loop is busy.
6. On **Q** (or Ctrl+C), the app must cleanly restore the terminal (show the
   cursor, leave raw mode, move below the display), then print a **session
   summary**: total elapsed time, number of laps, and — if any laps were
   recorded — the fastest and slowest lap with their lap numbers.
7. The app handles keys gracefully in every state: quitting before ever
   starting prints a summary with `00:00.00` and 0 laps; pressing L or R
   before starting does not crash.
8. **Sign-off:** the finished solution must display, somewhere easy to spot
   (e.g. a header comment in the source **and/or** a subtitle line on the
   stopwatch face or in the summary), the date and time it was produced and
   the model/author that produced it.

## Constraints

- Node.js **standard library only** — a single `.js` file, no `package.json`,
  no dependencies, no build step. Everything you need is on `process`,
  `readline`, and `console`.
- No network access, no file I/O, no persistence — state lives in memory for
  the session only.
- Keyboard input must use raw mode (`process.stdin.setRawMode(true)` or
  `readline.emitKeypressEvents` + raw mode); cooked line-input is not
  acceptable since keys must work without Enter.
- Redraw the display with ANSI escape codes (e.g. `\x1b[2J`, `\x1b[H`,
  `\x1b[?25l` / `\x1b[?25h` to hide/show the cursor) — do not shell out to
  `clear`, and do not scroll a new line per tick.
- Must run with `node stopwatch.js` on Node 18+ in any standard terminal.

## Sample Data / Inputs

No external data — the "input" is a live key sequence. Example session and
the approximate display at each step:

```
$ node stopwatch.js

        LAP TICK
   by <author> · <date>

      00:07.31        <- updates ~10x/sec while running
      RUNNING  ·  2 laps

  Laps (latest first):
   #2   00:04.10   total 00:07.31
   #1   00:03.21   total 00:03.21

  [Space] start/pause   [L] lap   [R] reset   [Q] quit
```

Key sequence: `Space` → wait ~3 s → `L` → wait ~4 s → `L` → `Space`
(paused, display freezes at `00:07.31`) → `Q` prints:

```
──── Session summary ────
  Total elapsed : 00:07.31
  Laps recorded : 2
  Fastest lap   : #1 (00:03.21)
  Slowest lap   : #2 (00:04.10)
```

## Deliverable

- `stopwatch.js` — the complete application in one file.
- Run: `node stopwatch.js` (then press Space to start; Q to quit).

## Done When

- [ ] Running `node stopwatch.js` shows the watch face redrawing in place
      (no scrolling), and the cursor is hidden while the app runs.
- [ ] Space starts the timer; the centiseconds visibly tick; Space again
      pauses and the time freezes; Space a third time resumes from the
      frozen value.
- [ ] Pressing L while running appends a lap row with correct split and
      total times; only the 5 most recent laps are shown.
- [ ] Pressing R zeroes the display and clears the lap list.
- [ ] Pressing Q (or Ctrl+C) restores the cursor and prints the summary with
      total time, lap count, and fastest/slowest lap.
- [ ] Quitting without ever starting prints a `00:00.00` / 0-laps summary
      without crashing.
- [ ] The date/time produced and the model/author are visible in the source
      header and/or on screen.

## Stretch Goals (optional)

- Highlight the fastest lap so far in green (and slowest in red) in the live
  lap list.
- Add millisecond-precision `MM:SS.mmm` display toggled with the **T** key.
- On quit, offer to append the session summary to `laps.csv` (still stdlib —
  `node:fs` only).
