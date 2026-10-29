# Stackwell — Guideline Tetromino Stacker

**Difficulty:** hard  |  **Stack:** HTML/CSS/JS (single file, Canvas 2D)  |  **Estimated time:** 5–8 hours

## The Problem

Everyone has "made Tetris" — almost nobody has made it *correctly*. The real
game is a small marvel of interacting systems: a fair 7-bag randomizer, a
rotation system with wall kicks so pieces never jam against the stack, a
gravity curve that tightens as you level, lock delay, input auto-repeat tuned
to the millisecond, and a scoring model that rewards building for the
four-line clear. Cut any corner and experienced players feel it instantly:
pieces stick to walls, the bag deals droughts, hard drops feel mushy. Build a
faithful, self-contained falling-block stacker that plays like the real
thing — the systems underneath matter more than the pixels on top.

## Requirements

1. The solution is a single `stackwell.html` file (embedded `<style>` and
   `<script>`) that runs by double-clicking it — `file://` protocol, no
   server, no build step.
2. **Playfield.** Canvas-rendered matrix of 10 columns × 20 **visible** rows,
   plus at least 2 hidden buffer rows above for spawning. A HUD shows Score,
   Level, Lines, and Hi-Score; side panels show the Hold box and a Next queue
   of **3** upcoming pieces. Layout fits a ~1280×800 viewport.
3. **Pieces.** The seven tetrominoes (I, O, T, S, Z, J, L) with the standard
   colors from Sample Data, spawning centered at the top in the orientations
   given there.
4. **7-bag randomizer.** Deal pieces in shuffled bags containing each of the
   7 exactly once; when a bag empties, deal a fresh one. The Next queue is fed
   from the bag so 3 previews are always available. (Uniform `Math.random`
   per piece — i.e. droughts and floods — is a fail.)
5. **Rotation with wall kicks.** CW and CCW rotation using the SRS kick
   tables embedded in Sample Data: on each rotation attempt, try the 5
   offsets for that transition in order and apply the first that fits; if
   none fit, the rotation fails. O never rotates. The kick tables must exist
   as named data constants in the source.
6. **Movement & auto-repeat.** ←/→ move one cell per keypress; holding a
   direction triggers DAS/ARR auto-repeat with a 167 ms initial delay and a
   33 ms repeat period. Movement is blocked by walls and the stack.
7. **Level-based gravity.** Game logic runs on a fixed 60 Hz timestep
   (accumulator over `requestAnimationFrame` — not `setInterval`); the piece
   falls one row per N frames, with N taken from the gravity table in Sample
   Data. Level starts at 1 and increases every 10 cleared lines.
8. **Soft & hard drop.** ↓ soft-drops at 1 row per 2 frames (30 rows/s), or
   at the current gravity speed if that is faster, scoring +1 per row.
   Space hard-drops: the piece instantly teleports to its landing position,
   scores +2 per row, and locks immediately (no lock delay).
9. **Lock delay.** When a falling piece cannot move down, it locks after
   500 ms of ground contact; each successful sideways move or rotation while
   grounded resets that timer.
10. **Ghost piece.** A translucent/outline copy of the active piece is drawn
    at its hard-drop landing position, updating live on every move, rotation,
    and gravity step.
11. **Hold queue.** C (or Shift) holds the active piece: first use stores it
    and spawns the next piece from the queue; later uses swap the held and
    active pieces (the swapped-in piece respawns at the top in spawn
    orientation). Only one hold per turn — hold is disabled (and the Hold box
    visibly dimmed) until the next piece locks.
12. **Line-clear flash animation.** Completed rows flash (blink to white at
    least twice over ~250–300 ms) while gameplay freezes; then the rows are
    removed, everything above drops instantly, and scoring is applied. A
    4-line clear is one event, not four singles.
13. **Scoring (T-spin-agnostic — no T-spin detection required).** Single 100,
    Double 300, Triple 500, Tetris 800, each multiplied by the level at the
    moment of the clear, plus the soft/hard-drop bonuses above. Score, lines,
    and level update visibly right after the clear animation.
14. **Pause.** P or Esc toggles pause: the loop and all timers freeze, the
    field dims behind a clear PAUSED overlay, and all gameplay input is
    ignored until resumed.
15. **Game over & restart.** Top-out when a newly spawned piece overlaps the
    stack. An overlay shows the final score, the hi-score, a visible
    "NEW HI-SCORE" badge when it was beaten, and a restart prompt (R key,
    Enter, and/or an on-screen button). Restart resets to a fresh level-1
    game; the hi-score survives.
16. **Hi-score persistence.** The hi-score is stored in `localStorage`,
    loaded on startup, shown in the HUD, and saved the moment it is beaten.
17. **Sign-off:** the finished solution must display, somewhere easy to spot,
    the date and time it was produced and the model/author that produced it
    (e.g. a footer on the page and/or a header comment in the source).

## Constraints

- One file, `stackwell.html`. All rendering via Canvas 2D (UI chrome may be
  HTML/CSS). No external assets — no images, fonts, or audio files.
- Third-party libraries ARE permitted for this batch (CDN `<script>` tag or
  inlined source), but none are required — vanilla is entirely feasible. Any
  library used must be declared in a header comment, and it must NOT be a
  game engine or library that implements falling-block/Tetris mechanics for
  you (input handling, rotation, gravity, and scoring must be your own code).
- No network calls of any kind at runtime; storage is `localStorage` only.
- Gravity must follow the fixed-timestep 60 Hz model so the frames-per-row
  table is exact; `setInterval`/`setTimeout` must not drive game logic.
- Must run correctly from `file://` in a current Chrome, Edge, or Firefox.
- Default controls: ←/→ move · ↓ soft drop · Space hard drop · ↑ or X rotate
  CW · Z rotate CCW · C or Shift hold · P or Esc pause · R restart. Show them
  on screen.

