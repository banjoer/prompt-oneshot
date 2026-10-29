# MergeGrid 2048

**Difficulty:** medium  |  **Stack:** HTML/CSS/JavaScript (single file)  |  **Estimated time:** 1–3 hours

## The Problem

2048 is the classic sliding-tile puzzle, but most quick clones feel broken: tiles teleport instead of gliding, merges pop in without feedback, one accidental swipe wipes out a great run, and closing the tab loses your best score. A good 2048 needs a real *move model* underneath the visuals — the game logic computes exactly where every tile travels and which tiles merge, and the rendering layer simply animates that result. That separation is what makes the motion smooth, the undo reliable, and the game feel fair. Your job is to build that: a polished, fully self-contained 2048 that plays beautifully with keyboard or touch, forgives mistakes with undo, and remembers your best score forever.

## Requirements

1. **Core game.** A 4×4 grid following standard 2048 rules: the game starts with two tiles; each valid move slides all tiles as far as possible in the chosen direction; two tiles of equal value that collide merge into one tile of double the value; each tile may merge at most once per move; after every valid move exactly one new tile spawns in a random empty cell — a 2 with 90% probability, a 4 with 10%.
2. **Smooth animations.** Tiles must visibly *glide* to their new cells and merged tiles must give a visual merge pulse/pop. Implement this as CSS transitions driven by a move model: the game logic first computes, for every tile, its origin cell, destination cell, and whether it merges or disappears; the renderer then positions real DOM elements with `transform: translate(...)` and lets CSS transitions animate the motion. Do not rebuild the grid from scratch per frame and do not animate with `setInterval` pixel-stepping.
3. **Keyboard + swipe input.** Arrow keys **and** WASD move the board. Swiping on a touchscreen (touchstart/touchend) moves in the swipe direction; a mouse click-drag must also work as a swipe. Input during an in-flight animation must be queued or safely ignored — never corrupt state. Prevent arrow keys from scrolling the page.
4. **Undo.** An "Undo" button (plus the `U` key) restores the board and score to a previous state, with **at least 3 steps** of history. Undo must be disabled (visibly) when no history remains, and must be usable across animations and after a game over.
5. **Score + best persistence.** Merges add the new tile's value to the score. Score and best score are displayed live; the best score persists in `localStorage` across page reloads and is shown next to the current score.
6. **Win / continue / game over.** Creating a 2048 tile shows a "You win" overlay offering **Keep playing** (continue the same board to higher tiles) and **New game**. When no empty cells remain and no adjacent equal tiles exist in either direction, show a "Game over" overlay with the final score, a **New game** button, and an **Undo** button to rescue the run. A move that changes nothing must not spawn a tile or consume an undo step.
7. **New game.** A "New game" button resets the board and score (best score is kept) without a page reload.
8. **Sign-off:** the finished solution must display, somewhere easy to spot, the date and time it was produced and the model/author that produced it (e.g. a header comment in the source plus a small footer line on the page).

## Constraints

- The deliverable is **exactly ONE self-contained `.html` file** — all CSS in a `<style>` block, all JavaScript in a `<script>` block. It must run by simply opening the file in a modern browser (`file://` double-click) — no build step, no server.
- Third-party libraries **are allowed** for this challenge (via CDN `<script>` tag or inlined source) — if you use any, name them and their version in a comment at the top of the file. Vanilla HTML/CSS/JS is equally acceptable and encouraged; everything required is achievable with the platform alone.
- All storage is local only (`localStorage`); no network calls at runtime, no external assets (fonts, images) fetched — everything renders offline.
- The game must remain playable at small viewport sizes (board scales to fit, touch input works).
- Keep logic and rendering separated: a pure board/move model, and a DOM layer that renders model diffs.

## Sample Data / Inputs

- Fixed 4×4 board; no external data needed.
- Example move model diff for a left move on row `[2, 2, 4, 0]` → `[4, 4, 0, 0]`: tile A (value 2, cell 0) travels to cell 0 and merges; tile B (value 2, cell 1) travels to cell 0 and disappears into the merge; tile C (value 4, cell 2) travels to cell 1; new merged tile (value 4) appears at cell 0 with a pulse; score +4.
- Suggested localStorage keys: `mergegrid.best` (number) and optionally `mergegrid.state` (serialized board + score + undo stack) for the stretch goal.

## Deliverable

- `mergegrid-2048.html` — the complete game in one file.
- Run: open `mergegrid-2048.html` in any modern browser (double-click, or `file:///path/to/mergegrid-2048.html`).

## Done When

- [ ] Opening the file shows a styled 4×4 board with two starting tiles, score, best score, Undo, and New game controls.
- [ ] Pressing an arrow key slides tiles with a visible glide animation; equal tiles merge with a pulse; a new tile fades/pops in after each valid move.
- [ ] A move that would change nothing does nothing (no spawn, no animation, no history entry).
- [ ] Swiping with a finger and click-dragging with a mouse both move the board; WASD also works; the page never scrolls during play.
- [ ] Undo restores the exact previous board and score and works at least 3 moves deep; it is visibly disabled when history is empty.
- [ ] Reloading the page keeps the best score.
- [ ] Reaching 2048 shows the win overlay; choosing "Keep playing" continues the same board.
- [ ] Filling the board with no merges left shows the game-over overlay with final score, New game, and a working Undo rescue.
- [ ] The page displays the production date/time and the producing model/author.

## Stretch Goals (optional)

- Persist the full game state (board, score, undo stack) in `localStorage` so a reload resumes mid-game.
- Add a move counter and a subtle spawn/merge sound using the Web Audio API (no audio files).
- Add a board-size selector (4×4, 5×5, 6×6) with the model handling any N×N.
