# Pixel Art Editor

**Difficulty:** Medium  |  **Stack:** HTML/CSS/JS (vanilla, single file, canvas)  |  **Estimated time:** 1–3 h

## The Problem

Doodling a game sprite or a tiny icon shouldn't require installing a graphics suite or uploading your work to a cloud editor. What you need is a small local drawing tool: a crisp pixel grid, a handful of honest tools (pencil, eraser, fill, eyedropper), undo that forgives mistakes, and one-click PNG export — all in a single file that remembers your work between sessions. Build that editor on the raw Canvas API with zero dependencies.

## Requirements

1. Deliver a single self-contained `pixelart.html` file using only vanilla HTML/CSS/JS and the raw Canvas API — all markup, styles, and logic inside it. It must work when opened directly from disk (`file://`) in a modern browser; no server needed.
2. Render the drawing grid on a `<canvas>` with selectable sizes **16×16, 32×32, 64×64** (e.g. buttons or a select). Switching sizes asks for confirmation (`confirm()` is acceptable) and clears the drawing on confirm; cancelling keeps the current drawing untouched.
3. Show a subtle **grid overlay** with a checkbox to toggle it on/off. Transparent pixels render as a light **checkerboard** pattern beneath the artwork. Rendering stays crisp at every grid size: disable image smoothing and use `image-rendering: pixelated` (plus integer canvas backing-store math) so pixel edges never blur.
4. **Draw by click and by drag:** pressing and holding the mouse button while moving paints a continuous stroke; releasing ends the stroke. Strokes never paint outside the grid and never throw on fast drags across cell boundaries.
5. Provide a toolbar with four tools and a visible active state: **Pencil** (paints the current color), **Eraser** (paints transparent), **Fill / bucket** (flood-fills the contiguous same-colored region), and **Eyedropper** (sets the current color to the clicked pixel's color, ignoring fully transparent picks or treating them as a no-op with a brief notice). Fill implements BFS/DFS iteratively with an explicit stack/queue — no recursion — so 64×64 fills never stack-overflow; filling a region with its own color is a no-op.
6. Provide a native `<input type="color">` **color picker** plus a palette of **16 preset swatches**, plus a strip of the **8 most recently used colors** that updates as the user draws (most-recent-first, deduplicated).
7. Support at least **20 steps of undo/redo** wired to Undo/Redo buttons and to **Ctrl/Cmd+Z** (undo) / **Ctrl/Cmd+Shift+Z** or Ctrl+Y (redo). One drag stroke counts as exactly **one** undo step; fill and clear each count as one step. Undo with empty history is a safe no-op.
8. **Download PNG** button exports the artwork with transparency preserved at **10× scale** (each pixel becomes a 10×10 block, e.g. 16×16 → 160×160 PNG) via an offscreen canvas and a download link. Autosave the drawing (pixels + grid size) to `localStorage` on every completed stroke/fill/clear and restore it on reload; corrupt stored data falls back to a blank canvas instead of crashing.
9. Provide a **Clear** button that asks for confirmation and wipes the canvas to fully transparent (recorded as one undo step).
10. **Sign-off:** the page must display, somewhere easy to spot (e.g. a footer), the date and time the solution was produced and the model/author that produced it (e.g. `Built 2026-10-30 10:15 by <model-name>`), plus a matching header comment at the top of the file.

## Constraints

- One file only: `pixelart.html`. No external CSS/JS files, no CDNs, no frameworks, no web fonts or images, no build step.
- Vanilla JS and the raw Canvas API only (`2d` context, `localStorage`, DOM). No network calls of any kind (`fetch`, XHR, beacons).
- Storage is `localStorage` exclusively — a single key holding pixels plus grid size. No IndexedDB, no cookies, no backend.
- Must run by double-clicking the file (`file://` protocol) in a current Chrome/Firefox/Edge/Safari. No dev server, no install.
- Crispness is mandatory: no anti-aliased pixel edges at any grid size; fill must be iterative, never recursive.

## Sample Data / Inputs

No input files. Starter pattern for manual testing — a 16×16 heart (`.` = transparent, `R` = red `#E63946`):

```
................
................
..RRR....RRR....
.RRRRR..RRRRR...
.RRRRRRRRRRRR...
.RRRRRRRRRRRR...
..RRRRRRRRRR....
...RRRRRRRR.....
....RRRRRR......
.....RRRR.......
......RR........
................
................
................
................
................
```

Suggested storage shape (implementation may vary, but pixels + size must round-trip):

```json
{ "size": 16, "pixels": ["#E63946", null, null, "..."] }
```

## Deliverable

- One file: `pixelart.html`
- Run: open `pixelart.html` in any modern browser (double-click it, or `File → Open`). No install, no server.

## Done When

- [ ] The page opens from `file://` showing a crisp canvas, 16/32/64 selector, grid toggle, toolbar with visible active tool, color picker, 16 presets, and 8 recent colors.
- [ ] Clicking and dragging paints a continuous stroke with the Pencil; the Eraser restores checkerboard transparency.
- [ ] Switching grid size prompts for confirmation; confirming clears, cancelling preserves the drawing.
- [ ] Grid toggle hides/shows the overlay; transparent areas always show the checkerboard; pixels stay sharp at all sizes.
- [ ] Fill flood-fills only the contiguous region (BFS, no stack overflow on 64×64) and is a no-op when the fill color equals the target.
- [ ] Eyedropper picks the clicked pixel's color into the picker; recent-colors strip updates to 8 deduplicated entries.
- [ ] Undo/redo covers 20 steps with one stroke = one step, wired to buttons and keyboard shortcuts; Clear confirms and is undoable.
- [ ] Download PNG saves a 10×-scaled image with transparency intact; reload restores the drawing; corrupt storage yields a blank canvas, not an error page.
- [ ] The sign-off (date/time produced + model/author) is visible on the page and in a source header comment.

## Stretch Goals (optional)

- Mirror modes (horizontal/vertical symmetry) toggled from the toolbar.
- Line and rectangle shape tools with live preview.
- Export scale selector (1× / 5× / 10× / 20×) and a `.json` save/load for sharing drawings.
