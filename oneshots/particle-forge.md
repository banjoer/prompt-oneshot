# Particle Forge — Interactive Cursor Particle Playground

**Difficulty:** medium  |  **Stack:** HTML/CSS/JS (Canvas 2D, vanilla)  |  **Estimated time:** 1–3 hours

## The Problem

Creative-coding demos are the best way to *feel* physics: velocity, forces,
and decay stop being equations and start being something you can push around
with your hand. But most particle demos online are either minified toys you
can't tweak, or heavyweight WebGL frameworks that need a build step. What's
missing is a middle ground: a single, dependency-free page where moving your
cursor spawns a swarm of glowing particles, and a small control panel lets you
switch the laws of physics live — rain them down with gravity, blow them
sideways with gusty wind, or scatter them away from your pointer like a
repulsor field. Build that playground.

## Requirements

1. The solution is a single `index.html` file (embedded `<style>` and
   `<script>`) that runs by simply opening it in a modern browser — no
   server, no build step, no dependencies.
2. A full-viewport `<canvas>` renders the simulation via the Canvas 2D API
   and a `requestAnimationFrame` loop. The canvas resizes to fill the window
   when the browser is resized, without crashing or distorting existing
   particles.
3. Particles spawn continuously at the pointer position while the pointer
   moves over the canvas (use Pointer Events so mouse *and* touch work), at
   a configurable spawn rate. Pressing/tapping the canvas emits an instant
   burst of ~25 particles at that spot, each with a randomized initial
   velocity.
4. Every particle has position, velocity, radius, hue, and remaining
   lifetime. Each frame it integrates its velocity, applies the active
   force mode, ages, and is rendered as a filled circle (glow/shadow
   optional).
5. A **force mode** selector offers exactly three modes, one active at a
   time, switchable at any moment and applied immediately to all live
   particles:
   - **Gravity** — constant downward acceleration.
   - **Wind** — horizontal acceleration that gusts (e.g. strength modulated
     by a sine wave over time, occasionally reversing direction).
   - **Repel** — particles are accelerated away from the current pointer
     position, with strength falling off with distance (no effect when the
     pointer is far away).
6. **Color cycling:** each particle's hue advances continuously over its
   lifetime (rendered with `hsl()`), so a single particle visibly shifts
   color as it travels; particles also fade out (alpha decreases) as they
   approach death.
7. **Lifecycle & performance guard:** particles die when their lifetime
   expires and are removed from the simulation. Enforce a hard cap of 1500
   live particles — when the cap is reached, the oldest particles are
   culled first. The page must stay smooth (no visible stutter) at the cap.
8. A compact **control panel** (fixed in a corner, not covering the whole
   canvas) provides:
   - the three-mode selector (buttons or segmented control, active mode
     visibly highlighted),
   - labeled sliders with live numeric readouts for: **spawn rate**
     (0–200 particles/sec), **force strength** (0–100%), **particle size**
     (1–12 px), **lifetime** (0.5–6 s) — all applied live, no Apply button,
   - a **Pause** button that freezes the simulation (particles stop moving
     and aging, spawning stops, the button label toggles to "Resume") while
     keeping the panel fully interactive,
   - a **Clear** button that instantly removes all particles (works both
     while running and while paused, repainting an empty canvas).
9. A small stats readout (in the panel or a corner) shows the current live
   particle count and a smoothed FPS value, updated at least twice per
   second.
10. **Sign-off:** the finished page must display, somewhere easy to spot
    (e.g. a footer or a line in the control panel), the date and time it was
    produced and the model/author that produced it; also include this as a
    header comment at the top of the source.

## Constraints

- Single `index.html` file: embedded `<style>` and `<script>`, no external
  files, fonts, libraries, or frameworks.
- Vanilla HTML/CSS/JS with the Canvas 2D API only — no WebGL, no build
  tooling.
- No network calls of any kind; works fully offline via `file://` by
  double-clicking the file.
- Storage, if used at all (see stretch goals), is `localStorage` only.
- Must run in a current Chrome/Firefox/Safari without console errors.

## Sample Data / Inputs

No external data needed. Default starting state:

| Setting         | Default   |
|-----------------|-----------|
| Force mode      | Gravity   |
| Spawn rate      | 80 / sec  |
| Force strength  | 50 %      |
| Particle size   | 4 px      |
| Lifetime        | 2.5 s     |

Manual test script — expected observations:

1. Move the pointer in slow circles → a ribbon of particles trails the
   cursor; each particle visibly drifts through hues as it fades.
2. Switch to **Wind** → the whole swarm is pushed sideways in visible
   gusts that periodically weaken and reverse.
3. Switch to **Repel** and sweep the pointer through the swarm → nearby
   particles scatter away from the cursor, distant ones are unaffected.
4. Click and hold one spot → repeated bursts; the particle counter climbs
   but never exceeds 1500, and FPS stays near 60.
5. Hit **Pause** → everything freezes mid-flight; move sliders and confirm
   the panel still responds; hit **Clear** → canvas empties while paused.
6. Hit **Resume** → remaining particles continue from exactly where they
   froze.

## Deliverable

- `index.html` — the complete playground.
- Run: open `index.html` in any modern browser (no server needed).

## Done When

- [ ] Opening the file shows a full-window canvas and a control panel; moving the cursor spawns a visible particle trail.
- [ ] All three force modes are selectable, the active one is highlighted, and switching modes instantly changes the motion of *existing* particles (gravity falls, wind gusts sideways, repel scatters from the pointer).
- [ ] Each particle visibly cycles through colors and fades out before disappearing; the particle count never exceeds 1500.
- [ ] All four sliders update the simulation live with numeric values shown next to their labels.
- [ ] Pause freezes motion and spawning, its label toggles to "Resume", and Clear empties the canvas both while running and while paused.
- [ ] The stats readout shows a live particle count and FPS.
- [ ] Clicking/tapping emits a one-shot burst at the pointer location.
- [ ] Resizing the browser window keeps the simulation running without errors.
- [ ] The page footer (or panel) shows the production date/time and the model/author.

## Stretch Goals (optional)

- Persist all control-panel settings to `localStorage` and restore them on reload.
- Add a fourth **Attract** mode (inverse of Repel) plus a toggleable "trails" effect (clear the canvas with a translucent rectangle each frame instead of fully).
- Add a **base hue** slider that offsets the color-cycling rainbow.
