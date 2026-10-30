# Lumen — a Whitted ray tracer with a scene file format
# File: lumen_render.py — camera model, intersections, Whitted integrator
# Produced: 2026-10-30 00:10
# Model/Author: Qwen 3.8 Flash (xhigh)
"""The rendering core.

Everything the hot loop touches is pre-flattened into plain tuples of
floats and the per-ray math is written out inline (no vector objects,
minimal allocations) so pure-Python still hits the performance targets.
The recursive integrator follows the Whitted model exactly:

    trace(ray, 0)  -> background color
    trace(ray, d)  -> nearest intersection; on a miss the background; else
                      ambient + sum over unoccluded lights of the Phong term
                      + reflect * trace(reflected_ray, d - 1)

Output is fully deterministic: identical scenes produce byte-identical
PPM files because the sampler uses fixed sub-pixel offsets — no jitter,
no randomness, no threading inside the pixel loop.
"""

import math
import time

from lumen_scene import Plane, Sphere

EPS = 1e-4      # intersection tolerance / ray-start offset (req. 6, 8, 9)
BIG = 1e30


def _flatten_material(mat):
    """Material as one flat tuple: amb(3) dif(3) spec(3) shine reflect."""
    return (mat.ambient[0], mat.ambient[1], mat.ambient[2],
            mat.diffuse[0], mat.diffuse[1], mat.diffuse[2],
            mat.specular[0], mat.specular[1], mat.specular[2],
            float(mat.shine), float(mat.reflect))


def _build_objects(scene):
    """Flatten the scene into (spheres, planes) tuple lists.

    sphere tuple: (cx, cy, cz, r2, r, mat)
    plane  tuple: (px, py, pz, nx, ny, nz, mat, chk,
                   ux, uy, uz, vx, vy, vz, scale, cmat)
    """
    spheres = []
    planes = []
    for obj in scene.objects:
        if isinstance(obj, Sphere):
            r = obj.r
            spheres.append((obj.c[0], obj.c[1], obj.c[2],
                            r * r, r, _flatten_material(obj.material)))
        else:
            assert isinstance(obj, Plane)
            mat = _flatten_material(obj.material)
            chk = obj.checker_material is not None
            if chk:
                # Checker basis (requirement 10):
                # u = normalize(N x (0,1,0)); if N parallel to (0,1,0) use (1,0,0)
                nx, ny, nz = obj.n
                cx = ny * 0.0 - nz * 1.0
                cy = nz * 0.0 - nx * 0.0
                cz = nx * 1.0 - ny * 0.0
                ulen = math.sqrt(cx * cx + cy * cy + cz * cz)
                if ulen < 1e-12:
                    ux, uy, uz = 1.0, 0.0, 0.0
                else:
                    ux, uy, uz = cx / ulen, cy / ulen, cz / ulen
                vx = ny * uz - nz * uy
                vy = nz * ux - nx * uz
                vz = nx * uy - ny * ux
                cmat = _flatten_material(obj.checker_material)
                scale = obj.checker_scale
            else:
                nx, ny, nz = obj.n
                ux = uy = uz = 0.0
                vx = vy = vz = 0.0
                cmat = mat
                scale = 1.0
            planes.append((obj.p[0], obj.p[1], obj.p[2],
                           nx, ny, nz, mat, chk,
                           ux, uy, uz, vx, vy, vz, scale, cmat))
    return spheres, planes


def _build_lights(scene):
    return [(l.pos[0], l.pos[1], l.pos[2],
             l.color[0], l.color[1], l.color[2]) for l in scene.lights]


def _camera_basis(scene):
    """Return (eye, forward, right, true_up, half_h, half_w) per requirement 5."""
    cam = scene.camera
    ex, ey, ez = cam.eye
    fx = cam.look[0] - ex
    fy = cam.look[1] - ey
    fz = cam.look[2] - ez
    flen = math.sqrt(fx * fx + fy * fy + fz * fz)
    fx, fy, fz = fx / flen, fy / flen, fz / flen
    ux, uy, uz = cam.up
    rx = fy * uz - fz * uy
    ry = fz * ux - fx * uz
    rz = fx * uy - fy * ux
    rlen = math.sqrt(rx * rx + ry * ry + rz * rz)
    rx, ry, rz = rx / rlen, ry / rlen, rz / rlen
    tx = ry * fz - rz * fy
    ty = rz * fx - rx * fz
    tz = rx * fy - ry * fx
    half_h = math.tan(math.radians(cam.fov) * 0.5)
    half_w = half_h * scene.width / scene.height
    return (ex, ey, ez), (fx, fy, fz), (rx, ry, rz), (tx, ty, tz), half_h, half_w


