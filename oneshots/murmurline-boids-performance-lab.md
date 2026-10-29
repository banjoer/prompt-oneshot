# Murmurline — 1,000-Agent Boids Performance Lab

**Difficulty:** extreme  |  **Stack:** JavaScript (browser, Canvas 2D, vanilla)  |  **Estimated time:** 8–12 hours

## The Problem

Flocking is the classic stress test for spatial queries: every boid needs its
neighbors every frame, and the naive all-pairs search costs 1.44M distance
checks per frame at 1,200 agents — over 86M per second — which collapses long
before the rendering does. Game engines, crowd simulators, and VFX tools all
solve this the same way: a spatial hash (uniform grid) or quadtree that turns
neighbor lookup from O(n²) into O(n). Build an interactive flocking lab that
*proves* you can hold 1,000+ boids at ~60 FPS on the main thread — with live
tuning of the flock's physics, a predator that splits the swarm, steer-around
obstacles, a trails mode, and an instrumented HUD that exposes the spatial
index internals (candidates examined, grid occupancy) so the performance claim
is visible, not just asserted.

## Requirements

1. The solution is a single `index.html` file (embedded `<style>` and
   `<script>`) that runs by opening it in a modern browser — no server, no
   build step, no dependencies.
2. A full-viewport `<canvas>` renders the simulation via the Canvas 2D API
   with a `requestAnimationFrame` loop. The canvas resizes with the window
   without crashing or losing the flock. Each boid is rendered as a small
   oriented triangle whose rotation matches its velocity heading.
3. **Flock dynamics:** each boid steers from three weighted forces —
   separation, alignment, cohesion — computed only from neighbors within its
   perception radius. Velocity is clamped to a configurable maximum speed,
   heading follows velocity, and the world wraps toroidally (a boid exiting
   one edge re-enters the opposite edge).
4. **Population & performance target:** the simulation starts with **1,200
   boids**. A population control (slider or stepper, range 200–3,000) adds or
   removes boids live without resetting the rest. The page must hold a
   smoothed **FPS ≥ 55 (target 60) at 1,200 boids with default settings** on
   a reasonably modern laptop.
5. **Spatial hashing is mandatory.** Neighbor lookup must use a uniform grid
   (cell size ≈ perception radius) or a quadtree, rebuilt every frame —
   all-pairs iteration is forbidden. The grid cell size must track the
   perception-radius slider (adapt on change), and neighbor queries must work
   correctly across the wrap-around seam (a boid hugging the left edge sees
   boids hugging the right edge).
6. **Live tuning sliders**, each with a numeric readout, all applied on the
   very next frame with no Apply button and no reset of simulation state:
   - **Separation weight** (0–3)
   - **Alignment weight** (0–3)
   - **Cohesion weight** (0–3)
   - **Perception radius** (10–120 px)
   - **Max speed** (1–8 px/frame)
7. **Predator:** a visually distinct entity (larger, red dart/triangle) that
   wanders with smoothed steering and turns to chase the nearest boid within
   its own detection range (~250 px). Boids within a flee radius (~1.5× the
   perception radius) receive a strong escape force away from it. The predator
   can be grabbed by pointer-drag and repositioned; releasing it resumes
   autonomous behavior. A toggle enables/disables it entirely.
8. **Obstacles:** clicking empty canvas places a fixed-radius circular
   obstacle (~26 px); right-clicking removes the nearest obstacle within 40
   px; up to 40 obstacles. Boids steer around them with an avoidance force so
   they visibly bend around discs without penetrating them. Placing ≥ 30
   obstacles must not break the FPS target (obstacle lookup must also be
   sublinear — reuse the grid or an equivalent structure).
9. **Trails toggle:** when ON, each frame fades the canvas with a translucent
   fill so boids leave motion trails; when OFF, the canvas is fully cleared.
   The toggle applies live. The HUD and control panel must be **DOM overlays,
   never drawn into the canvas**, so they stay crisp with trails on.
10. **Instrumented HUD** (DOM overlay), updated 2–4 times per second, showing:
    smoothed FPS, average frame time (ms), live boid count, **average
    candidate checks per boid per frame** (grid-bucket members examined,
    before the radius test), average accepted neighbors per boid, and
    occupied grid cells. At 1,200 boids and default radius, the candidate
    average must sit in the tens — visibly nowhere near 1,200.
