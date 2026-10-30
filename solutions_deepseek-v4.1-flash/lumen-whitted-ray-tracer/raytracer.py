# Lumen 1.0 -- command-line entry point, banner, progress log, PPM writer.
# Produced: 2026-10-29 23:36 by DeepSeek V4.1 Flash (opencode)

"""Lumen: a self-contained Whitted ray tracer.

Usage:
    python3 raytracer.py <scene-file> <output.ppm>
"""

import sys

# The task is local-only: main() opens the scene and the output, and the
# interpreter should not litter the working tree with bytecode caches.
sys.dont_write_bytecode = True

import os
import time

from lumen_render import Renderer
from lumen_scene import SceneError, parse_scene

PROGRAM = "lumen"
VERSION = "1.0"
AUTHOR = "DeepSeek V4.1 Flash (opencode)"
BUILT_AT = "2026-10-29 23:36"

USAGE = "usage: python3 raytracer.py <scene-file> <output.ppm>\n"


def _progress_interval(rows):
    """Rows between progress lines: never more than 2% of the image apart."""
    interval = int(rows * 0.02)
    if interval < 1:
        interval = 1
    return interval


def main(argv):
    if len(argv) != 3:
        sys.stderr.write(USAGE)
        return 2

    scene_path = argv[1]
    output_path = argv[2]

    try:
        scene = parse_scene(scene_path)
    except SceneError as exc:
        if exc.line is None:
            sys.stderr.write("error: %s: %s\n" % (scene_path, exc.message))
        else:
            sys.stderr.write("error: %s:%d: %s\n" % (scene_path, exc.line, exc.message))
        return 1

    renderer = Renderer(scene)

    # Startup banner and scene summary.
    out = sys.stdout
    out.write(
        "%s %s \u2014 built by %s on %s\n"
        % (PROGRAM, VERSION, AUTHOR, BUILT_AT)
    )
    out.write(
        "scene: %s \u2014 %dx%d, %dx%d samples, depth %d, %d objects, %d lights\n"
        % (
            scene_path,
            scene.width,
            scene.height,
            scene.samples,
            scene.samples,
            scene.depth,
            len(scene.objects),
            len(scene.lights),
        )
    )
    out.write("input: %s\noutput: %s\n" % (scene_path, output_path))
    out.flush()

    rows = scene.height
    interval = _progress_interval(rows)
    start = time.perf_counter()
    last_update = start
    next_row = interval

    def on_row(done):
        nonlocal last_update, next_row
        now = time.perf_counter()
        if done >= next_row or (now - last_update) >= 2.0 or done == rows:
            elapsed = now - start
            percent = 100.0 * done / rows
            if done > 0:
                eta = elapsed * (rows - done) / done
            else:
                eta = 0.0
            out.write(
                "rendering: [%*d/%d rows] %5.1f%%  elapsed %.1fs  eta %.1fs\n"
                % (len(str(rows)), done, rows, percent, elapsed, eta)
            )
            out.flush()
            last_update = now
            while next_row <= done:
                next_row += interval

    buffer = renderer.render(on_row)
    total = time.perf_counter() - start

    header = ("P6\n%d %d\n255\n" % (scene.width, scene.height)).encode("ascii")
    try:
        with open(output_path, "wb") as handle:
            handle.write(header)
            handle.write(buffer)
        size = os.path.getsize(output_path)
    except OSError as exc:
        reason = exc.strerror or str(exc)
        sys.stderr.write("error: %s: %s\n" % (output_path, reason))
        return 1

    pixels = scene.width * scene.height
    ms_per_pixel = total * 1000.0 / pixels
    out.write(
        "done: %dx%d in %.1fs (%.2f ms/pixel) -> %s (%d bytes)\n"
        % (scene.width, scene.height, total, ms_per_pixel, output_path, size)
    )
    out.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
