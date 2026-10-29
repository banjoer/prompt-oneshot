# Whack-a-Mole Frenzy

**Difficulty:** Easy  |  **Stack:** Vanilla HTML/CSS/JavaScript (browser)  |  **Estimated time:** 30–60 min

## The Problem
Arcade reflex games live and die on a tight feedback loop: hit, miss, score, go faster. You're building a tiny whack-a-mole game that runs entirely in the browser — moles pop out of a grid of holes for a shrinking window of time, the player scores points for clicking them before they duck back down, and a countdown clock keeps the pressure on. A persistent best score in localStorage gives players a reason to reload the page and beat their own record.

## Requirements
1. A single self-contained `index.html` (inline CSS + JS, no external files) that runs when opened directly in a browser.
2. A 3×3 grid of "holes". At most ONE mole is visible at any moment, rendered as a clearly visible emoji (🐹 or similar) inside its hole.
3. A round lasts exactly 30 seconds, shown as a prominently displayed countdown that updates every second (e.g. `Time: 27s`).
4. Clicking the visible mole before it hides scores +1 point, and the mole immediately relocates to a random different hole. The score is displayed live.
5. Clicking a hole with no mole in it (or clicking the grid while no mole is up) adds +1 to a miss counter, displayed live alongside the score.
6. The mole starts by staying visible for 1000 ms; that window shrinks by 50 ms for every 5 successful hits, down to a hard floor of 350 ms — the game must visibly speed up as the player scores.
7. When the countdown reaches 0 the round ends: moles stop spawning, clicks no longer count, and a game-over panel shows the final score, total misses, and a "Play Again" button that resets everything and starts a fresh round.
8. The best score ever achieved persists in `localStorage` under the key `whackBest`, is displayed next to the current score from page load, and updates at game over when beaten — with a visible "New best!" indicator when that happens.
9. A "Start" button begins the round; the game must not auto-start on page load, and Start must be disabled/hidden while a round is in progress.
10. **Sign-off:** the finished solution must display, somewhere easy to spot, the date and time it was produced and the model/author that produced it — a visible page footer (e.g. `Built 2026-10-29 14:32 · <model name>`) AND a matching header comment at the top of the HTML file.

## Constraints
- Vanilla HTML/CSS/JS only: no frameworks, no libraries, no build step, no network calls, no external assets (emoji or pure CSS shapes for the mole).
- Everything lives in one `index.html`; aim for under ~250 lines.
- Storage is limited to `localStorage` only.
- Must work from `file://` — double-click to play, no server required.

## Sample Data / Inputs
- Grid: 3×3 holes; one mole at a time, random hole each spawn.
- Round length: 30 s.
- Mole visibility: 1000 ms initially, −50 ms per 5 hits, floor 350 ms.
- Scoring: +1 per hit; misses counted separately (no point deduction).
- Persistence: `localStorage["whackBest"]` = integer, default 0.

## Deliverable
- One file: `index.html`.
- Run: open `index.html` in any modern browser (double-click it). No install, no server.

## Done When
- [ ] Page loads showing a Start button, a 3×3 grid, score 0, misses 0, time 30s, and best score (0 on first run).
- [ ] Clicking Start begins the countdown and moles begin appearing one at a time in random holes.
- [ ] Clicking a visible mole increments the score; clicking an empty hole increments misses.
- [ ] The mole visibly stays up for less time as the score climbs (by ~20 hits the game feels noticeably frantic).
- [ ] At 0 s the game freezes, shows score + misses, and Play Again starts a clean new round.
- [ ] After beating the best score, reloading the page still shows the new best, and "New best!" appeared at the game-over panel.
- [ ] The footer sign-off with date/time and model/author is visible on the page, with a matching header comment in the source.

## Stretch Goals (optional)
- Brief "whack" animation (scale/bounce) on a hit and a red flash on a miss.
- Golden mole: a 1-in-10 spawn is golden and worth +3 points.
- Sound effects via the Web Audio API (generated in code, no audio files).
