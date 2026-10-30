# ONE-SHOT AUTONOMOUS BENCHMARK: BUILD AND DELIVER A BROWSER FLOOR-PLAN CAD TOOL

You are the sole product architect, CAD interaction designer, computational-geometry
engineer, senior frontend engineer, accessibility specialist, QA engineer, and release
engineer for this task. In the current working directory, create a complete polished
browser-based interior floor-plan editor called **Planform Studio**.

This is a strict one-shot autonomy benchmark. There will be no clarifications, approvals,
follow-up instructions, or second attempt. Once you stop, the submission is frozen and
judged exactly as delivered.

Do not stop at a product plan, static mockup, SVG diagram, room configurator, or partially
connected toolbar. Work continuously through domain modeling, geometry, editing
interactions, responsive UI, persistence, import/export, calculations, testing, real
browser verification, visual debugging, documentation, screenshots, and final delivery.
Make strong reasonable decisions without asking questions.

## 1. Product mission

Planform Studio is a local-first lightweight space-planning tool for homeowners,
designers, and students. It allows a user to sketch an orthogonal apartment plan, place
openings and furniture, inspect real dimensions and areas, compare material quantities,
save locally, and export a useful plan. It should feel like disciplined compact CAD—not
a decoration game, generic dashboard, or marketing page.

Use an original visual identity: architectural, calm, precise, tactile, and legible.
Consider warm drawing-paper neutrals, charcoal construction lines, restrained terracotta
or cobalt accents, excellent typographic numerals, and crisp custom SVG icons. Avoid fake
luxury branding, photorealistic furniture imagery, and ornamental interface chrome that
interferes with drawing.

The initial application must open a complete editable example called **Courtyard Flat**:
an original approximately 82 m² two-bedroom apartment with living/dining area, kitchen,
bathroom, entry, circulation, exterior walls, internal walls, doors, windows, room labels,
dimensions, and a small set of furniture. It must be generated from the same real project
model used for user-created plans—not rendered as a background image.

## 2. Scope, licensing, and safety

- The current working directory is the entire project and delivery boundary.
- Do not inspect, reuse, compare against, or modify another contestant's output.
- Do not alter host services, GPU/model configuration, Ollama, OpenCode, Docker, or files
  outside the project.
- Do not use accounts, credentials, paid APIs, hosted databases, analytics, or telemetry.
- The application must work offline after dependencies are installed.
- Do not hotlink runtime fonts, icons, images, scripts, maps, or APIs.
- Prefer original SVG/CSS/procedural assets. Internet research may use primary technical
  documentation and permissively licensed sources only.
- Record third-party source, author, license, and modifications in `ATTRIBUTIONS.md`.
  Include it even when all assets are original.
- Do not copy a commercial CAD application's branding, proprietary icons, templates,
  floor plans, furniture catalogue, or trade dress.
- Use reasonable assumptions and robust fallbacks. Do not wait for user input.

## 3. Technical and architectural requirements

Choose the stack most likely to deliver precise interaction and maintainable state in one
run. TypeScript with a conventional local build is preferred. SVG is strongly encouraged
for the drawing plane because it supports inspectable geometry, crisp export, and DOM
automation; Canvas or a hybrid renderer is acceptable if it remains accurate and tested.

Hard requirements:

- Modern desktop-browser application with no backend.
- Production build, preview, static analysis, unit tests, and browser E2E commands.
- No essential runtime network dependency after installation.
- A model-view separation: geometry and project state must not exist only as rendered DOM.
- Internal dimensions stored consistently in centimetres or millimetres, never derived
  from current screen pixels.
- Versioned project schema, local autosave, and safe corrupt/unsupported-data handling.
- Accurate screen/world coordinate conversion at every supported zoom and device scale.
- Modular code; avoid a single enormous component or file.
- Zero known dead buttons, placeholder inspectors, fake exports, console errors, or TODO
  features in the delivered interface.
- No required production environment variables or secrets.
- Stable evaluator hooks from section 12 must remain attached to real UI elements.

## 4. Drawing-space model

### 4.1 Project and units

