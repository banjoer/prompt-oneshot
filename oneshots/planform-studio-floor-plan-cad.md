# Planform Studio — Floor-Plan CAD

**Difficulty:** Extreme  |  **Stack:** HTML/CSS/JS (vanilla, single file, SVG)  |  **Estimated time:** 8+ hours

## The Problem

Homeowners sketching a renovation, design students learning space planning, and renters testing furniture layouts all need the same missing middle: something more truthful than a doodle but lighter than professional CAD — real metres, real areas, walls with thickness, doors that swing, and material estimates, all in a tool that opens instantly and saves locally. Generic drawing apps fake it with rectangles that carry no dimensions; pro CAD demands licenses and training. Build the disciplined middle: a single-file, local-first floor-plan CAD with a true metric model, editable rooms, walls, openings, furniture, live calculations, and SVG/PNG export.

## Requirements

1. Deliver a single self-contained `planform.html` file using only vanilla HTML/CSS/JS with SVG for the drawing plane. It must work when opened directly from disk (`file://`); no server, no build step, no libraries.
2. **Starter example:** on first run (no saved state) generate a complete editable example called **Courtyard Flat** from the same project model used for user plans — never a background image: roughly 82 m², 2 bedrooms plus living/dining, kitchen, bath, and entry/circulation, with exterior and interior walls, at least 3 doors, 2 windows, room labels with dimensions, and at least 6 furniture pieces. A `Reset to example` command with confirmation restores it.
3. **Units and project model:** store all geometry internally in centimetres (integers); display in metres/centimetres (e.g. `3.60 m`, `45 cm`). Support project bounds from 3×3 m up to 30×30 m. Reject zero-length geometry and below-minimum rooms with an inline message. A status bar always shows project name, dirty/saved state, active tool, cursor coordinates in m/cm, zoom %, and snap setting.
4. **Viewport:** a bounded infinite-feel drawing surface with a major/minor metric grid that adapts density to zoom; mouse-wheel zoom centred on the pointer; pan via Hand tool, `Space`-drag, or middle-mouse drag; `Fit` command framing the whole plan plus an explicit zoom readout. Independent toggles for grid, dimensions, furniture, and labels hide/show without deleting data. The plan can never be panned or zoomed into an irrecoverable void.
5. **Room tool (`R`):** drag an axis-aligned rectangle with a live `W × D × Area` preview; enforce a minimum practical size (e.g. 120×120 cm); after commit, rooms support select, move, resize via handles (snapping to grid with live dimensions), rename, duplicate, numeric width/depth editing in the inspector, and delete. Coincident shared edges between adjacent rooms render as a single wall weight, not a doubled blob. Room labels show name and computed area (m²).
6. **Wall tool (`W`):** draw orthogonal standalone wall segments (click-then-click or drag) with a consistent thickness shown in drawing and used in calculations; zero-length and degenerate segments are rejected. Walls participate in selection, move, and delete like rooms.
7. **Door/Window tools (`D`/`N` or toolbar equivalents):** place openings only on valid wall segments — position and orientation snap to the host wall. Doors carry an editable width and swing/flip setting and render as a leaf plus swing arc (never a plain rectangle); windows carry an editable width and render as a distinct wall-opening symbol. Openings that extend past the wall end or overlap another opening are rejected with a message. Moving or resizing the host wall keeps attached openings valid (repositioned/clamped) or explains their removal.
8. **Select tool (`V`):** click-to-select plus marquee multi-select with unambiguous selection outlines/handles distinct from hover. Support pointer drag-move, arrow-key nudge (Shift for a larger step), `Delete`/`Backspace`, duplicate, copy/cut/paste, `Ctrl/Cmd+A` select-all, and `Esc` cancel. Multi-selection offers align left/center/right/top/middle/bottom. Numeric inspector edits commit as one undoable action (not one step per keystroke).
9. **Furniture library:** a built-in searchable/categorized panel with at least: single bed, double bed, sofa, armchair, dining table, dining chair, counter, sink, cooker, fridge, toilet, basin, shower/bath, wardrobe, desk, plant, and one outdoor/courtyard object. Symbols use simple top-down SVG geometry with true footprint dimensions shown in the inspector; support place/select/move/rotate in 90° steps/duplicate/delete, grid snap, and a warning (not silent corruption) when a piece lies outside room or project bounds. Furniture participates in save and export.
10. **Measure tool (`M`):** click two points for a point-to-point distance with both orthogonal and straight-line readings; dimension text stays readable at all zooms and never scales into illegibility.
11. **Live calculations:** every committed edit immediately updates room areas (m²), a project summary (total room area, room count, total wall length, opening count, furniture count), and a material-estimates panel computed from stated fictional assumptions shown next to the numbers: flooring area by room plus a configurable waste % (default 10%), paintable wall area from a configurable ceiling height minus a simplified opening deduction, and skirting/baseboard length minus door widths. All estimates are labelled as planning aids, explicitly not for construction, with a short disclaimer in the UI.
12. **History:** at least 50 undo steps where one drag, resize, or inspector commit equals one action; Undo/Redo buttons plus `Ctrl/Cmd+Z` and `Ctrl/Cmd+Shift+Z` (or `Ctrl/Cmd+Y`); new work after undo invalidates the redo branch.
13. **Persistence and project files:** autosave the full project (geometry, openings, furniture, selection-safe state, viewport, units, visibility toggles, preferences) to `localStorage` under a versioned key (e.g. `planform.v1`) after each committed change; reload restores it. Corrupt or unsupported saved data offers safe recovery/reset instead of a crash loop. Export the complete project as versioned JSON and re-import it with schema validation and useful error messages. Never imply cloud backup or collaboration.
14. **Export and presentation:** export a clean standalone SVG (with `viewBox` and a scale note) and a high-resolution PNG preview of the current plan, honouring the visibility toggles and using safe filenames derived from the project name. Provide a read-only presentation mode that hides editing chrome, fits the plan, and shows title, legend, room schedule, material summary, and the planning disclaimer — without modifying project state.
15. **Responsive and onboarding:** excellent at 1440×900 and genuinely usable at 390×844 (drawers/sheets for inspector, furniture, and calculations; plan stays visible; pan/zoom/select work; no horizontal page overflow; no `desktop required` wall). A concise first-run coach overlay teaches select, room drawing, openings, furniture, and export; it is dismissible and reopenable. A shortcuts dialog (`?`) lists every tool and action.
16. **Accessibility and input quality:** semantic buttons/labels/groups/dialogs, visible focus rings, modal focus containment with `Escape` close and focus restoration, full keyboard access to all non-canvas chrome, tool/selection/warning states never conveyed by color alone, `prefers-reduced-motion` respected, and a textual project summary (rooms, areas, counts) readable without the drawing. Destructive shortcuts are inert while focus is in a text field.
17. **Sign-off:** the finished solution must display, somewhere easy to spot (e.g. a footer or presentation sheet), the date and time it was produced and the model/author that produced it (e.g. `Built 2026-10-29 14:32 by <model-name>`), plus a matching header comment at the top of the file.

