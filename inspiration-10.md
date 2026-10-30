# ONE-SHOT AUTONOMOUS BENCHMARK: BUILD AND DELIVER A COMPLETE PIXEL-IMAGE EDITOR

You are the sole product designer, interaction designer, senior graphics engineer,
frontend engineer, accessibility specialist, QA engineer, and release engineer for this
task. In the current working directory, create and deliver a polished browser-based pixel
art and small-image editor called **Mosaic Studio**.

This is a strict one-shot autonomy benchmark. You will receive no clarification,
approval, follow-up instruction, or second attempt. Once you end the run, the submission
is frozen and judged exactly as left on disk.

Do not stop after planning, scaffolding, drawing a mockup, or implementing a canvas with
one brush. Work continuously through architecture, implementation, graphics algorithms,
interaction design, persistence, import/export, testing, real browser use, visual
inspection, debugging, documentation, screenshots, and final delivery. Do not ask
questions. Make coherent decisions and complete the product before responding.

## 1. Product mission

Mosaic Studio is a focused local-first creative tool for designing icons, sprites, small
illustrations, and pixel art. It should feel like a compact professional application—not
a toy drawing demo and not a generic dashboard wrapped around a canvas.

The experience should be calm, tactile, precise, and immediately understandable. Use an
original visual identity with excellent typography, restrained color, crisp iconography,
clear hierarchy, and deliberate light/dark contrast. A new user must be able to open the
app, understand the starter document, draw accurately, work with layers, undo mistakes,
save locally, export an image, reload, and continue without external instructions.

The initial state must show a finished, procedurally generated example document titled
**Sunset Courier**: an original 64×64 pixel composition featuring a small courier or
vehicle crossing a warm sunset landscape. It need not be photorealistic, but it must be
visually coherent and demonstrate the editor's palette, layers, transparency, and crisp
pixel rendering. Generate it in project code or data; do not use copyrighted game art.

## 2. Autonomy, licensing, and safety

- Treat the current working directory as the complete project and delivery boundary.
- Do not inspect, reuse, compare against, or modify another benchmark submission.
- Do not change host, model, Ollama, OpenCode, Docker, GPU, or service configuration.
- Do not stop unrelated processes or use credentials, paid APIs, hosted storage,
  telemetry, analytics, or user accounts.
- The final application must run offline after dependencies have been installed.
- Do not load runtime fonts, scripts, images, icons, APIs, or assets from a CDN.
- Internet research is allowed for primary technical documentation and permissively
  licensed assets, but original procedural graphics and inline SVG icons are preferred.
- Never use ripped sprites, trademarked characters, ambiguous downloads, or assets with
  incompatible redistribution terms.
- Record the URL, author, license, and modifications for every third-party asset in
  `ATTRIBUTIONS.md`. Include the file even if every visual is original.
- If optional research or asset acquisition becomes slow or unreliable, immediately use
  robust local or procedural alternatives and continue.
- Make reasonable assumptions where necessary. Never wait for user confirmation.

## 3. Technical delivery requirements

Choose the frontend architecture most likely to produce a dependable editor in one run.
TypeScript and a conventional Vite-based project are preferred. React, Preact, Vue,
Svelte, or a carefully structured framework-free implementation are acceptable.

Hard requirements:

- Modern-browser application with no backend and no account.
- Production build, preview, static analysis, unit tests, and browser E2E scripts.
- Offline operation after dependency installation; no runtime network dependency.
- Modular domain logic separated from rendering and interface components.
- Accurate pointer-to-pixel mapping at every supported zoom and device-pixel ratio.
- Versioned project format and local persistence with graceful corrupt-data recovery.
- No secrets or required environment variables in the production build.
- No placeholder controls, dead buttons, unfinished panels, TODO labels, or knowingly
  advertised features that do nothing.
- No uncaught errors or console errors during tested happy paths.
- Do not include `node_modules`, browser caches, recordings, or disposable debug files.
- Add stable evaluator hooks exactly as specified in section 12. Do not remove or rename
  them during polish.

## 4. Document and canvas model

Implement a real pixel-document model rather than treating the visible canvas as the
only source of truth.

### 4.1 Documents

- New-document dialog with name, width, height, and background choice.
- Useful presets including 16×16, 32×32, 64×64, and 128×128.
- Allow custom dimensions from 8×8 through at least 256×256 with validation.
- Transparent and opaque background choices.
- Display the document name, logical dimensions, zoom percentage, and dirty/saved state.
- Confirm before replacing a document with unsaved changes when data could be lost.
- Include a safe reset-to-starter-project action with confirmation.

