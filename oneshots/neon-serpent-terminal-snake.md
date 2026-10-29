# Neon Serpent — Terminal Snake

**Difficulty:** Medium  |  **Stack:** Python  |  **Estimated time:** 1–3 hours

## The Problem
Arcade games live and die on feel: responsive input, a smooth render loop, and a reason to chase "one more run." Snake is the purest test of that loop — a real-time game squeezed into a grid of characters. Building it with raw ANSI escape codes (no `curses`, no libraries) forces you to own the terminal yourself: an alternate screen, a hidden cursor, non-blocking key reads, and a frame clock that keeps gameplay consistent. Add a speed ramp that punishes greed and a persistent high-score table that survives restarts, and you have a tiny game that is genuinely fun and visibly alive in any terminal.

## Requirements
1. The game is a single Python file, `snake.py`, runnable with the system Python 3 on a POSIX terminal (Linux/macOS): `python3 snake.py`. No third-party packages, and do **not** use the `curses` module — render everything yourself with ANSI escape codes.
2. **Playfield & rendering.** Draw a bordered playfield (interior at least 30×15 cells) in an alternate screen buffer with the cursor hidden. Render the snake, the food, and a HUD line (score, high score, current speed level) using ANSI colors. Use full redraws or cell-diff redraws — either is fine — but there must be no flicker, no scroll, and no leftover artifacts as the snake moves.
3. **Controls.** Arrow keys **and** WASD steer the snake. Input is non-blocking and polled every frame; pressing a key must feel instant (buffered direction applies on the next tick). A 180° reversal directly into the snake's own neck is ignored. `p` pauses/unpauses (with a visible "PAUSED" indicator), `q` quits cleanly from gameplay, pause, and menus.
4. **Core gameplay.** The snake starts length 3 in the middle, moving right. Food (`●` or similar glyph) spawns on a random free cell — never on the snake's body. Eating food grows the snake by 1 and adds 10 points. Hitting a wall or the snake's own body ends the run.
5. **Speed ramp.** The game tick starts at 150 ms. Each food eaten shortens the tick by 7 ms, down to a hard floor of 60 ms. The HUD shows the current speed as a level number (e.g. `LV 1`, `LV 2`, … where level = one per food eaten) so the ramp is visible while playing. Movement timing must use a monotonic clock — never `time.sleep()` alone in a way that lets input lag accumulate.
6. **Start & game-over screens.** On launch, show a title/start screen listing the saved high scores and "press any key to start." On death, show a game-over screen with the final score; if the score makes the top 5, prompt for a 3-character name/initials (editable before confirming with Enter, uppercase A–Z/0–9) and record it. From the game-over screen, `r` restarts instantly and `q` exits.
7. **Persistent high scores.** Keep the top 5 scores (initials + score + date `YYYY-MM-DD`) in a local JSON file `snake_scores.json` created next to the script. It must survive restarts. If the file is missing, start with an empty table; if it contains invalid JSON, show a one-line warning, back the bad file up to `snake_scores.json.bak`, and start fresh — never crash and never silently delete the user's data.
8. **Clean terminal hygiene.** On **every** exit path — normal quit, game over then quit, `Ctrl+C`, or an unexpected exception — the program must restore the terminal: show the cursor, leave the alternate screen, reset colors, and restore the original termios settings (use `try/finally` and a `SIGINT` handler). A crashed run must never leave the user's shell garbled.
9. **Sign-off:** the finished solution must display, somewhere easy to spot, the date and time it was produced and the model/author that produced it — show it as a small footer line on the start screen (e.g. `built 2026-10-29 14:32 · <model/author>`) **and** as a header comment in the source.

## Constraints
- Python 3 standard library only (`sys`, `os`, `time`, `random`, `json`, `select`, `termios`, `tty`, `signal`, `datetime`, …). No pip, no `curses`, no external assets.
- Single source file: `snake.py`. The score file is created by the program, never shipped.
- Local storage only. No network calls, no environment variables required, no config beyond the score file.
- Must run in a real POSIX terminal of at least 40×20 characters; if the terminal is smaller, print a clear message and exit cleanly instead of drawing a broken board.
- All timing derives from `time.monotonic()`; all randomness from the `random` module (seeded normally).

## Sample Data / Inputs
Suggested score-file shape (implementation may vary, but it must round-trip):

```json
{
  "scores": [
    {"initials": "ACE", "score": 120, "date": "2026-10-29"},
    {"initials": "NIB", "score": 80,  "date": "2026-10-28"}
  ]
}
```

Sketch of one rendered frame (colors omitted; borders, HUD, snake, and food are the contract):

```
┌────────────────────────────────┐
│ SCORE 0040   BEST 0120   LV 4  │
├────────────────────────────────┤
│                                │
│          ●                     │
│                                │
│              ██████            │
│                    ▀           │
│                                │
└────────────────────────────────┘
 arrows / WASD move · p pause · q quit
```

Example terminal interaction:

```
$ python3 snake.py
<start screen: title, top-5 table, built-by footer, "press any key">
<any key>            → gameplay starts, snake auto-moves right
<eat 4 foods>        → SCORE 0040, LV 4, visibly faster tick
<crash into wall>    → game over, prompt "NEW BEST! initials: ___"
<type ACE, Enter>    → score saved to snake_scores.json
<q>                  → clean shell, cursor back, no artifacts
$ cat snake_scores.json   → ACE 0040 is now the top entry
```

## Deliverable
- `snake.py` — the only source file.
- Run command: `python3 snake.py`

## Done When
- [ ] `python3 snake.py` opens a start screen showing the high-score table and the sign-off footer, in an alternate screen with the cursor hidden.
- [ ] Arrow keys and WASD both steer; input feels instant; reversing 180° into the neck is ignored; `p` pauses with a visible indicator.
- [ ] Eating food grows the snake, adds 10 points, and the game gets noticeably faster every few foods, with the `LV` indicator rising in the HUD.
- [ ] Wall and self collisions both end the run with a game-over screen; `r` restarts without relaunching the program.
- [ ] A qualifying score prompts for 3 initials, is written to `snake_scores.json`, and still appears on the start screen after quitting and relaunching.
- [ ] Corrupting `snake_scores.json` by hand and relaunching shows a warning, preserves the bad file as `.bak`, and the game still plays.
- [ ] Quitting via `q` **and** via `Ctrl+C` mid-game both leave the shell fully restored (cursor visible, colors reset, normal screen).
- [ ] The source header comment and the start-screen footer both show the production date/time and the model/author.

## Stretch Goals (optional)
- **Wrap mode:** press `w` on the start screen to toggle a wrap-around arena (no wall death) as a separate high-score table.
- **Bonus fruit:** every ~25 seconds a `★` appears for 5 seconds, worth 50 points, with its own countdown blink.
- **Ghost trail:** fade the snake's tail with dim ANSI colors, or color-shift the snake from head to tail for a neon look.
