# Lumen: A Whitted Ray Tracer with a Scene File Format

**Difficulty:** extreme  |  **Stack:** Python 3.9+ (standard library only, multi-file allowed)  |  **Estimated time:** 8–12 hours

## The Problem

Before GPUs ate the world, ray tracing was how you proved a renderer was correct: fire a ray per pixel, bounce it around a scene, and let physics do the lighting. Production tools like POV-Ray showed that a *text scene description language* plus a compact Whitted integrator is enough to produce genuinely beautiful images — and it remains one of the best end-to-end tests of a programmer's command of parsing, 3D math, numerical edge cases, and performance discipline. Your job is to build **Lumen**: a self-contained Python ray tracer that reads a declarative scene file (camera, spheres, planes, Phong materials, point lights), renders it with recursive mirror reflections, hard shadows, and checkerboard floors, supersamples for anti-aliasing, narrates its own progress in the console like a real render farm job, and writes a binary PPM image you can open and look at. No numpy, no Pillow — just the standard library and correct math, fast enough to render the sample scenes in minutes, not hours.

## Requirements

1. **CLI contract.** The program runs as `python3 raytracer.py <scene-file> <output.ppm>`. With wrong argument counts it prints a usage line to stderr and exits non-zero. On success it exits 0. Multi-file solutions are allowed (encouraged), but `raytracer.py` must be the single entry point and everything must be created from scratch.
2. **Scene language parser.** Parse the scene file line by line. Tokens are separated by whitespace; `#` starts a comment that runs to end of line; blank lines are ignored. The first token of each non-blank, non-comment line is a lowercase directive keyword. Support exactly these directives:
   - `image <width:int> <height:int>` — output dimensions in pixels. Required, at most once.
   - `background <r> <g> <b>` — color returned by rays that miss everything. Optional, default `0 0 0`.
   - `camera <ex> <ey> <ez> <lx> <ly> <lz> <ux> <uy> <uz> <fov>` — eye point, look-at point, up hint, and **vertical** field of view in degrees (`0 < fov < 180`). Required, at most once.
   - `depth <n:int >= 0>` — maximum number of recursive reflection bounces. Optional, default `3`.
   - `samples <n:int >= 1>` — supersampling factor; each pixel is sampled on an `n × n` sub-grid. Optional, default `1`.
   - `material <name> ambient <ar> <ag> <ab> diffuse <dr> <dg> <db> specular <sr> <sg> <sb> shine <s> reflect <t>` — keywords appear in this fixed order; `name` is a single token; `shine >= 0`; `0 <= reflect <= 1`.
   - `sphere <cx> <cy> <cz> <radius> <material-name>` — `radius > 0`.
   - `plane <px> <py> <pz> <nx> <ny> <nz> <material-name> [checker <material2-name> <scale>]` — an infinite plane through point `p` with normal `n` (need not be unit length; normalize it). The optional `checker` clause alternates between the two materials in world-space squares of side `scale`.
   - `light <x> <y> <z> <r> <g> <b>` — a point light; light color components are `>= 0` and may exceed 1. Multiple lights are allowed.