## Constraints

- One file only: `planform.html`. No external CSS/JS files, no CDNs, no frameworks, no images, no web fonts, no build step.
- Vanilla browser APIs only: SVG + DOM, `localStorage`, `JSON`, `Blob`/download links, Canvas 2D only for PNG rasterization. No network calls of any kind.
- Geometry lives in a real project model in centimetres, separate from screen pixels; screen/world conversion must be exact at every zoom. Never derive stored dimensions from pixels.
- Underlying model and calculations must be deterministic and unit-consistent; displayed numbers are computed, never hardcoded.
- Must run by double-clicking the file (`file://`) in a current Chrome/Firefox/Edge/Safari.

## Sample Data / Inputs

Courtyard Flat starter room list (exact layout may vary; areas must compute live from geometry and sum to ~82 m²):

```
Living/Dining   5.4 m × 4.2 m   ≈ 22.7 m²
Bedroom 1       3.6 m × 3.3 m   ≈ 11.9 m²
Bedroom 2       3.2 m × 3.0 m   ≈ 9.6 m²
Kitchen         3.0 m × 2.6 m   ≈ 7.8 m²
Bath            2.4 m × 2.0 m   ≈ 4.8 m²
Entry/Hall      4.0 m × 2.2 m   ≈ 8.8 m²
Courtyard       4.5 m × 3.8 m   ≈ 17.1 m² (outdoor, counts separately in summary)
```

