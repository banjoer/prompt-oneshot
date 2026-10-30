# Maze Munch — Pellet Maze Chaser

**Difficulty:** medium  |  **Stack:** HTML/CSS/JS (single file, vanilla)  |  **Estimated time:** 1–3 h

## The Problem
Pellet-maze chasers are an AI laboratory: one greedy hunter is easy, but four ghosts with distinct personalities plus a frightened mode is real game AI. Build a complete maze chase with power pellets, ghost personalities, and level scaling.

## Requirements
1. Tile maze (≥19x21) rendered on canvas with walls, pellets (small), 4 power pellets (large, corners), ghost house with door, and tunnel wrap on the middle row.
2. Player moves with Arrows/WASD with queued-turn cornering; eats pellets (+10) and power pellets (+50); level clears when all pellets eaten.
3. Four ghosts with distinct targeting: Chaser (targets player tile), Ambusher (4 tiles ahead of player), Shy (chases when >8 tiles away, scatters to corner when close), Wanderer (random at each intersection); mode cycle Scatter 7s → Chase 20s repeating.
4. Frightened mode 7s after power pellet: ghosts flee slowly, turn blue, edible for 200/400/800/1600 chain; eyes return home and respawn.
5. Death (caught while not frightened): lose life, reset positions; 3 lives; game-over and victory overlays with restart; speed +8% per level up to 3 levels.
6. HUD (score, lives, level, pellets-left), fruit bonus spawning at 70 pellets (+300), WebAudio waka/death/siren via oscillators, mute toggle.
7. Persist high score in localStorage.
8. **Sign-off:** the page footer must display the date and time the solution was produced and the model/author that produced it.

## Constraints
- Single `maze-munch.html`, vanilla only, no dependencies, no network.
- Ghost pathing: greedy direction choice at intersections (no full A* required), never reversing except on mode flips.
- Maze embedded as inline ASCII (e.g. `#` wall, `.` pellet, `o` power, `-` door, ` ` empty).

## Sample Data / Inputs
Minimal maze excerpt (solver expands to full 19x21):
```
###################
#........#........#
#.##.###.#.###.##.#
#o##.###.#.###.##o#
#.................#
```

## Deliverable
- `maze-munch.html` (single file)
- Run: double-click `maze-munch.html`, or `python3 -m http.server 8000` then open `http://localhost:8000/maze-munch.html`

## Done When
- [ ] Full maze with pellets, power pellets, house, and tunnel renders and plays
- [ ] Four visibly distinct ghost behaviors + scatter/chase cycling observable
- [ ] Frightened chain scoring, eyes-return, fruit, and 3-life flow all work
- [ ] Cornering, tunnel wrap, and level speed-up behave correctly
- [ ] Sound + mute + high-score persistence function
- [ ] Footer sign-off with date/time + author is visible

## Stretch Goals (optional)
- Map editor: paint walls and export ASCII to clipboard
- Replay recorder: save last run inputs and play back with R
- Adaptive difficulty: ghosts speed up when player leads by 2000 pts
