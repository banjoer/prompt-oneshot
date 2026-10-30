#!/usr/bin/env python3
# Ulam Prime Spiral Renderer - draws the classic prime spiral as a binary image.
# Generated 2026-10-29 22:47 CET by DeepSeek V4.1 Flash (opencode).
"""Ulam Prime Spiral Renderer.

Usage:
    python3 ulam_spiral.py [N] [--scale K] [--png]

Lays the integers 1 .. N*N on an N x N square spiral (1 in the centre, 2 to
its right, then counterclockwise), decides primality itself, and renders one
pixel per cell: dark for primes, light for everything else.  The default
output is a binary PPM (P6) named ``ulam_spiral.ppm``; ``--png`` writes
``ulam_spiral.png`` instead (stdlib zlib/struct only).

Options:
    N            odd grid size, default 101
    --scale K    draw every cell as a K x K block (default 1)
    --png        write a PNG instead of the default PPM
    -h, --help   show this help

Standard library only.  Nothing is read from disk and the only file written
is the image named in the console summary.
"""

import math
import struct
import sys
import time
import zlib

# ---------------------------------------------------------------------------
# Sign-off (also repeated as the last line of the console summary)
# ---------------------------------------------------------------------------
BUILT_AT = "2026-10-29 22:47 CET"
AUTHOR = "DeepSeek V4.1 Flash (opencode)"
SIGN_OFF = "generated {} by {}".format(BUILT_AT, AUTHOR)

# ---------------------------------------------------------------------------
# Rendering constants
# ---------------------------------------------------------------------------
PRIME_RGB = (20, 20, 20)        # dark pixel for a prime
COMPOSITE_RGB = (245, 245, 240)  # light pixel for 0, 1 and composites
DEFAULT_SIZE = 101
PPM_NAME = "ulam_spiral.ppm"
PNG_NAME = "ulam_spiral.png"
MAX_SCALE = 64
MAX_PIXELS_PER_SIDE = 20000

USAGE = """\
usage: python3 ulam_spiral.py [N] [--scale K] [--png]

  N            odd grid size (default {default})
  --scale K    render each cell as a K x K block (default 1)
  --png        write a PNG instead of the default PPM
  -h, --help   show this help
""".format(default=DEFAULT_SIZE)


class UsageError(Exception):
    """Bad command line; reported without a traceback."""


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------
def parse_args(argv):
    """Return (size, scale, use_png) or raise UsageError."""
    size = None
    scale = 1
    use_png = False

    i = 0
    while i < len(argv):
        arg = argv[i]

        if arg in ("-h", "--help"):
            sys.stdout.write(USAGE)
            raise SystemExit(0)

        if arg == "--png":
            use_png = True
            i += 1
            continue

        if arg == "--scale" or arg.startswith("--scale="):
            if arg == "--scale":
                if i + 1 >= len(argv):
                    raise UsageError("--scale needs a value")
                raw = argv[i + 1]
                i += 2
            else:
                raw = arg.split("=", 1)[1]
                i += 1
            try:
                scale = int(raw, 10)
            except ValueError:
                raise UsageError("--scale must be a positive integer (got {!r})".format(raw))
            if scale < 1:
                raise UsageError("--scale must be a positive integer (got {})".format(scale))
            if scale > MAX_SCALE:
                raise UsageError("--scale must be at most {} (got {})".format(MAX_SCALE, scale))
            continue

        if size is not None:
            raise UsageError("only one grid size may be given (got {} and {!r})".format(size, arg))

        try:
            size = int(arg, 10)
        except ValueError:
            if arg.startswith("-"):
                raise UsageError("unknown option {!r}".format(arg))
            raise UsageError("grid size must be an odd positive integer (got {!r})".format(arg))
        i += 1

    if size is None:
        size = DEFAULT_SIZE

    if size <= 0:
        raise UsageError("grid size must be an odd positive integer (got {})".format(size))
    if size % 2 == 0:
        raise UsageError(
            "grid size must be odd so the spiral has a true centre cell (got {})".format(size)
        )
    if size * scale > MAX_PIXELS_PER_SIDE:
        raise UsageError(
            "image would be {} x {} pixels; reduce N or --scale (limit {} per side)".format(
                size * scale, size * scale, MAX_PIXELS_PER_SIDE
            )
        )

    return size, scale, use_png


