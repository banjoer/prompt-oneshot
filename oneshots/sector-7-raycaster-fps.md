# Sector-7 — From-Scratch Raycaster FPS

**Difficulty:** extreme  |  **Stack:** HTML/CSS/JS (single file, vanilla canvas)  |  **Estimated time:** 8+ h

## The Problem
Before GPUs there was raycasting: a 2.5D engine that turns a 2D grid into a textured corridor at 60 fps on CPU alone. Build a Wolfenstein-lite with 5 hand-made sectors, enemy AI, and a minimap — no 3D library, just math.

## Requirements
1. Hand-rolled raycaster on a 2D canvas: DDA ray march per screen column, fish-eye correction, distance shading, procedural wall/floor textures (no images), ceiling/floor gradient + sprite billboarding for pickups/foes.
2. 5 inline ASCII sectors (≥21x21, chars: `#` wall variants `012`, `.` floor, `D` door, `E` exit, `P` player start, `k` key, `e` foe spawn, `m` medkit, `a` ammo) with locked doors requiring keys.
3. Player: WASD + mouse-look (pointer lock) + arrows fallback, sprint Shift, shoot click/Space with hitscan + spread/recoil, 100 HP / 50 armor that absorbs 1/3 damage.
4. Foes: 3 types (Trooper hitscan, Rusher melee, Spitter slow projectile) with states patrol/chase/attack/death, line-of-sight checks, and pain-chance; 6 weapons-pickups and ammo economy across 2 guns (Blaster infinite weak, Scatter strong, 8 shells max pickup).
5. HUD (HP/armor/ammo/score/sector/kills), damage vignette, muzzle flash light, minimap with foe blips toggleable Tab, pause/help, death/victory screens with time + accuracy stats.
6. WebAudio procedural gunshots/steps/doors/pickups (oscillator + noise buffers only).
7. Fixed-step sim 60 Hz decoupled from render; hold 60 fps on a 960x540 viewport (render scale adjustable 0.5–1.0 in settings).
8. Persist best clear time + high score per sector in localStorage; `?sector=` deep-link loads a sector.
9. **Sign-off:** the title screen and HUD help panel must both display the date and time the solution was produced and the model/author that produced it.

## Constraints
- Single `sector-7.html`, vanilla only, no three.js/Phaser/Babylon, no network, no image assets.
- Raycast + sprites + minimap all from scratch; all sectors/textures inline.
- Playable with keyboard-only fallback (no pointer-lock required).

## Sample Data / Inputs
Sector excerpt (solver expands to 21x21 ×5):
```
#####################
#P....#.....e......##
#.###.#.###.#####..#
#.k.#...#D#.....#E.#
```

## Deliverable
- `sector-7.html` (single file)
- Run: double-click `sector-7.html`, or `python3 -m http.server 8000` then open `http://localhost:8000/sector-7.html?sector=1`

## Done When
- [ ] Corridors render with corrected projection, shading, billboarded sprites at 60 fps
- [ ] 5 sectors with doors/keys/exit/pickups complete end to end
- [ ] 3 foe AIs with LOS, 2 guns with ammo economy, armor absorption all behave
- [ ] HUD, minimap, pause, death/victory stats, and settings render scale work
- [ ] Procedural audio + persistence + `?sector=` deep-link function
- [ ] Title + help sign-off with date/time + author is visible

## Stretch Goals (optional)
- Secret push-walls revealing caches (2+ per game)
- Speedrun timer with split file export to clipboard
- Enemy-infighting when crossfire hits another foe