### 4.2 Pixel canvas

- Render pixels sharply without interpolation at integer and non-integer display sizes.
- Checkerboard transparency background that remains visually subordinate to artwork.
- Zoom from at least 100% to 3200%, with toolbar controls and keyboard shortcuts.
- Fit-to-view command and a clearly visible zoom readout.
- Pan using a dedicated hand tool and Space-drag or middle-button drag on desktop.
- Optional pixel grid that appears only at useful zoom levels and can be toggled.
- Cursor/pixel coordinate readout.
- Correct clipping: tools may never paint outside the logical document.
- Pointer capture so a stroke remains coherent when the pointer temporarily leaves the
  canvas. Interpolate dragged strokes so fast movement does not leave unintended gaps.

## 5. Required editing tools

Every tool must have a visible selected state, accessible name, tooltip or concise help,
appropriate cursor, and working keyboard shortcut where specified.

### 5.1 Drawing

- **Pencil** (`P`): hard-edged pixel drawing using the foreground color.
- **Eraser** (`E`): makes pixels transparent rather than painting the checkerboard.
- Brush sizes of 1, 2, 4, and 8 logical pixels. Shapes must remain hard-edged.
- **Line** (`L`): preview and commit a continuous pixel line.
- **Rectangle** (`R`): outline and filled modes.
- **Ellipse** (`O`): outline and filled modes with sensible pixel rasterization.
- Holding Shift should constrain line/shape behavior where conventional and practical.

### 5.2 Color and fill

- **Fill** (`F`): contiguous flood fill bounded to the active layer and exact source
  color. It must not leak diagonally unless the interface explicitly offers that mode.
- **Eyedropper** (`I` or Alt): samples the visible composite color under the pointer.
- Foreground color control with hex input and an accessible native/custom picker.
- Curated starter palette matching Sunset Courier.
- Add, replace, and remove custom palette swatches with sensible safeguards.
- Recent-color history containing at least the last eight distinct selected colors.
- Transparent color must be represented clearly rather than as misleading white.

### 5.3 Selection and transform

- Rectangular marquee selection with clear marching-ants or equivalent boundary.
- Move the selected pixels within the active layer with transparent source behavior.
- Select all, deselect, delete selection, copy, cut, and paste using conventional
  shortcuts when browser permissions allow.
- Pasted pixels must become an explicit movable selection or otherwise have a clear,
  reversible placement step.
- Flip selection or active layer horizontally and vertically.
- Operations that change pixels must participate in undo/redo as one logical action.

## 6. Layer system

Provide a genuine composited layer model:

- At least eight layers supported without degraded normal interaction.
- Starter project uses meaningful named layers such as `Sky`, `Landscape`, `Courier`,
  and `Highlights`.
- Add, duplicate, rename, delete, reorder, show/hide, and select layers.
- Per-layer opacity from 0–100% with immediate composite preview.
- Transparent thumbnails that update after edits.
- Protect the user from deleting the final remaining layer.
- Deleting a non-empty layer requires a clear reversible action or confirmation.
- Layer order, visibility, opacity, names, and pixel data persist and export correctly.
- Drawing always affects only the active visible layer; hidden-layer editing must be
  prevented or clearly communicated.

## 7. History, state, and resilience

- Undo and redo buttons plus `Ctrl/Cmd+Z`, `Ctrl/Cmd+Shift+Z`, and where appropriate
  `Ctrl/Cmd+Y`.
- At least 50 logical history steps. A pointer drag is one history step, not hundreds.
- New edits after undo invalidate the redo branch correctly.
- History covers drawing, fill, transforms, layer operations, and meaningful document
  changes.
- Autosave the active project locally after changes using a versioned schema.
- Restore the document, active layer, palette, tool settings, and appropriate viewport
  state after reload.
- Detect malformed, unsupported, or corrupt saved data. Offer a safe recovery path and
  never trap the user behind a loading screen.
- Show a restrained save-status indication; do not pretend data was uploaded.
- Include a clear local-data/reset control and confirmation dialog.

## 8. Import and export

- Export the visible composite as a valid PNG at exact logical dimensions.
- Offer at least 1× and 4× nearest-neighbor PNG export.
- Export a versioned Mosaic Studio project JSON containing complete editable state.
- Import that project format with schema validation and useful error messaging.
- Import a local PNG as a new document, respecting supported dimension limits.
- Browser downloads must use descriptive filenames derived safely from the document name.
- Never upload or transmit imported images. State this plainly in the relevant UI.
- Add a compact export dialog showing format, scale, resulting dimensions, and whether
  transparency is preserved.

