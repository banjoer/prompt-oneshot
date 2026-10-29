# Gradient Blob Studio

**Difficulty:** easy  |  **Stack:** HTML/CSS/JS (vanilla)  |  **Estimated time:** 30–60 min

## The Problem

Designers love those soft, organic "blob" gradients you see on landing pages — but hand-tuning `border-radius` and `linear-gradient` values in dev tools is tedious, and the result is usually static. A tiny generative art toy that renders an animated, multi-blob gradient scene with a few sliders would let anyone explore hue, angle, and "blobbiness" live, then steal the generated CSS with one click. Build that toy as a single self-contained web page.

## Requirements

1. The page shows a large preview area (at least 60% of the viewport height) filled with a gradient background of at least two colors derived from the current settings, plus at least three visible soft-edged "blob" shapes layered on top.
2. Three labeled sliders control the artwork live (updates must appear as the slider moves, without any Apply button):
   - **Hue** (0–360): shifts the base hue of the gradient and blobs (use `hsl()` colors).
   - **Angle** (0–360): sets the gradient direction in degrees.
   - **Blobbiness** (0–100): morphs the blob shapes, e.g. by interpolating the corner values of an 8-value `border-radius` like `30% 70% 70% 30% / 30% 30% 70% 70%`.
3. The scene animates continuously on its own (e.g. blobs drift/pulse via CSS keyframes or `requestAnimationFrame`); the animation must keep running while sliders are adjusted.
4. A **"Copy CSS"** button copies ready-to-paste CSS for the current static look (gradient + blob rules) to the clipboard using `navigator.clipboard.writeText`, and shows visible confirmation (e.g. the button label briefly changes to "Copied!") for about 2 seconds.
5. A **"Randomize"** button sets all three sliders to random valid values and updates the artwork accordingly.
6. The current slider values are displayed numerically next to each slider label.
7. **Sign-off:** the finished page must display, somewhere easy to spot (e.g. a footer), the date and time it was produced and the model/author that produced it; also include this as a header comment in the source.

## Constraints

- Single `index.html` file: embedded `<style>` and `<script>`, no external files, fonts, libraries, or frameworks.
- No network calls of any kind; works fully offline by double-clicking the file.
- Vanilla HTML/CSS/JS only — no build step.
- Must work in a current Chrome/Firefox/Safari without console errors.

## Sample Data / Inputs

No external data needed. Default starting state: Hue `280`, Angle `120`, Blobbiness `60`. Example of the blob `border-radius` technique you can interpolate:

- Blobbiness 0 → `50% 50% 50% 50% / 50% 50% 50% 50%` (perfect circles)
- Blobbiness 100 → `25% 75% 60% 40% / 70% 30% 65% 35%` (very wobbly)

## Deliverable

- `index.html`
- Run: open `index.html` in any modern browser (no server needed).

## Done When

- [ ] Opening the file shows an animated multi-blob gradient scene.
- [ ] Moving each slider visibly changes hue, gradient angle, and blob shape in real time, with numeric values shown.
- [ ] Clicking "Copy CSS" puts valid CSS on the clipboard (verifiable by pasting into a text editor) and shows a "Copied!" confirmation.
- [ ] Clicking "Randomize" produces a visibly different artwork and updates the sliders.
- [ ] The page footer shows the production date/time and the model/author.

## Stretch Goals (optional)

- Persist slider state in `localStorage` and restore on reload.
- A "Download PNG" button that renders the current frame to a `<canvas>` and saves it.
- Slider to control blob count (1–8).
