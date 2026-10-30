# Castle Toss — Slingshot Physics Siege

**Difficulty:** medium  |  **Stack:** HTML/CSS/JS (single file, vanilla)  |  **Estimated time:** 1–3 h

## The Problem
Siege puzzlers are applied physics: drag an arm, launch a boulder, and topple hand-built forts. Without a stable integrator and believable stacking, towers jitter or never fall — build a fixed-step rigid-body slinger with 8 hand-tuned forts.

## Requirements
1. Canvas scene with slingshot (drag within radius to aim, trajectory dotted preview), 3 ammo types across levels: Boulder (heavy), Scatter (splits into 3 mid-flight on click/tap), Swift (fast, low gravity effect).
2. Custom 2D physics from scratch (no library): AABB/round bodies, gravity, impulse collisions, friction/restitution, fixed 120 Hz substeps; blocks (wood/stone/glass with distinct HP) topple and break.
3. Enemy sentries (circles) pop when crushed or falling >threshold; level clears when all sentries pop; shots-limited stars (1–3) per level.
4. 8 built-in levels defined inline (block list + sentry list + par shots); level select bar with locked/unlocked progression and star display.
5. Slingshot band stretch animation, dust puff particles on impacts, screen shake scaled by impact, WebAudio thwack/crash/pop via oscillators.
6. HUD (level, shots left, score, stars), pause, win/fail overlays with retry/next.
7. Persist stars + bests per level in localStorage.
8. **Sign-off:** the page footer must display the date and time the solution was produced and the model/author that produced it.

## Constraints
- Single `castle-toss.html`, vanilla only, no physics library, no network.
- Physics hand-rolled and stable: towers at rest must not drift/jitter; tunneling prevented via substeps.
- All art procedural on canvas; no external images.

## Sample Data / Inputs
Level format inline:
```js
{ammo:['boulder','boulder','swift'], blocks:[{x:600,y:400,w:40,h:120,mat:'wood'},...], sentries:[{x:650,y:300},...], par:3}
```

## Deliverable
- `castle-toss.html` (single file)
- Run: double-click `castle-toss.html`, or `python3 -m http.server 8000` then open `http://localhost:8000/castle-toss.html`

## Done When
- [ ] Drag-aim with trajectory preview and 3 distinct ammo behaviors work
- [ ] Hand-rolled physics topples/breaks forts without resting jitter
- [ ] Sentry pop, win/fail, and 1–3 star scoring per par behave
- [ ] 8 levels with lock/unlock progression load from inline data
- [ ] Particles, shake, sound, pause, and persistence all function
- [ ] Footer sign-off with date/time + author is visible

## Stretch Goals (optional)
- Level editor: drag blocks and export JSON to clipboard
- Wind gusts shown by flag that push Swift shots
- Slow-mo toggle on final killing blow
