# Gridline Defense — Canvas Tower Defense

**Difficulty:** hard  |  **Stack:** HTML/CSS/JavaScript (Canvas, single self-contained `.html` file)  |  **Estimated time:** 4–8 hours

## The Problem

Tower defense is the quintessential real-time systems game: a simulation loop, spatial reasoning on a grid, an economy, and dozens of interacting entities with different stats — all running at 60 fps without a framework. Casual game portals are full of half-finished TD clones that collapse the moment waves scale, projectiles pile up, or the player tries to sell an upgraded tower. Building one that actually *works* — deterministic pathing, honest damage/armor math, an economy that stays balanced for 15+ waves, and a UI that communicates range, cost, and refund at a glance — is a genuine engineering exercise in state management, game-loop architecture, and canvas rendering. Your job: build the complete, playable, balanced game in ONE file.

## Requirements

1. **Single-file deliverable.** The entire game — markup, styles, and logic — lives in one `.html` file that runs by double-clicking it (opened via `file://`). No build step, no server.
2. **Grid map with fixed path.** Render a grid of at least 20×12 cells on a `<canvas>`. A fixed enemy path snakes across the grid from a spawn point to an exit (see Sample Data for the exact path). The path must be visually distinct (e.g. darker tiles), and towers may NOT be placed on path cells.
3. **Three tower types, three upgrade tiers each:**
   - **Gun Tower** — fast-firing, single-target, moderate damage. Cost: 50g.
   - **Frost Tower** — low damage, applies a slow (e.g. 35% speed reduction, 1.5 s duration; slows must not stack multiplicatively beyond a documented cap). Cost: 75g.
   - **Splash Tower** — slow-firing projectile that explodes for area damage around the impact point. Cost: 100g.
   Each tower supports **two upgrades** (Mk I → Mk II → Mk III), each tier visibly changing the tower sprite/color and improving at least two stats (damage, range, fire rate, slow strength, or blast radius). Upgrade costs must be shown before purchase.
4. **Real projectiles, real armor math.** Shots are simulated projectiles that travel toward their target (no instant hitscan), with a tracer/muzzle effect. Armored enemies reduce each hit by a flat armor value (e.g. damage taken = max(1, damage − armor)). Show floating damage numbers on hit.
5. **Gold economy.** Start with 200g. Enemies pay a bounty on kill; each completed wave pays a bonus (25g + 5g × wave number). Calling the next wave early (before the current one is cleared) grants +10% of the pending wave's bounty potential as a risk/reward bonus.
6. **Fifteen escalating waves with distinct enemy types**, exactly as defined in the Sample Data table below, including: **Grunt** (baseline), **Runner** (fast, low HP), **Bulwark** (armored, slow), **Swarmling** (many, very weak, fast spawn interval), and a **Boss** on waves 5, 10, and 15 (large HP pool, high bounty, leaks cost multiple lives). HP scales with the multiplier in the table. Spawn intervals and counts must match the spec so difficulty is reproducible.
7. **Range preview & placement feedback.** While a tower type is selected from the palette, show a translucent range ring following the cursor, tint cells green (valid) or red (invalid — on path, occupied, or unaffordable). Selecting an already-built tower also shows its range ring plus its stats, upgrade options, and sell value in a side panel.
8. **Sell-back.** Any tower can be sold for **70% of total gold invested** (base cost + all upgrades paid), rounded down. Selling is immediate, with a small visual confirmation (e.g. coin burst).
9. **Lives, score, win/lose.** Start with 20 lives. Leaked enemies cost 1 life (Bosses cost 5). Score = cumulative damage dealt + bounties; display a live score. Lives ≤ 0 → game-over overlay with final score and a restart button. Surviving wave 15 → victory overlay with score and a grade (S/A/B/C by lives remaining: ≥18/≥12/≥6/<6).
10. **Speed toggle and flow controls.** A 1x/2x speed toggle that scales the whole simulation (movement, firing, spawn cadence) without changing game math; a pause button; and a "Send next wave" button that is always available. Multiple waves may overlap if sent early.
11. **HUD & polish.** Persistent HUD showing gold, lives, wave x/15, score, speed state; a tower palette with icons, hotkeys (1/2/3), costs, and affordability dimming; per-enemy HP bars; a faint path-direction indicator (arrows or chevrons) so the route is readable at a glance. The game must remain responsive (no long tasks) at 2x speed on wave 15.
12. **Sign-off:** the finished solution must display, somewhere easy to spot, the date and time it was produced and the model/author that produced it — e.g. a visible footer line on the page AND a header comment at the top of the file.

## Constraints

- **One self-contained `.html` file.** Everything inline (`<style>`, `<script>`), or third-party libraries via CDN `<script>` tags / inlined source. Libraries are allowed but not required — vanilla canvas is entirely sufficient; if you use any, list them in a comment at the top of the file.
- No network calls at runtime beyond optional CDN script loads; no external assets — all graphics drawn with canvas primitives (shapes, gradients) or emoji; audio optional (WebAudio-generated only).
- No build tools, no modules loaded from disk, no `fetch` of local files — must work from `file://` in a current Chrome/Firefox.
- Persistence (optional best-score saving) may use `localStorage` only.
- All game math must be framerate-independent (use delta time or a fixed timestep), so 1x and 2x are mathematically identical apart from speed.

## Sample Data / Inputs