- New-plan dialog with name, unit display, initial drawing size, and blank/example choice.
- Store geometry in metric base units; allow display in metres/centimetres and optionally
  feet/inches without corrupting underlying geometry.
- Sensible project bounds equivalent to at least 3×3 m through 30×30 m.
- Display project name, saved/dirty state, active tool, cursor coordinates, zoom, and snap.
- Validate impossible or extreme numeric input with useful inline messages.
- Confirm destructive replacement/reset when unsaved work could be lost.

### 4.2 Viewport and grid

- Infinite-feeling but safely bounded drawing surface with major/minor metric grid.
- Zoom from an overview through detailed opening/furniture placement.
- Mouse-wheel/trackpad zoom centered sensibly on the pointer.
- Pan with a hand tool and Space-drag or middle-button drag.
- Fit plan, zoom in/out, and explicit zoom readout.
- Toggle grid, dimensions, furniture, and labels without deleting data.
- Grid density and labels adapt to zoom rather than becoming illegible noise.
- Prevent revealing broken renderer voids or losing the complete plan irrecoverably.

## 5. Required architectural editing

The plan must be truly editable. Every committed edit must be reflected in project state,
calculations, rendering, persistence, history, and export.

### 5.1 Rooms and walls

- **Room tool** (`R`): drag an axis-aligned rectangular room with live width, depth, and
  area preview. Set a minimum practical size.
- Select, move, resize, duplicate, rename, and delete rooms.
- Resize handles snap to the active grid and show live dimensions.
- Room inspector allows exact numeric width/depth and meaningful room type.
- Render outer and shared/internal wall boundaries clearly. Shared coincident room edges
  must not produce an unreadable double-heavy wall.
- Support standalone orthogonal wall segments with a **Wall tool** (`W`) or provide an
  equivalently capable method for creating partitions not expressible as room rectangles.
- Wall thickness is represented consistently in drawing and calculations.
- Prevent zero-length geometry and handle overlaps/intersections deterministically.
- Room labels show name and area and remain centered or intelligently placed.

### 5.2 Doors and windows

- Door and window tools place openings only on valid wall segments.
- Snap opening position and orientation to the selected wall.
- Door properties include width and left/right or inward/outward swing where relevant.
- Render a recognizable door leaf and swing arc, not merely a colored rectangle.
- Window properties include width and a clear wall opening symbol.
- Move, duplicate, edit, flip, and delete openings.
- Reject or resolve openings that extend beyond a wall or overlap another opening.
- Moving/resizing related geometry must keep attached openings valid or communicate why
  an opening was removed/repositioned.

### 5.3 Selection and manipulation

- Select tool (`V`) supports clicking objects and a rectangular multi-select marquee.
- Selected objects have unambiguous outlines/handles distinct from hover.
- Move with pointer drag and nudge using arrow keys; modified arrow key may use a larger
  increment.
- Delete/Backspace, duplicate, copy, cut, paste, select all, and Escape-to-cancel where
  conventional and safe.
- Alignment commands for multi-selected movable objects: left, center, right, top,
  middle, bottom; distribute where practical.
- Numeric inspector edits must be undoable and not create one history step per keystroke.
- Locking an object against accidental movement is encouraged but not required.

## 6. Furniture and fixtures

Provide an original compact local symbol library—no external runtime catalogue.

Required symbols:

- Single bed, double bed, sofa, armchair, dining table, dining chair.
- Kitchen counter, sink, cooker, refrigerator.
- Toilet, basin, shower or bath.
- Wardrobe, desk, plant, and one outdoor/courtyard object.

Behavior:

- Browse/search by category and drag or insert onto the plan.
- Symbols use simple readable top-down SVG/procedural geometry.
- Select, move, rotate in 90° increments, duplicate, and delete.
- Display real footprint dimensions in the inspector.
- Snap to grid and optionally align to nearby walls/objects.
- Warn rather than silently corrupt when furniture lies outside room/project bounds.
- Furniture must never be baked into the background; it participates in save/export.

## 7. Measurements and calculations

