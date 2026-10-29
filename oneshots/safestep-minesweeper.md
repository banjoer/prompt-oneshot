# Safestep Minesweeper

**Difficulty:** Medium  |  **Stack:** HTML/CSS/JavaScript (single file, browser)  |  **Estimated time:** 1–3 h

## The Problem
Classic Minesweeper has a notorious flaw: on many implementations the very first click can detonate a mine, and even "first-click-safe" clones often reveal a single useless cell that leaves the player guessing. A properly engineered board deals the mines only *after* the player commits to an opening cell — guaranteeing that the first click is not merely safe but cascades into a satisfying region of cleared ground to reason from. From there the game lives on its tactile verbs: flood-fill reveals sweeping across empty water, flags marking deductions, and the "chord" that clears a satisfied number's neighbours in one decisive click. Build the definitive coffee-break logic game — three difficulties, a timer, a mine counter, and persistent best times — all in one double-clickable HTML file.

## Requirements
1. One single self-contained `.html` file with all CSS and JavaScript inline. It must run by double-clicking it (`file://`) in a modern browser — no server, no build step.
2. A difficulty selector offering exactly three presets, usable before the first click and switchable at any time (switching starts a fresh board):
   - **Beginner** — 9×9 grid, 10 mines
   - **Intermediate** — 16×16 grid, 40 mines
   - **Expert** — 30 columns × 16 rows, 99 mines
3. **Lazy board generation:** no mines exist until the player's first left-click on a covered cell. Mines are then placed uniformly at random among all cells *except* the clicked cell and its 8 neighbours. Consequently the first clicked cell always has 0 adjacent mines, so the flood fill (requirement 4) always opens a region covering at least the clicked cell plus all of its existing neighbours.
4. **Flood-fill reveal:** revealing a covered cell with 0 adjacent mines automatically reveals all connected empty cells and every numbered cell bordering them, in a single click.
5. Left-click reveals a covered cell; right-click toggles a 🚩 flag on a covered cell. Flagged cells cannot be revealed by left-click, chord, or flood fill. The browser's context menu must be suppressed over the board.
6. Revealed numbers 1–8 use distinguishable colours following the classic code: 1 blue, 2 green, 3 red, 4 dark blue, 5–8 additional distinct colours (at least four colours total).
7. **Chord reveal:** left-clicking an already-revealed number whose count of adjacent flags equals that number reveals every still-covered, unflagged neighbour in one action. If any of those flags is misplaced, the chord detonates the actual mine(s) it touches and the game is lost.
8. A **mine counter** displays `total mines − flags placed` at all times (it may go negative), and a **timer** starts only on the first click, ticks once per second, freezes on win or loss, and caps its display at 999.
9. **Loss:** clicking (or chording into) a mine marks the detonated cell with 💥, reveals all other mines, marks every wrongly placed flag with ❌, and locks the board — further cell clicks do nothing.
10. **Win:** when every non-mine cell is revealed, the board locks, all mines auto-display flags, the timer stops, and a clearly visible win state appears (e.g. the reset face turns to 😎 and/or a "You win!" banner shows).
11. A central **reset button** (a face reflecting game state — 🙂 ready/playing, 😵 lost, 😎 won) restarts the current difficulty at any time, returning the board to its pristine state: no mines placed, timer at 0, counter at the preset total.
12. **Best times** per difficulty persist in `localStorage` under a single key `safestepBest` holding JSON such as `{"beginner":12,"intermediate":96}` (integer seconds; a missing key means no record yet). Each difficulty's best time is displayed next to its selector, and beating it on a win shows a "New best!" indicator and updates storage.
13. First-click fairness holds across resets and difficulty switches: the very first click of every fresh board — at any position, on any difficulty — never detonates and always opens a multi-cell region.
14. **Sign-off:** the finished solution must display, somewhere easy to spot, the date and time it was produced and the model/author that produced it — a visible page footer (e.g. `Built 2026-10-29 14:32 · <model name>`) AND a matching header comment at the top of the HTML file.

## Constraints
- Everything lives in ONE `.html` file: inline `<style>` and `<script>`, no other local files.
- Third-party libraries ARE allowed for this batch (CDN `<script>` tags or inlined source), but none are needed — vanilla HTML/CSS/JS is the intended solution. If any library is used, it must be named in the header comment, and its CDN tag is the single permitted network reference.
- Otherwise: no runtime network calls, no external assets — emoji and pure CSS for all visuals (mine 💣, flag 🚩, faces 🙂😵😎).
- Storage is limited to `localStorage` only — no cookies, no IndexedDB, no backend.
- Must work from `file://` — double-click to play.
- The board may be rendered as a DOM grid or `<canvas>` (solver's choice), but every interaction above must work with plain mouse input.

## Sample Data / Inputs
- Difficulty presets: `Beginner 9×9 / 10 mines` · `Intermediate 16×16 / 40 mines` · `Expert 30×16 / 99 mines`.
- Suggested number colours: 1 `#0000ff`, 2 `#008000`, 3 `#ff0000`, 4 `#000080`, 5 `#800000`, 6 `#008080`, 7 `#000000`, 8 `#808080`.
- Persistence schema: `localStorage["safestepBest"] = '{"beginner":12,"intermediate":96,"expert":241}'` (any subset of keys may be present).
- Mine counter initial values: 10 / 40 / 99 per preset; timer starts at 0 and displays up to 999.

## Deliverable
- Exactly one file, e.g. `minesweeper.html`.
- Run: double-click `minesweeper.html` (or open it via the browser's File → Open). No install, no server, no build.

## Done When
- [ ] Opening the file shows the difficulty selector, a fully covered board at the selected size, the mine counter at the preset total, the timer at 0, and any previously stored best times.
- [ ] Across at least 20 fresh boards with first clicks at varied positions (corners, edges, centre) on all three difficulties, the first click never detonates and always opens a multi-cell region.
- [ ] Revealing a 0 cell cascades the reveal through all connected empty cells and their bordering numbers in one click.
- [ ] Right-click toggles flags, the mine counter updates accordingly, flagged cells cannot be revealed, and the context menu never appears over the board.
- [ ] Left-clicking a satisfied number chords open its remaining covered neighbours; chording with a wrongly placed flag detonates a mine and loses the game.
- [ ] The timer stays at 0 until the first click, then ticks each second and freezes on win/loss.
- [ ] A loss shows 💥 on the detonated cell, reveals all mines, marks wrong flags with ❌, and locks the board; a win auto-flags all mines, stops the timer, and shows the win state.
- [ ] The reset face restarts a clean board at the current difficulty, and switching difficulty restarts with the correct dimensions and mine count.
- [ ] After recording a best time, reloading the page still shows it; beating it displays "New best!" and updates `localStorage`.
- [ ] The footer sign-off with date/time and model/author is visible on the page, with a matching header comment in the source.

## Stretch Goals (optional)
- Right-click cycles covered → 🚩 → ❓ → covered, and ❓ cells are revealed but not chorded.
- Touch support: long-press to flag, responsive cell sizing so Expert is playable on a phone.
- Web Audio API sound effects (reveal tick, chord sweep, explosion) generated entirely in code — no audio files.