def render(scene, progress_cb=None):
    """Render `scene` and return `bytes` of W*H RGB triplets, top row first.

    `progress_cb(rows_done, total_rows, elapsed)` is called after every
    completed row so the caller can narrate progress in real time.
    """
    sqrt = math.sqrt
    pow_ = math.pow
    floor = math.floor
    perf = time.perf_counter

    W = scene.width
    H = scene.height
    n = scene.samples
    inv_n2 = 1.0 / (n * n)
    max_depth = scene.depth
    bg = scene.background

    spheres, planes = _build_objects(scene)
    lights = _build_lights(scene)
    (ex, ey, ez), (Fx, Fy, Fz), (Rx, Ry, Rz), (Ux, Uy, Uz), half_h, half_w = \
        _camera_basis(scene)
    # Pre-scale the basis so a pixel offset (u, v) in [-1, 1] contributes
    # u*Rs + v*Us to the direction.
    Rsx, Rsy, Rsz = Rx * half_w, Ry * half_w, Rz * half_w
    Usa, Uso, Usu = Ux * half_h, Uy * half_h, Uz * half_h

    # ------------------------------------------------------------------
    # Shadow test (requirement 8). Direction is normalized, so t is a
    # distance: blocked if any object hits with 1e-4 < t < dist.
    # ------------------------------------------------------------------
    def occluded(ox, oy, oz, dx, dy, dz, dist):
        for sp in spheres:
            mx = ox - sp[0]
            my = oy - sp[1]
            mz = oz - sp[2]
            b = mx * dx + my * dy + mz * dz
            disc = b * b - (mx * mx + my * my + mz * mz - sp[3])
            if disc > 0.0:
                s = sqrt(disc)
                t = -b - s
                if t <= EPS:
                    t = -b + s
                if EPS < t < dist:
                    return True
        for pl in planes:
            dn = dx * pl[3] + dy * pl[4] + dz * pl[5]
            if -1e-12 < dn < 1e-12:
                continue
            t = ((pl[0] - ox) * pl[3] + (pl[1] - oy) * pl[4]
                 + (pl[2] - oz) * pl[5]) / dn
            if EPS < t < dist:
                return True
        return False

    # ------------------------------------------------------------------
    # Whitted integrator (requirements 6, 7, 9, 10)
    # ------------------------------------------------------------------
    def trace(ox, oy, oz, dx, dy, dz, depth):
        if depth <= 0:
            return bg

        # --- nearest intersection over all spheres then planes ---------
        tb = BIG
        hit = None
        kind = 0            # 0 miss, 1 sphere, 2 plane
        hdn = 0.0           # d dot n at a plane hit
        for sp in spheres:
            mx = ox - sp[0]
            my = oy - sp[1]
            mz = oz - sp[2]
            b = mx * dx + my * dy + mz * dz
            disc = b * b - (mx * mx + my * my + mz * mz - sp[3])
            if disc > 0.0:
                s = sqrt(disc)
                t = -b - s
                if t <= EPS:
                    t = -b + s
                if t > EPS and t < tb:
                    tb = t
                    hit = sp
                    kind = 1
        for pl in planes:
            dn = dx * pl[3] + dy * pl[4] + dz * pl[5]
            if -1e-12 < dn < 1e-12:
                continue
            t = ((pl[0] - ox) * pl[3] + (pl[1] - oy) * pl[4]
                 + (pl[2] - oz) * pl[5]) / dn
            if t > EPS and t < tb:
                tb = t
                hit = pl
                kind = 2
                hdn = dn
        if kind == 0:
            return bg

        px = ox + tb * dx
        py = oy + tb * dy
        pz = oz + tb * dz

        if kind == 1:
            ri = 1.0 / hit[4]
            nx = (px - hit[0]) * ri
            ny = (py - hit[1]) * ri
            nz = (pz - hit[2]) * ri
            dn = dx * nx + dy * ny + dz * nz
            mat = hit[5]
        else:
            nx = hit[3]
            ny = hit[4]
            nz = hit[5]
            dn = hdn
            mat = hit[6]
            if hit[7]:      # checkerboard: choose material by cell parity
                k = (floor((px * hit[8] + py * hit[9] + pz * hit[10]) / hit[14])
                     + floor((px * hit[11] + py * hit[12] + pz * hit[13]) / hit[14]))
                if k & 1:
                    mat = hit[15]

        # --- Phong local shading (requirement 7) ------------------------
        # color = ambient + sum of unoccluded light contributions.
        # No clamping until byte quantization.
        ndv = -dn                      # N.V with V = -D (toward the eye)
        cr = mat[0]; cg = mat[1]; cb = mat[2]
        dr = mat[3]; dg = mat[4]; db = mat[5]
        kr = mat[6]; kg = mat[7]; kb = mat[8]
        shine = mat[9]
        for lt in lights:
            lx = lt[0] - px
            ly = lt[1] - py
            lz = lt[2] - pz
            dist2 = lx * lx + ly * ly + lz * lz
            if dist2 <= 0.0:
                continue
            dist = sqrt(dist2)
            il = 1.0 / dist
            ldx = lx * il
            ldy = ly * il
            ldz = lz * il
            ndl = nx * ldx + ny * ldy + nz * ldz
            # Mirror L about N and dot with V:
            #   R = 2(N.L)N - L,  V = -D  =>  R.V = 2(N.L)(N.V) + L.D
            rv = 2.0 * ndl * ndv + (ldx * dx + ldy * dy + ldz * dz)
            if ndl <= 0.0 and rv <= 0.0 and shine > 0.0:
                continue               # nothing could be added
            # shadow ray from the lifted point (requirement 8)
            if occluded(px + nx * EPS, py + ny * EPS, pz + nz * EPS,
                        ldx, ldy, ldz, dist):
                continue
            dd = ndl if ndl > 0.0 else 0.0
            if rv > 0.0:
                spec = pow_(rv, shine)
            else:
                spec = pow_(0.0, shine)
            cr += lt[3] * (dr * dd + kr * spec)
            cg += lt[4] * (dg * dd + kg * spec)
            cb += lt[5] * (db * dd + kb * spec)

        # --- recursive mirror reflection (requirement 9) ----------------
        refl = mat[10]
        if refl > 0.0:
            rr_, rg_, rb_ = trace(px + nx * EPS, py + ny * EPS,
                                  pz + nz * EPS,
                                  dx - 2.0 * dn * nx,
                                  dy - 2.0 * dn * ny,
                                  dz - 2.0 * dn * nz,
                                  depth - 1)
            cr += refl * rr_
            cg += refl * rg_
            cb += refl * rb_
        return (cr, cg, cb)

    # ------------------------------------------------------------------
    # Pixel loop with n x n uniform supersampling (requirements 11, 13)
    # ------------------------------------------------------------------
    sub = [(i + 0.5) / n for i in range(n)]
    # per-column u offsets: u = 2*(x + uoff)/W - 1
    ucol = [[2.0 * (x + s) / W - 1.0 for s in sub] for x in range(W)]

    image = bytearray()
    push = image.append
    trace_ = trace
    t0 = perf()

    for y in range(H):
        # row base directions for each sub-row sample: F + v*U
        vrow = []
        for s in sub:
            v = 1.0 - 2.0 * (y + s) / H
            vrow.append((Fx + v * Usa, Fy + v * Uso, Fz + v * Usu))
        for x in range(W):
            uc = ucol[x]
            sr = 0.0
            sg = 0.0
            sb = 0.0
            for j in range(n):
                rvx, rvy, rvz = vrow[j]
                for i in range(n):
                    u = uc[i]
                    dx = rvx + u * Rsx
                    dy = rvy + u * Rsy
                    dz = rvz + u * Rsz
                    s = 1.0 / sqrt(dx * dx + dy * dy + dz * dz)
                    dx *= s
                    dy *= s
                    dz *= s
                    cr, cg, cb = trace_(ex, ey, ez, dx, dy, dz, max_depth)
                    sr += cr
                    sg += cg
                    sb += cb
            r = sr * inv_n2
            if r < 0.0:
                rb = 0
            elif r >= 1.0:
                rb = 255
            else:
                rb = int(r * 255.0 + 0.5)
            g = sg * inv_n2
            if g < 0.0:
                gb = 0
            elif g >= 1.0:
                gb = 255
            else:
                gb = int(g * 255.0 + 0.5)
            b = sb * inv_n2
            if b < 0.0:
                bb = 0
            elif b >= 1.0:
                bb = 255
            else:
                bb = int(b * 255.0 + 0.5)
            push(rb)
            push(gb)
            push(bb)
        if progress_cb is not None:
            progress_cb(y + 1, H, perf() - t0)
    return bytes(image)
