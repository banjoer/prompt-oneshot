# Lumen -- Whitted ray tracing integrator (spheres, planes, Phong, shadows).
# Produced: 2026-10-29 23:36 by DeepSeek V4.1 Flash (opencode)

"""Recursive Whitted ray tracer for the scene structures built by lumen_scene."""

import math

EPS = 1.0e-4
INF = float("inf")


def _occluded(objects, ox, oy, oz, dx, dy, dz, distance):
    """True if any object lies strictly between the origin and the light."""
    for obj in objects:
        if obj[0] == 0:
            ocx = ox - obj[1]
            ocy = oy - obj[2]
            ocz = oz - obj[3]
            b = ocx * dx + ocy * dy + ocz * dz
            disc = b * b - (ocx * ocx + ocy * ocy + ocz * ocz - obj[5])
            if disc > 0.0:
                root = math.sqrt(disc)
                t = -b - root
                if t <= EPS:
                    t = -b + root
                if EPS < t < distance:
                    return True
        else:
            denom = dx * obj[4] + dy * obj[5] + dz * obj[6]
            if denom != 0.0:
                t = (
                    (obj[1] - ox) * obj[4]
                    + (obj[2] - oy) * obj[5]
                    + (obj[3] - oz) * obj[6]
                ) / denom
                if EPS < t < distance:
                    return True
    return False


