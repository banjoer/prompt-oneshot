# Ulam Prime Spiral Renderer

A single-file Python 3 program that lays the integers `1 … N²` on an `N × N`
square spiral (1 at the center, 2 immediately to its right, then
counterclockwise: up, left, down, right, …), decides primality itself by trial
division, and renders the result as a one-cell-per-pixel binary PPM image
(`P6`): dark pixels `(20, 20, 20)` for primes on a light background
`(245, 245, 240)`. The famous diagonal prime streaks appear as soon as you
open the file.

Python 3.8+ standard library only — no pip, no Pillow, no network, no files
read, and nothing precomputed: the image is generated entirely by
computation. A plain run writes exactly one file, `ulam_spiral.ppm`.

## Run

```bash
python3 ulam_spiral.py            # 101 x 101, writes ulam_spiral.ppm
python3 ulam_spiral.py 201        # 201 x 201
python3 ulam_spiral.py 5          # tiny grid, good for sanity checks
```

Optional stretch goals are implemented:

```bash
python3 ulam_spiral.py --scale 4     # each cell drawn as a 4 x 4 pixel block
python3 ulam_spiral.py --png         # ALSO write ulam_spiral.png (zlib + struct only)
python3 ulam_spiral.py --color       # accent the center cell (red) and twin primes (blue)
python3 ulam_spiral.py --help
```

Invalid sizes are rejected before anything is written:

```
$ python3 ulam_spiral.py 8
error: grid size must be odd so the spiral has a center cell (got 8)
usage: python3 ulam_spiral.py [N] [--scale K] [--png] [--color]
$ echo $?
2
```

## Output

Default run (`ulam_spiral.py`, timing varies):

```
Ulam Prime Spiral
grid:    101 x 101 (10201 cells)
primes:  1252 (12.27%)
output:  ulam_spiral.ppm (P6, 101 x 101)
elapsed: 8 ms
generated 2026-10-30 00:09:19 by Qwen 3.8 Flash (xhigh)
```

The final line is the sign-off; the same date/time and author appear in the
header comment at the top of `ulam_spiral.py`.

Open `ulam_spiral.ppm` with GIMP, `feh`, `display`, or any PPM-capable
viewer. `preview.png` in this folder is the default 101 × 101 image
rendered at 6× via the program's own `--scale 6 --png` for easy viewing.

## How it works

- `spiral_grid(n)` walks the grid from the center with run lengths
  1, 1, 2, 2, 3, 3, … turning right → up → left → down (counterclockwise).
  Grid row 0 is the top row of the spiral (largest y), matching the reference
  5×5 layout, so image rows and console layout agree.
- `is_prime(n)` is 6k ± 1 trial division up to `math.isqrt(n)` — primality is
  decided per value, no prime tables.
- `render_image()` assembles raw RGB scanlines; `write_ppm()` emits
  `P6\n<w> <h>\n255\n` + bytes with plain file I/O, and `write_png()` builds
  a valid 8-bit truecolor PNG from `struct` chunk headers and a `zlib`-
  compressed filter-0 IDAT.

## Verification performed

Full harness in `/tmp/opencode/verify_ulam.py` — 43 checks, all passing:

| Check | Result |
|-------|--------|
| `n=5` grid equals the sample layout, row by row | exact match |
| `n=5`, `n=7`, `n=101` prime counts | `9`, `15`, `1252` ✓ |
| default prime density | `12.27%` ✓ |
| all 10 201 PPM pixels vs. independently computed primality mask | 0 mismatches |
| PPM structure | `P6\n101 101\n255\n` + exactly 30 603 RGB bytes |
| `ulam_spiral.py 8` / `0` / `-3` / `abc` / `10.5` / extra arg / bad options | clear stderr message, exit 2, no image written |
| `n=201` count vs. independent Sieve of Eratosthenes | 4236 = 4236 ✓ |
| `--scale 2 --png --color` | PNG signature, chunk order, IHDR, CRCs, filter bytes all valid; decodes to same pixels; accents present |
| `n=1` edge case | 0 primes, 1×1 image |
| sign-off | header comment and final summary line show identical date/time + author |

## Files

- `ulam_spiral.py` — the complete program (the deliverable).
- `ulam_spiral.ppm` — image produced by the default run (101 × 101).
- `preview.png` — the same image at 6× scale, written by the program itself,
  for viewers that prefer PNG.