- Automatic width/depth dimensions for selected rooms.
- Dedicated measure tool (`M`) for point-to-point orthogonal or Euclidean distance.
- Dimension text remains readable and does not scale into unusable sizes.
- Live room area in square metres using real project units.
- Project summary with total room area, room count, wall length, opening count, and
  furniture count.
- Material estimate panel using explicitly stated fictional assumptions:
  - Flooring area by room/type with configurable 10% waste default.
  - Paintable wall surface estimate using configurable ceiling height, subtracting a
    simplified opening area.
  - Baseboard/skirting length estimate excluding door widths where feasible.
- Clearly label estimates as planning aids, not construction or engineering advice.
- Calculations update immediately after relevant edits and are unit tested.

## 8. History, persistence, and project files

- Undo/redo buttons and conventional keyboard shortcuts.
- At least 50 logical history actions; a drag/resize is one action.
- History includes geometry, properties, openings, furniture, layer/display changes where
  meaningful, deletes, duplicates, and imports.
- New work after undo invalidates the redo branch correctly.
- Autosave locally using a versioned, validated project schema.
- Restore the plan, selection-safe editing state, viewport, units, visibility settings,
  and relevant preferences after reload.
- Detect corrupt or unsupported saves and offer safe recovery/reset without a crash loop.
- Export complete editable project JSON and import it with useful validation errors.
- Include a reset-to-Courtyard-Flat command with confirmation.
- Never imply cloud backup, collaboration, or server persistence.

## 9. Export and presentation modes

- Export the full plan as a clean standalone SVG with viewBox and meaningful scale note.
- Export a high-resolution PNG preview.
- Export/print a simplified presentation sheet containing project title, plan, legend,
  scale disclaimer, room schedule, and material summary.
- Exported graphics must include current walls, openings, labels, dimensions according to
  visibility settings, and furniture if enabled.
- Use safe descriptive filenames based on the project name.
- Provide a read-only presentation mode that hides editing chrome and fits the complete
  plan without modifying project state.
- Do not claim professional blueprint, permit, structural, electrical, plumbing, or code
  compliance. Include a concise fictional/planning disclaimer.

## 10. Application interface and responsive behavior

Create a disciplined CAD workspace:

- Top bar: identity, project actions, undo/redo, visibility, presentation, export.
- Left tool rail: select, pan, room, wall, door, window, measure, furniture.
- Central drawing stage with grid and plan.
- Right inspector for selection properties, project/layers, and calculations.
- Status bar for coordinates, units, snap, zoom, selection, and contextual guidance.

Requirements:

- Concise first-run guidance teaching select, room drawing, openings, furniture, and
  export. It must be dismissible and reopenable.
- Searchable furniture panel or well-organized categories.
- Keyboard-shortcut/help dialog.
- Clear invalid-placement feedback and cancel behavior.
- No fake collaborators, cloud sync, subscription prompts, comments, or dormant tools.
- Use custom coherent icons with accessible names; do not rely on unlabeled glyphs.

Responsive targets:

- Excellent at 1440×900 and usable at 1280×720.
- At 390×844, provide a genuinely usable review/light-editing mode: plan remains visible,
  pan/zoom/select work, essential tools are reachable, and inspector/furniture/calculation
  panels use accessible drawers or sheets.
- No horizontal page overflow or controls permanently outside the viewport.
- Touch targets are practical and plan gestures do not unpredictably scroll the page.
- It is acceptable to simplify advanced multi-select alignment on phones, but do not
  replace the application with a “desktop required” message.

## 11. Accessibility and interaction quality

- Semantic buttons, labels, groups, dialogs, tabs, status, and error announcements.
- Complete keyboard access to UI chrome and sensible shortcuts for drawing operations.
- Strong focus indicators and logical focus restoration after dialogs/drawers.
- Focus containment in modal dialogs; Escape closes non-destructive overlays.
- Selection, invalid placement, active tool, and warnings never rely only on color.
- Respect reduced motion; geometry editing must not depend on transitions.
- Provide a textual project summary and selected-object description for users who cannot
  interpret the spatial drawing.
