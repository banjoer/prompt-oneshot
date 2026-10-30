# Neon Serpent — Terminal Snake

A single-file, neon-flavoured Snake game for a real POSIX terminal.
Everything is rendered with raw ANSI escape codes — no `curses`, no third-party
packages, no external assets.

**Built 2026-10-29 23:53 · DeepSeek V4.1 Flash (OpenCode)**

## Run

```sh
python3 snake.py
```

Requires an interactive Linux/macOS terminal of at least **40 × 20** characters.
Smaller terminals get a clear message instead of a broken board.

## Controls

| Key | Action |
| --- | --- |
| Arrow keys / `WASD` | Steer (buffered until the next tick; 180° reversals ignored) |
| `p` | Pause / resume (visible `PAUSED` panel) |
| `q` | Quit cleanly from any screen |
| `r` | Restart instantly from the game-over screen |
| `Enter` | Confirm initials at the game-over prompt |
| `Backspace` | Edit initials |

## Rules & feel

- Snake starts at length 3 in the middle, moving right.
- Food (`●`) is always placed on a free cell; eating it grows the snake by 1
  and adds **10 points**.
- The tick starts at **150 ms**, drops **7 ms per food**, and never goes below
  **60 ms**. The HUD shows the current level (`LV n`) and the high score.
- Death by wall or self-collision ends the run.
- A top-5 score prompts for 1–3 uppercase initials (`A–Z`, `0–9`). The table
  keeps initials, score, and a `YYYY-MM-DD` date.

## High scores

Scores live next to the script in `snake_scores.json`:

```json
{
  "scores": [
    {"initials": "ACE", "score": 120, "date": "2026-10-29"}
  ]
}
```

The file is created on first save (it is not shipped). Missing files start
empty. If the file contains invalid JSON, the start screen shows a one-line
warning and the bad file is preserved as `snake_scores.json.bak` before a fresh
table is started.

## Terminal hygiene

The game uses the alternate screen buffer, hides the cursor, polls input
non-blockingly with `select()`, and drives ticks from `time.monotonic()`.
`finally` cleanup plus a `SIGINT` handler restore the cursor, colours, normal
screen, and original `termios` settings on quit, `Ctrl+C`, or an unexpected
exception.
