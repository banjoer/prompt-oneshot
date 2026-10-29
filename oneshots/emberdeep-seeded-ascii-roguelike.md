# Emberdeep: A Seeded ASCII Roguelike in a Single HTML File

**Difficulty:** extreme  |  **Stack:** HTML/CSS/JavaScript — one self-contained `.html` file, no build step  |  **Estimated time:** 8–14 hours

## The Problem

The traditional roguelike is a rite of passage for systems programmers: procedural map generation, field of view, a turn scheduler, combat math, and monster AI must interlock correctly or the whole game falls apart — and because everything is turn-based and grid-bound, every subsystem is independently verifiable. Adding a seeded RNG turns the game into a benchmark: identical inputs must produce identical runs, which is exactly how classic roguelikes are speedrun, shared, and debugged. Your job is to build **Emberdeep**, a complete traditional roguelike — six procedurally generated floors, shadowcasting field of view with fog-of-war memory, melee and ranged combat, five monster archetypes with genuinely different brains, potions and XP, permadeath, and a run summary — that runs by double-clicking a single `.html` file. No engine, no bundler, no server: one file, opened from disk, played with the keyboard.

## Requirements

1. **Single-file launch.** The entire game ships as one `.html` file with all CSS and JavaScript inline. Double-clicking it (a `file://` URL) in a current Chrome or Firefox opens the game with zero console errors, zero build steps, and zero network requests.
2. **Start screen & seed input.** The first screen shows the title, a controls summary, and a text input for the run **seed**, prefilled with a random suggestion. Pressing Enter starts the run; an empty seed or an edited seed both work. The seed is shown in the HUD for the whole run and again in the end-of-run summary.
3. **Seeded determinism.** All randomness — dungeon generation, spawning, item rolls, monster AI decisions, combat rolls — comes from one seeded PRNG stream created at run start from the seed string (use the reference implementation in Sample Data, or an equivalent documented seeded PRNG). `Math.random()` must not appear in game logic, and no wall-clock dependence is allowed. Floors may be generated lazily on first entry, which stays deterministic because floor entry order is fixed. Consequence: the same seed plus the same keystroke sequence yields identical maps, identical message logs, and identical run summaries in two separate browser sessions.
4. **Screen layout.** One screen with no page scrolling at 1280×800: a **72×40 tile map**, a **HUD panel** (HP current/max, level, XP current/needed, floor, power, defense, arrows, seed, and the numbered inventory list), and a **message log** showing at least the last 7 messages, newest last. ASCII/monospace glyphs with a cell size of at least 14px; canvas or DOM rendering are both acceptable.
5. **Dungeon generation.** Each floor is generated with BSP (recommended) or any algorithm satisfying these observable properties: 6–12 rectangular rooms (4–12 tiles wide, 4–9 high, 1-tile wall margin); rooms connected by 1-wide L-shaped corridors such that every room is reachable from every other; no overlapping rooms. The player starts at the center of the first-created room; the stairs-down `>` sit at the center of the room with the greatest BFS path distance from the player's room. Floors 1–5 have stairs; floor 6 instead holds **the Emberheart** (`&`) at that farthest-room position. Descending is one-way (no stairs-up).
6. **Field of view & fog of war.** Implement recursive shadowcasting (or an equivalently behaved 8-octant algorithm) with radius 8 around the player: tiles in line of sight are lit, wall tiles block sight and cast real shadows (a tile directly behind a wall relative to the player is not visible). Every tile is in one of three states: **unexplored** (rendered black/blank), **explored but not currently visible** (remembered layout rendered at ≤40% brightness, monsters not shown), and **visible** (full brightness, monsters and items shown). FOV recomputes after every turn.
7. **Turn loop & controls.** Strictly turn-based: a player action that consumes a turn triggers one action per living monster (in spawn order), then FOV recompute, then repaint. Keys: arrows/`hjkl` cardinal, `yubn` diagonal, `.` (or numpad 5) wait, `f` fire an arrow, `1`–`9` drink the potion in that inventory slot, `>` or Enter descend while standing on stairs. Bumping a wall costs no turn; bumping a monster is a melee attack. Walking onto an item picks it up automatically. Moving, attacking, waiting, firing, drinking, and descending each consume exactly one turn. Keys pressed while monsters act must be neither lost nor double-processed.
8. **Player stats & combat math.** The player starts with HP 30, power 4, defense 1, accuracy 80, evasion 10, 8 arrows, level 1, XP 0. All attacks (player and monster) use: hit chance `= clamp(attacker.accuracy − defender.evasion, 5, 95)` percent; a hit deals melee damage `max(1, attacker.power − defender.defense + rint(0,2))`. Player ranged attacks consume one arrow, target the nearest visible monster (ties broken in reading order: top-to-bottom, left-to-right), deal `max(1, power − target.defense + rint(0,1))`, and subtract 3 from the hit chance per Chebyshev tile of distance beyond 3. Firing with no arrows or no visible monster prints a message and consumes no turn. Line of sight for targeting uses the same shadowcasting routine centered on the shooter.
9. **Monsters & AI.** Five archetypes with the exact stats from the Sample Data table and visibly distinct behavior:
   - **Gnawer Rat — wanderer:** moves to a random free adjacent tile until the player is within Chebyshev distance 6 with LOS, then chases via BFS shortest path.
   - **Skittering Kobold — coward:** when the player is within Chebyshev 4 with LOS, moves to the free adjacent tile with the greatest Chebyshev distance from the player; if no such tile exists and the player is adjacent it attacks, otherwise it stays put; otherwise it wanders.
   - **Goblin Stalker — hunter:** when it sees the player it records the player's tile and pathfinds (BFS) toward the most recently seen position every turn, attacking when adjacent; on reaching a remembered tile without seeing the player it forgets and wanders.
   - **Mire Spitter — ranged kiter:** with LOS at Chebyshev 2–6 it spits (a ranged attack using its own stats and the same formulas); if adjacent to the player it moves away like a kobold and does not attack that turn; with LOS beyond 6 it steps closer via BFS; otherwise it wanders.
   - **Bonecrusher Ogre — slow brute:** chases like the Stalker but acts only on every second player turn.
   Monsters never stack: if a chosen tile is occupied, the monster tries the remaining best alternatives in the deterministic direction order NW, N, NE, W, E, SW, S, SE, and stays put if all are blocked. BFS uses 8-directional movement with uniform cost.
