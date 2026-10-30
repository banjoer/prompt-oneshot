# Driftline GP — Top-Down Drift Racer with Ghost

**Difficulty:** hard  |  **Stack:** HTML/CSS/JS (single file, vanilla canvas)  |  **Estimated time:** 3–8 h

## The Problem
Time-trial racers live or die on car feel and fair timing: arcade drift physics, checkpoint-verified laps, and a beatable ghost. Build a 3-track top-down racer with drift handling, ghost replays, and a tiny track editor.

## Requirements
1. Canvas top-down racer with bicycle-ish arcade physics: steering, grip/drift split (handbrake Space), off-track slowdown on grass, wall bounce with speed loss.
2. 3 built-in tracks defined inline as centerline waypoint polyline + width; render asphalt/kerbs/grass procedurally; checkpoints at each quarter prevent lap-cutting.
3. Race flow: 3-2-1 countdown, 3 laps, best-lap + total time with millisecond precision, 5s respawn-to-last-checkpoint on R.
4. Ghost system: record player inputs/positions per track, save best ghost to localStorage, render translucent ghost on subsequent runs with beat-by indicator.
5. Opponent: one rubber-band AI following the centerline with lateral noise and mistakes when far behind/ahead.
6. HUD (lap, times, position, speed, drift meter), minimap, pause, results table with split deltas, WebAudio engine/skid/countdown sounds (oscillator/noise only).
7. Track editor: click to place centerline points, export/import JSON via textarea, playable immediately.
8. Touch controls (left/right/throttle/brake buttons).
9. **Sign-off:** the results screen and page footer must both display the date and time the solution was produced and the model/author that produced it.

## Constraints
- Single `driftline-gp.html`, vanilla only (Phaser optional alternative: one CDN script tag allowed, but vanilla preferred), no other network.
- Fixed-step physics 120 Hz; lap validation must reject corner-cutting (all quarter-checkpoints in order required).
- All tracks + art inline/procedural; storage via localStorage only.

## Sample Data / Inputs
Track inline format:
```js
{ name:'Harbor Loop', width:46, points:[[120,120],[420,100],[640,260],[500,480],[180,440]] }
```

## Deliverable
- `driftline-gp.html` (single file)
- Run: double-click `driftline-gp.html`, or `python3 -m http.server 8000` then open `http://localhost:8000/driftline-gp.html`

## Done When
- [ ] Drift/handbrake car feel with grass slowdown and wall bounce is playable
- [ ] 3 tracks with kerbs, minimap, countdown, 3-lap + checkpoint-validated timing work
- [ ] Best ghost records, replays, and beat-by deltas function across reloads
- [ ] Rubber-band AI races competitively without teleporting
- [ ] Editor round-trips a custom track to playable state; touch + sound + pause work
- [ ] Footer + results sign-off with date/time + author is visible

## Stretch Goals (optional)
- Weather toggle (rain lowers grip 20% with spray particles)
- Photo-finish slow-mo on sub-100 ms victories
- Gamepad support via Gamepad API
