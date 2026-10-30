# Lumen 1.0

A self-contained Whitted ray tracer written in pure standard-library Python.

Produced 2026-10-29 23:36 by **DeepSeek V4.1 Flash (opencode)**.

## Run

```bash
python3 raytracer.py gallery.scene gallery.ppm
python3 raytracer.py corner.scene corner.ppm
```

`gallery.scene` and `corner.scene` are the reference scenes from the task. Both
render to binary P6 PPM images (top row first).

## Files

| File | Purpose |
| --- | --- |
| `raytracer.py` | Entry point: CLI contract, banner, scene summary, progress log, PPM writer. |
| `lumen_scene.py` | Strict line-oriented scene parser and validator. |
| `lumen_render.py` | Camera model, ray intersections, Phong shading, shadows, checkerboard selection, recursive reflections, supersampling. |
| `gallery.scene` | Reference scene: red / mirror / green spheres on a checkered floor. |
| `corner.scene` | Reference scene: blue / chrome / gold spheres, wood checker floor, back wall. |
| `gallery.ppm`, `corner.ppm` | Example renders produced by this implementation. |

## Implementation notes

- **Parser:** comments are stripped at `#`; blank lines are ignored; directives
  are matched case-sensitively. All numeric tokens are checked against strict
  decimal spellings, so `nan`, `inf`, underscores, and hex forms are rejected.
  All validation finishes before the output file is opened.
- **Camera:** orthonormal basis from eye / look-at / up, image plane at unit
  distance, vertical FOV, aspect-corrected width, normalized rays.
- **Intersections:** analytic sphere quadratic and infinite plane, nearest
  hit with `t > 1e-4`; the same routines are used for shadow occlusion.
- **Shading:** `ambient + sum(light * (diffuse * max(0, N·L) + specular *
  max(0, R·V)^shine))` for every unoccluded point light; shadows start at
  `P + N * 1e-4`.
- **Reflections:** recursive `D - 2(D·N)N` bounces while depth remains, then
  the result is weighted by the material's `reflect`. `depth 0` therefore keeps
  local shading but produces no mirror bounces.
- **Checker planes:** orthonormal in-plane basis derived from the normalized
  normal, with the required fallback for normals parallel to `(0, 1, 0)`.
- **Supersampling:** deterministic `n × n` uniform sub-pixel grid, averaged in
  linear color, clamped only when quantizing to bytes.
- **Logging:** banner and scene summary, progress every ≤2% of rows (60 updates
  for both reference scenes), elapsed time and ETA, then a completion line with
  total time, ms/pixel, path, and byte size. All output is flushed.
- **Determinism:** no randomness, no threads; repeated runs are byte-identical.

## Verification performed

- `gallery.ppm`: 320×240 P6, 230415 bytes; checkered floor, red/green/mirror
  spheres, mirror reflecting the floor and both neighbours, Phong highlights,
  and two-light shadows.
- `corner.ppm`: 240×180 P6, 129615 bytes; wood checker floor, matte wall,
  blue/chrome/gold spheres with cool fill light.
- `depth 0` copy: mirror sphere becomes dark (local shading only).
- `samples 1` copy: visibly more jagged silhouettes than `samples 2`.
- Two renders of the same scene: `cmp` reports identical files.
- Bad scenes (`torus`, duplicates, missing directives, bad numbers, ranges,
  wrong argument counts) exit 1 with `error: file:line: message` and write no
  PPM.
- Local timings: gallery 2.4–3.1 s, corner 5.0–6.5 s (well under the 5/10
  minute targets).
