# Rigsmith — SVG Character Factory with Engine-Ready Sprite Sheets

**Difficulty:** extreme  |  **Stack:** HTML/CSS/JS (single file, SVG + Canvas 2D export)  |  **Estimated time:** 10–16 hours

## The Problem

A 2D game needs nine locomotion/emote clips plus six facial expressions, each as a
frame sequence, and every character variant multiplies that work. Commercial tools
(Spine, Rive, DragonBones) solve this by separating a **parametric rig** from a
**clip library**, then baking the rig into atlases an engine can consume. Without
that separation, artists hand-draw hundreds of frames and any proportion tweak
invalidates all of them. Build a browser-only character factory: dial a creature's
body, face, and style with live sliders, watch a shared skeleton drive nine body
clips and six expressions on three different archetypes, zoom into the face, then
bake a transparent PNG sprite sheet plus a TexturePacker-style JSON atlas that
drops into Phaser/PixiJS without post-processing.

## Requirements

1. **Single-file app.** Deliver one `index.html` with embedded `<style>` and
   `<script>`. It must run by double-clicking the file (`file://`), with no server,
   build step, package manager, or network access. The workbench is a three-pane
   layout: control rack on the left, character stage in the center, animation rail
   and export panel on the right/bottom. It must remain usable at 1280×800 without
   elements overlapping or being unreachable.

2. **Deterministic character spec.** All character appearance flows from one
   serializable `spec` object (numeric parameters + enum choices + a numeric
   `seed`). Use a seeded PRNG (e.g. mulberry32 or xorshift32) for every randomized
   decoration (patterns, freckles, tufts); `Math.random()` must not be used
   anywhere in the character, pose, or export path. The current seed is always
   visible and editable, with a dice button for a new seed. The same seed + spec
   must produce byte-identical serialized SVG frames on repeated renders.

3. **Three archetypes on one rig.** Provide `humanoid` (upright biped: two arms, two
   legs, neck, round head), `beast` (quadruped/anthro: forelegs mapped to the arm
   chain, hind legs to the leg chain, snout, ears, tail), and `blob` (gelatinous
   body with stub limbs, squash-and-stretch, minimal neck). They must be visibly
   different in topology and silhouette, not just recolored. All three expose the
   same canonical bone names — `root`, `hips`, `spine`, `chest`, `neck`, `head`,
   `shoulder/elbow/wrist` L/R, `hip/knee/ankle` L/R, `tail`, `ear` L/R — so the
   same clip library drives all of them. Switching archetype keeps every slider
   value and the active clip. A **bone overlay** toggle draws the skeleton
   (joints as dots, bones as lines) over the character and updates live.

4. **Live parametric controls.** At least 18 controls across three groups, each
   with a visible numeric readout and no Apply button:
   - **Body:** height (0.7–1.3), torso width (0.6–1.6), head size (0.6–1.5),
     belly (0–1), arm length (0.6–1.4), leg length (0.6–1.5), neck length (0–1),
     ear size (0–1), snout (0–1), tail length (0–1).
   - **Face:** eye size (0.6–1.6), eye spacing (0.6–1.6), pupil size (0.4–1.4),
     brow angle (−1–1), mouth curve (−1–1), blush (0–1).
   - **Style:** palette hue (0–360), saturation (0–0.9), outline weight (0–8),
     pattern density (0–1), plus enum selects for archetype, ear/horn variant,
     and style preset (at least `flat`, `ink`, `papercut`, each visibly changing
     fills, outlines, and shading treatment).

   Any control change must be reflected on the stage and every animation tile
   within one animation frame, including while animations are running.

5. **SVG-only character renderer.** The stage is an inline `<svg>` with
   `viewBox="0 0 512 512"`. All character art is SVG geometry — paths, circles,
   ellipses, gradients, patterns — never raster images, never `<foreignObject>`,
   never CSS keyframes, transitions, or SMIL to animate the character. Poses must
   be baked into element attributes (`transform`, `d`, `opacity`, fill/stroke) so
   that serializing the SVG alone reproduces exactly what is on screen. Strokes
   and details must stay crisp when zoomed to 4×.

