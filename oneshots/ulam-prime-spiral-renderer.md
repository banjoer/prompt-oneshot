# Ulam Prime Spiral Renderer

**Difficulty:** easy  |  **Stack:** Python 3 (stdlib only)  |  **Estimated time:** 30–60 min

## The Problem

In 1963, Stanisław Ulam doodled integers in a spiral during a boring lecture, circled the primes, and noticed they clump along diagonal lines — a pattern that still fascinates number theorists today. Most people only ever see this as a picture someone else made. Build a small, self-contained Python program that computes the Ulam spiral itself, renders it to an image file you can open and look at, and prints a short statistical summary of what it found — no libraries, no downloads, just math and pixels.

## Requirements

1. The program lays the integers `1 … N²` out on an `N × N` grid in a square spiral: `1` at the center, `2` immediately to its right, then continuing **counterclockwise** (up, left, down, right, …), matching the reference layout in Sample Data exactly.
2. `N` is taken from an optional command-line argument (default `101`). Only **odd** values are accepted (so a true center cell exists); reject even or non-positive values with a clear error message and non-zero exit code.
3. Primality is decided by the program itself (trial division is fine at this scale — no external prime tables).
4. The grid is rendered to a **binary PPM image (P6)** named `ulam_spiral.ppm`, one cell per pixel: prime cells as dark pixels (`(20, 20, 20)`), non-prime cells as light pixels (`(245, 245, 240)`). The image must have `P6`, the dimensions, and the max value as its header, followed by raw RGB bytes.
5. Row orientation must match the Sample Data layout (the first row of the image is the top row of the spiral, i.e. the largest y), so the classic diagonal prime streaks are visible when the image is viewed.
6. After writing the image, the program prints a short console summary containing, in this order: the grid size and total cell count, the number of primes found, the prime density as a percentage (2 decimal places), the output filename and image dimensions, and the elapsed computation time in milliseconds.
7. **Sign-off:** the finished solution must display, somewhere easy to spot, the date and time it was produced and the model/author that produced it — as a header comment at the top of the source file **and** as the final line of the console summary.

## Constraints

- Python 3.8+ standard library only (`sys`, `math`, `time`, `datetime`, etc.). No pip, no third-party packages, no PIL/Pillow — the PPM is written with plain file I/O.
- No network access, no files read from disk; the only file written is `ulam_spiral.ppm`.
- Everything lives in one source file, `ulam_spiral.py`.
- The image is generated entirely by computation — do not embed precomputed prime lists or pixel data.

## Sample Data / Inputs

The 5×5 spiral (`python3 ulam_spiral.py 5`) must produce exactly this arrangement of values in the grid:

```
17 16 15 14 13
18  5  4  3 12
19  6  1  2 11
20  7  8  9 10
21 22 23 24 25
```

Verifiable prime counts (number of primes among `1 … N²`):

| `N` | cells (`N²`) | primes |
|-----|--------------|--------|
| 5   | 25           | 9      |
| 7   | 49           | 15     |
| 101 | 10201        | 1252   |

Example console summary for the default run (format to match; time will vary):

```
Ulam Prime Spiral
grid:    101 x 101 (10201 cells)
primes:  1252 (12.27%)
output:  ulam_spiral.ppm (P6, 101 x 101)
elapsed: 42 ms
generated 2026-10-29 14:32:07 by <model/author>
```

## Deliverable

- `ulam_spiral.py` — the complete program.
- Run: `python3 ulam_spiral.py` (default `N = 101`) or `python3 ulam_spiral.py 201`.
- View: open `ulam_spiral.ppm` in any PPM-capable viewer (GIMP, `feh`, `display`, most OS image viewers, or a VS Code PPM extension).

## Done When

- [ ] `python3 ulam_spiral.py` runs without errors and writes `ulam_spiral.ppm`.
- [ ] The opened image shows the unmistakable Ulam pattern: dark prime pixels forming visible diagonal streaks on a light background, one cell per pixel.
- [ ] `python3 ulam_spiral.py 7` reports exactly `15` primes, and `python3 ulam_spiral.py 5` reports exactly `9`, matching the table above.
- [ ] The default run reports exactly `1252` primes `(12.27%)`.
- [ ] `python3 ulam_spiral.py 8` (even size) fails with a clear error message and no image written.
- [ ] The console summary shows grid size, prime count, density, output filename, and elapsed time; the source header and the last printed line show the production date/time and the model/author.

## Stretch Goals (optional)

- Color accents: mark the center cell `1`, twin primes, or the number's spiral "ring" in distinct colors.
- Add a `--png` flag that writes a valid PNG instead, using only `zlib` and `struct` from the stdlib.
- Add a `--scale K` option that renders each cell as a `K × K` block for big-print images.
