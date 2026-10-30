#!/usr/bin/env python3
"""Ulam Prime Spiral Renderer.

Lays the integers 1..N*N on an N x N grid in a counterclockwise square spiral
(1 at the center, 2 immediately to its right, then up, left, down, right, ...),
decides primality itself by trial division, renders prime cells as dark pixels
on a light background into a binary PPM image (P6) named ``ulam_spiral.ppm``
(one cell per pixel, first image row = top row of the spiral), and prints a
short statistical summary.

Usage:
    python3 ulam_spiral.py               # default N = 101
    python3 ulam_spiral.py 201           # any positive odd N
    python3 ulam_spiral.py --scale 4     # stretch: each cell as a 4x4 pixel block
    python3 ulam_spiral.py --png         # stretch: also write a valid PNG (zlib/struct)
    python3 ulam_spiral.py --color       # stretch: accent center cell + twin primes

Python 3 standard library only (sys, math, time, os, struct, zlib): no third
party packages, no network, no files read, and no precomputed prime tables or
pixel data — the image is generated entirely by computation. The plain run
writes exactly one file, ``ulam_spiral.ppm``.

Sign-off: produced 2026-10-30 00:09:19 by Qwen 3.8 Flash (xhigh).
"""

import math
import struct
import sys
import time
import zlib

DEFAULT_N = 101
OUTPUT_PPM = "ulam_spiral.ppm"
OUTPUT_PNG = "ulam_spiral.png"

PRIME_RGB = (20, 20, 20)         # dark pixels mark the primes
NON_PRIME_RGB = (245, 245, 240)  # light background for everything else
CENTER_RGB = (200, 30, 30)       # --color accent: the center cell (value 1)
TWIN_RGB = (40, 90, 220)         # --color accent: primes p with p+2 also prime

PRODUCED_AT = "2026-10-30 00:09:19"
AUTHOR = "Qwen 3.8 Flash (xhigh)"


def is_prime(n):
    """Trial division with a 6k +/- 1 wheel — decided here, never looked up."""
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    root = math.isqrt(n)
    factor = 5
    while factor <= root:
        if n % factor == 0 or n % (factor + 2) == 0:
            return False
        factor += 6
    return True


def spiral_grid(n):
    """Return an n x n grid (row 0 = top row, i.e. the largest y) holding the
    integers 1..n*n in a square spiral: 1 at the center, 2 to its right, then
    counterclockwise (up, left, down, right, ...)."""
    grid = [[0] * n for _ in range(n)]
    center = n // 2
    grid[center][center] = 1
    total = n * n
    value = 1
    x = y = 0
    step = 1
    dirs = ((1, 0), (0, 1), (-1, 0), (0, -1))  # right, up, left, down = CCW
    side = 0
    while value < total:
        for _ in range(2):  # every step length is used for two consecutive sides
            dx, dy = dirs[side % 4]
            for _ in range(step):
                x += dx
                y += dy
                value += 1
                if value > total:
                    break
                grid[center - y][center + x] = value
            side += 1
            if value > total:
                break
        step += 1
    return grid


def prime_flags(total):
    """flags[v] is True iff v is prime, for v in 0..total+2 (+2 slack lets the
    --color twin-prime check peek at p + 2 without bounds tests)."""
    flags = [False] * (total + 3)
    for v in range(2, total + 1):
        flags[v] = is_prime(v)
    return flags


def cell_rgb(value, flags, color_mode):
    if color_mode and value == 1:
        return CENTER_RGB
    if flags[value]:
        if color_mode and flags[value + 2]:
            return TWIN_RGB
        return PRIME_RGB
    return NON_PRIME_RGB


def render_image(grid, flags, scale, color_mode):
    """Build the raw RGB scanlines (top row first) as a bytes object."""
    height = len(grid)
    width = len(grid[0]) * scale
    parts = []
    for row in grid:
        line = bytearray()
        for value in row:
            line += bytes(cell_rgb(value, flags, color_mode))
            if scale > 1:
                triple = line[-3:]
                line += triple * (scale - 1)
        block = bytes(line)
        for _ in range(scale):
            parts.append(block)
    return width, height * scale, b"".join(parts)


def write_ppm(path, width, height, raw):
    with open(path, "wb") as fh:
        fh.write(b"P6\n%d %d\n255\n" % (width, height))
        fh.write(raw)


def write_png(path, width, height, raw):
    """Minimal valid 8-bit truecolor PNG using only zlib + struct."""
    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    stride = width * 3
    scanlines = b"".join(
        b"\x00" + raw[y * stride:(y + 1) * stride] for y in range(height)
    )
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(scanlines, 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(png)


USAGE = "usage: python3 ulam_spiral.py [N] [--scale K] [--png] [--color]"


def fail(message, code=2):
    print("error: %s\n%s" % (message, USAGE), file=sys.stderr)
    sys.exit(code)


def parse_args(argv):
    """Validate options; exit non-zero (writing nothing) on any bad input."""
    n, scale, png, color = DEFAULT_N, 1, False, False
    positional_seen = False
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-h", "--help"):
            print(USAGE)
            sys.exit(0)
        elif arg == "--png":
            png = True
        elif arg == "--color":
            color = True
        elif arg == "--scale":
            if i + 1 >= len(argv):
                fail("--scale needs an integer K >= 1")
            i += 1
            try:
                scale = int(argv[i])
            except ValueError:
                fail("--scale needs an integer K >= 1 (got %r)" % argv[i])
            if scale < 1:
                fail("--scale needs an integer K >= 1 (got %d)" % scale)
        elif arg.startswith("--"):
            fail("unknown option %r" % arg)
        else:
            if positional_seen:
                fail("unexpected extra argument %r" % arg)
            positional_seen = True
            try:
                n = int(arg)
            except ValueError:
                fail("grid size must be an integer (got %r)" % arg)
            if n <= 0:
                fail("grid size must be a positive odd integer (got %d)" % n)
            if n % 2 == 0:
                fail("grid size must be odd so the spiral has a center cell "
                     "(got %d)" % n)
        i += 1
    return n, scale, png, color


def main(argv):
    n, scale, png, color = parse_args(argv)
    total = n * n

    started = time.perf_counter()
    grid = spiral_grid(n)
    flags = prime_flags(total)
    prime_count = sum(1 for v in range(2, total + 1) if flags[v])
    width, height, raw = render_image(grid, flags, scale, color)
    write_ppm(OUTPUT_PPM, width, height, raw)
    if png:
        write_png(OUTPUT_PNG, width, height, raw)
    elapsed_ms = (time.perf_counter() - started) * 1000.0

    density = 100.0 * prime_count / total
    print("Ulam Prime Spiral")
    print("grid:    %d x %d (%d cells)" % (n, n, total))
    print("primes:  %d (%.2f%%)" % (prime_count, density))
    print("output:  %s (P6, %d x %d)" % (OUTPUT_PPM, width, height))
    if png:
        print("also:    %s (PNG, %d x %d)" % (OUTPUT_PNG, width, height))
    print("elapsed: %d ms" % round(elapsed_ms))
    print("generated %s by %s" % (PRODUCED_AT, AUTHOR))


if __name__ == "__main__":
    main(sys.argv[1:])