6. **Zoom and pan.** A `Full` / `Body` / `Face` segmented control smoothly
   animates the viewBox (≤ 300 ms) and recomputes framing from current
   proportions; `Face` must center on the head even after head-size, neck-length,
   or archetype changes. Mouse wheel zooms 0.5–6× about the cursor, drag pans,
   and `Reset view` restores the active preset. All of this must work while the
   selected clip is playing.

7. **Rig, IK, and secondary motion.** Clips are keyframes over normalized time
   (0–1) with easing, driving bone rotations, translations, and scales. Legs in
   `walk`, `run`, `step`, and `crawl` must use **two-bone IK** with explicit
   contact targets: a stance foot stays on the ground line (`y = 448` in the
   512-unit viewBox) within ±2 px across its stance frames, and never floats or
   sinks. Tail and ears use a deterministic spring-damper follow-through driven
   by root/head motion. Add a ground-line + contact-shadow toggle so foot
   planting is observable.

8. **Nine body clips**, each with distinct silhouette and timing, previewable and
   exportable for all three archetypes:

   | Clip | Duration | Loop | Required read |
   |------|----------|:----:|---------------|
   | `idle` | 1.0 s | yes | breathing: chest scale + head bob, tail sway |
   | `walk` | 0.66 s | yes | alternating arm/leg swing, heel-to-toe, one foot always planted |
   | `run` | 0.4 s | yes | forward lean, bigger stride, at least two airborne frames |
   | `jump` | 1.0 s | no | crouch anticipation → launch → apex → fall → land → recover |
   | `crawl` | 1.0 s | yes | low belly, alternating limb reach, head near ground |
   | `step` | 0.6 s | yes | deliberate tip-toe/high-knee march, slower cadence than walk |
   | `taunt` | 1.2 s | no | arm gesture (beckon/wave) + head cock + chest puff |
   | `dance` | 1.2 s | yes | hip sway, alternating arm pumps, head bob, tail/wobble follow |
   | `climb` | 1.0 s | yes | alternating overhead reaches, opposite leg push, body hugging a wall |

   The stage shows the selected clip with play/pause, a 0–100 % scrub slider,
   0.25–2× speed, and a loop toggle. One-shot clips end on their final pose
   instead of snapping to the start.

9. **Face rig and six expression clips.** Eyes have sclera, iris/pupil, highlight,
   upper/lower lids, and brows; the mouth is a deformable path with optional
   teeth/tongue. Face sliders define the neutral face; expressions layer on top.
   Provide `expr_neutral`, `expr_happy`, `expr_angry`, `expr_sad`,
   `expr_surprise`, and `expr_sleepy` — 0.5 s, 4 frames, looping. Each must be
   distinguishable by brow angle, lid closure, pupil state, and mouth shape, plus
   at least one accent mark (e.g. anger vein, tear, sweat drop, `z` glyphs,
   sparkle) drawn in SVG. Expression previews use a head-and-shoulders framing.

10. **Live animation rail.** Show all 15 clips (nine body + six expressions) as
    simultaneously playing tiles, each rendering the current character and spec
    at small size, with a name label and loop/one-shot badge. Clicking a tile
    selects it on the main stage. Add a `Pause gallery` toggle and a live FPS
    readout for stage+gallery. At default spec with the gallery playing, the app
    must hold ≥ 45 FPS on a modern laptop and ≥ 55 FPS with the gallery paused.

11. **Sprite-sheet baking.** An export panel offers cell size `64 | 128 | 256`
    (default 256), frames per body clip `4–16` (default 8), and expressions fixed
    at 4 frames. One row per clip, one column per frame, columns = body frame
    count, transparent background (optional ground shadow, default off). Baking
    must: sample each clip uniformly over its duration; serialize each frame's
    SVG with explicit `width`/`height` equal to the cell size plus its own
    embedded styles; rasterize through `Image` + a single Canvas 2D atlas; yield
    between frames so the UI stays responsive; and display `Baking 37/168` progress.
    After baking, show an atlas preview on a checkerboard with its pixel
    dimensions and frame count, plus **Download PNG** and **Download JSON**
    buttons. File names are `rigsmith-<seed>-atlas.png` and
    `rigsmith-<seed>-atlas.json`; object URLs must be revoked after use.

