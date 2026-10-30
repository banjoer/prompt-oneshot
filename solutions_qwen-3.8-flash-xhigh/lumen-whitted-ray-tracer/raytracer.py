# Lumen — a Whitted ray tracer with a scene file format
# File: raytracer.py — entry point, CLI, console narration, PPM writer
# Produced: 2026-10-30 00:10
# Model/Author: Qwen 3.8 Flash (xhigh)
"""Lumen 1.0 — a self-contained Whitted ray tracer.

Usage:
    python3 raytracer.py <scene-file> <output.ppm>

Reads a Lumen scene description, renders it with recursive mirror
reflections, hard shadows and Phong shading, narrates progress to the
console, and writes a binary P6 PPM.  Standard library only.
"""

import sys
import time

from lumen_render import render
from lumen_scene import (BUILD_AUTHOR, BUILD_DATE, PROGRAM_NAME,
                         PROGRAM_VERSION, SceneError, parse_scene)

BANNER = "%s %s — built by %s on %s" % (PROGRAM_NAME, PROGRAM_VERSION,
                                        BUILD_AUTHOR, BUILD_DATE)


def usage(prog):
    sys.stderr.write("usage: %s <scene-file> <output.ppm>\n" % prog)


class Progress:
    """Narrates row-by-row rendering progress to stdout.

    Emits an update at least every 2% of the rows, at least 10 times per
    render, always within a few seconds of activity, and never with a
    silent stretch longer than 5 seconds while rows are landing.
    """

    def __init__(self, total_rows, is_tty):
        self.total = total_rows
        self.tty = is_tty
        # Emit every ~2% of the rows; a tiny image still updates each row.
        self.step = max(1, total_rows * 2 // 100)
        self.last_rows = 0
        self.last_elapsed = 0.0
        self.started = False

    def update(self, rows_done, total_rows, elapsed):
        if not self.started:
            self._emit(rows_done, elapsed)      # first row -> no silent start
            return
        if rows_done - self.last_rows >= self.step:
            self._emit(rows_done, elapsed)
        elif elapsed - self.last_elapsed >= 5.0 and rows_done > self.last_rows:
            self._emit(rows_done, elapsed)

    def _emit(self, rows_done, elapsed):
        self.started = True
        self.last_rows = rows_done
        self.last_elapsed = elapsed
        pct = 100.0 * rows_done / self.total
        if rows_done > 0:
            eta = elapsed / rows_done * (self.total - rows_done)
        else:
            eta = 0.0
        line = ("rendering: [%3d/%d rows] %5.1f%%  elapsed %5.1fs  "
                "eta %5.1fs" % (rows_done, self.total, pct, elapsed, eta))
        if self.tty:
            sys.stdout.write("\r" + line)
        else:
            sys.stdout.write(line + "\n")
        sys.stdout.flush()


def ppm_header(width, height):
    return ("P6\n%d %d\n255\n" % (width, height)).encode("ascii")


def main(argv):
    prog = argv[0] if argv else "raytracer.py"
    if len(argv) != 3:
        usage(prog)
        return 2

    scene_path = argv[1]
    out_path = argv[2]

    sys.stdout.write(BANNER + "\n")
    sys.stdout.flush()

    try:
        scene = parse_scene(scene_path)
    except SceneError as err:
        sys.stderr.write(err.format(scene_path) + "\n")
        return 1

    n = scene.samples
    sys.stdout.write(
        "scene: %s — %dx%d, %dx%d samples, depth %d, %d objects, %d "
        "lights\n" % (scene_path, scene.width, scene.height, n, n,
                      scene.depth, scene.object_count, scene.light_count))
    sys.stdout.write("output: %s\n" % out_path)
    sys.stdout.flush()

    progress = Progress(scene.height, sys.stdout.isatty())
    # Reflection recursion is bounded by the scene depth; keep the default
    # interpreter limit comfortable even for absurd values.
    sys.setrecursionlimit(max(1000, 2000 + 10 * scene.depth))
    t0 = time.perf_counter()
    data = render(scene, progress_cb=progress.update)
    elapsed = time.perf_counter() - t0

    header = ppm_header(scene.width, scene.height)
    with open(out_path, "wb") as fh:
        fh.write(header)
        fh.write(data)
    total_bytes = len(header) + len(data)

    pixels = scene.width * scene.height
    ms_per_pixel = elapsed * 1000.0 / pixels if pixels else 0.0
    sys.stdout.write(
        "done: %dx%d in %5.1fs (%.2f ms/pixel) -> %s (%d bytes)\n"
        % (scene.width, scene.height, elapsed, ms_per_pixel, out_path,
           total_bytes))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except BrokenPipeError:
        # Downstream reader (e.g. `| head`) went away; exit quietly.
        import os
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
