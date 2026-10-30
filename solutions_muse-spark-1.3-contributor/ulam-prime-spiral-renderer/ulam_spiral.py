# Ulam Prime Spiral Renderer
# Generated: 2026-10-29 23:25:00 CET by Muse Spark 1.3 Contributor (OpenCode)
"""Ulam prime spiral renderer: lays 1..N^2 on an NxN counterclockwise spiral,
renders primes to a binary PPM image, and prints a statistical summary.

Usage:
    python3 ulam_spiral.py [N]

    N must be a positive odd integer (default 101).
"""

import math
import sys
import time
from datetime import datetime

MODEL_AUTHOR = "Muse Spark 1.3 Contributor (OpenCode)"

PRIME_RGB = (20, 20, 20)
OTHER_RGB = (245, 245, 240)
OUTPUT_FILENAME = "ulam_spiral.ppm"


def is_prime(n: int) -> bool:
    """Trial-division primality test."""
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    limit = int(math.isqrt(n))
    for d in range(3, limit + 1, 2):
        if n % d == 0:
            return False
    return True


def build_spiral(n: int):
    """Return n x n grid with 1..n^2 in counterclockwise square spiral.

    1 at center, 2 immediately to its right, then up, left, down, ...
    Row 0 is the top row (largest y), matching the reference layout.
    """
    grid = [[0] * n for _ in range(n)]
    c = n // 2
    x, y = c, c
    grid[y][x] = 1
    # right, up, left, down
    dirs = ((1, 0), (0, -1), (-1, 0), (0, 1))
    num = 2
    step_len = 1
    dir_idx = 0
    total = n * n
    while num <= total:
        for _ in range(2):
            dx, dy = dirs[dir_idx % 4]
            for _ in range(step_len):
                if num > total:
                    break
                x += dx
                y += dy
                grid[y][x] = num
                num += 1
            dir_idx += 1
            if num > total:
                break
        step_len += 1
    return grid


def parse_size(argv) -> int:
    if len(argv) == 1:
        return 101
    if len(argv) != 2:
        print(f"Usage: {argv[0]} [odd_positive_int]", file=sys.stderr)
        sys.exit(2)
    try:
        n = int(argv[1])
    except ValueError:
        print(f"error: size must be a positive odd integer, got {argv[1]!r}", file=sys.stderr)
        sys.exit(2)
    if n <= 0 or n % 2 == 0:
        print(f"error: size must be a positive odd integer, got {argv[1]!r}", file=sys.stderr)
        sys.exit(2)
    return n


def main() -> None:
    start = time.perf_counter()
    n = parse_size(sys.argv)

    grid = build_spiral(n)

    total = n * n
    # Count primes among 1..N^2 by testing each cell value.
    prime_count = 0
    for row in grid:
        for v in row:
            if is_prime(v):
                prime_count += 1
    density = (prime_count / total * 100.0) if total else 0.0

    # Render to binary PPM (P6), one cell per pixel, top row first.
    with open(OUTPUT_FILENAME, "wb") as f:
        f.write(f"P6\n{n} {n}\n255\n".encode("ascii"))
        for row in grid:
            for v in row:
                if is_prime(v):
                    f.write(bytes(PRIME_RGB))
                else:
                    f.write(bytes(OTHER_RGB))

    elapsed_ms = int((time.perf_counter() - start) * 1000)

    print("Ulam Prime Spiral")
    print(f"grid:    {n} x {n} ({total} cells)")
    print(f"primes:  {prime_count} ({density:.2f}%)")
    print(f"output:  {OUTPUT_FILENAME} (P6, {n} x {n})")
    print(f"elapsed: {elapsed_ms} ms")
    print(f"generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} by {MODEL_AUTHOR}")


if __name__ == "__main__":
    main()
