# Contrast Sentinel — WCAG Color-Pair Checker

**Difficulty:** easy  |  **Stack:** HTML/CSS/JS (vanilla, single file)  |  **Estimated time:** 30–60 min

## The Problem

Every frontend developer has shipped text that looked fine on their own
monitor and was unreadable for someone else — low-vision users, bright
sunlight, cheap displays. The WCAG contrast-ratio formula settles the
argument with a number, but developers usually have to leave their editor
and paste hex codes into a website to get it. This challenge is a
standalone, offline web tool that computes the WCAG contrast ratio between
a foreground and background color in pure JavaScript, shows the two colors
live as a text-on-background preview, and stamps the pair with clear
PASS/FAIL badges for the AA and AAA conformance levels. No framework, no
build step, no network — just one file you can keep on your desktop.

## Requirements

1. The page provides two color inputs labeled **Foreground (text)** and
   **Background**. Each input consists of a native color picker
   (`<input type="color">`) **and** a hex text field; editing either one
   keeps the other in sync and recomputes everything immediately.
2. Hex text fields accept `#RRGGBB` and `#RGB` (with or without the leading
   `#`, case-insensitive). Invalid input shows a clear inline error next to
   the offending field and leaves the last valid color unchanged.
3. The tool computes the WCAG 2.x contrast ratio in vanilla JavaScript:
   linearize each sRGB channel (`c/12.92` if `c ≤ 0.04045`, otherwise
   `((c + 0.055) / 1.055) ** 2.4`), then
   `L = 0.2126·R + 0.7152·G + 0.0722·B`, then
   `ratio = (L_lighter + 0.05) / (L_darker + 0.05)`.
4. The ratio is displayed prominently, rounded to exactly two decimals in
   the form `4.54 : 1`, and updates live on every color change (including
   dragging the color picker).
5. A **live preview swatch** shows sample text rendered in the foreground
   color on the background color — one block of normal-size body text and
   one large/bold headline — so the user sees the pair the way a reader
   would.
6. Four **pass/fail badges** are shown, each visibly green (`PASS`) or red
   (`FAIL`), labeled with its threshold:
   - **AA normal text** — ratio ≥ 4.5
   - **AA large text** — ratio ≥ 3
   - **AAA normal text** — ratio ≥ 7
   - **AAA large text** — ratio ≥ 4.5
7. A one-line **verdict** summarizes the strictest level passed, e.g.
   "Passes WCAG AAA" / "Passes WCAG AA" / "Passes AA large text only" /
   "Fails all WCAG levels".
8. A **Swap** button exchanges foreground and background with a single
   click (the ratio must stay identical, since the formula is symmetric).
9. **Sign-off:** the finished page must display, somewhere easy to spot
   (e.g. a footer), the date and time it was produced and the model/author
   that produced it.

## Constraints

- Vanilla HTML/CSS/JS only — everything in **one file** (`index.html`), no
  frameworks, no libraries, no build step, no external fonts, icons, or
  CDNs.
- No network calls of any kind; the page must work fully offline opened
  straight from `file://`.
- No persistence needed — nothing is written to `localStorage`, cookies,
  or files.
- The contrast math must be implemented by hand from the formula in
  requirement 3 — do not shell out to any computed-style or canvas trick.
- Layout must be usable at common laptop widths (no horizontal scrolling at
  1280 px) and readable in both the pickers and the preview.

## Sample Data / Inputs

Use these known pairs to verify the math (foreground on background):

| Foreground | Background | Expected ratio | Expected badges |
|------------|------------|----------------|-----------------|
| `#000000` | `#FFFFFF` | `21.00 : 1` | all four PASS |
| `#FFFFFF` | `#000000` | `21.00 : 1` | all four PASS (symmetric) |
| `#767676` | `#FFFFFF` | `4.54 : 1` | AA normal PASS, AA large PASS, AAA normal FAIL, AAA large PASS |
| `#FF0000` | `#FFFFFF` | `≈ 4.00 : 1` | AA normal FAIL, AA large PASS, AAA normal FAIL, AAA large FAIL |
| `#FFFF00` | `#FFFFFF` | `1.07 : 1` | all four FAIL |

Edge inputs to handle: `fff`, `#FFF`, `Ff00Aa`, `#GGGGGG` (invalid),
`#1234` (invalid length).

## Deliverable

- `index.html` — the complete tool (markup, styles, and script inline).
- Run: open `index.html` in any modern browser (double-click it, or
  `python3 -m http.server` and visit `http://localhost:8000/index.html`).

## Done When

- [ ] Entering `#767676` foreground on `#FFFFFF` background displays
      `4.54 : 1` with exactly the badge pattern in the sample table.
- [ ] Black on white displays `21.00 : 1` and all four badges read PASS;
      after clicking Swap the colors exchange and the ratio is unchanged.
- [ ] `#FFFF00` on `#FFFFFF` displays `1.07 : 1`, all four badges read
      FAIL, and the verdict line says it fails all WCAG levels.
- [ ] Typing an invalid hex value (e.g. `#GGGGGG`) shows an inline error
      and the previous valid color and ratio stay on screen.
- [ ] Dragging either color picker updates the hex field, the ratio, the
      badges, and the preview swatch live, without reloading the page.
- [ ] The preview swatch visibly renders sample normal text and a large
      headline in the chosen foreground on the chosen background.
- [ ] The date/time produced and the model/author are visible on the page.

## Stretch Goals (optional)

- Add a "nudge to pass" hint: when AA normal fails, suggest how much to
  darken the foreground (or lighten the background) to reach 4.5.
- Add a "Copy CSS" button that puts `color: #…; background-color: #…;` on
  the clipboard.
- Add a small palette of preset pairs (e.g. the sample table as clickable
  chips) for quick demos.