## 9. Application experience

Design a complete creative workspace, not a collection of default form elements.

Suggested desktop organization:

- Top application bar with identity, document controls, undo/redo, and export.
- Left tool rail with drawing and navigation tools.
- Central canvas stage with rulers/readouts where useful.
- Right inspector containing color/palette and layers.
- Bottom status area for dimensions, coordinates, zoom, and contextual guidance.

Requirements:

- A concise first-run coach overlay or guided hints that teach pencil, color, layers,
  undo, and export without blocking normal use. It must be dismissible and reopenable.
- Keyboard-shortcuts/help dialog.
- Clear empty, loading, error, confirmation, and success states.
- Thoughtful tooltips and compact microcopy; avoid verbose tutorial walls.
- Light or dark workspace is acceptable, but artwork, checkerboard, controls, focus, and
  selected states must remain legible.
- Avoid fake operating-system chrome, fake collaboration avatars, fake cloud status,
  upgrade banners, pricing, social feeds, and irrelevant product-marketing sections.

### Responsive behavior

- Desktop target: excellent at 1440×900 and usable at 1280×720.
- Narrow target: usable at 390×844 without horizontal page overflow.
- On narrow screens, preserve canvas interaction and the most important drawing controls.
  Secondary layers/palette/settings may use drawers, tabs, or bottom sheets.
- Touch drawing, tapping tools, pinch zoom, or explicit zoom controls must work without
  causing the page itself to scroll unpredictably.
- Do not simply shrink the desktop interface until controls become unusable.

## 10. Accessibility and input quality

- Semantic buttons, dialogs, labels, groups, and status announcements.
- Complete keyboard access to all non-canvas controls.
- Visible focus indicators and logical focus order.
- Dialog focus containment, Escape close where safe, and focus restoration.
- Color is never the sole indicator of active tool, selected layer, errors, or state.
- Minimum practical pointer targets, especially at the narrow viewport.
- Respect `prefers-reduced-motion`; core editing must never depend on animation.
- Decorative SVG/canvas content should be hidden from assistive technology; important
  state must have equivalent text.
- Provide an accessible canvas description containing document name, dimensions, active
  layer, and a concise explanation that editing is spatial.
- Prevent destructive keyboard shortcuts while focus is inside text fields.

## 11. Testing and independent verification contract

Use deterministic algorithms and expose them to meaningful unit tests. Tests must verify
behavior rather than merely restating constants or implementation details.

### Required unit/integration coverage

- Pixel coordinate conversion and document bounds.
- Continuous stroke interpolation.
- Line, rectangle, ellipse, and fill rasterization including edge cases.
- Flood-fill boundaries and transparent colors.
- Layer compositing, visibility, ordering, and opacity.
- Undo/redo grouping, branching, and maximum history behavior.
- Selection move, deletion, flip, cut/copy/paste domain operations.
- Versioned serialization round trip and invalid/corrupt input rejection.
- Dimension/name/color validation.
- PNG scale dimension calculation and safe filenames.

### Required browser E2E scenarios

1. Starter project loads with four named layers and visible artwork.
2. Create a 32×32 transparent document and confirm correct metadata.
3. Select pencil/color, draw a multi-pixel drag, and verify the document changes.
4. Undo removes the stroke and redo restores it.
5. Add and rename a layer, draw on it, toggle visibility, change opacity, and reorder it.
6. Fill a bounded region without affecting an isolated region.
7. Create, move, and delete a rectangular selection.
8. Export PNG and project JSON; validate downloads and basic contents/dimensions.
9. Reload restores saved state.
10. Invalid project import and corrupt local state fail safely.
11. Keyboard shortcuts do not fire destructively while editing a text field.
12. Narrow viewport provides usable canvas, pencil, color, undo, layers access, and export.
13. No uncaught exceptions, console errors, broken resources, or runtime network requests.

Do not weaken tests to make a broken implementation pass. Run the final production build
through the real browser. Inspect screenshots rather than assuming DOM presence proves
visual correctness. In particular, verify effective opacity, clipping, overlays, canvas
pixel content, sharp rendering, and the actual first viewport at desktop and mobile.

## 12. Stable evaluator hooks

The final running application must expose these exact hooks on the corresponding visible
interactive elements:

- `data-testid="app-shell"`
- `data-testid="app-title"`
- `data-testid="editor-canvas"` on the actual editing canvas
- `data-testid="tool-pencil"`
- `data-testid="tool-fill"`
- `data-testid="undo"`
- `data-testid="redo"`
- `data-testid="layers-panel"`
- `data-testid="new-document"`
- `data-testid="export"`