## Sample Data / Inputs

Spawn shapes (1 = filled), colors, and the SRS kick tables. Kick offsets are
`(x, y)` pairs with **+y = up**; negate y if your grid is +y = down. The first
test `(0,0)` is plain rotation; apply the remaining offsets in order.

```json
{
  "colors": { "I": "#00f0f0", "O": "#f0f000", "T": "#a000f0", "S": "#00f000",
              "Z": "#f00000", "J": "#0000f0", "L": "#f0a000" },
  "shapes": {
    "I": [[0,0,0,0],[1,1,1,1],[0,0,0,0],[0,0,0,0]],
    "O": [[1,1],[1,1]],
    "T": [[0,1,0],[1,1,1],[0,0,0]],
    "S": [[0,1,1],[1,1,0],[0,0,0]],
    "Z": [[1,1,0],[0,1,1],[0,0,0]],
    "J": [[1,0,0],[1,1,1],[0,0,0]],
    "L": [[0,0,1],[1,1,1],[0,0,0]]
  },
  "kicks_JLSTZ": {
    "0>R": [[0,0],[-1,0],[-1,1],[0,-2],[-1,-2]],
    "R>0": [[0,0],[1,0],[1,-1],[0,2],[1,2]],
    "R>2": [[0,0],[1,0],[1,-1],[0,2],[1,2]],
    "2>R": [[0,0],[-1,0],[-1,1],[0,-2],[-1,-2]],
    "2>L": [[0,0],[1,0],[1,1],[0,-2],[1,-2]],
    "L>2": [[0,0],[-1,0],[-1,-1],[0,2],[-1,2]],
    "L>0": [[0,0],[-1,0],[-1,-1],[0,2],[-1,2]],
    "0>L": [[0,0],[1,0],[1,1],[0,-2],[1,-2]]
  },
  "kicks_I": {
    "0>R": [[0,0],[-2,0],[1,0],[-2,-1],[1,2]],
    "R>0": [[0,0],[2,0],[-1,0],[2,1],[-1,-2]],
    "R>2": [[0,0],[-1,0],[2,0],[-1,2],[2,-1]],
    "2>R": [[0,0],[1,0],[-2,0],[1,-2],[-2,1]],
    "2>L": [[0,0],[2,0],[-1,0],[2,1],[-1,-2]],
    "L>2": [[0,0],[-2,0],[1,0],[-2,-1],[1,2]],
    "L>0": [[0,0],[1,0],[-2,0],[1,-2],[-2,1]],
    "0>L": [[0,0],[-1,0],[2,0],[-1,2],[2,-1]]
  }
}
```

Rotation states are 0 (spawn), R (CW from spawn), 2 (180°), L (CCW from
spawn); rotation is within the piece's bounding box (3×3, or 4×4 for I).

Gravity (frames per row at 60 Hz) and scoring:

```json
{
  "gravity": { "1": 48, "2": 43, "3": 38, "4": 33, "5": 28, "6": 23,
               "7": 18, "8": 13, "9": 8, "10": 6, "11": 5, "12": 5,
               "13": 4, "14": 4, "15": 3, "16": 3, "17": 3, "18": 2,
               "19": 2, "20+": 1 },
  "scoring": { "single": 100, "double": 300, "triple": 500, "tetris": 800,
               "softDropPerRow": 1, "hardDropPerRow": 2 }
}
```

## Deliverable

- One file: `stackwell.html` (embedded `<style>` and `<script>`; no other
  files).
- Run: double-click `stackwell.html` or open it via a `file://` URL in a
  modern browser. No server, no tooling.

## Done When

- [ ] Opening the file shows the 10×20 field, HUD (score/level/lines/
      hi-score), Hold box, 3-piece Next queue, and the controls list.
- [ ] Every 7 pieces dealt contains each tetromino exactly once; the Next
      queue always previews the real upcoming 3 pieces.
- [ ] Rotating a T or I pressed against the wall or the stack visibly kicks
      it into a legal position instead of jamming; rotating in open space
      never shifts the piece.
- [ ] The ghost piece tracks the landing position live and matches exactly
      where a hard drop lands.
- [ ] Holding ← slides the piece smoothly across the field after a short
      delay (DAS/ARR), while tapping moves exactly one cell.
- [ ] Soft drop scores +1/row, hard drop +2/row, and a hard drop locks
      instantly; a piece resting on the stack locks ~0.5 s after its last
      successful move/rotate.
- [ ] Clearing lines plays a visible white flash before the collapse; a
      Tetris (4 rows) scores 800 × level as a single event.
- [ ] After 10 lines the level increments and the fall speed visibly
      increases; by the level-9 range the game is fast but still playable.
- [ ] P pauses with a dimmed overlay and frozen timers; gameplay resumes
      cleanly with no jump in the piece position.
- [ ] Holding a piece dims the Hold box until the next lock; pressing hold
      twice in one turn does nothing the second time.
- [ ] Topping out shows final score, hi-score (with a NEW HI-SCORE badge when
      beaten), and R restarts a fresh game; the hi-score is still there after
      a full page reload.
- [ ] A visible sign-off shows the production date/time and the model/author.

## Stretch Goals (optional)

- Back-to-back Tetris bonus (×1.5) and a combo counter (+50 × combo × level),
  displayed as floating text.
- Full T-spin detection (3-corner rule) with proper guideline bonuses.
- Web Audio–synthesized sound effects (move, rotate, lock, clear, level-up)
  and a Korobeiniki-ish chiptune loop — all generated in code, no audio files.
- 40-line sprint mode with an on-screen timer and its own persisted best time.