- Mark decorative SVG geometry appropriately without hiding important object names/state.
- Prevent canvas shortcuts while typing in an input.
- Maintain readable contrast against both drawing paper and application chrome.

## 12. Stable evaluator hooks

Attach these exact hooks to the corresponding genuine application elements:

- `data-testid="app-shell"`
- `data-testid="app-title"`
- `data-testid="floorplan-canvas"` on the real SVG/canvas/drawing surface
- `data-testid="tool-select"`
- `data-testid="tool-room"`
- `data-testid="tool-door"`
- `data-testid="undo"`
- `data-testid="redo"`
- `data-testid="inspector"`
- `data-testid="project-summary"`
- `data-testid="new-plan"`
- `data-testid="new-plan-confirm"` on the destructive confirmation action
- `data-testid="export"`
- `data-testid="export-svg"` on the actual SVG download action
- `data-testid="export-project"` on the actual editable-project JSON download action
- `data-testid="coach-dismiss"` on the first-run guidance dismissal action
- `data-testid="inspector-toggle"` on the narrow-layout inspector drawer/sheet control

The genuine `floorplan-canvas` element must expose these live, derived state attributes:

- `data-room-count`
- `data-opening-count`
- `data-furniture-count`
- `data-selected-count`
- `data-total-area-m2`

These hooks supplement rather than replace accessible roles and names. Do not create
hidden dummy controls, hard-coded counters, or separate evaluator-only state to satisfy
them. The evaluator will use these controls to create a blank project, draw and select a
room, undo/redo, reload, and validate genuine SVG and editable JSON downloads.

## 13. Testing contract

Meaningful automated tests are mandatory. Keep geometry/calculation logic sufficiently
pure that it can be verified without relying entirely on browser screenshots.

### Required unit/integration coverage

- Screen/world coordinate conversion across zoom/pan.
- Grid snapping for positive and negative coordinates.
- Rectangle normalization, resizing, bounds, and area.
- Orthogonal wall length, shared-edge handling, and zero-length rejection.
- Door/window placement projection, orientation, wall bounds, and overlap rejection.
- Selection movement, nudge, rotation, duplication, and multi-object alignment.
- Undo/redo grouping and redo-branch invalidation.
- Room/project area, wall length, flooring waste, paint, and skirting estimates.
- Unit display conversion and parsing.
- Project serialization round trip, migration path, and corrupt input rejection.
- SVG export contains expected project geometry and valid bounds.

### Required browser E2E scenarios

1. Courtyard Flat loads with recognizable rooms, labels, openings, furniture, dimensions,
   project identity, summary, and no console errors.
2. Create a blank plan, draw a room, verify width/depth/area, rename it, and edit a numeric
   property.
3. Draw or add an internal wall and reject a zero-length attempt.
4. Place a door and window on valid walls; invalid/off-wall placement is prevented.
5. Insert furniture, move, rotate, duplicate, and delete it.
6. Move and resize a room; attached/rendered state and summary update coherently.
7. Undo and redo each major operation, including a grouped drag.
8. Multi-select objects and apply at least one alignment command.
9. Measure a known distance and verify the displayed result.
10. Change calculation assumptions and verify material estimates update.
11. Export SVG, PNG/presentation output, and project JSON; validate downloads.
12. Reload restores autosaved work; corrupt save/project import recovers safely.
13. Narrow viewport supports visible plan, pan/zoom/select, core tool access, inspector
    drawer, summary, and export without page overflow.
14. No runtime external requests, uncaught errors, broken resources, or placeholder UI.

Tests written by the implementation are necessary but not sufficient proof. Launch the
production build and inspect actual desktop/mobile screenshots. Verify effective opacity,
viewport intersection, clipping, occlusion, geometry rendering, selected/invalid states,
and that the first viewport contains a real plan rather than an empty grid.

## 14. Required delivery artifacts

The final directory must contain:

- Complete source, original/local assets, dependency manifest, and lockfile.
- Unit/integration and browser E2E tests.
- Production build and preview configuration.
- `README.md` with commands, architecture, units, tools/shortcuts, persistence, project
  format, calculations, exports, reset behavior, testing, disclaimers, and limitations.