These are stable automation hooks, not a substitute for accessible names or proper tests.
Do not hide duplicate dummy elements merely to satisfy selectors.

## 13. Required delivery artifacts

The final directory must contain:

- Complete source, local assets, dependency manifest, and lockfile.
- Automated unit/integration and browser E2E tests.
- Production build and preview configuration.
- `README.md` with exact commands, architecture, tools/shortcuts, persistence behavior,
  import/export details, reset instructions, tests, and honest limitations.
- `ATTRIBUTIONS.md`, including an explicit statement for original procedural visuals.
- `BENCHMARK_REPORT.md` recording implementation choices, exact commands actually run,
  test counts/results, browser matrix, bundle size, screenshots, defects found/fixed,
  evaluator-hook checklist, and honest remaining limitations.
- `screenshots/` with at least six final PNGs:
  - Desktop starter artwork and complete workspace.
  - Desktop drawing operation or edited result.
  - Layers and palette interaction.
  - Export dialog.
  - Narrow workspace.
  - Narrow layers/palette drawer or sheet.

Capture screenshots from the final production build, not a mockup or obsolete state.

## 14. Acceptance scenarios

### A. Immediate credibility

At 1440×900, Mosaic Studio identity, Sunset Courier artwork, canvas, core tools, layers,
and export action are visible and coherent. The first viewport is not blank, obstructed,
or dominated by onboarding.

### B. Draw and recover

A user can create a document, draw a continuous hard-edged stroke, change color, undo,
redo, and understand what changed without reading source code or documentation.

### C. Layered editing

A user can add, rename, reorder, hide, fade, duplicate, and delete layers while the
composite and thumbnails respond correctly and edits remain isolated to the active layer.

### D. Selection and fill correctness

Flood fill respects boundaries; selection move/delete/flip behaves predictably; every
operation is reversible and never paints outside document bounds.

### E. Durable delivery

Reload restores the project, corrupt data recovers safely, project JSON round-trips, PNG
exports have correct dimensions, and the production build works without runtime network.

### F. Responsive craft

At 390×844, the canvas and critical tools remain usable, drawers do not trap focus or
overflow, touch interaction does not fight page scrolling, and export remains reachable.

### G. Honest release

All required scripts, tests, screenshots, documentation, hooks, and reports exist and
match what was actually verified. There are no hidden placeholders or false claims.

## 15. Recommended execution sequence

1. Inspect the empty/current workspace and available toolchain once.
2. Define the document, pixel, layer, history, and serialization domain model.
3. Scaffold the build and establish a running canvas immediately.
4. Implement and test raster algorithms independently from interface code.
5. Implement pencil, eraser, fill, shapes, coordinates, zoom, and pan.
6. Implement layers, history, selection, palette, persistence, and import/export.
7. Build the complete responsive workspace and accessible dialogs/drawers.
8. Generate and load Sunset Courier using the same real document model.
9. Add browser scenarios and run static analysis, unit tests, build, and E2E.
10. Use the actual editor to modify an image and validate the exported artifact.
11. Inspect desktop/mobile screenshots with vision and computed-style checks; fix defects.
12. Write documentation and the benchmark report from actual results.
13. Re-run decisive tests after final changes and inspect the delivery tree.
14. Only then provide the final delivery response.

Do not spend the run repeatedly describing the plan. Advance the working product. If an
approach, dependency, or optional feature fails, diagnose it briefly, switch to the most
reliable fallback, and continue without silently dropping hard requirements.

## 16. Benchmark priorities

The evaluator prioritizes:

1. Correct, satisfying drawing and editing behavior.
2. Autonomous completion, truthful verification, and recovery from defects.
3. Layer/history/selection/persistence integrity.
4. Visual coherence and professional creative-tool ergonomics.
5. Export correctness and offline reproducibility.
6. Responsive and accessible interaction quality.
7. Maintainable architecture and meaningful tests.
8. Optional flourish only after all core behavior works.

A compact, coherent editor scores higher than a broad collection of broken tools, but
omitting required systems is not an acceptable form of scope reduction.

## 17. Final-response contract

Your final response must be a concise factual delivery note only after the application is
genuinely complete. Include the product name and path, exact install/run/test/build
commands, exact verification results, documentation and screenshot locations, and honest
remaining limitations.

Do not end with a plan, code for the user to assemble, an offer to continue, or a request
for approval. The delivered editor—not an explanation—is the result.
