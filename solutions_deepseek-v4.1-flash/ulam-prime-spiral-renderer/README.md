# Ulam Prime Spiral Renderer

A single-file Python 3 program that lays `1 … N²` on an `N × N` square spiral
(1 in the centre, 2 to its right, then counterclockwise), decides primality
itself with a sieve, and writes the result as a one-cell-per-pixel binary
image. Dark pixels are primes, light pixels are everything else — so the
famous diagonal prime streaks appear as soon as you open the file.

Standard library only: no pip, no Pillow, no network, no input files.

## Run

```bash
python3 ulam_spiral.py            # 101 x 101, writes ulam_spiral.ppm
python3 ulam_spiral.py 201        # 201 x 201
python3 ulam_spiral.py 5          # tiny grid, good for sanity checks
```

Extra options (optional stretch goals):

```bash
python3 ulam_spiral.py 401 --scale 4      # each cell drawn as a 4 x 4 block
python3 ulam_spiral.py 401 --png          # PNG output instead of PPM (zlib + struct)
python3 ulam_spiral.py --help
```

Invalid sizes are rejected before anything is written:

```
$ python3 ulam_spiral.py 8
error: grid size must be odd so the spiral has a true centre cell (got 8)
Try 'python3 ulam_spiral.py --help' for usage.
$ echo $?
2
```

## Output

Default run:

```
Ulam Prime Spiral
grid:    101 x 101 (10201 cells)
primes:  1252 (12.27%)
output:  ulam_spiral.ppm (P6, 101 x 101)
elapsed: 3 ms
generated 2026-10-29 22:47 CET by DeepSeek V4.1 Flash (opencode)
```

`ulam_spiral.ppm` is a binary P6 PPM: `P6`, the dimensions, `255`, then raw
RGB bytes (row 0 = top row of the spiral, matching the reference layout).
Each cell is one pixel: `(20, 20, 20)` for primes, `(245, 245, 240)` otherwise.

Open it with GIMP, `feh`, `display`, or any PPM-capable viewer. `preview.png`
in this folder is the default 101 × 101 image rendered with `--png --scale 5`
so it can be inspected in any browser or image viewer.

## How it works

- `build_spiral(n)` walks the grid from the centre with run lengths
  1, 1, 2, 2, 3, 3, … turning right → up → left → down, i.e. counterclockwise.
  With odd `n` the walk stops exactly on `n²` in the bottom-right corner.
- `sieve(limit)` is a bytearray Sieve of Eratosthenes over `0 … n²`; nothing is
  precomputed or read from disk.
- `render_rows()` expands each cell to a `scale × scale` block, and the image
  is written with plain `open(..., "wb")` (PPM) or `zlib`/`struct` (PNG).

## Verification performed

| Check | Result |
|-------|--------|
| `n=5` grid equals the sample layout | exact match |
| `n=5`, `n=7`, `n=101` prime counts | `9`, `15`, `1252` ✓ |
| default density | `12.27 %` ✓ |
| every PPM pixel matches the computed mask | 0 mismatches |
| PPM header | `P6\n101 101\n255\n` + 30603 bytes |
| even / zero / negative / non-numeric sizes | clear error, exit code 2, no image written |
| spiral contains each value `1 … n²` exactly once, centred | verified for n = 1, 3, 5, 7, 9, 21, 51, 101 |
| sieve vs. trial division, `0 … 20000` | 0 mismatches |
| `--scale` / `--png` | blocks uniform; PNG decodes to the same pixels |

## Files

- `ulam_spiral.py` — the complete program (the deliverable).
- `ulam_spiral.ppm` — image produced by the default run.
- `preview.png` — enlarged (5×) PNG of the default run, for easy viewing.