10. **Items & potions.** Each floor spawns `rint(2,4)` items (table in Sample Data) on free floor tiles outside the player's starting room. Potions (`!`, color-coded by type) enter the numbered inventory list and are drunk with their digit key: **Crimson Draught** heals 40% of max HP, **Ember Tonic** grants permanent +1 power, **Iron Tonic** grants permanent +1 defense. **Arrow bundles** add 5 arrows immediately. Every pickup and every drink writes a message to the log, and drinking consumes a turn.
11. **XP & levels.** Killing a monster awards its XP value. XP needed for the next level is `20 × current level`; excess XP carries over. Level-up grants max HP +6 (and heals 6), power +1, and every third level (3, 6, 9, …) also defense +1, with a log message.
12. **Six floors & difficulty scaling.** A run spans floors 1–6 with the per-floor monster counts and spawn weights in the Sample Data table; monsters spawn on free floor tiles in rooms other than the player's starting room, at Chebyshev distance ≥ 6 from the player's start (relax the distance rule only after 100 failed random tries). Descending prints a message and increments the floor counter. Walking onto the Emberheart on floor 6 wins the run.
13. **Permadeath & run summary.** There is no save/load: refreshing the page abandons the run. When the player dies, a full-screen summary shows: seed, outcome (slain/victorious), floor reached, level, XP, total kills plus per-archetype kill counts, turns taken, total damage dealt, total damage taken, and the cause of death (e.g. "slain by a Mire Spitter on floor 3"). The victory screen shows the same summary. From either screen: Enter starts a new run with the same seed, `r` starts a run with a new random seed.
14. **Message log.** Every attack (hit/miss, damage amount, attacker and target names), every kill, every pickup and drink, every level-up, every descent, and the death line each produce exactly one log message, color-coded by category (player actions light, incoming damage red, items green, level-ups yellow). Sample phrasing is in Sample Data; the last ≥7 messages are always visible.
15. **Performance.** One full turn — input handling, all monster actions, FOV recompute, and repaint — must complete in under 16 ms on a typical modern laptop: no per-turn layout thrash, no full-DOM rebuilds, and no perceptible delay or lost/doubled input when keys are held down or mashed.
16. **Sign-off:** the start screen must carry a visible footer line giving the date and time the solution was produced and the model/author that produced it (e.g. `built by <model> · 2026-10-29 14:32`), and the same credit must appear as an HTML comment on the first lines of the file.