Example project JSON shape on export (implementation may vary, but units, version, rooms, walls, openings, and furniture must all round-trip):

```json
{
  "app": "planform",
  "version": 1,
  "name": "Courtyard Flat",
  "units": "cm",
  "rooms": [{ "name": "Living/Dining", "x": 0, "y": 0, "w": 540, "d": 420 }],
  "walls": [{ "x1": 0, "y1": 0, "x2": 540, "y2": 0, "thickness": 24 }],
  "openings": [{ "kind": "door", "wall": 0, "offset": 120, "width": 90, "swing": "left-in" }],
  "furniture": [{ "type": "sofa", "x": 80, "y": 60, "rotation": 0 }]
}
```

## Deliverable

- One file: `planform.html`
- Run: open `planform.html` in any modern browser (double-click it, or `File → Open`). No install, no server.

## Done When

- [ ] The page opens from `file://` showing the Courtyard Flat example (~82 m², all listed room types, walls, ≥3 doors with leaf+arc, ≥2 windows, labels+dims, ≥6 furniture pieces) with no console errors.
- [ ] Drawing a room with `R` shows live W×D×Area, rejects tiny/zero-size rooms, and the committed room appears in the summary with a correct computed area.
- [ ] Rooms move/resize/rename/duplicate/delete correctly; numeric W/D edits in the inspector commit as one undo step; shared edges render single-weight.
- [ ] Standalone orthogonal walls draw with visible thickness and participate in wall-length totals; zero-length segments are rejected.
- [ ] Doors/windows snap to walls with correct leaf+arc / opening symbols, editable widths, and door flip; overlong or overlapping placements are refused; moving the host wall keeps or explains openings.
- [ ] Select supports click + marquee, drag-move, arrow nudge, delete/duplicate/copy/paste/select-all/Esc, and multi-align; selection is never color-only.
- [ ] The furniture panel offers all 17 required symbols with true footprints; pieces place, rotate 90°, snap, and warn when out of bounds.
- [ ] Measure shows orthogonal + straight-line distances with readable text at min and max zoom.
- [ ] Summary (total area/count/wall length/openings/furniture) and material estimates (flooring+10%, paint via ceiling height minus openings, skirting minus doors, labelled planning-aid with disclaimer) update immediately after edits.
- [ ] A drag followed by Undo/Redo behaves as one step; a new edit after undo clears redo; 50-step depth holds for a long session.
- [ ] Reloading restores plan, viewport, and toggles; corrupting the `localStorage` value by hand and reloading offers recovery; `Reset to example` with confirmation restores Courtyard Flat.
- [ ] JSON export re-imports to an identical plan (bad files give readable errors); SVG and PNG exports download under safe names and honour visibility toggles; presentation mode is read-only and shows title/legend/schedule/summary/disclaimer.
- [ ] The app is fully usable at 1440×900 and review-editable at 390×844 with no page overflow; the coach is dismissible/reopenable and the shortcuts dialog opens.
- [ ] The sign-off (date/time produced + model/author) is visible in the UI and in a source header comment.

## Stretch Goals (optional)

- Feet/inches display mode that converts without touching the centimetre model.
- DXF-ish line-entity export (minimal valid subset) alongside SVG/PNG.
- One-click autoscale print sheet (plan + schedule + summary fitted to A4/Letter proportions).
