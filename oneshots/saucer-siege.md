# Saucer Siege

**Difficulty:** medium  |  **Stack:** HTML/CSS/JavaScript (single file, canvas)  |  **Estimated time:** 1–3 hours

## The Problem

Space Invaders defined the arcade loop: a descending wall of enemies, one cannon, and the creeping dread of a swarm that gets faster the more of it you kill. Most web clones get the silhouette right and the feel wrong — formations that glide instead of stomp, shields that vanish in one hit, bullets you can spam, and scores that disappear when the tab closes. Your job is to build a faithful, complete, single-file homage: a marching alien grid that accelerates as it thins, a cannon limited to one bullet in flight, pixel-eroding shield bunkers, alien bombs, a mystery UFO, escalating waves, and a hi-score that survives a page reload.

## Requirements

1. **Single-file game.** The entire game ships as one self-contained `index.html` (inline CSS and JS) that renders on a `<canvas>` element and runs by simply opening the file in a browser — no server, no build step.
2. **Marching formation.** Aliens spawn as a grid (suggested: 5 rows × 11 columns) and move as one block in discrete, chunky steps on a timer — sideways, and when any living alien touches a screen edge, the whole formation drops one step down and reverses direction. No smooth per-frame drifting: the cadence must read as the classic stomp.
3. **Speed-up as it thins.** The march interval shrinks as aliens die: a full grid creeps (e.g. one step per ~700 ms) while the last few aliens sprint (e.g. one step per ~60–100 ms). The acceleration must be clearly perceptible as the formation thins, and each new wave starts a little faster than the previous one.
4. **Pixel-art aliens with tiered scoring.** At least 3 visually distinct alien types by row, drawn from inline bitmap data (arrays of strings, see Sample Data) — not plain rects or circles. Suggested values: top row = 30 pts, middle rows = 20 pts, bottom rows = 10 pts, shown in a legend on the title screen.
5. **Cannon with limited fire.** The player cannon moves horizontally along the bottom (Left/Right arrows and/or A/D), clamped to the playfield. At most ONE player bullet may exist on screen at a time — pressing fire (Space) while a bullet is in flight does nothing. A bullet destroys exactly one alien (or the UFO) on contact.
6. **Destructible shield bunkers.** Four bunkers sit between the swarm and the cannon, built from a grid of small pixels (e.g. each bunker ~22×16 cells of 3–4 px). Both player bullets and alien bombs erode them: on impact, carve out a small blast hole (removing individual pixels, not deleting whole bunker blocks). Remaining bunker pixels keep blocking both directions of fire, so cover visibly degrades over a run.
7. **Alien bombs.** Living aliens periodically drop bombs (suggested: straight-falling and wobbling/zigzag variants, visually distinct). Bombs that hit the cannon cost a life; bombs that hit bunkers or the bottom edge explode harmlessly. Drop rate increases with each wave.
8. **Mystery UFO.** A red bonus saucer crosses the top of the screen on a semi-random schedule (roughly every 15–25 s of play), never during interstitials. Shooting it awards a random bonus (e.g. 50–300 pts in 50-pt steps) displayed as floating text at the kill position.
9. **Waves, lives & invasion.** The player starts with 3 lives shown on the HUD. Losing all lives shows a game-over screen with final score and a restart option. Clearing the grid triggers a brief "Wave N" interstitial, then a fresh full formation that starts one step lower (down to a sane floor) with a faster march and bomb rate. If any alien reaches the cannon's row, the run ends immediately (invasion), regardless of remaining lives.
10. **Persistent hi-score.** The HUD shows score, hi-score, lives, and wave. The hi-score is stored in `localStorage`, updated only when beaten, and must survive a full page reload.
11. **Game states.** A clean state flow: title screen (with controls + score legend) → playing → wave-clear interstitial → game over → back to title/restart. Include a pause key (P or Esc) that freezes all motion. No console errors in any state.
12. **Sign-off:** the finished solution must display, somewhere easy to spot, the date and time it was produced and the model/author that produced it (e.g. a header comment in the source, a footer on the page, or an about line on the title screen).

