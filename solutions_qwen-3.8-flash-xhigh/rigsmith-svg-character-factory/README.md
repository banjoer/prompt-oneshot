# Rigsmith — SVG Character Factory with Engine-Ready Sprite Sheets

**Deliverable:** `index.html` — a single-file, offline, vanilla-JS character factory (SVG rig + Canvas 2D export).

## Run

- **Double-click** `index.html` (works from `file://` — no server, no build, no network).
- Optional for a real phone: serve this folder and open the LAN URL —
  `python3 -m http.server 8000` — the app itself makes zero network requests.

## What's inside

| Requirement | Where |
|---|---|
| Three-pane workbench (desktop) / pinned 50 dvh stage + tabbed panels (≤900 px), `viewport-fit=cover`, safe-area insets | CSS + `#work`/`#tabs` |
| Deterministic spec (mulberry32 seeded PRNG, unseeded RNG never called; visible/editable seed + dice) | `DEF`, `normSpec`, `mulberry32` |
| One canonical skeleton (`root,hips,spine,chest,neck,head,shoulder/elbow/wrist L/R,hip/knee/ankle L/R,tail,ear L/R`) retargeted to humanoid / beast / blob; live bone overlay | `solveJoints`, `makeBones` |
| 20 sliders + 3 enum selects, numeric readouts, sub-frame propagation to stage + all 15 tiles | `SLIDERS`, `ENUMS`, `buildControls`, `refreshTiles` |
| SVG-only renderer; poses baked into attributes; string == pixels (`serializeFrameSVG` = patched DOM) | `buildScene`, `patch`, `nodeToSVG` |
| Full/Body/Face viewBox presets (280 ms tween, rest-pose recomputation on proportion changes), wheel/drag/pinch 0.5–6×, `touch-action:none` scoped to stage, +/−/reset buttons | `setPreset`, `stepView`, `bindStagePointer` |
| Two-bone leg IK with explicit contact targets — planted soles pinned to y=448 (measured ≤0.63 px across walk/run/step/crawl frames); deterministic fixed-step spring-damper tail/ear follow-through; ground-line + contact-shadow toggle | `ikPair`, `soleY`, `springVal`, `springOffsets` |
| 9 body clips (idle/walk/run/jump/crawl/step/taunt/dance/climb) + 6 expression clips (neutral/happy/angry/sad/surprise/sleepy, 0.5 s × 4 frames, accent marks: blink dots, sparkles, anger vein, tear, sweat drop, zzz glyphs) | `clipAct`, `EXPR_FACE`, `makeFace` |
| Live 15-tile gallery with badges, click-to-select, Pause-gallery, FPS readout (60 FPS desktop, 56–58 FPS in 390×844 touch emulation with the gallery playing; 60 paused) | `buildRail`, loop scheduling |
| Sprite-sheet baking: 64/128/256 cells, 4–16 body frames, uniform sampling, `Baking n/N` progress, yields between frames (~3 s for 168 frames at 256 px in headless Chromium), canvas-limit probe with auto cell reduction + notice, checkerboard preview, `rigsmith-<seed>-atlas.png/json`, revoked object URLs, new-tab fallback + save hint for mobile | `probeCanvas`, `bake`, `saveURL` |
| TexturePacker JSON Array atlas: `meta` (app/version/image/size/scale/seed/generatedAt/generator/spec), `frames[]` with rects, pivots (0.5/0.875 body, 0.5/0.5 expr), 8-hex FNV-1a `sourceHash` (stable across re-bakes), `animations` with fps/loop/ordered frames | `bake` JSON block |
| Presets Pip / Moss / Gloop reproduce exactly; Randomize (no NaN/invisible faces); Reset; Reset-all | `PRESETS`, `randomize` |
| localStorage persistence (spec+seed, clip, zoom preset) + keyboard `Space 1 2 3 [ ] B E` with visible hints | `saveNow/loadSaved`, `bindKeys` |
| Sign-off: header comment, always-visible footer, `meta.generator` | `BUILT`/`GEN` constants + markup |

## Manual test aids

`window.__rs` exposes `plantCheck(clip, N)` (sole deviations from the ground line),
`serializeFrameSVG` (determinism), and `bake()` for scripted verification.

## Verified with (headless Chromium, Playwright)

- Zero console errors / page errors / unhandled rejections on `file://`.
- Byte-identical repeated frame serialization; identical `sourceHash` arrays across two bakes.
- Planted-foot sole deviation: walk 0.00, run 0.63, step 0.00, crawl 0.00 px (spec: ±2).
- Defaults bake: 2048×3840 px, 96 frames (72 body + 24 expr), 15 rows, 8 cols in ≈3 s;
  256×16 → 4096×3840, 168 frames in ≈3.2 s (spec: <30 s).
- 360×640 touch emulation: no horizontal page scroll, 50 dvh stage, tabbed panels, live swipeable rail.
- Reload/resize preserves spec, seed, clip, and zoom preset; Pip/Moss/Gloop reproduce.