class Renderer:
    """Turns a validated Scene into a flat RGB byte buffer."""

    __slots__ = (
        "objects",
        "lights",
        "background",
        "eye",
        "width",
        "height",
        "samples",
        "max_depth",
        "half_width",
        "half_height",
        "fwd",
        "right",
        "up",
    )

    def __init__(self, scene):
        self.objects = scene.objects
        self.lights = scene.lights
        self.background = scene.background
        self.eye = scene.eye
        self.width = scene.width
        self.height = scene.height
        self.samples = scene.samples
        self.max_depth = scene.depth

        # Camera basis: forward = normalize(look - eye),
        # right = normalize(forward x up), trueUp = right x forward.
        ex, ey, ez = scene.eye
        lx, ly, lz = scene.look
        ux, uy, uz = scene.up
        fx = lx - ex
        fy = ly - ey
        fz = lz - ez
        inv = 1.0 / math.sqrt(fx * fx + fy * fy + fz * fz)
        fx *= inv
        fy *= inv
        fz *= inv

        rx = fy * uz - fz * uy
        ry = fz * ux - fx * uz
        rz = fx * uy - fy * ux
        inv = 1.0 / math.sqrt(rx * rx + ry * ry + rz * rz)
        rx *= inv
        ry *= inv
        rz *= inv

        vx = ry * fz - rz * fy
        vy = rz * fx - rx * fz
        vz = rx * fy - ry * fx

        half_height = math.tan(math.radians(scene.fov) * 0.5)
        half_width = half_height * (scene.width / float(scene.height))

        self.fwd = (fx, fy, fz)
        self.right = (rx, ry, rz)
        self.up = (vx, vy, vz)
        self.half_width = half_width
        self.half_height = half_height

    # ------------------------------------------------------------------
    # Core recursive integrator.
    # ------------------------------------------------------------------
    def trace(self, ox, oy, oz, dx, dy, dz, depth):
        """Return the linear RGB color seen along a normalized ray.

        ``depth`` counts the reflection bounces still available.  Calling
        ``trace(..., 0)`` returns the background color, as specified; the
        primary rays are therefore launched with ``max_depth + 1``.  This
        makes ``depth 0`` scenes show local shading but no mirrors.
        """
        if depth <= 0:
            return self.background

        objects = self.objects

        # Nearest positive intersection (t > EPS).
        best = INF
        hit = None
        for obj in objects:
            if obj[0] == 0:
                ocx = ox - obj[1]
                ocy = oy - obj[2]
                ocz = oz - obj[3]
                b = ocx * dx + ocy * dy + ocz * dz
                disc = b * b - (ocx * ocx + ocy * ocy + ocz * ocz - obj[5])
                if disc > 0.0:
                    root = math.sqrt(disc)
                    t = -b - root
                    if t > EPS:
                        if t < best:
                            best = t
                            hit = obj
                    else:
                        t = -b + root
                        if EPS < t < best:
                            best = t
                            hit = obj
            else:
                denom = dx * obj[4] + dy * obj[5] + dz * obj[6]
                if denom != 0.0:
                    t = (
                        (obj[1] - ox) * obj[4]
                        + (obj[2] - oy) * obj[5]
                        + (obj[3] - oz) * obj[6]
                    ) / denom
                    if EPS < t < best:
                        best = t
                        hit = obj

        if hit is None:
            return self.background

        t = best
        px = ox + dx * t
        py = oy + dy * t
        pz = oz + dz * t

        if hit[0] == 0:
            # Sphere normal is radial; radius is already known.
            inv_r = 1.0 / hit[4]
            nx = (px - hit[1]) * inv_r
            ny = (py - hit[2]) * inv_r
            nz = (pz - hit[3]) * inv_r
            material = hit[6]
        else:
            nx = hit[4]
            ny = hit[5]
            nz = hit[6]
            material = hit[7]
            checker = hit[8]
            if checker is not None:
                inv_scale = checker[1]
                k = int(
                    math.floor(
                        (px * checker[2] + py * checker[3] + pz * checker[4])
                        * inv_scale
                    )
                ) + int(
                    math.floor(
                        (px * checker[5] + py * checker[6] + pz * checker[7])
                        * inv_scale
                    )
                )
                if k & 1:
                    material = checker[0]

        # View vector, from the hit point toward the eye.
        ex, ey, ez = self.eye
        vx = ex - px
        vy = ey - py
        vz = ez - pz
        inv = 1.0 / math.sqrt(vx * vx + vy * vy + vz * vz)
        vx *= inv
        vy *= inv
        vz *= inv

        ar = material[0]
        ag = material[1]
        ab = material[2]
        dr = material[3]
        dg = material[4]
        db = material[5]
        sr = material[6]
        sg = material[7]
        sb = material[8]
        shine = material[9]
        reflect = material[10]

        cr = ar
        cg = ag
        cb = ab

        # Slightly displaced shadow origin, as required, to beat self-shadowing.
        sx = px + nx * EPS
        sy = py + ny * EPS
        sz = pz + nz * EPS

        for light in self.lights:
            lx = light[0] - px
            ly = light[1] - py
            lz = light[2] - pz
            dist2 = lx * lx + ly * ly + lz * lz
            if dist2 <= 0.0:
                continue
            distance = math.sqrt(dist2)
            inv = 1.0 / distance
            lx *= inv
            ly *= inv
            lz *= inv

            if _occluded(objects, sx, sy, sz, lx, ly, lz, distance):
                continue

            ndl = nx * lx + ny * ly + nz * lz
            if ndl > 0.0:
                diffuse = ndl
            else:
                diffuse = 0.0

            # R = 2 (N . L) N - L
            rrx = 2.0 * ndl * nx - lx
            rry = 2.0 * ndl * ny - ly
            rrz = 2.0 * ndl * nz - lz
            rv = rrx * vx + rry * vy + rrz * vz
            if rv < 0.0:
                rv = 0.0
            specular = rv ** shine

            lr = light[3]
            lg = light[4]
            lb = light[5]
            cr += lr * (dr * diffuse + sr * specular)
            cg += lg * (dg * diffuse + sg * specular)
            cb += lb * (db * diffuse + sb * specular)

        if reflect != 0.0:
            dn = dx * nx + dy * ny + dz * nz
            rx = dx - 2.0 * dn * nx
            ry = dy - 2.0 * dn * ny
            rz = dz - 2.0 * dn * nz
            inv = 1.0 / math.sqrt(rx * rx + ry * ry + rz * rz)
            rr, rg, rb = self.trace(
                sx, sy, sz, rx * inv, ry * inv, rz * inv, depth - 1
            )
            cr += reflect * rr
            cg += reflect * rg
            cb += reflect * rb

        return (cr, cg, cb)

    # ------------------------------------------------------------------
    # Image loop.
    # ------------------------------------------------------------------
    def render(self, on_row=None):
        """Render the image, returning a bytearray of RGB triplets."""
        width = self.width
        height = self.height
        n = self.samples
        inv_n = 1.0 / n
        inv_count = 1.0 / float(n * n)

        fx, fy, fz = self.fwd
        rx, ry, rz = self.right
        ux, uy, uz = self.up
        ex, ey, ez = self.eye
        trace = self.trace

        buffer = bytearray(width * height * 3)

        # Sample the pixel on an n x n uniform sub-grid (deterministic).
        for iy in range(height):
            base = iy * width * 3
            for ix in range(width):
                ar = 0.0
                ag = 0.0
                ab = 0.0
                for j in range(n):
                    # ndc y in [-1, 1], row 0 is the top of the image.
                    vy = 1.0 - 2.0 * (iy + (j + 0.5) * inv_n) / height
                    oy = vy * self.half_height
                    for i in range(n):
                        vx = 2.0 * (ix + (i + 0.5) * inv_n) / width - 1.0
                        ox = vx * self.half_width
                        dx = fx + rx * ox + ux * oy
                        dy = fy + ry * ox + uy * oy
                        dz = fz + rz * ox + uz * oy
                        inv = 1.0 / math.sqrt(dx * dx + dy * dy + dz * dz)
                        r, g, b = trace(
                            ex, ey, ez, dx * inv, dy * inv, dz * inv,
                            self.max_depth + 1,
                        )
                        ar += r
                        ag += g
                        ab += b
                idx = base + ix * 3
                r = ar * inv_count
                g = ag * inv_count
                b = ab * inv_count
                if r < 0.0:
                    r = 0.0
                elif r > 1.0:
                    r = 1.0
                if g < 0.0:
                    g = 0.0
                elif g > 1.0:
                    g = 1.0
                if b < 0.0:
                    b = 0.0
                elif b > 1.0:
                    b = 1.0
                buffer[idx] = int(r * 255.0 + 0.5)
                buffer[idx + 1] = int(g * 255.0 + 0.5)
                buffer[idx + 2] = int(b * 255.0 + 0.5)

            if on_row is not None:
                on_row(iy + 1)

        return buffer
