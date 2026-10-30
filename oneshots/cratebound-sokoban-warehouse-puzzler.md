# Cratebound — Sokoban Warehouse Puzzler

**Difficulty:** easy  |  **Stack:** HTML/CSS/JS (single file, vanilla)  |  **Estimated time:** 30–60 min

## The Problem
Warehouses need foolproof push-plans: a worker can only push one crate at a time and can't pull. Cratebound is a tiny Sokoban that teaches planning under irreversible moves — push all crates onto docks with the fewest pushes, with undo/restart when you box yourself in.

## Requirements
1. Render a tile grid (wall / floor / dock / crate / crate-on-dock / player) on canvas or DOM grid, with distinct colors and a move + push counter HUD.
2. Move with Arrow keys + WASD, block walking into walls and pushing two crates or a crate into a wall.
3. Push detection: stepping into a crate moves it if the cell beyond is free floor/dock; increment pushes separately from moves.
4. Win detection: all docks covered → overlay banner with moves/pushes and "Next level" button.
5. Ship 5 built-in levels of increasing size (selectable via buttons 1–5); embed levels as inline ASCII maps using `#` wall, ` ` floor, `.` dock, `$` crate, `@` player, `*` crate-on-dock.
6. Undo (U key + button, unlimited history) and Restart level (R key + button).
7. Persist best moves/pushes per level in localStorage and show them on the level-select bar.
8. **Sign-off:** the page footer must display the date and time the solution was produced and the model/author that produced it.

## Constraints
- Single `cratebound.html` file, vanilla HTML/CSS/JS only, no dependencies, no network, no build step.
- Storage only via localStorage. All levels inline — no fetch.
- Must run by double-clicking the file or via any static server.

## Sample Data / Inputs
Level 1 map (5x5):
```
#####
#.+ #
# $ #
#@  #
#####
```
Legend: `#` wall, ` ` floor, `.` dock, `$` crate, `@` player. Level 5 must be at least 9x9 with ≥4 crates.

## Deliverable
- `cratebound.html` (single file)
- Run: double-click `cratebound.html`, or `python3 -m http.server 8000` then open `http://localhost:8000/cratebound.html`

## Done When
- [ ] Grid renders with visibly distinct tiles and HUD counters
- [ ] Arrow/WASD movement, pushes, and wall/double-push blocking all work
- [ ] Win banner appears only when all docks are covered, with Next-level flow
- [ ] 5 switchable levels load correctly; Undo and Restart work
- [ ] Best scores persist across reload via localStorage
- [ ] Footer sign-off with date/time + author is visible

## Stretch Goals (optional)
- Push-only step sound via WebAudio oscillator (no assets)
- Move-animation tween between tiles
- Share-level-code box that base64-encodes a custom ASCII map