11. **Pause/Resume** freezes the simulation mid-frame (forces stop, panel
    stays fully interactive, button label toggles) and **Reset** reseeds the
    flock at the current population while keeping obstacles in place.
12. **Sign-off:** the finished page must display, somewhere easy to spot (a
    footer or a line in the control panel), the date and time it was produced
    and the model/author that produced it; also include this as a header
    comment at the top of the source.

## Constraints

- Single `index.html` file: embedded `<style>` and `<script>`, no external
  files, fonts, libraries, or frameworks.
- Vanilla JavaScript with the Canvas 2D API only. **No WebGL, no Web Workers,
  no OffscreenCanvas** — the performance must come from the spatial index on
  the main thread, not from hardware or threading escape hatches.
- No network calls of any kind; works fully offline via `file://` by
  double-clicking the file.
- Storage, if used at all (see stretch goals), is `localStorage` only.
- Must run in a current Chrome/Firefox/Safari without console errors.

## Sample Data / Inputs

No external data needed. Default starting state:

| Setting           | Default      |
|-------------------|--------------|
| Population        | 1,200 boids  |
| Separation weight | 1.2          |
| Alignment weight  | 1.0          |
| Cohesion weight   | 1.0          |
| Perception radius | 40 px        |
| Max speed         | 3.5 px/frame |
| Predator          | enabled      |
| Trails            | off          |

Manual test script — expected observations:

1. Load the page → a swirling flock of ~1,200 triangles forms coherent
   streams within a few seconds; HUD shows FPS near 60 and average candidates
   per boid in the tens.
2. Drag the perception-radius slider to 120 px → the flock merges into broad,
   slow ribbons; the HUD's candidate average rises but stays far below 1,200,
   and occupied cell count drops (grid adapted).
3. Set cohesion and alignment to 0 → the flock dissolves into a directionless
   gas; restore defaults → structure re-emerges.
4. Drag the predator into a dense stream → the stream splits around it and
   re-forms behind it.
5. Click to place ~20 obstacles in a cluster → boids bend around the discs;
   FPS stays within target.
6. Toggle trails ON → the flock paints fading ribbons; the HUD text stays
   perfectly crisp.
7. Pause, move every slider, resume → all changes took effect live; the flock
   continues from the frozen state.

## Deliverable

- `index.html` — the complete simulation lab.
- Run: open `index.html` in any modern browser (no server needed).

## Done When

- [ ] Opening the file shows 1,200 boids flocking in coherent streams at a smoothed FPS ≥ 55, with the HUD updating FPS, frame time, boid count, candidate checks, accepted neighbors, and occupied cells.
- [ ] The HUD's average-candidates number stays in the tens at default settings — proof the spatial hash, not brute force, is doing the lookup.
- [ ] All five tuning sliders (separation, alignment, cohesion, perception radius, max speed) change the flock's behavior live, with numeric readouts, and dragging the perception-radius slider visibly changes the grid's occupied-cell count.
- [ ] The population control moves between 200 and 3,000 boids live without resetting the simulation.
- [ ] The predator wanders, chases nearby boids, splits streams when dragged through them, and can be toggled off.
- [ ] Clicking places obstacles and right-clicking removes them; boids steer around discs without penetrating, and 30 obstacles don't break the FPS target.
- [ ] Boids wrap around all four edges, and flocks visibly interact across the seam (neighbor lookup wraps too).
- [ ] Trails toggle fades motion trails while the DOM HUD/panel stays sharp.
- [ ] Pause freezes the flock mid-flight with the panel still interactive; Reset reseeds boids but keeps obstacles.
- [ ] The page footer (or panel) shows the production date/time and the model/author.

## Stretch Goals (optional)

- **Predator eats:** boids caught by the predator are removed, with an eaten counter and a respawn control.
- **Backend benchmark:** add a quadtree implementation and a toggle to A/B it against the uniform grid, with the HUD exposing candidate counts for each.
- **Presets:** save the full slider configuration as named presets in `localStorage`, with load/delete UI.
