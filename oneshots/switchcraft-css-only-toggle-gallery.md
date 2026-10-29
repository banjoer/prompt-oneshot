# Switchcraft — CSS-Only Toggle Gallery

**Difficulty:** easy  |  **Stack:** HTML/CSS/JS (vanilla, single file)  |  **Estimated time:** 30–60 min

## The Problem
Design systems live and die by their smallest components. Toggle switches are everywhere — settings pages, feature flags, notification preferences — yet developers constantly re-implement them from scratch or paste in snippets from random blog posts that break under their theme. A tiny, self-contained gallery of hand-crafted, CSS-only animated switches with a built-in "copy the CSS" button turns that friction into a one-click operation, and doubles as a showcase of what modern CSS can do without a single line of animation JavaScript.

## Requirements
1. The page displays a gallery of **at least 6 visually distinct toggle switches**, each presented as a card with a name (see Sample Data for the six required styles).
2. Every switch is a **real, functional checkbox**: clicking it toggles its state, it is keyboard-focusable, pressing Space toggles it, and it has an associated `<label>` so clicking the label also toggles.
3. The **on/off animation of every switch is pure CSS** (`transition` and/or `@keyframes` driven by the checkbox state, e.g. `:checked`). JavaScript must never set or animate the visual on/off state of a switch.
4. Each card has a **"Copy CSS" button** that copies that switch's complete CSS rules to the clipboard and shows clear feedback (e.g. the button label changes to "Copied!" for ~1.5 s, then reverts).
5. A **page-level light/dark theme toggle** in the page header restyles the entire page — background, cards, text — and every switch must remain clearly visible and fully functional in both themes.
6. The chosen theme **persists across reloads** via `localStorage`; on first visit (nothing stored) the page follows the OS `prefers-color-scheme` setting.
7. The gallery uses a **responsive grid**: cards sit in a single column on narrow screens and reflow to 2–3 columns on wide screens.
8. **Sign-off:** the finished page must display, in a clearly visible footer, the date and time it was produced and the model/author that produced it.

## Constraints
- One single `.html` file containing all markup, all CSS in `<style>`, and all JS in `<script>`.
- Vanilla HTML/CSS/JS only — no frameworks, no libraries, no CDN links, no webfont/icon downloads (system font stack and Unicode emoji only).
- No network calls of any kind; the page must fully work when opened directly from disk (`file://`) by double-clicking.
- JavaScript is allowed **only** for: clipboard copying + button feedback, and the page theme toggle + persistence. All switch behaviour and animation must be CSS-driven.
- Clipboard access must use `navigator.clipboard.writeText`, with a graceful fallback message (e.g. "Clipboard unavailable") if the API is missing or denied.

## Sample Data / Inputs
Build these six switch styles (names are required; the visual interpretation is up to you):
1. **Classic Slide** — a rounded pill track with a knob that slides across.
2. **Neon Glow** — dark track; when on, the knob and track glow via a coloured `box-shadow`.
3. **Squishy** — the knob visibly stretches and squishes (scale transform) partway through the slide.
4. **Day / Night** — the knob shows a sun ☀ that morphs into a moon 🌙 as it slides; the track shifts from sky to night.
5. **Pulse** — when switched on, the knob emits a repeating ripple ring (CSS `@keyframes`).
6. **Flip Lock** — the knob rotates 180°, revealing a locked 🔒 / unlocked 🔓 face.

No other input data is needed.

## Deliverable
- Exactly one file: `toggle-gallery.html` (all CSS and JS inline).
- Run: open `toggle-gallery.html` in any modern browser (double-click or File → Open). No server, no build step.

## Done When
- [ ] Opening the file shows a header with the gallery title, a theme toggle, and a grid of ≥ 6 named switch cards.
- [ ] Every switch toggles on click, on label click, and with the Space key when focused — and animates smoothly in both directions.
- [ ] With JavaScript disabled, every switch is still fully toggleable and animated (only the copy buttons and theme toggle stop working).
- [ ] Each "Copy CSS" button puts that switch's CSS on the clipboard (verifiable by pasting into a text editor) and shows a "Copied!" confirmation.
- [ ] Clicking the theme toggle instantly restyles the whole page; after reloading the tab, the last chosen theme is still active.
- [ ] Resizing the window reflows the grid from 1 to 2–3 columns.
- [ ] A footer clearly shows the production date/time and the model/author.

## Stretch Goals (optional)
- Respect `prefers-reduced-motion`: disable or minimise switch animations for users who request it.
- Announce copy success to screen readers via an `aria-live` region.
- Add a "Copy all CSS" button in the header that copies the full stylesheet in one click.