## Constraints

- Exactly one `.html` file; all CSS/JS inline; no build step, no modules imported from disk, no external fonts or images. It must run from a `file://` double-click in a current Chrome or Firefox.
- Vanilla JS is strongly preferred. At most one third-party library (e.g. rot.js) may be used, via a CDN `<script>` tag or inlined; if used it must be named in the top-of-file comment — and remember the game will be graded offline, by double-click.
- No network calls, no servers, no analytics. Storage: none required; `localStorage` may only prefill the last-used seed string — never to save or resume a run (permadeath is absolute).
- All randomness flows through the documented seeded PRNG; `Math.random()` is forbidden in game logic (allowed only to suggest the prefilled seed on the start screen); the wall clock may only appear in the sign-off line.
- Keyboard-only input; ES2020+ browser APIs (canvas, etc.) are fine.

## Sample Data / Inputs

**Seeded PRNG reference** (hash the seed string, then mulberry32; the `rint` used by every formula above is defined here):

```js
function seedFromString(str) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
// rint(rng, lo, hi): inclusive integer = lo + Math.floor(rng() * (hi - lo + 1))
// Weighted picks: roll rng() * totalWeight, walk the table in its listed order.
```

**Monster table:**

| Glyph | Name | HP | Pow | Def | Acc | Eva | XP | AI | First floor |
|-------|------|----|-----|-----|-----|-----|----|----|-------------|
| `r` | Gnawer Rat | 6 | 3 | 0 | 70 | 15 | 5 | wander → chase (sight 6) | 1 |
| `k` | Skittering Kobold | 8 | 3 | 0 | 75 | 20 | 8 | flee (sight 4) | 1 |
| `g` | Goblin Stalker | 12 | 4 | 1 | 75 | 10 | 12 | chase with memory | 1 |
| `s` | Mire Spitter | 10 | 4 | 0 | 80 | 5 | 14 | ranged (2–6), kites | 2 |
| `O` | Bonecrusher Ogre | 26 | 7 | 2 | 70 | 0 | 30 | chase, acts every 2nd turn | 4 |

**Per-floor spawns** (monster count, then weighted archetype picks):

| Floor | Count | Weights (rat/kobold/goblin/spitter/ogre) |
|-------|-------|------------------------------------------|
| 1 | 6 | 5/3/2/0/0 |
| 2 | 8 | 4/3/3/1/0 |
| 3 | 10 | 2/3/4/2/0 |
| 4 | 12 | 0/2/4/3/1 |
| 5 | 14 | 0/0/4/4/2 |
| 6 | 16 | 0/0/4/4/3 |

**Item table** (per floor: `rint(2,4)` items, weighted):