- `ATTRIBUTIONS.md`, even when all graphics are original.
- `BENCHMARK_REPORT.md` with implementation decisions, exact commands/results, test
  counts, browser matrix, bundle size, screenshot inventory, defects found and fixed,
  evaluator-hook checklist, acceptance checklist, and honest limitations.
- `screenshots/` containing at least six final PNGs:
  - Desktop complete Courtyard Flat workspace.
  - Desktop room or wall editing state.
  - Door/window and furniture state.
  - Measurements/calculation or presentation view.
  - Narrow plan view.
  - Narrow inspector/furniture/summary drawer.

Screenshots must come from the final production build and reflect the delivered state.

## 15. Acceptance scenarios

### A. Immediate plan credibility

At 1440×900, Planform identity, a complete nonblank Courtyard Flat plan, architectural
tools, inspector, dimensions, summary, undo/redo, and export are visible and coherent.

### B. Geometry creation

A user can create and resize rooms/walls with reliable snapping and numeric dimensions.
Area and wall calculations match stored metric geometry rather than screen pixels.

### C. Architectural semantics

Doors/windows attach only to valid walls and render correctly. Furniture has real
footprints, can be transformed, and remains part of persistent/exported project state.

### D. Reversible editing

Selection, dragging, resizing, numeric edits, duplication, deletion, alignment, and
opening placement form logical undo/redo actions with no state corruption.

### E. Useful output

Project JSON round-trips, SVG remains crisp and complete, PNG/presentation output is
readable, calculations are clearly qualified, and filenames are safe.

### F. Durable and responsive

Autosave/reload works, corrupt state has a recovery path, production runs offline, and
the 390×844 experience supports meaningful plan inspection/editing without overflow.

### G. Honest complete release

All required scripts, hooks, tests, screenshots, documentation, disclaimers, and reports
exist and accurately describe the delivered product. No controls are decorative lies.

## 16. Recommended execution sequence

1. Inspect the workspace and toolchain once; choose SVG/Canvas architecture quickly.
2. Define project geometry, units, IDs, history commands, and serialization schema.
3. Establish a production build and render Courtyard Flat from real state.
4. Implement/test coordinate conversion, snapping, rooms, walls, openings, and selection.
5. Implement furniture, dimensions, calculations, history, persistence, and export.
6. Build the full desktop interface and responsive drawer/sheet behavior.
7. Add accessible semantics, shortcuts, guidance, invalid states, and recovery paths.
8. Run static analysis, unit tests, build, and browser E2E.
9. Use the actual application to create and modify a plan; inspect exported files.
10. Capture/inspect final desktop and narrow screenshots with vision and geometry checks.
11. Fix product defects, rerun decisive tests, and then write truthful documentation.
12. Inspect the final tree for missing artifacts, placeholders, and accidental junk.
13. Only then provide the final response.

Do not spend the run repeatedly planning or narrating. Make the application work. If an
approach fails, diagnose briefly, choose a reliable fallback, and continue without
silently removing hard requirements.

## 17. Benchmark priorities

The evaluator prioritizes:

1. Correct geometry, coordinate, snapping, and editing behavior.
2. Autonomous completion and truthful evaluator-resistant verification.
3. Undo/redo, persistence, and project/export integrity.
4. Professional CAD usability and information clarity.
5. Door/window/furniture semantics and calculations.
6. Responsive, accessible interaction.
7. Maintainable architecture and meaningful tests.
8. Optional visual flourish after core correctness.

A smaller precise tool scores above a sprawling unreliable pseudo-CAD application, but
required systems may not be replaced with screenshots or decorative controls.

## 18. Final-response contract

Only after the application is genuinely complete, respond with a concise factual delivery
note including product name/path, exact install/run/test/build commands, exact verification
results, documentation and screenshot paths, and honest limitations.

Do not end with plans, assembly instructions, promises, approval requests, or an offer to
continue. The delivered application—not the response—is the result.
