# Neon Serpent — Terminal Snake

Solution for [`oneshots/neon-serpent-terminal-snake.md`](../../oneshots/neon-serpent-terminal-snake.md).

**Built:** 2026-10-30 00:54 CET · Qwen 3.8 Flash (xhigh thinking)

## Run

```sh
python3 snake.py
```

Single file, Python 3 standard library only (Linux/macOS, terminal ≥ 40×20).
No `curses`, no pip packages, no network, no env vars required.

## Controls

| Key | Action |
|-----|--------|
| `↑↓←→` / `wasd` (plus `hjkl`) | steer — buffered, applied on the next tick; 180° reversals ignored |
| `p` | pause / resume (blinking **PAUSED** banner) |
| `q` / `Esc` / `Ctrl+C` | quit cleanly from gameplay, pause and every menu |
| any key | start from the menu |
| `w` (menu) | toggle **CLASSIC ↔ WRAP** arena (wrap has its own score table) |
| on initials prompt | type `A–Z 0–9`, `←`/`Backspace` move left, `→` right, `Enter` save |
| `r` | instant restart from game over |

## Files

- `snake.py` — the only source file.
- `snake_scores.json` — created by the program next to the script on first save
  (`{"scores": [...], "wrap_scores": [...]}`, same shape as the spec sample plus
  the extra wrap table). Saved atomically via temp-file + `os.replace`.
- `snake_scores.json.bak(.N)` — if the score file is unreadable JSON/data it is
  *moved* (not deleted) to a unique `.bak`, a one-line warning shows on the
  start screen, and the game starts with a fresh table.

## Design notes

- **Rendering** — an in-memory cell buffer is rebuilt each frame and emitted as
  **one** write to the alternate screen (`?1049h`, cursor hidden): home, redraw
  every line, `ESC[K` each line, no trailing newline. No flicker, no scrolling,
  no leftovers (mid-run terminal *shrinks* clamp through the buffer, so output
  can never exceed the live size; shrinking below 40×20 exits cleanly).
- **Timing** — every deadline uses `time.monotonic()`; the loop blocks in
  `select()` only until the next tick (≤150 ms) so input is always read the
  moment it arrives, and the tick schedule resyncs after pauses/overruns.
- **Speed ramp** — `tick = max(60, 150 − 7·food)` exactly as specified. The HUD
  speed level follows the spec's sample frame (`40 pts → LV 4`), i.e. one level
  per food eaten with `LV 1` as the base, and it also prints the raw tick
  (`· 122ms`) where width allows, so the ramp is visible continuously.
- **Input** — raw-ish `tty.setcbreak` (keeps `ISIG` so **Ctrl+C is a real
  SIGINT** handled by `signal.signal`, plus IXON off so Ctrl+S can't stall the
  render). Escape sequences (`ESC [ A` and `ESC O A`) are parsed incrementally;
  held keys are drained at screen changes.
- **Hygiene** — one idempotent `Terminal.close()` (cursor on, colors reset,
  leave alt screen, restore termios) runs from `finally` on every path: quit,
  menu exit, SIGINT/SIGTERM/SIGHUP, and crashes (restore happens *before* the
  traceback is raised).
- **Stretch goals** — all three implemented: wrap arena with its own table,
  bonus `★` (every ~25 s, 5 s life, 50 pts, blinking countdown in HUD and on
  the fruit), and a neon head→tail color fade with `█ ▓ ▒ ░` ghost trail.
  Eating the star never shortens the tick and never grows the snake (only
  regular food does, per the core spec).
- Filling the whole arena ends the run with a “PERFECT!” rather than a crash.

## Verification

186 automated checks, all green:

- **121** headless logic/storage tests (`Snake` model, speed ramp, reversal
  filtering, tail-follow legality, spawn safety, bonus cadence; `ScoreStore`
  round-trips, corrupt→`.bak`→fresh, entry sanitising, top-5 ordering & ties;
  key-sequence parser incl. split escape sequences; layout math at 40×20 …
  120×50).
- **24** raw-PTY byte-level tests: alt screen enter/leave, cursor hide/restore,
  teardown after last frame, SIGINT exit code 0, and — after an *injected
  crash* — `stty -a` proves `echo`/`icanon` termios are restored and the shell
  keeps working.
- **41** interactive tmux tests: start screen + footer, eating while the HUD
  score/LV climb, food & star glyphs, wall death → game over, initials typing →
  save → `snake_scores.json` contains ACE, `r` restart, relaunch shows the saved
  table, WASD + pause, wrap toggle survives the walls 9 s+, corrupt file
  warning + preserved bytes + playable, 30×10 terminal gets the clear refusal
  message and exit 1, real `Ctrl+C` mid-game leaves a clean shell, and frames
  never exceed the terminal height.
