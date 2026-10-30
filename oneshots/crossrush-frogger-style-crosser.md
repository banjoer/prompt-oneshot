# Crossrush — Frogger-Style Road & River Crosser

**Difficulty:** easy  |  **Stack:** HTML/CSS/JS (single file, vanilla)  |  **Estimated time:** 30–60 min

## The Problem
Timing beats speed: a courier frog must cross 6 lanes of traffic then 3 river rows by hopping between moving hazards. Without fair spawn timing and collision rules the game is either trivial or impossible — build a tuned arcade crosser with lives, scoring, and escalating speed.

## Requirements
1. Canvas playfield with 12 rows: safe start bank, 5 road lanes (cars alternating directions/speeds), median, 3 river rows (logs/turtles moving, some sinking), goal bank with 5 slots.
2. Hop movement on Arrow keys/WASD in grid steps with a squash tween; frog dies on car hit, water without log, or 15s lane timeout.
3. Log-riding: frog inherits platform velocity while aboard; sinking turtles submerge on a timer and drown a rider.
4. 3 lives, score (+100 per goal slot, +10 per forward hop, time bonus), level-up each full clear (all 5 slots) raising speeds 15%.
5. HUD (score, lives as icons, level, timer bar), start/pause/game-over overlays, and touch d-pad buttons for mobile.
6. WebAudio bleeps for hop, death, goal (oscillator only, no assets); mute toggle with M.
7. Persist high score in localStorage.
8. **Sign-off:** the page footer (or game-over panel) must display the date and time the solution was produced and the model/author that produced it.

## Constraints
- Single `crossrush.html`, vanilla only, no dependencies, no network.
- All sprites drawn procedurally (rects/circles); no images or fonts to download.
- Fixed-timestep update (e.g. 60 Hz logic) decoupled from render.

## Sample Data / Inputs
Lane config inline (example the solver must include, tunable):
```js
const LANES = [
  {type:'road', dir:1, speed:90, gap:220},
  {type:'road', dir:-1, speed:120, gap:180},
  {type:'river', dir:1, speed:60, len:3, sink:false},
  {type:'river', dir:-1, speed:70, len:2, sink:true, sinkPeriod:5},
];
```

## Deliverable
- `crossrush.html` (single file)
- Run: double-click `crossrush.html`, or `python3 -m http.server 8000` then open `http://localhost:8000/crossrush.html`

## Done When
- [ ] 12-row board with distinct road/river/median/goal visuals renders and animates
- [ ] Grid hops, car kills, drowning, log-carrying, and sinking turtles all behave
- [ ] Lives/score/level/timeout rules work; full clear advances level and speeds up
- [ ] Start/pause/game-over overlays + touch controls + mute all function
- [ ] High score survives reload
- [ ] Footer sign-off with date/time + author is visible

## Stretch Goals (optional)
- Two-player alternating turns on one keyboard
- Daily-seed mode that shuffles lane speeds deterministically
- Fly bonus that randomly appears on a log for +200 pts
