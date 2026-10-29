# Skyline Hop — One-Button Endless Runner

**Difficulty:** easy  |  **Stack:** HTML/CSS/JavaScript (single file, Canvas)  |  **Estimated time:** 30–60 min

## The Problem

The Chrome dino game proved a whole arcade can live in one sprite and one
button — but it only exists inside a browser error page. You want a pocket
arcade you fully own: a single `.html` file you can double-click, email to a
friend, or drop on a USB stick, that plays a complete endless runner — jump and
double-jump over an infinite procedurally-spaced obstacle field, with a speed
ramp that keeps tension rising, a layered parallax skyline scrolling behind,
and a hi-score that survives closing the tab. No server, no build step, no
assets folder — just one file that is the entire game.

## Requirements

1. **Single deliverable:** the entire game (markup, styles, logic) lives in
   ONE `.html` file that runs by double-clicking it (opened via `file://`) in
   any modern desktop or mobile browser — no server, no console, no build.
2. **Game loop:** render on a `<canvas>` driven by `requestAnimationFrame`,
   using delta-time physics so gameplay speed is identical at any refresh
   rate. The canvas has a fixed logical resolution (e.g. 800×400) and scales
   to fit the window without distortion.
3. **One-button control:** Space, ArrowUp, mouse click, and touch tap all
   trigger the SAME single action. There are no other gameplay controls.
4. **Jump + double-jump:** pressing the button while grounded jumps; pressing
   it once more while airborne performs exactly one double-jump (with a
   distinct visual cue, e.g. a spin or flip). Both jumps are refreshed only
   by landing. Gravity and jump velocities must make the arc feel snappy, not
   floaty.
5. **Procedural obstacles:** obstacles spawn at the right edge with randomized
   horizontal spacing. Each gap is drawn from a range computed from the
   CURRENT world speed so that every obstacle is always clearable (e.g.
   `gap = rand(0.9, 1.6) × speed × timeToClear`, where `timeToClear` is the
   airtime of a single jump plus a safety margin). No unfair, impossible
   jumps.
6. **Speed ramp:** world speed starts at ~260 px/s and increases linearly
   (~+6 px/s every second) up to a cap (~620 px/s). Current speed must be
   visible in a small debug-style readout on screen.
7. **Collision & game over:** axis-aligned bounding-box overlap between the
   runner and any obstacle ends the run and shows a GAME OVER panel with the
   final score, the hi-score, and a "press to restart" prompt. The same one
   button restarts instantly.
8. **Parallax background:** at least THREE independently scrolling layers
   (e.g. far skyline silhouette, mid buildings with lit windows, near
   foreground shapes), each moving at a different fraction of world speed,
   each wrapping seamlessly forever.
9. **Score & persistence:** score increases with distance survived (floor of
   pixels/50 or similar). The hi-score is saved to `localStorage`, loaded on
   start, displayed next to the live score, and a "NEW BEST!" badge appears
   on the game-over panel when it is beaten.
10. **Sign-off:** the finished file must display, somewhere easy to spot (a
    header comment in the source AND a small footer line on the page), the
    date and time the solution was produced and the model/author that
    produced it.

## Constraints

- Standard library / platform APIs only: vanilla HTML, CSS, and JavaScript
  with the Canvas 2D API. **Third-party libraries ARE permitted for this
  batch** (via CDN `<script>` tag or inlined source) but are NOT needed; if
  you use any, declare each one (name + version + URL) in the header comment.
- No network calls at runtime, no external assets: all graphics are drawn
  with canvas primitives (rects, arcs, paths) or CSS. No images, fonts, or
  audio files to download.
- Persistence is `localStorage` only, and the game must not crash if it is
  unavailable (private mode) — fall back to a session-only hi-score.
- Must run from `file://` with zero errors in the browser console.
- All randomness may use `Math.random()`; no seeding required.

## Sample Data / Inputs

Suggested starting tuning values (adjust to taste, but keep gaps provably
clearable per requirement 5):

| Constant            | Value        |
|---------------------|--------------|
| Logical canvas      | 800 × 400 px |
| Gravity             | 2200 px/s²   |
| Jump velocity       | −720 px/s    |
| Double-jump velocity| −620 px/s    |
| Ground height       | 60 px        |
| Start speed         | 260 px/s     |
| Speed ramp          | +6 px/s per s|
| Speed cap           | 620 px/s     |
| Obstacle width      | 18–42 px     |
| Obstacle height     | 28–70 px     |
| Parallax factors    | 0.15 / 0.4 / 0.75 (far / mid / near) |

Single-jump airtime with these values ≈ 0.65 s, so at 620 px/s a clearable
gap range is roughly 560–1000 px — your formula should produce this
automatically from the speed.

## Deliverable

- Exactly one file: `skyline-hop.html`
- Run it: double-click the file (or drag it into any modern browser). No
  commands required.

## Done When

- [ ] Double-clicking the file opens a running game — no console errors.
- [ ] Space, click, and tap each make the runner jump; a second mid-air press
      performs exactly one visible double-jump; a third does nothing.
- [ ] Obstacles arrive with varied spacing and are never impossible at the
      current speed (survive a 90-second run without an unavoidable hit).
- [ ] The speed readout climbs from ~260 toward ~620 px/s and stops at the
      cap; scrolling visibly accelerates.
- [ ] Three background layers scroll at clearly different speeds and never
      show a seam or gap.
- [ ] Hitting an obstacle shows GAME OVER with score + hi-score; pressing the
      button restarts cleanly.
- [ ] Beating the hi-score shows "NEW BEST!" and the new best survives a full
      page reload.
- [ ] The footer shows the production date/time and the model/author sign-off.

## Stretch Goals (optional)

- Day/night cycle that slowly shifts the sky palette as the score grows.
- Two obstacle classes (low blocks to hop, tall bars that REQUIRE the
  double-jump) while still guaranteeing every spawn is clearable.
- Tiny WebAudio beeps for jump, double-jump, and crash — generated in code,
  no audio files.