3. **Validation.** A material must be defined before any `sphere`/`plane` references it; duplicate material names, duplicate `image`/`camera` directives, wrong argument counts, non-numeric numbers, out-of-range values, and unknown directives are all fatal. A missing `image` or `camera` directive at end-of-file is also fatal.
4. **Error reporting.** Every fatal parse/validation error goes to stderr in the form `error: <scene-file>:<line-number>: <message>` (for file-wide problems such as a missing `camera`, use `error: <scene-file>: <message>`), no PPM file is written, and the process exits with status 1.
5. **Camera model.** Build an orthonormal basis from eye/look/up (`forward = normalize(look − eye)`, `right = normalize(forward × up)`, `trueUp = right × forward`). Place the image plane one unit along `forward` with half-height `tan(fov/2)` and half-width scaled by the aspect ratio `width/height`. Rays must be normalized.
6. **Intersections.** Analytic ray–sphere (quadratic) and ray–plane intersection, returning the nearest positive `t`. Ignore hits with `t <= 1e-4`. Planes are infinite; both spheres and planes cast and receive shadows.
7. **Local shading (Phong).** For a hit with material `m`: `color = m.ambient + Σ over unoccluded lights of light.color * (m.diffuse * max(0, N·L) + m.specular * max(0, R·V)^m.shine)`, component-wise, where `L` points to the light, `V` to the eye, and `R` is `L` mirrored about `N`. Do not clamp until the very end.
8. **Shadows.** From each hit point, cast a shadow ray starting at `P + N * 1e-4` toward every light. If any object intersects the ray with `1e-4 < t < distance(P, light)`, that light contributes nothing (ambient still applies).
9. **Whitted reflections.** `color += m.reflect * trace(reflected_ray, depth − 1)`, where the reflected ray starts at `P + N * 1e-4` with direction `D − 2(D·N)N`. `trace(ray, 0)` returns the background color — so `depth 0` must produce an image with no reflections at all. There is no refraction.
10. **Checkerboard planes.** For a checker plane with unit normal `N`: let `u = normalize(N × (0,1,0))`, falling back to `u = (1,0,0)` when `N` is parallel to `(0,1,0)`; let `v = N × u`. For hit point `P` compute `k = floor((P·u)/scale) + floor((P·v)/scale)`; use the plane's primary material when `k` is even, the checker material when `k` is odd. All other shading (shadows, reflections) treats the chosen material as the surface material.
11. **Supersampling.** With `samples n`, fire `n × n` rays per pixel at uniform sub-positions `(x + (i+0.5)/n, y + (j+0.5)/n)` in pixel coordinates and average the results. Sampling must be deterministic — no random jitter — so that two runs on the same scene produce **byte-identical** PPM files.
12. **Progressive console render log.** The renderer must narrate itself, flushing output so updates appear in real time:
    - A startup banner containing the program name/version and the sign-off credit (see requirement 15), followed by a scene summary: resolution, samples, depth, object count, light count, input and output paths.
    - During rendering, progress updates at least every 2% of completed rows and at least 10 updates per render, each showing rows done/total, percent, elapsed wall time, and an ETA. The first update must appear within 5 seconds of the render starting (no long silent pauses). Use one line per update, or a carriage-return-updated line only when stdout is a TTY.
    - A completion line with total render time, average time per pixel, and the output file path and size in bytes.
13. **PPM output.** Write a **binary P6** PPM: header `P6\n<width> <height>\n255\n` followed by `width * height` RGB byte triplets, row 0 first being the **top** of the image. Final pixel colors are clamped to `[0,1]`, scaled by 255, and rounded.
14. **Performance discipline.** Pure standard-library Python only, but hot loops must be written with care (bind locals, avoid per-ray allocations where cheap to avoid). Target: `gallery.scene` (320×240, 2×2 samples) renders in under 5 minutes on a typical modern laptop; both sample scenes together in under 10 minutes.
15. **Sign-off:** every Python source file must begin with a header comment giving the date and time it was produced and the model/author that produced it, and the startup banner (requirement 12) must print the same author/model and date line.

## Constraints

- Python 3.9 or newer, **standard library only** (`math`, `sys`, `time`, `argparse`, `dataclasses`, etc.). No third-party packages — no numpy, no Pillow, no C extensions.
- Local-only: the program reads exactly the scene file named on the command line and writes exactly the output file named on the command line. No network, no environment probing, no other file access.
- The solution is one or more `.py` files created from scratch, run with a single `python3 raytracer.py ...` command. No build step, no packaging.
- All colors and geometry are `float`; keep shading math in linear space and clamp only when quantizing to bytes.
- Deterministic output: same scene file ⇒ byte-identical PPM across runs (verifiable with `cmp` or a checksum).

## Sample Data / Inputs

Save these two files verbatim next to `raytracer.py`. They are the reference inputs for the acceptance checklist.

**`gallery.scene`**

```
# gallery.scene — three spheres on a black-and-white checkered floor
image 320 240
background 0.05 0.07 0.10
camera 0.0 2.5 9.0   0.0 1.0 0.0   0.0 1.0 0.0   50
depth 4
samples 2

material floor_a ambient 0.05 0.05 0.05 diffuse 0.85 0.85 0.85 specular 0.10 0.10 0.10 shine 8  reflect 0.05
material floor_b ambient 0.02 0.02 0.02 diffuse 0.15 0.15 0.15 specular 0.05 0.05 0.05 shine 4  reflect 0.05
material red     ambient 0.05 0.01 0.01 diffuse 0.80 0.15 0.12 specular 0.40 0.40 0.40 shine 32 reflect 0.10
material green   ambient 0.01 0.05 0.01 diffuse 0.15 0.75 0.20 specular 0.30 0.30 0.30 shine 16 reflect 0.05
material mirror  ambient 0.02 0.02 0.02 diffuse 0.05 0.05 0.05 specular 0.90 0.90 0.90 shine 64 reflect 0.85

plane 0 0 0  0 1 0  floor_a checker floor_b 1.0

sphere -2.2 1.0  0.0 1.0 red
sphere  0.0 1.2 -2.0 1.2 mirror
sphere  2.2 0.8  0.5 0.8 green

light -6 8 6  1.00 0.95 0.85
light  7 5 3  0.35 0.35 0.45
```

**`corner.scene`**

