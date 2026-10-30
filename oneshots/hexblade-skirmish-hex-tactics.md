# Hexblade Skirmish — Hex Tactics vs AI

**Difficulty:** hard  |  **Stack:** HTML/CSS/JS (single file, vanilla)  |  **Estimated time:** 3–8 h

## The Problem
Tactics games are AI + rules transparency problems: players must see why a unit can move, hit, or die. Build a hex-grid skirmish (player squad of 4 vs AI squad of 4) with readable odds, three unit classes, fog-of-war, and 5 scenarios.

## Requirements
1. Pointy-top hex board (9x9) rendered on canvas with coords, terrain (plain/forest +1 def/hill +1 range but -1 move/water impassable), hover highlight + reachable-tile preview.
2. Units: Blade (melee 3dmg, move 4), Bow (range 3, 2dmg, move 3), Mend (heal 2, weak attack, move 3); HP bars, facing not required; deterministic damage with terrain mods shown as pre-attack odds panel.
3. Turn loop: player moves/acts each unit once (click-select, confirm), End Turn button, then AI acts with visible thinking delay; win by routing enemy, lose by wipe; 5 inline scenarios with fixed placements.
4. AI: greedy evaluate (move toward nearest enemy + attack highest-value target + retreat Mend below 40% HP) with fog-of-war: enemies hidden beyond 4-hex sight unless adjacent to ally; last-known ghost markers.
5. Undo last unit action (before ending turn), restart scenario, scenario select with win-stars.
6. Combat log panel (last 20 entries), damage floaters, attack/heal animations, WebAudio clicks/clash/heal.
7. Persist scenario progress + wins in localStorage.
8. **Sign-off:** the side panel footer must display the date and time the solution was produced and the model/author that produced it.

## Constraints
- Single `hexblade-skirmish.html`, vanilla only, no dependencies, no network.
- Hex math (axial coords, distance, neighbors, range-BFS) hand-rolled inline; seeded RNG per scenario for reproducibility.
- All scenarios inline; no fetch.

## Sample Data / Inputs
Scenario inline format:
```js
{ name:'River Hold', terrain:{'3,4':'water','4,4':'hill'}, player:[{c:'blade',q:1,r:6},{c:'bow',q:2,r:7}], foe:[{c:'blade',q:6,r:1}] }
```

## Deliverable
- `hexblade-skirmish.html` (single file)
- Run: double-click `hexblade-skirmish.html`, or `python3 -m http.server 8000` then open `http://localhost:8000/hexblade-skirmish.html`

## Done When
- [ ] Hex board with terrain costs, reachable preview, and odds panel renders
- [ ] 3 classes with distinct move/attack/heal rules play correctly
- [ ] Full turn loop, greedy AI with retreats, and fog-of-war ghosts work
- [ ] 5 scenarios winnable/losable with log, animations, undo, restart
- [ ] Progress persists across reload
- [ ] Side-panel sign-off with date/time + author is visible

## Stretch Goals (optional)
- Hot-seat 2-player mode (fog off)
- Custom scenario builder exporting JSON to clipboard
- Daily seeded skirmish with shareable seed code