| Glyph | Item | Weight | Effect |
|-------|------|--------|--------|
| `!` | Crimson Draught | 45 | inventory potion: heal 40% of max HP |
| `!` | Ember Tonic | 15 | inventory potion: +1 power, permanent |
| `!` | Iron Tonic | 15 | inventory potion: +1 defense, permanent |
| `\|` | Arrow Bundle | 25 | +5 arrows, immediate |

**Level table** (XP to next level = 20 × current level):

| Level | 1→2 | 2→3 | 3→4 | 4→5 | 5→6 |
|-------|-----|-----|-----|-----|-----|
| XP needed | 20 | 40 | 60 | 80 | 100 |

**Sample log lines** (phrasing may differ; information content may not):

```
You hit the Goblin Stalker for 5.
The Gnawer Rat misses you.
The Mire Spitter spits at you for 3.
You drink the Crimson Draught. (+11 HP)
Welcome to level 3! (+6 max HP, +1 power, +1 defense)
You descend to floor 4.
You are slain by the Bonecrusher Ogre.
```

**Suggested test seeds:** `EMBER-01`, `delve-42`, `permadeath` — plus a blank/random seed.

## Deliverable

- `emberdeep.html` — the entire game, one file.
- Run it: double-click the file (or `File → Open` in Chrome/Firefox). No server, no install, no commands.

## Done When

- [ ] The single file opens via `file://` double-click with no console errors and shows the start screen: seed input, controls, and the sign-off footer.
- [ ] Two fresh browser sessions started with seed `EMBER-01` display identical floor-1 layouts (verified by exploring both and comparing the remembered map) and identical monster letters/positions once those areas become visible.
- [ ] Every floor's rooms are all reachable from the start room; stairs `>` appear on floors 1–5 in a room far from the start; floor 6 has the Emberheart instead of stairs.
- [ ] FOV is visibly real: a lit radius around the player, walls blocking sight with shadows behind them (peek around a corner — the far side stays dark), remembered tiles rendered dimmed, unexplored tiles black, monsters hidden outside the lit area.
- [ ] Bump-melee works: the log shows hit/miss lines with damage numbers, and a dead rat vanishes and awards its XP.
- [ ] `f` fires an arrow at the nearest visible monster (arrow count decrements, log line, damage applies); with no arrows or no visible monster it prints a message and no turn passes (monsters do not move).
- [ ] AI is observably distinct: the goblin beelines across a lit room toward you and follows you out of sight to your last position; the kobold backs away as you approach and attacks only when cornered; the spitter stops at range, spits (you take damage from a non-adjacent monster), and retreats when you close in; the rat meanders until you are near; the ogre (floor 4+) visibly moves only every other turn.
- [ ] Potions picked up appear in the numbered inventory; pressing the digit drinks the correct one, applies the exact effect, logs it, and consumes a turn.
- [ ] Level-ups occur at exactly 20/40/60/… XP with the stated stat gains and a log line; excess XP carries over.
- [ ] Descending generates a fresh floor, increments the floor counter, and increases monster counts per the table; walking onto the Emberheart on floor 6 shows the victory summary.
- [ ] Death shows the permadeath summary with every listed field (seed, outcome, floor, level, XP, kills total and per archetype, turns, damage dealt/taken, killer); Enter restarts with the same seed and produces the identical floor 1; `r` starts a new random seed.
- [ ] Refreshing mid-run loses the run permanently (no save scumming).
- [ ] The whole UI — 72×40 map, HUD, 7-line log — fits in a 1280×800 window without scrolling, and held-down or mashed keys never drop or double-fire turns.

## Stretch Goals (optional)

- **Light & hunger clocks:** a torch that shrinks the FOV radius as it burns (refill with oil flasks) and a food timer that forces pace — both still fully deterministic under the seed.
- **The Necromancer:** a sixth archetype (floors 5–6) that keeps its distance and raises any corpse in its line of sight as a skeleton, once per corpse.
- **Juice without breaking determinism:** WebAudio blips for hits/pickups and a 100 ms arrow-flight animation — purely cosmetic layers on top of the deterministic simulation.
