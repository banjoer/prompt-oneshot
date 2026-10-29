# Void Vector — Asteroid Drift Shooter

**Difficulty:** medium  |  **Stack:** HTML/CSS/JavaScript (single file, canvas)  |  **Estimated time:** 1.5–3 hours

## The Problem

The classic arcade vector shooter is the perfect stress test for real-time game fundamentals: a physics loop with momentum, continuous collision detection, entity lifecycle management, and persistent state — all in a 60 fps frame budget. You are building a complete, playable Asteroids-style game: a lone ship drifting through a rock field, armed with a blaster and one desperate hyperspace jump. Half-finished clones are everywhere (no inertia, no splitting rocks, no wave progression); yours must be the real deal — tight controls, escalating waves, and a hi-score that survives closing the tab.

## Requirements

1. **Ship physics:** The player ship is drawn as a vector-outline triangle. LEFT/RIGHT (or A/D) rotate it; UP (or W) applies thrust along the ship's current heading. There is no friction — velocity persists (inertia), capped at a sensible maximum speed. A visible thruster flame flickers while thrusting.
2. **Screen wrap:** Everything (ship, bullets, asteroids) that leaves one edge of the playfield re-enters from the opposite edge. No clamping, no bouncing.
3. **Shooting:** SPACE fires bullets from the ship's nose in the facing direction. Bullets have a fixed lifetime (e.g. ~1 second) and a maximum of 4–6 live at once. Bullets inherit nothing from ship velocity except position — keep it simple and predictable.
4. **Asteroids:** Drawn as irregular vector polygons (randomized jagged outlines, at least 8 vertices) in three sizes — large, medium, small — each with random drift velocity and slow rotation. Shooting a large asteroid splits it into 2 mediums; a medium splits into 2 smalls; a small is destroyed. Fragments inherit roughly their parent's position with new random velocities.
5. **Collision & lives:** Ship–asteroid contact destroys the ship (brief explosion/particle effect or flash), costs one life, and respawns the ship at center after a short delay with ~2 seconds of invulnerability (ship blinks while invulnerable). The player starts with 3 lives, displayed on the HUD. Extra life every 10,000 points.
6. **Hyperspace:** SHIFT (or H) is the panic button: the ship vanishes and reappears at a random location. There must be real risk — a small chance (e.g. 1 in 5) the jump malfunctions and destroys the ship, plus you can materialize inside an asteroid.
7. **Waves:** Clearing all asteroids starts the next wave after a brief pause. Wave N spawns N+2 large asteroids, placed away from the ship's spawn point, with slightly higher base speed each wave. Show a "WAVE N" banner between waves.
8. **Scoring & hi-score:** Large = 20, medium = 50, small = 100 points. Current score, lives, and wave are always visible in a HUD. The all-time hi-score is persisted in `localStorage` and shown on the title/game-over screen; beating it must be acknowledged (e.g. "NEW HI-SCORE!").
9. **Game flow:** Title/start screen (press ENTER to start) → gameplay → game-over screen showing final score and hi-score (press ENTER to restart). The game must be fully replayable without reloading the page.
10. **Rendering:** Single `<canvas>`, retro vector aesthetic — bright monochrome strokes (one accent color allowed) on a black background, no images, no sprites, no audio files (Web Audio bleeps are optional). Runs at a stable frame rate via `requestAnimationFrame` with delta-time-based movement so speed is framerate-independent.
11. **Sign-off:** The finished solution must display, somewhere easy to spot, the date and time it was produced and the model/author that produced it — as a header comment at the top of the HTML file AND in small text on the title screen.

## Constraints

- Deliverable is exactly ONE self-contained `.html` file, playable by double-clicking it (file:// protocol, no server, no build step).
- Third-party libraries ARE allowed via CDN `<script>` tags or inlined source — state any you use in a comment. None are needed; vanilla canvas is encouraged.
- No network calls at runtime (CDN loads excepted), no external assets, no images, no fonts to download (use canvas `fillText` with a generic monospace font).
- Storage: `localStorage` only, and only for the hi-score.
- Must work in a current Chrome/Firefox at a window size of at least 800×600.
- Keyboard only — no mouse or touch required.

## Sample Data / Inputs

Suggested tuning constants (starting points, not mandates):

```js
const TURN_SPEED = 4.5;        // radians/sec
const THRUST = 300;            // px/sec^2
const MAX_SPEED = 400;         // px/sec
const BULLET_SPEED = 500;      // px/sec
const BULLET_LIFE = 1.0;       // seconds
const MAX_BULLETS = 5;
const AST_RADII = { large: 60, medium: 32, small: 15 };
const BASE_AST_SPEED = 60;     // px/sec, scaled up per wave
const HYPERSPACE_FAIL = 0.2;   // 20% malfunction chance
const START_LIVES = 3;
const EXTRA_LIFE_EVERY = 10000;
```

Asteroid shape recipe: for radius r, pick 9–12 angles evenly around the circle and jitter each radius by ±35%; connect the dots; rotate slowly over time.

## Deliverable

- `void-vector.html` — the complete game.
- Run: double-click the file, or `open void-vector.html` (macOS) / `xdg-open void-vector.html` (Linux). Press ENTER to play.

## Done When

- [ ] Double-clicking the file opens a title screen with controls listed and the saved hi-score (or 0 on first run).
- [ ] The ship rotates, thrusts with visible flame, drifts with inertia, and wraps around all four screen edges.
- [ ] Firing a large asteroid produces exactly 2 mediums; mediums produce 2 smalls; smalls are destroyed.
- [ ] Colliding with a rock costs a life, respawns the blinking invulnerable ship at center, and at 0 lives shows the game-over screen.
- [ ] SHIFT teleports the ship and visibly sometimes fails (a malfunction destroys the ship).
- [ ] Clearing the field advances to a faster wave with more asteroids, with a wave banner shown.
- [ ] Closing and reopening the browser preserves the hi-score; a new best score is flagged on the game-over screen.
- [ ] Restarting after game over works without reloading the page.
- [ ] The sign-off (date/time + model/author) is visible on the title screen and in a source header comment.

## Stretch Goals (optional)

- A flying saucer that crosses the screen every ~20 seconds and shoots at the player for bonus points.
- Screen shake and particle debris on every destruction.
- Attract mode: after 10 idle seconds on the title screen, an AI-free demo field of drifting asteroids plays behind the menu.
