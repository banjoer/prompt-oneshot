# Lumen — a Whitted ray tracer with a scene file format
# File: ppm2png.py — tiny viewer helper (NOT part of the renderer itself)
# Produced: 2026-10-30 00:10
# Model/Author: Qwen 3.8 Flash (xhigh)
"""Convert a Lumen binary P6 PPM to a PNG so it opens in any image viewer.

    python3 ppm2png.py gallery.ppm gallery.png

Pure standard library (struct + zlib).  This file is a convenience tool for
humans inspecting the render output; the renderer itself never uses it.
"""

import struct
import sys
import zlib


def read_p6(path):
    """Return (width, height, rgb_bytes) for a binary P6 PPM."""
    data = open(path, "rb").read()
    if data[:2] != b"P6":
        raise ValueError("not a binary P6 PPM")
    pos = 2
    vals = []
    while len(vals) < 3:
        while pos < len(data) and data[pos:pos + 1] in (b" ", b"\t", b"\n",
                                                        b"\r"):
            pos += 1
        while data[pos:pos + 1] == b"#":          # header comments
            while data[pos:pos + 1] != b"\n":
                pos += 1
        j = pos
        while data[j:j + 1] not in (b" ", b"\t", b"\n", b"\r"):
            j += 1
        vals.append(int(data[pos:j]))
        pos = j
    width, height, maxv = vals
    if maxv != 255:
        raise ValueError("only maxval 255 is supported")
    pos += 1  # exactly one whitespace byte separates header from raster
    raw = data[pos:pos + width * height * 3]
    if len(raw) != width * height * 3:
        raise ValueError("truncated raster data")
    return width, height, raw


def _chunk(tag, payload):
    body = struct.pack(">I", len(payload)) + tag + payload
    crc = zlib.crc32(tag + payload) & 0xFFFFFFFF
    return body + struct.pack(">I", crc)


def ppm2png(pin, pout):
    width, height, raw = read_p6(pin)
    rows = [b"\x00" + raw[y * width * 3:(y + 1) * width * 3]
            for y in range(height)]
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0,
                                       0, 0))
    png += _chunk(b"IDAT", zlib.compress(b"".join(rows), 6))
    png += _chunk(b"IEND", b"")
    with open(pout, "wb") as fh:
        fh.write(png)
    print("%s -> %s (%dx%d)" % (pin, pout, width, height))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.stderr.write("usage: python3 ppm2png.py <input.ppm> <output.png>\n")
        sys.exit(2)
    ppm2png(sys.argv[1], sys.argv[2])
