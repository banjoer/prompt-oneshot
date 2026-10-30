# Color Palette Generator

**Difficulty:** Easy  |  **Stack:** HTML/CSS/JS (vanilla, single file)  |  **Estimated time:** 15–60 min

## The Problem

Choosing colors for a slide deck, side project, or landing page usually means tab-hopping between palette sites, signing in, or screenshotting swatches you can't copy. What you actually want is a tiny local tool: five harmonious colors on one screen, hex codes you can read at a glance, and one keypress to roll a fresh set while keeping the shades you already like. Build that tool as a single file that opens instantly from disk and works with no internet.

## Requirements

1. Deliver a single self-contained `palette.html` file using only vanilla HTML/CSS/JS — all markup, styles, and logic inside it. It must work when opened directly from disk (`file://`) in a modern browser; no server needed.
2. Render exactly **5 swatches** side by side, each filling an equal share of the available width. Each swatch shows its **HEX code** (e.g. `#3FA7D6`, uppercase, 6 digits) centered on the swatch.
3. Pick the HEX label color automatically per swatch: black text on light backgrounds, white text on dark backgrounds (luminance-based check), so every code is readable.
4. Provide a visible **Generate** button. Clicking it — or pressing **Spacebar** (without scrolling the page, and not while focus is in an input/button) — replaces every *unlocked* swatch with a new random color.
5. Each swatch has a **lock toggle** (button showing 🔓 / 🔒 with an accessible label). Clicking it locks/unlocks that swatch; locked swatches keep their color across regeneration. At least one lock state change must be visually obvious.
6. **Click-to-copy:** clicking a swatch's HEX code copies that exact code to the clipboard via the Clipboard API (with a `document.execCommand` fallback allowed for `file://`). On success show a brief **toast** (e.g. "Copied #3FA7D6!") that appears and auto-dismisses within ~2 seconds; on failure show a brief error toast instead of throwing.
7. Add a CSS `transition` on background color (e.g. `transition: background-color 0.3s ease`) so color swaps animate smoothly rather than snapping.
8. Handle edge cases without crashing: regenerating with all 5 swatches locked changes nothing; copying works for every swatch; an empty or missing clipboard permission degrades to the error toast. Persist the locked palette to `localStorage` (single key, e.g. `palette.v1`) and restore it on reload; corrupt stored JSON falls back to a fresh random palette.
9. **Sign-off:** the page must display, somewhere easy to spot (e.g. a footer), the date and time the solution was produced and the model/author that produced it (e.g. `Built 2026-10-30 10:15 by <model-name>`), plus a matching header comment at the top of the file.

## Constraints

- One file only: `palette.html`. No external CSS/JS files, no CDNs, no frameworks, no web fonts or images, no build step.
- Vanilla JS and DOM APIs only, plus the Clipboard API and `localStorage`. No network calls of any kind (`fetch`, XHR, beacons).
- Must run by double-clicking the file (`file://` protocol) in a current Chrome/Firefox/Edge/Safari. No dev server, no install.
- Layout must stay usable at desktop widths (5 swatches in a row) and stack or shrink gracefully on narrow mobile screens.

## Sample Data / Inputs

No input files. Example of a valid palette state (implementation may vary):

```
Swatch 1: #3FA7D6 (unlocked, dark text)
Swatch 2: #F4E04D (unlocked, dark text)
Swatch 3: #2B2D42 (locked 🔒, light text)
Swatch 4: #EF8354 (unlocked, dark text)
Swatch 5: #0D1B2A (locked 🔒, light text)
```

Luminance rule of thumb: compute relative brightness from the RGB channels; use white text when the background is dark, black text when it is light.

## Deliverable

- One file: `palette.html`
- Run: open `palette.html` in any modern browser (double-click it, or `File → Open`). No install, no server.

## Done When

- [ ] The page opens from `file://` and shows exactly 5 equal-width swatches, each labelled with a valid uppercase 6-digit HEX code.
- [ ] Every HEX label is readable (dark text on light swatches, light text on dark swatches).
- [ ] Clicking Generate (and pressing Spacebar) re-rolls all unlocked swatches with a visible smooth color transition.
- [ ] Locking a swatch (🔒) protects it across repeated Generate/Spacebar presses; unlocking re-enables it.
- [ ] Locking all 5 swatches and pressing Generate leaves the palette unchanged with no errors.
- [ ] Clicking any HEX code copies that exact code and shows a "Copied!" toast that disappears on its own; clipboard denial shows an error toast, not a crash.
- [ ] Reloading the page restores the locked colors; corrupting the `localStorage` value by hand and reloading yields a fresh working palette.
- [ ] The layout works on desktop and narrow mobile widths with no overlapping text.
- [ ] The sign-off (date/time produced + model/author) is visible on the page and in a source header comment.

## Stretch Goals (optional)

- Export palette button that copies all 5 codes as a comma-separated list (e.g. `#3FA7D6, #F4E04D, …`).
- Keyboard shortcut `C` copies the first unlocked swatch's code.
- "Copy all" toast variant confirming the full palette was copied.
