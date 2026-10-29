# Brickstorm Breakout

**Difficulty:** medium  |  **Stack:** JavaScript (browser, canvas)  |  **Estimated time:** 1–3 hours

## The Problem

Arcade classics survive because their core loop is trivial to learn and hard to master — but a half-built Breakout clone is worse than none: balls that tunnel through bricks, paddles that deflect randomly, and scores that vanish when the tab closes all ruin the feel. Your job is to build a complete, polished, single-file Breakout game that runs in any modern browser: real paddle/ball physics with angle control, multiple hand-designed levels, a lives system, and a best score that survives page reloads.

## Requirements

1. **Single-file game.** The entire game ships as one self-contained `index.html` (inline CSS and JS) that renders on a `<canvas>` element and runs by simply opening the file in a browser — no server, no build step.
2. **Paddle & ball physics.** The paddle moves horizontally, controlled by both the mouse and the Left/Right arrow keys. The ball bounces off the two side walls and the ceiling, and off the paddle with a reflection angle that varies based on where it strikes the paddle (center ≈ straight up, edges ≈ steep angle, capped so the ball never travels horizontally forever).
3. **Bricks with hit points.** Bricks are arranged in a grid near the top. A brick takes 1–3 hits to destroy, with its remaining hit points visible at a glance (e.g. distinct colors per durability, visibly dimming/cracking as it takes damage). Multi-hit bricks award more points.
4. **At least 3 levels, defined as data.** Brick layouts are declared as plain arrays/strings in the code (one layout per level), not generated purely at random. The three bundled layouts must be visibly distinct (e.g. a solid wall, a pyramid, a checkerboard/ring). When every breakable brick is cleared, the game advances to the next level with a brief "Level N" interstitial and a slightly faster ball. After the final level, show a victory screen.
5. **Lives & game over.** The player starts with 3 lives, shown on the HUD. A ball falling below the paddle costs one life and respawns served on the paddle; losing the last life shows a game-over screen with the final score and a restart option.
6. **Score & persistent best.** The HUD shows current score, lives, and level. Brick values are fixed and visible in the code (suggested: 1-hit = 50, 2-hit = 100, 3-hit = 150). The all-time best score is saved to `localStorage`, displayed next to the current score, and updated only when beaten — it must survive a full page reload.
7. **Game states.** A clear state flow: title/start screen → playing → paused (Space or P) → level-clear interstitial → game over / victory → back to start. The ball must never move before the player launches it (click or Space) after each serve.
8. **No runaway states.** The ball's speed stays within sane bounds (minimum vertical component so it can't bounce nearly-flat forever; maximum total speed so it can't tunnel through bricks at typical 60 fps frame steps).
9. **Sign-off:** the finished solution must display, somewhere easy to spot, the date and time it was produced and the model/author that produced it (e.g. a header comment in the source, a footer on the page, or an about line on the title screen).

## Constraints

- Vanilla HTML/CSS/JavaScript only — no libraries, no frameworks, no CDNs, no network calls, no external assets (draw everything with canvas primitives; any sound, if added, must be synthesized with the Web Audio API).
- Storage is `localStorage` only; no cookies, no IndexedDB, no servers.
- Fixed logical canvas size (e.g. 800×600) is fine; it must remain playable in a typical laptop browser window.
- Must work from `file://` — double-clicking `index.html` is the full install procedure.
- Target a stable 60 fps using `requestAnimationFrame`; keep the physics step consistent even if a frame is late (clamp the delta).

## Sample Data / Inputs

Suggested level format (you may adapt it, but layouts must stay data-driven):

```js
// '#' = 1-hit brick, 'o' = 2-hit, '@' = 3-hit, '.' = empty
const LEVELS = [
  [
    "########",
    "########",
    "########",
  ],
  [
    "...##...",
    "..#oo#..",
    ".#@oo@#.",
    "..#oo#..",
    "...##...",
  ],
  [
    "@.#..#.@",
    "o.#@@#.o",
    "@.#..#.@",
    "........",
    "##o##o##",
  ],
];
```

Suggested scoring: `#` = 50 pts, `o` = 100 pts, `@` = 150 pts.

## Deliverable

- Exactly one file: `index.html` (inline `<style>` and `<script>`).
- Run: open `index.html` in any modern browser (Chrome/Firefox/Safari/Edge). No commands required.

## Done When

- [ ] Double-clicking `index.html` opens a title screen; clicking/Space launches the ball.
- [ ] Paddle follows both mouse and arrow keys without leaving the canvas.
- [ ] Ball bounce angle off the paddle visibly depends on hit position.
- [ ] Multi-hit bricks change appearance when damaged and award the correct points.
- [ ] Clearing all bricks advances to a new, visibly different layout at least twice, ending in a victory screen.
- [ ] Ball falling past the paddle costs a life; three lost balls end the game with a restartable game-over screen.
- [ ] Score, lives, level, and best score are all visible during play.
- [ ] Reload the page after a run: the best score is still shown and only updates when beaten.
- [ ] Pause (Space or P) freezes the ball; no console errors at any point.

## Stretch Goals (optional)

- Power-up capsules dropped by some bricks (wide paddle, multi-ball, slow ball) with on-screen effect timers.
- Synthesized blip sounds (paddle hit, brick hit, life lost) via the Web Audio API, with a mute toggle.
- A tiny built-in level editor: a fourth "Custom" level editable via a text area on the title screen, validated before play.