## Constraints

- Everything lives in ONE `.html` file; it must run from `file://` by double-clicking — that's the entire install procedure.
- Third-party libraries ARE allowed for this challenge (via CDN `<script>` tag or inlined source), but none are required — vanilla canvas is sufficient. If you use any, the game must still load and play correctly; prefer inlining so it works fully offline.
- Storage is `localStorage` only; no cookies, no IndexedDB, no servers, no external assets (sprites come from inline bitmap data; any sound must be synthesized with the Web Audio API).
- Fixed logical playfield (e.g. 480×560) scaled to fit the window is fine; it must remain playable in a typical laptop browser window.
- Target a stable 60 fps with `requestAnimationFrame`; clamp the frame delta so a hiccup can't teleport bullets through aliens.

## Sample Data / Inputs

Classic-style sprites you may use as-is or adapt (`X` = filled pixel):

```js
const SQUID = [ // 30 pts, top row
  "...XX...",
  "..XXXX..",
  ".XXXXXX.",
  "XX.XX.XX",
  "XXXXXXXX",
  "..X..X..",
  ".X.XX.X.",
  "X.X..X.X",
];
const CRAB = [ // 20 pts, middle rows
  "..X.....X..",
  "...X...X...",
  "..XXXXXXX..",
  ".XX.XXX.XX.",
  "XXXXXXXXXXX",
  "X.XXXXXXX.X",
  "X.X.....X.X",
  "...XX.XX...",
];
const OCTOPUS = [ // 10 pts, bottom rows
  "....XXXX....",
  ".XXXXXXXXXX.",
  "XXXXXXXXXXXX",
  "XXX..XX..XXX",
  "XXXXXXXXXXXX",
  "...XX..XX...",
  "..XX.XX.XX..",
  "XX........XX",
];
```

Suggested tuning (adapt freely, but the ratios must hold):

```js
const MARCH_MS_FULL = 700;   // step interval with 55 aliens alive
const MARCH_MS_LAST = 70;    // step interval with 1 alien alive
const BOMB_MS = [1400, 700]; // random drop interval range, shrinks per wave
const UFO_EVERY_MS = [15000, 25000];
const UFO_BONUS = [50, 100, 150, 200, 300];
// march interval scales with living aliens, e.g.:
// interval = MARCH_MS_LAST + (MARCH_MS_FULL - MARCH_MS_LAST) * (alive / total)
```

## Deliverable

- Exactly one file: `index.html` (inline `<style>` and `<script>`).
- Run: open `index.html` in any modern browser (Chrome/Firefox/Safari/Edge). No commands required.

## Done When

- [ ] Double-clicking `index.html` opens a title screen with controls and the score legend; Space starts the run.
- [ ] The full formation stomps side-to-side in discrete steps and drops/reverses at the edges.
- [ ] Killing aliens audibly/visibly accelerates the march; the last alien moves dramatically faster than the full grid.
- [ ] Only one player bullet can be on screen at a time; mashing fire while it's airborne changes nothing.
- [ ] Bunkers erode pixel-by-pixel from both player bullets and alien bombs, and remaining pixels keep blocking shots.
- [ ] Alien bombs (at least two visually distinct types) fall; a hit on the cannon costs one of 3 lives.
- [ ] The UFO crosses the top periodically and pays a visible random bonus when shot.
- [ ] Clearing the grid advances to a faster, lower-spawning wave; the wave number is on the HUD.
- [ ] An alien reaching the cannon row ends the run immediately, even with lives left.
- [ ] Reload the page after a run: the hi-score persists and only updates when beaten.
- [ ] Pause freezes everything; no console errors in any state.

## Stretch Goals (optional)

- The classic 4-note descending bass loop, synthesized with the Web Audio API, whose tempo tracks the march speed-up (plus a mute toggle).
- Shot-tracking UFO payout: reproduce the arcade trick where the bonus is forced to 300 pts on the 23rd player shot of a wave.
- Bunker damage carries over between waves (no repairs) until the run ends.
- Simple touch controls (drag to move, tap to fire) so the game is playable on a phone.