12. **Engine-ready atlas contract.** The JSON must be a valid TexturePacker
    "JSON Array" atlas that Phaser 3 and PixiJS load without edits:
    - `meta`: `app`, `version`, `image` (matching the PNG file name),
      `size {w,h}`, `scale: "1"`, `seed`, `generatedAt` (ISO 8601), `generator`
      (see requirement 16), and `spec` (the full parameter object).
    - `frames[]`: unique `filename` `"<clip>_<NN>"` (zero-padded), `frame
      {x,y,w,h}`, `rotated: false`, `trimmed: false`, `spriteSourceSize
      {x,y,w,h}`, `sourceSize {w,h}`, `pivot` (`0.5, 0.875` for body clips so
      feet sit on the anchor; `0.5, 0.5` for expressions), and `sourceHash` — an
      8-hex-digit FNV-1a hash of that frame's serialized SVG.
    - `animations`: one entry per clip with `fps` (= frames ÷ duration, rounded
      to one decimal), `loop` boolean, and the ordered `frames` filename list.

    Frames must visually match the stage: same palette, outlines, and expression
    marks — no missing styles caused by relying on page-level CSS. Re-exporting
    the same seed + spec must produce identical `sourceHash` values.

13. **Presets and generation.** Provide three built-in presets that load the seed
    and all listed overrides exactly:

    | Preset | Archetype | Seed | Overrides |
    |--------|-----------|------|-----------|
    | Pip | humanoid | 1337 | head size 1.2, eye size 1.25, blush 0.4, mouth curve 0.35, hue 24, style `ink` |
    | Moss | beast | 90210 | snout 0.85, ear size 0.9, tail length 0.9, pattern 0.6, hue 96, outline 2, style `flat` |
    | Gloop | blob | 4242 | belly 0.95, eye spacing 1.35, leg length 0.7, pattern 0.7, hue 282, style `papercut` |

    `Randomize` derives a new seed and jitters parameters within their ranges
    without producing NaN or invisible faces; `Reset` restores the defaults from
    Sample Data. A preset must reproduce the identical character after a reload.

14. **Local persistence and shortcuts.** Persist spec, seed, selected clip, and
    zoom preset to `localStorage` and restore on load; `Reset all` clears storage
    and defaults. Keyboard: `Space` play/pause, `1/2/3` Full/Body/Face, `[`/`]`
    previous/next clip, `B` bone overlay, `E` bake export. Shortcut hints are
    visible in the UI.

15. **Robustness.** No console errors or unhandled promise rejections in a current
    Chrome, Firefox, or Safari. Exporting at 256 px with 16 body frames (168
    frames total) must complete in under 30 s with continuous progress. The page
    must never lock up during baking, and the atlas canvas must stay within
    browser limits at every offered setting.

16. **Sign-off:** the finished app must show, in an always-visible footer, the
    date and time it was produced and the model/author that produced it; repeat
    the same sign-off as a header comment at the top of `index.html`; and stamp it
    into the exported JSON as `meta.generator` (author/model) and
    `meta.generatedAt` (export time).

## Constraints

- One `index.html`, embedded `<style>` and `<script>`; no external CSS, JS,
  fonts, icon packs, libraries, or CDNs. Use a system font stack.
- Vanilla JS only. SVG for all character rendering; Canvas 2D only for export
  rasterization. No WebGL, no `<foreignObject>`, no SMIL/CSS animation for poses.
- No network calls of any kind. Exports are generated locally and downloaded with
  `Blob`/object URLs.
- Storage is `localStorage` only; no cookies, no IndexedDB requirement.
- One skeleton, one clip library, three archetypes: no per-archetype clip
  duplication (retarget through bone mapping instead).
- Must run from `file://` in current Chrome, Firefox, and Safari.

## Sample Data / Inputs

Default spec:

| Parameter | Default | Parameter | Default |
|-----------|---------|-----------|---------|
| archetype | `humanoid` | eye size | 1.0 |
| seed | 1337 | eye spacing | 1.0 |
| height | 1.0 | pupil size | 1.0 |
| torso width | 1.0 | brow angle | 0 |
| head size | 1.0 | mouth curve | 0.15 |
| belly | 0.25 | blush | 0.2 |
| arm length | 1.0 | hue | 22 |
| leg length | 1.0 | saturation | 0.55 |
| neck length | 0.4 | outline weight | 3 |
| ear size | 0.6 | pattern density | 0.35 |
| snout | 0.2 | style preset | `ink` |
| tail length | 0.3 | ear variant | `round` |