```
# corner.scene — a row of spheres between a wood-checkered floor and a back wall
image 240 180
background 0.02 0.02 0.03
camera 0.0 3.0 10.0   0.0 1.0 -2.0   0.0 1.0 0.0   45
depth 3
samples 3

material wall    ambient 0.04 0.04 0.05 diffuse 0.60 0.60 0.65 specular 0.05 0.05 0.05 shine 4  reflect 0.00
material wood_a  ambient 0.05 0.04 0.03 diffuse 0.70 0.55 0.35 specular 0.10 0.10 0.10 shine 8  reflect 0.10
material wood_b  ambient 0.02 0.02 0.02 diffuse 0.20 0.18 0.15 specular 0.05 0.05 0.05 shine 4  reflect 0.05
material blue    ambient 0.01 0.02 0.06 diffuse 0.15 0.30 0.85 specular 0.50 0.50 0.50 shine 48 reflect 0.20
material gold    ambient 0.06 0.04 0.01 diffuse 0.85 0.60 0.15 specular 0.60 0.60 0.60 shine 32 reflect 0.35
material chrome  ambient 0.02 0.02 0.02 diffuse 0.10 0.10 0.10 specular 0.80 0.80 0.80 shine 64 reflect 0.75

plane 0 0 0   0 1 0  wood_a checker wood_b 1.5
plane 0 0 -6  0 0 1  wall

sphere -1.6 0.75 -2.0 0.75 blue
sphere  0.0 0.75 -3.2 0.75 chrome
sphere  1.6 0.75 -2.0 0.75 gold

light -4 7 4  1.00 0.90 0.80
light  5 6 2  0.30 0.40 0.60
```

Illustrative console log (your exact numbers will differ):

```
lumen 1.0 — built by <model/author> on 2026-10-29 14:32
scene: gallery.scene — 320x240, 2x2 samples, depth 4, 4 objects, 2 lights
rendering: [ 40/240 rows]  16.7%  elapsed 8.2s  eta 40.9s
rendering: [ 80/240 rows]  33.3%  elapsed 16.5s  eta 33.0s
...
done: 320x240 in 49.6s (0.65 ms/pixel) -> gallery.ppm (230418 bytes)
```

## Deliverable

- `raytracer.py` (plus any sibling `.py` modules you split the code into — all created from scratch).
- Run commands:
  - `python3 raytracer.py gallery.scene gallery.ppm`
  - `python3 raytracer.py corner.scene corner.ppm`
- View the results by opening the PPM in GIMP / feh / ImageMagick's `display`, or convert it with `convert gallery.ppm gallery.png`.

## Done When

- [ ] Both sample scenes render to valid binary P6 PPM files of the exact declared dimensions that open in an image viewer.
- [ ] `gallery.ppm` visibly shows: a black-and-white checkered floor receding to the horizon, a red sphere on the left, a green sphere on the right, a mirror sphere in the middle reflecting the floor **and** its neighbors, smooth Phong highlights, and two distinguishable shadows per object on the floor (one per light).
- [ ] `corner.ppm` shows the brown checker floor, the matte back wall, and the blue/chrome/gold spheres with colored light from the cool second light visible on their right flanks.
- [ ] Editing a copy of `gallery.scene` to `depth 0` removes all reflections from the re-rendered image (mirror sphere goes dark), proving recursion is real.
- [ ] Editing a copy of `gallery.scene` to `samples 1` produces visibly jaggier sphere silhouettes than `samples 2`.
- [ ] The console shows the banner (with sign-off credit), the scene summary, at least 10 real-time progress updates with percent/elapsed/ETA, and a completion line — with no silent stretch longer than 5 seconds.
- [ ] Appending the line `torus 0 0 0 1` to a copy of a scene makes the run fail with `error: <file>:<line>: ...unknown directive 'torus'...` on stderr, exit status 1, and no PPM written.
- [ ] Rendering the same scene twice yields byte-identical PPM files (`cmp` reports no differences).
- [ ] Both sample scenes complete without hanging, at the performance target of requirement 14.
- [ ] Every `.py` file carries the date/time + model/author header comment, and the same credit appears in the startup banner.

## Stretch Goals (optional)

- **Refraction:** add an optional `refract <ior>` keyword to `material` and trace transmitted rays with Snell's law (plus Fresnel-weighted mix with reflection) to make convincing glass spheres.
- **Soft shadows:** add `arealight <x> <y> <z> <radius> <r> <g> <b> <n>` that casts `n` jittered shadow rays (seeded RNG — output must stay deterministic) toward a sphere light for penumbrae.
- **Parallel rendering:** split the image into tiles across `multiprocessing` workers (stdlib only), keep the progress log coherent, and print the measured speedup in the completion line.