# ---------------------------------------------------------------------------
# Maths
# ---------------------------------------------------------------------------
def build_spiral(n):
    """Return n rows of n ints: 1 at the centre, 2 right, then counterclockwise."""
    grid = [[0] * n for _ in range(n)]
    total = n * n
    row = col = n // 2
    grid[row][col] = 1

    value = 1
    run = 1
    # right, up, left, down -- in (row, col) deltas, so up is row - 1.
    directions = ((0, 1), (-1, 0), (0, -1), (1, 0))
    direction = 0

    while value < total:
        for _ in range(2):
            if value >= total:
                break
            d_row, d_col = directions[direction % 4]
            for _ in range(run):
                if value >= total:
                    break
                value += 1
                row += d_row
                col += d_col
                grid[row][col] = value
            direction += 1
        run += 1

    return grid


def sieve(limit):
    """Return a bytearray where flag[v] is 1 iff v is prime, for 0 <= v <= limit."""
    is_prime = bytearray(b"\x01") * (limit + 1)
    if limit >= 0:
        is_prime[0] = 0
    if limit >= 1:
        is_prime[1] = 0
    for p in range(2, math.isqrt(limit) + 1):
        if is_prime[p]:
            start = p * p
            is_prime[start:limit + 1:p] = b"\x00" * (((limit - start) // p) + 1)
    return is_prime


# ---------------------------------------------------------------------------
# Image encoding
# ---------------------------------------------------------------------------
def render_rows(grid, is_prime, scale):
    """Return the image as a list of raw RGB byte rows (top row first)."""
    dark = bytes(PRIME_RGB)
    light = bytes(COMPOSITE_RGB)
    rows = []

    for grid_row in grid:
        line = bytearray()
        for value in grid_row:
            line += (dark if is_prime[value] else light) * scale
        row_bytes = bytes(line)
        for _ in range(scale):
            rows.append(row_bytes)

    return rows


def write_ppm(path, rows, width, height):
    """Write a binary P6 PPM, one pixel per cell (times the scale)."""
    header = "P6\n{} {}\n255\n".format(width, height).encode("ascii")
    with open(path, "wb") as handle:
        handle.write(header)
        handle.writelines(rows)


def _png_chunk(tag, payload):
    return (
        struct.pack(">I", len(payload))
        + tag
        + payload
        + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
    )


def write_png(path, rows, width, height):
    """Write an 8-bit RGB PNG using only zlib and struct."""
    raw = b"".join(b"\x00" + row for row in rows)  # filter type 0 per scanline
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    data = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(raw, 9))
        + _png_chunk(b"IEND", b"")
    )
    with open(path, "wb") as handle:
        handle.write(data)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    try:
        size, scale, use_png = parse_args(argv)
    except UsageError as exc:
        sys.stderr.write("error: {}\n".format(exc))
        sys.stderr.write("Try 'python3 ulam_spiral.py --help' for usage.\n")
        return 2

    started = time.perf_counter()

    grid = build_spiral(size)
    is_prime = sieve(size * size)
    prime_count = sum(is_prime[value] for row in grid for value in row)

    rows = render_rows(grid, is_prime, scale)
    width = height = size * scale
    out_name = PNG_NAME if use_png else PPM_NAME
    if use_png:
        write_png(out_name, rows, width, height)
    else:
        write_ppm(out_name, rows, width, height)

    elapsed_ms = int(round((time.perf_counter() - started) * 1000))
    cells = size * size
    density = (100.0 * prime_count / cells) if cells else 0.0

    print("Ulam Prime Spiral")
    print("grid:    {} x {} ({} cells)".format(size, size, cells))
    print("primes:  {} ({:.2f}%)".format(prime_count, density))
    print("output:  {} ({}, {} x {})".format(
        out_name, "PNG" if use_png else "P6", width, height))
    print("elapsed: {} ms".format(elapsed_ms))
    print(SIGN_OFF)
    return 0


if __name__ == "__main__":
    sys.exit(main())
