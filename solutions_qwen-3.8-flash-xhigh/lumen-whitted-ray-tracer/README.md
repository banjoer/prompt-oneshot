# Lumen — a Whitted ray tracer with a scene file format

**Challenge:** [`oneshots/lumen-whitted-ray-tracer.md`](../../oneshots/lumen-whitted-ray-tracer.md) (🔴 Extreme)
**Built by:** Qwen 3.8 Flash (xhigh) on 2026-10-30 00:10 — pure Python 3.9+ standard library, no numpy, no Pillow.

## Run

```sh
python3 raytracer.py gallery.scene gallery.ppm
python3 raytracer.py corner.scene corner.ppm
```

Wrong argument counts print a usage line to stderr and exit non-zero; fatal
scene errors exit 1 in the form `error: <file>:<line>: <message>` and never
write the PPM.

## Files

| File | Role |
|------|------|
| `raytracer.py` | entry point: CLI, banner/scene summary/progress log/completion line, PPM writer |
| `lumen_scene.py` | line-by-line scene-language parser + all validation rules |
| `lumen_render.py` | camera basis, analytic ray–sphere/ray–plane intersections, Phong + hard shadows + recursive Whitted reflections + checkerboards, supersampled pixel loop |
| `gallery.scene`, `corner.scene` | the two reference scenes, verbatim from the challenge |
| `gallery.ppm`, `corner.ppm` | rendered results (binary P6) |
| `ppm2png.py` | optional viewer helper (struct+zlib, not part of the renderer) |

View results with any PPM-capable viewer (`display x.ppm`, `feh x.ppm`, GIMP,
`convert x.ppm x.png`) or with the bundled helper:
`python3 ppm2png.py gallery.ppm gallery.png`.

## Measured performance (this machine, 4-core laptop, single-threaded)

| Scene | Config | Time | Target |
|-------|--------|------|--------|
| `gallery.scene` | 320×240, 2×2 samples, depth 4 | **~2.5 s** | < 5 min |
| `corner.scene` | 240×180, 3×3 samples, depth 3 | **~4.5 s** | both < 10 min |

## Console log (excerpt, actual)

```
lumen 1.0 — built by Qwen 3.8 Flash (xhigh) on 2026-10-30 00:10
scene: gallery.scene — 320x240, 2x2 samples, depth 4, 4 objects, 2 lights
output: gallery.ppm
rendering: [  1/240 rows]   0.4%  elapsed   0.0s  eta   0.6s
rendering: [  5/240 rows]   2.1%  elapsed   0.0s  eta   0.6s
... 60 updates, never a gap wider than 2% of rows ...
done: 320x240 in   2.2s (0.03 ms/pixel) -> gallery.ppm (230415 bytes)
```

Updates go to real stdout, one line each when piped; a carriage-return line
is used only when stdout is a TTY.

## Implementation notes

* **Hot-loop discipline** — the whole integrator works on flat tuples of
  floats with inlined component math; locals are bound at the top of
  `render()`; the pixel loop allocates nothing per ray except the final
  RGB triple. This is why pure Python beats the 5-minute budget by ~100×.
* **Camera (req 5)** — `forward = normalize(look−eye)`,
  `right = normalize(forward×up)`, `trueUp = right×forward`, plane at 1 unit,
  half-height `tan(fov/2)`, half-width ×`aspect`; every ray normalized.
  Row 0 is the top of the image.
* **Integrator (reqs 6–9)** — quadratic sphere solve and plane intersection,
  nearest `t > 1e-4`; Phong with `color = ambient + Σ light·(diffuse·max(0,N·L)
  + specular·max(0,R·V)^shine)` where `R·V` is computed algebraically as
  `2(N·L)(N·V) + L·D`; shadow rays from `P + N·1e-4` blocked when
  `1e-4 < t < distance`; reflection `color += reflect·trace(D−2(D·N)N, depth−1)`
  from `P + N·1e-4`. No clamping until byte quantization.
* **`depth 0` semantics (req 9, literal)** — the spec defines
  `trace(ray, 0) → background`, so at `depth 0` even primary rays return the
  background: the rendered image is the uniform background color and every
  reflection (and the mirror sphere with them) is gone. The sample scenes use
  depth 3–4 and are unaffected.
* **Checkers (req 10)** — `u = normalize(N×(0,1,0))` with the `(1,0,0)`
  fallback for `N ∥ (0,1,0)`, `v = N×u`, parity of
  `floor(P·u/scale) + floor(P·v/scale)` picks the material; shadows and
  reflections then use that material.
* **Supersampling (req 11)** — uniform `(x+(i+0.5)/n, y+(j+0.5)/n)` grid,
  averaged; no RNG anywhere, so repeated runs are byte-identical
  (verified with `cmp`).
* **Validation (reqs 2–4)** — unknown directives, bad arities, bad keywords
  inside `material`, non-numeric/out-of-range tokens, duplicate
  `image`/`camera`/material names, missing required directives at EOF,
  materials referenced before definition, zero-length plane normals,
  degenerate camera bases — all fatal, reported with line numbers (file-wide
  problems without), exit 1, no output file.

## Verified acceptance items

- ✅ both scenes render to valid P6 PPMs of the exact declared sizes, viewable
  (checkered floor to the horizon; red/mirror/green spheres; mirror reflects
  floor **and** both neighbours; Phong highlights; two distinct shadows per
  object from the two lights; corner shows the wood checker floor, matte wall
  and blue/chrome/gold spheres with the cool light on their right flanks).
- ✅ `depth 0` copy → image becomes uniform background (all reflections gone).
- ✅ `samples 1` copy → visibly stair-stepped silhouettes vs smooth `samples 2`.
- ✅ `torus 0 0 0 1` appended →
  `error: <file>:<line>: unknown directive 'torus'` on stderr, exit 1, no PPM.
- ✅ double render `cmp`-clean on both scenes.
- ✅ 60 real-time progress updates with rows/percent/elapsed/ETA; first
  update < 0.1 s; completion line with time, ms/pixel, path and byte size.
- ✅ every `.py` file carries the date/time + model/author header and the
  banner prints the same credit.

Stretch goals (refraction, area lights, multiprocessing) intentionally not
included: the base requirement's performance budget is met ~100× over with
deterministic single-threaded code.