**Map path (grid 20 cols × 12 rows, cell coordinates are `col,row`, 0-indexed):**
Enter at `(0,2)` → east to `(15,2)` → south to `(15,5)` → west to `(4,5)` → south to `(4,8)` → east to `(17,8)` → south to `(17,11)` → exit east off-grid at row 11. All cells along this polyline are path cells.

**Enemy archetypes:**

| Type      | Base HP | Speed (cells/s) | Armor | Bounty | Lives | Notes                          |
|-----------|--------:|----------------:|------:|-------:|------:|--------------------------------|
| Grunt     | 40      | 1.0             | 0     | 6g     | 1     | baseline                       |
| Runner    | 25      | 2.2             | 0     | 7g     | 1     | fast, low HP                   |
| Bulwark   | 120     | 0.55            | 4     | 12g    | 1     | flat 4 dmg reduction per hit   |
| Swarmling | 12      | 1.4             | 0     | 2g     | 1     | spawn interval 0.35 s          |
| Boss      | 900     | 0.45            | 3     | 120g   | 5     | waves 5/10/15; radius ~1.5 cells|

**Wave table** (`HP = base × multiplier`, spawn interval in seconds, `n` = count; groups spawn sequentially within a wave):

| Wave | Composition                                  | HP mult | Interval |
|-----:|----------------------------------------------|--------:|---------:|
| 1    | 8× Grunt                                     | 1.00    | 1.00     |
| 2    | 12× Grunt                                    | 1.10    | 0.90     |
| 3    | 10× Runner                                   | 1.00    | 0.70     |
| 4    | 8× Grunt + 4× Bulwark                        | 1.20    | 0.90     |
| 5    | 6× Grunt + **1× Boss**                       | 1.25    | 0.80     |
| 6    | 16× Swarmling                                | 1.00    | 0.35     |
| 7    | 12× Runner + 6× Grunt                        | 1.35    | 0.70     |
| 8    | 8× Bulwark                                   | 1.45    | 0.90     |
| 9    | 24× Swarmling + 6× Runner                    | 1.30    | 0.35     |
| 10   | 8× Grunt + 4× Bulwark + **1× Boss**          | 1.60    | 0.80     |
| 11   | 16× Runner                                   | 1.60    | 0.55     |
| 12   | 10× Bulwark + 10× Swarmling                  | 1.75    | 0.60     |
| 13   | 20× Runner + 10× Grunt                       | 1.85    | 0.55     |
| 14   | 30× Swarmling + 8× Bulwark                   | 2.00    | 0.35     |
| 15   | 12× Grunt + 6× Bulwark + **1× Boss**         | 2.40    | 0.70     |

**Tower stat baselines (Mk I → Mk III):**

| Tower  | Damage        | Range (cells) | Fire rate (/s) | Special (per tier)              | Upgrade cost |
|--------|---------------|--------------:|---------------:|---------------------------------|-------------:|
| Gun    | 8 / 14 / 24   | 3.0 / 3.5 / 4.0 | 2.5 / 3.0 / 3.5 | —                              | 40g / 70g    |
| Frost  | 3 / 5 / 8     | 2.5 / 3.0 / 3.5 | 1.0 / 1.2 / 1.5 | slow 35% / 45% / 55%, 1.5 s    | 50g / 85g    |
| Splash | 12 / 20 / 34  | 3.5 / 4.0 / 4.5 | 0.7 / 0.8 / 1.0 | blast radius 1.0 / 1.25 / 1.5 cells | 65g / 110g |

(Solvers may tune these slightly for balance, but must document any deviations in a comment.)

## Deliverable

- Exactly one file, e.g. `gridline-defense.html`, containing the complete game.
- Run: double-click the file, or `open gridline-defense.html` / `xdg-open gridline-defense.html` — no server, no build.

## Done When

- [ ] Opening the file from `file://` shows the grid, the full path with direction cues, the HUD (200g, 20 lives, wave 0/15, score 0), and the tower palette.
- [ ] Clicking a palette entry (or pressing 1/2/3) shows a cursor-following range ring; invalid cells tint red; clicking a valid cell builds the tower and deducts gold.
- [ ] "Send next wave" spawns wave 1 (8 Grunts at the stated cadence) walking the full path; leaking one costs 1 life.
- [ ] Gun, Frost, and Splash towers behave per spec: visible traveling projectiles, slow effect visibly decelerates enemies, splash damages clusters.
- [ ] Selecting a built tower shows its range, stats, upgrade buttons (with costs) and sell value equal to 70% of invested gold; upgrading changes its appearance and stats; selling refunds and clears the cell.
- [ ] Wave 5 spawns a Boss; killing it pays 120g×scale; a leaking Boss costs 5 lives.
- [ ] The 1x/2x toggle visibly doubles simulation speed; pause freezes everything; early wave calls grant the documented bonus and can overlap waves.
- [ ] Reaching 0 lives shows a game-over overlay with restart; clearing wave 15 shows the victory overlay with a lives-based grade.
- [ ] At 2x on wave 14–15 with 20+ towers, the game stays smooth (no visible stutter).
- [ ] A footer line and a top-of-file comment state the production date/time and the model/author.

## Stretch Goals (optional)

- **Target priority selector** per tower (First / Last / Strongest / Fastest), reflected in a small icon on the tower.
- **Interest mechanic:** at each wave's end, earn +2% of current gold (capped), rewarding economical play.
- **Wave editor mode:** a JSON textarea + "load custom waves" button that re-runs the game with user-defined compositions validated against the schema above.
