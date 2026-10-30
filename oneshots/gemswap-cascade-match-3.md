# Gemswap Cascade — Match-3 Jewel Puzzler

**Difficulty:** medium  |  **Stack:** HTML/CSS/JS (single file, vanilla)  |  **Estimated time:** 1–3 h

## The Problem
Match-3 games look simple but hide real systems work: swap validation, cascade resolution, gravity refill, and a no-dead-board guarantee. Build a juicy 8x8 jewel swapper with cascades, timed + zen modes, and persistent bests.

## Requirements
1. 8x8 board of 6 gem types rendered on canvas or DOM with distinct shapes/colors (color-blind-safe: shape differs, not just hue); click/drag or click-click to swap orthogonally adjacent gems.
2. Swap rule: only swaps creating a ≥3 match commit; illegal swaps animate and snap back.
3. Cascade loop: highlight matches → pop with shrink/fade → gravity collapse → refill from top → repeat, with combo multiplier (x1, x2, …) per cascade step.
4. No-dead-board guarantee: after cascades settle, if no legal move exists, reshuffle automatically with a "Shuffled!" toast.
5. Two modes: Zen (30 moves) and Blitz (60 seconds with +2s per 50-gem burst); scoring 60/120/240 for match-3/4/5 plus line-clear bonus for 4+ (clear whole row/col).
6. HUD (score, moves/time left, combo meter), animated score popups, pause overlay, game-over panel with restart.
7. Persist best Zen and best Blitz scores in localStorage.
8. Hint button (3 per game) that pulses a legal swap; special-gem creation on match-4 (row-blaster).
9. **Sign-off:** the page footer must display the date and time the solution was produced and the model/author that produced it.

## Constraints
- Single `gemswap-cascade.html`, vanilla only, no dependencies, no network.
- Deterministic seeded RNG (`mulberry32(seed)`) so a `?seed=` query param reproduces a board.
- 60 fps render via requestAnimationFrame; game logic must not depend on frame rate.

## Sample Data / Inputs
Gem types: `['D' diamond, 'R' ruby-square, 'E' emerald-circle, 'S' sapphire-hex, 'T' topaz-triangle, 'O' onyx-pentagon]`. Initial board must contain zero pre-made matches and at least one legal move — generate-then-fix inline.

## Deliverable
- `gemswap-cascade.html` (single file)
- Run: double-click `gemswap-cascade.html`, or `python3 -m http.server 8000` then open `http://localhost:8000/gemswap-cascade.html?seed=42`

## Done When
- [ ] 8x8 shape-distinct board renders; only match-making swaps commit
- [ ] Cascades with combo multiplier, gravity, refill, and pop animations work
- [ ] Dead boards auto-reshuffle; Hint pulses a real legal move
- [ ] Zen and Blitz modes with correct scoring, timer/moves, pause, game-over
- [ ] Best scores persist across reload; `?seed=` reproduces boards
- [ ] Footer sign-off with date/time + author is visible

## Stretch Goals (optional)
- Hammer booster (1 per game clears any single tile)
- Particle burst pool capped at 300 particles
- Color-blind palette toggle (high-contrast set)