Clip table (preview timing and default export frame counts): `idle` 8 frames,
`walk` 8, `run` 6, `jump` 10, `crawl` 8, `step` 6, `taunt` 10, `dance` 12,
`climb` 8; expressions 4 each. Export defaults: 256 px cells, 8 body frames,
transparent background, no shadow, 15 rows, 8 columns (at defaults) →
2048×3840 px, 96 frames.

Manual test script — expected observations:

1. Open the file → Pip (humanoid, seed 1337) stands on the ground line; the
   gallery shows 15 animated tiles; footer sign-off is visible; FPS ≥ 45.
2. Drag **head size** from 0.6 to 1.5 while `walk` plays → head and face scale
   every frame, zoom presets still frame the head, no clipping off-canvas.
3. Click `Face` → the view animates to a head-and-shoulders crop; change **brow
   angle**, **mouth curve**, and **pupil size** → changes are immediate and
   visible at 4× zoom.
4. Switch to `beast` → the same walk clip plays with four contact legs and a
   tail follow-through; bone overlay shows forelegs on the arm chain. Repeat with
   `blob` → squash-and-stretch locomotion, no broken poses.
5. Select `jump` → crouch, launch, airborne, land, recover, then hold the final
   pose (no snap). Select `dance` → hips sway and arms alternate; scrub to 50 %
   and back → deterministic pose, gallery in sync.
6. Toggle ground line + shadow → stance feet in `walk` stay on the line across
   contact frames within ±2 px; `run` shows airborne frames.
7. Note the seed, randomize, then enter the seed and reload the preset → the
   character is identical. Export at 256/8 → progress advances, UI stays
   interactive; the preview shows a transparent 2048×3840 atlas.
8. Open the PNG in an image viewer → rows are clips, unused cells transparent,
   colors/outlines match the stage. Inspect the JSON → `frames`, `animations`,
   `meta`, and `sourceHash` present; bake again → hashes unchanged.

## Deliverable

- `index.html` — the complete character factory, animation previews, and export
  pipeline.
- Run: open `index.html` in a current browser (double-click; no server needed).

## Done When

- [ ] `index.html` opens offline from `file://` with a three-pane workbench, visible footer sign-off, and no console errors.
- [ ] Three archetypes are visibly distinct yet share one skeleton and all nine body clips.
- [ ] At least 18 sliders/pickers update the stage and all 15 tiles within a frame, with numeric readouts.
- [ ] `Full`/`Body`/`Face` zoom presets animate smoothly, track head position as proportions change, and wheel/drag zoom-pan works during playback.
- [ ] Bone overlay shows a coherent skeleton for each archetype; ground-line mode proves stance feet stay planted within ±2 px.
- [ ] All nine body clips read as specified, with jump/taunt ending on their final pose and run showing airborne frames.
- [ ] Six expression clips are visually distinct and layer correctly over the face sliders.
- [ ] The 15-tile gallery plays live, selecting tiles drives the stage, and FPS targets are met.
- [ ] Baking shows frame progress, keeps the UI responsive, and produces a transparent atlas preview at the chosen cell size.
- [ ] Downloads yield `rigsmith-<seed>-atlas.png` and a valid TexturePacker JSON atlas with correct rects, pivots, animations, spec, and stable `sourceHash` values.
- [ ] Presets Pip/Moss/Gloop reproduce exactly, and spec + seed survive a reload via `localStorage`.
- [ ] Keyboard shortcuts, reset, and randomize work without producing invalid geometry.

## Stretch Goals (optional)

- **Timeline editor:** expose keyframes for the selected clip with draggable bone rotation handles and onion-skin ghosting.
- **Palette variants:** bake a second atlas recolored for team variants, driven by a hue-rotation offset and recorded in `meta`.
- **Godot/Aseprite export:** add a `.tres` SpriteFrames resource and an Aseprite-style JSON hash in addition to the TexturePacker array.
