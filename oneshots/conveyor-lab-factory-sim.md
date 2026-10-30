# Conveyor Lab — Factory Automation Sim

**Difficulty:** extreme  |  **Stack:** HTML/CSS/JS (single file, vanilla; Phaser 3 via CDN optionally allowed)  |  **Estimated time:** 8+ h

## The Problem
Factory sims are throughput-debug puzzles: ore in, plates out, and every bottleneck visible. Build a Factorio-lite where belts, inserters, furnaces, and assemblers form live production lines feeding a 4-stage research goal — with real rates, power, and pollution pushback.

## Requirements
1. Tile grid (≥32x32) canvas with pan/zoom, ghost placement + rotate (R), bulldoze, and cut/copy/paste of block selections; toolbar: belt, inserter, miner, furnace, assembler, pole, chest, wall, turret.
2. Item simulation from scratch: belts move discrete items along paths with merging/splitting, inserters swing items chest↔belt↔machine at fixed ticks, furnaces smelt ore→plate (2s), assemblers craft gears→science (4s) per inline recipes.
3. Power grid: boilers/poles coverage radius; unpowered machines stall with icon; consumption readout in MW.
4. Pollution + biters: furnaces/boilers emit pollution cloud (diffusing overlay), spawning waves from nests at thresholds; turrets auto-fire with ammo, walls block; lose when HQ destroyed, win on completing 4 research tiers.
5. Research: science packs consumed by lab HQ through tiers T1–T4 (20/40/80/150 packs), each unlocking discount or speed +10%; live stats: items/min per line, power, pollution, kills.
6. Save/load: full grid + stocks serialized to localStorage slots (3 slots) with thumbnail label; pause/speed toggle (1x/2x/4x); onboarding hint bar for first 5 minutes.
7. WebAudio machine hum/alarms/craft pings (oscillator/noise only) with mute; minimap with pollution overlay toggle.
8. **Sign-off:** the title screen and HUD status bar must both display the date and time the solution was produced and the model/author that produced it.

## Constraints
- Single `conveyor-lab.html`; vanilla preferred; ONE Phaser 3.x CDN `<script>` tag permitted as alternative — no other libraries, no runtime network.
- Fixed-tick simulation (e.g. 20 ticks/s) decoupled from render; must sustain 500+ live belt items at 60 fps.
- All recipes/waves inline; storage via localStorage only.

## Sample Data / Inputs
Recipes inline:
```js
const RECIPES = { plate:{in:{ore:2}, out:{plate:1}, t:2}, gear:{in:{plate:2}, out:{gear:1}, t:4}, sci1:{in:{gear:1,plate:2}, out:{sci1:1}, t:5} };
```

## Deliverable
- `conveyor-lab.html` (single file)
- Run: double-click `conveyor-lab.html`, or `python3 -m http.server 8000` then open `http://localhost:8000/conveyor-lab.html`

## Done When
- [ ] 9-tool build palette with rotate/ghost/bulldoze/copy-paste works on pan/zoom grid
- [ ] Belts/inserters/furnaces/assemblers produce plates→gears→science at stated rates
- [ ] Power coverage stalls/unstalls machines with live MW readout
- [ ] Pollution diffusion triggers biter waves; turrets/walls defend HQ; win/lose triggers fire
- [ ] T1–T4 research completes via pack consumption; stats + minimap accurate
- [ ] 3 save slots reload exactly; speed toggle + hints + mute work
- [ ] Title + HUD sign-off with date/time + author is visible

## Stretch Goals (optional)
- Blueprint strings: export/import base64 selections via clipboard
- Night/train visual toggle with headlight cones
- Leaderboard of fastest T4 times stored locally
