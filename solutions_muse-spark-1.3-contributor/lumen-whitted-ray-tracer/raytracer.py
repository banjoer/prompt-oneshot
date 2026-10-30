# Lumen 1.0 — Whitted ray tracer
# Produced by Muse Spark 1.3 Contributor on 2026-10-29 22:25 UTC
"""Lumen: a self-contained Whitted ray tracer with a text scene format.

Usage: python3 raytracer.py <scene-file> <output.ppm>
Standard library only.
"""
import sys
import math
import time
import os

VERSION = "1.0"
AUTHOR = "Muse Spark 1.3 Contributor"
DATESTR = "2026-10-29 22:25 UTC"
EPS = 1e-4


def eprint(msg):
    sys.stderr.write(msg + "\n")


def parse_error(scene_path, lineno, msg):
    if lineno is None:
        eprint("error: %s: %s" % (scene_path, msg))
    else:
        eprint("error: %s:%d: %s" % (scene_path, lineno, msg))
    sys.exit(1)


def parse_int(tok, scene_path, lineno, what):
    try:
        # require integer syntax (no float dots, no exponents for ints)
        # int() accepts leading/trailing whitespace and +/- signs; reject floats
        if tok == "":
            raise ValueError()
        v = int(tok)
        # ensure canonical: float-like strings like "3.0" already fail int(),
        # but strings like "3.5" fail too. Also reject hex etc? int() with base 10
        # rejects "0x10" already. Extra check: token must match int pattern.
        s = tok.strip()
        # allow leading +/-
        t = s[1:] if s[:1] in ("+", "-") else s
        if t == "" or not t.isdigit():
            raise ValueError()
        return v
    except ValueError:
        parse_error(scene_path, lineno, "%s: invalid integer '%s'" % (what, tok))
        return 0


def parse_float(tok, scene_path, lineno, what):
    try:
        v = float(tok)
    except ValueError:
        parse_error(scene_path, lineno, "%s: invalid number '%s'" % (what, tok))
        return 0.0
    if not math.isfinite(v):
        parse_error(scene_path, lineno, "%s: non-finite number '%s'" % (what, tok))
    return v


def parse_scene(scene_path):
    width = None
    height = None
    image_seen = False
    image_line = 0
    bg_r, bg_g, bg_b = 0.0, 0.0, 0.0
    cam_vals = None
    cam_line = 0
    cam_seen = False
    max_depth = 3
    samples_n = 1
    materials = {}  # name -> idx
    mat_amb = []  # list of [r,g,b]
    mat_diff = []
    mat_spec = []
    mat_shine = []
    mat_reflect = []
    spheres = []  # list of (cx,cy,cz,r,mat_idx,line)
    planes = []  # list of dict
    lights = []

    try:
        f = open(scene_path, "r")
    except OSError as e:
        eprint("error: %s: cannot open file: %s" % (scene_path, e.strerror if hasattr(e, "strerror") else str(e)))
        sys.exit(1)

    with f:
        for lineno, raw in enumerate(f, start=1):
            # strip comment
            ci = raw.find("#")
            if ci != -1:
                raw = raw[:ci]
            stripped = raw.strip()
            if stripped == "":
                continue
            toks = stripped.split()
            directive = toks[0]
            if directive == "image":
                if image_seen:
                    parse_error(scene_path, lineno, "duplicate 'image' directive")
                if len(toks) != 3:
                    parse_error(scene_path, lineno, "image expects 2 arguments, got %d" % (len(toks) - 1))
                w = parse_int(toks[1], scene_path, lineno, "image width")
                h = parse_int(toks[2], scene_path, lineno, "image height")
                if w <= 0 or h <= 0:
                    parse_error(scene_path, lineno, "image dimensions must be positive integers, got %d %d" % (w, h))
                width = w
                height = h
                image_seen = True
                image_line = lineno
            elif directive == "background":
                if len(toks) != 4:
                    parse_error(scene_path, lineno, "background expects 3 arguments, got %d" % (len(toks) - 1))
                bg_r = parse_float(toks[1], scene_path, lineno, "background r")
                bg_g = parse_float(toks[2], scene_path, lineno, "background g")
                bg_b = parse_float(toks[3], scene_path, lineno, "background b")
            elif directive == "camera":
                if cam_seen:
                    parse_error(scene_path, lineno, "duplicate 'camera' directive")
                if len(toks) != 11:
                    parse_error(scene_path, lineno, "camera expects 10 arguments, got %d" % (len(toks) - 1))
                vals = []
                for k in range(1, 11):
                    vals.append(parse_float(toks[k], scene_path, lineno, "camera arg %d" % k))
                fov = vals[9]
                if not (0.0 < fov < 180.0):
                    parse_error(scene_path, lineno, "camera fov must satisfy 0 < fov < 180, got %s" % toks[10])
                cam_vals = vals
                cam_seen = True
                cam_line = lineno
            elif directive == "depth":
                if len(toks) != 2:
                    parse_error(scene_path, lineno, "depth expects 1 argument, got %d" % (len(toks) - 1))
                d = parse_int(toks[1], scene_path, lineno, "depth")
                if d < 0:
                    parse_error(scene_path, lineno, "depth must be >= 0, got %d" % d)
                max_depth = d
            elif directive == "samples":
                if len(toks) != 2:
                    parse_error(scene_path, lineno, "samples expects 1 argument, got %d" % (len(toks) - 1))
                s = parse_int(toks[1], scene_path, lineno, "samples")
                if s < 1:
                    parse_error(scene_path, lineno, "samples must be >= 1, got %d" % s)
                samples_n = s
            elif directive == "material":
                # material <name> ambient <ar> <ag> <ab> diffuse <dr> <dg> <db> specular <sr> <sg> <sb> shine <s> reflect <t>
                if len(toks) != 18:
                    parse_error(scene_path, lineno, "material expects 17 arguments (got %d tokens total); usage: material <name> ambient <r> <g> <b> diffuse <r> <g> <b> specular <r> <g> <b> shine <s> reflect <t>" % len(toks))
                name = toks[1]
                if name in materials:
                    parse_error(scene_path, lineno, "duplicate material '%s'" % name)
                if toks[2] != "ambient" or toks[6] != "diffuse" or toks[10] != "specular" or toks[14] != "shine" or toks[16] != "reflect":
                    parse_error(scene_path, lineno, "material keywords must appear in fixed order: ambient diffuse specular shine reflect")
                ar = parse_float(toks[3], scene_path, lineno, "material ambient r")
                ag = parse_float(toks[4], scene_path, lineno, "material ambient g")
                ab = parse_float(toks[5], scene_path, lineno, "material ambient b")
                dr = parse_float(toks[7], scene_path, lineno, "material diffuse r")
                dg = parse_float(toks[8], scene_path, lineno, "material diffuse g")
                db = parse_float(toks[9], scene_path, lineno, "material diffuse b")
                sr = parse_float(toks[11], scene_path, lineno, "material specular r")
                sg = parse_float(toks[12], scene_path, lineno, "material specular g")
                sb = parse_float(toks[13], scene_path, lineno, "material specular b")
                shine = parse_float(toks[15], scene_path, lineno, "material shine")
                refl = parse_float(toks[17], scene_path, lineno, "material reflect")
                if not (shine >= 0.0):
                    parse_error(scene_path, lineno, "material shine must be >= 0, got %s" % toks[15])
                if not (0.0 <= refl <= 1.0):
                    parse_error(scene_path, lineno, "material reflect must satisfy 0 <= reflect <= 1, got %s" % toks[17])
                idx = len(mat_amb)
                materials[name] = idx
                mat_amb.append((ar, ag, ab))
                mat_diff.append((dr, dg, db))
                mat_spec.append((sr, sg, sb))
                mat_shine.append(shine)
                mat_reflect.append(refl)
            elif directive == "sphere":
                if len(toks) != 6:
                    parse_error(scene_path, lineno, "sphere expects 5 arguments, got %d" % (len(toks) - 1))
                cx = parse_float(toks[1], scene_path, lineno, "sphere cx")
                cy = parse_float(toks[2], scene_path, lineno, "sphere cy")
                cz = parse_float(toks[3], scene_path, lineno, "sphere cz")
                rad = parse_float(toks[4], scene_path, lineno, "sphere radius")
                if not (rad > 0.0):
                    parse_error(scene_path, lineno, "sphere radius must be > 0, got %s" % toks[4])
                mname = toks[5]
                if mname not in materials:
                    parse_error(scene_path, lineno, "undefined material '%s' (material must be defined before use)" % mname)
                spheres.append((cx, cy, cz, rad, materials[mname]))
            elif directive == "plane":
                if len(toks) != 8 and len(toks) != 11:
                    parse_error(scene_path, lineno, "plane expects 7 arguments ([checker <mat2> <scale>] optional), got %d" % (len(toks) - 1))
                px = parse_float(toks[1], scene_path, lineno, "plane px")
                py = parse_float(toks[2], scene_path, lineno, "plane py")
                pz = parse_float(toks[3], scene_path, lineno, "plane pz")
                nx = parse_float(toks[4], scene_path, lineno, "plane nx")
                ny = parse_float(toks[5], scene_path, lineno, "plane ny")
                nz = parse_float(toks[6], scene_path, lineno, "plane nz")
                nlen = math.sqrt(nx * nx + ny * ny + nz * nz)
                if not (nlen > 1e-12):
                    parse_error(scene_path, lineno, "plane normal must be non-zero")
                mname = toks[7]
                if mname not in materials:
                    parse_error(scene_path, lineno, "undefined material '%s' (material must be defined before use)" % mname)
                mat1 = materials[mname]
                mat2 = -1
                scale = 1.0
                if len(toks) == 11:
                    if toks[8] != "checker":
                        parse_error(scene_path, lineno, "plane optional clause must start with 'checker', got '%s'" % toks[8])
                    m2name = toks[9]
                    if m2name not in materials:
                        parse_error(scene_path, lineno, "undefined material '%s' (material must be defined before use)" % m2name)
                    mat2 = materials[m2name]
                    scale = parse_float(toks[10], scene_path, lineno, "plane checker scale")
                    if not (scale > 0.0):
                        parse_error(scene_path, lineno, "plane checker scale must be > 0, got %s" % toks[10])
                planes.append((px, py, pz, nx / nlen, ny / nlen, nz / nlen, mat1, mat2, scale))
            elif directive == "light":
                if len(toks) != 7:
                    parse_error(scene_path, lineno, "light expects 6 arguments, got %d" % (len(toks) - 1))
                lx = parse_float(toks[1], scene_path, lineno, "light x")
                ly = parse_float(toks[2], scene_path, lineno, "light y")
                lz = parse_float(toks[3], scene_path, lineno, "light z")
                lr = parse_float(toks[4], scene_path, lineno, "light r")
                lg = parse_float(toks[5], scene_path, lineno, "light g")
                lb = parse_float(toks[6], scene_path, lineno, "light b")
                if not (lr >= 0.0 and lg >= 0.0 and lb >= 0.0):
                    parse_error(scene_path, lineno, "light color components must be >= 0, got %s %s %s" % (toks[4], toks[5], toks[6]))
                lights.append((lx, ly, lz, lr, lg, lb))
            else:
                parse_error(scene_path, lineno, "unknown directive '%s'" % directive)

    if not image_seen:
        parse_error(scene_path, None, "missing required 'image' directive")
    if not cam_seen:
        parse_error(scene_path, None, "missing required 'camera' directive")

    return {
        "width": width,
        "height": height,
        "background": (bg_r, bg_g, bg_b),
        "camera_vals": cam_vals,
        "camera_line": cam_line,
        "depth": max_depth,
        "samples": samples_n,
        "materials": materials,
        "mat_amb": mat_amb,
        "mat_diff": mat_diff,
        "mat_spec": mat_spec,
        "mat_shine": mat_shine,
        "mat_reflect": mat_reflect,
        "spheres": spheres,
        "planes": planes,
        "lights": lights,
    }


def build_camera(cam_vals, scene_path, cam_line):
    ex, ey, ez, lx, ly, lz, ux, uy, uz, fov = cam_vals
    # forward = normalize(look - eye)
    fx = lx - ex
    fy = ly - ey
    fz = lz - ez
    fl = math.sqrt(fx * fx + fy * fy + fz * fz)
    if not (fl > 1e-12):
        parse_error(scene_path, cam_line, "camera eye and look-at points coincide")
    fx /= fl
    fy /= fl
    fz /= fl
    # right = normalize(forward x up)
    # forward x up = (fy*uz - fz*uy, fz*ux - fx*uz, fx*uy - fy*ux)
    rx = fy * uz - fz * uy
    ry = fz * ux - fx * uz
    rz = fx * uy - fy * ux
    rl = math.sqrt(rx * rx + ry * ry + rz * rz)
    if not (rl > 1e-12):
        parse_error(scene_path, cam_line, "camera up vector is parallel to view direction")
    rx /= rl
    ry /= rl
    rz /= rl
    # trueUp = right x forward? spec says trueUp = right x forward
    # right x forward = (ry*fz - rz*fy, rz*fx - rx*fz, rx*fy - ry*fx)
    tx = ry * fz - rz * fy
    ty = rz * fx - rx * fz
    tz = rx * fy - ry * fx
    # Note: right x forward gives vector pointing opposite? Let's verify:
    # standard: trueUp = right cross forward? Usually up = right x forward? With
    # right = forward x up0 normalized, then trueUp = right x forward gives
    # a vector pointing roughly along original up but orthonormal. Actually
    # cross(right, forward) = ? For forward=(0,0,-1), up0=(0,1,0):
    # right = forward x up0 = (0*0-(-1)*1, (-1)*0-0*0, 0*1-0*0) = (1,0,0). Good.
    # right x forward = (0*(-1)-0*0, 0*0-1*(-1), 1*0-0*0) = (0,1,0). Good.
    # So formula above is right x forward. Good.
    return (ex, ey, ez, fx, fy, fz, rx, ry, rz, tx, ty, tz, fov)


def build_planes(planes_raw):
    # precompute checker basis u,v per spec
    out = []
    for (px, py, pz, nx, ny, nz, mat1, mat2, scale) in planes_raw:
        if mat2 != -1:
            # u = normalize(N x (0,1,0)), fallback (1,0,0) when parallel
            # N x (0,1,0) = (ny*0 - nz*1, nz*0 - nx*0, nx*1 - ny*0) = (-nz, 0, nx)
            ux = -nz
            uy = 0.0
            uz = nx
            ul = math.sqrt(ux * ux + uy * uy + uz * uz)
            if ul < 1e-12:
                ux, uy, uz = 1.0, 0.0, 0.0
            else:
                ux /= ul
                uy /= ul
                uz /= ul
            # v = N x u = (ny*uz - nz*uy, nz*ux - nx*uz, nx*uy - ny*ux)
            vx = ny * uz - nz * uy
            vy = nz * ux - nx * uz
            vz = nx * uy - ny * ux
        else:
            ux, uy, uz = 0.0, 0.0, 0.0
            vx, vy, vz = 0.0, 0.0, 0.0
        out.append((px, py, pz, nx, ny, nz, mat1, mat2, scale, ux, uy, uz, vx, vy, vz))
    return out


def render(scene, scene_path, out_path):
    W = scene["width"]
    H = scene["height"]
    bg_r, bg_g, bg_b = scene["background"]
    max_depth = scene["depth"]
    ns = scene["samples"]
    mat_amb = scene["mat_amb"]
    mat_diff = scene["mat_diff"]
    mat_spec = scene["mat_spec"]
    mat_shine = scene["mat_shine"]
    mat_reflect = scene["mat_reflect"]
    spheres_raw = scene["spheres"]
    planes_raw = build_planes(scene["planes"])
    lights_raw = scene["lights"]

    ex, ey, ez, fx, fy, fz, rx, ry, rz, tx, ty, tz, fov = build_camera(scene["camera_vals"], scene_path, scene["camera_line"])

    half_h = math.tan(math.radians(fov * 0.5))
    half_w = half_h * (float(W) / float(H))

    n_objects = len(spheres_raw) + len(planes_raw)
    n_lights = len(lights_raw)

    # flatten for speed: bind to locals
    # spheres: separate lists
    sph_cx = [s[0] for s in spheres_raw]
    sph_cy = [s[1] for s in spheres_raw]
    sph_cz = [s[2] for s in spheres_raw]
    sph_r = [s[3] for s in spheres_raw]
    sph_r2 = [s[3] * s[3] for s in spheres_raw]
    sph_mat = [s[4] for s in spheres_raw]
    n_sph = len(spheres_raw)

    pl_px = [p[0] for p in planes_raw]
    pl_py = [p[1] for p in planes_raw]
    pl_pz = [p[2] for p in planes_raw]
    pl_nx = [p[3] for p in planes_raw]
    pl_ny = [p[4] for p in planes_raw]
    pl_nz = [p[5] for p in planes_raw]
    pl_m1 = [p[6] for p in planes_raw]
    pl_m2 = [p[7] for p in planes_raw]
    pl_sc = [p[8] for p in planes_raw]
    pl_ux = [p[9] for p in planes_raw]
    pl_uy = [p[10] for p in planes_raw]
    pl_uz = [p[11] for p in planes_raw]
    pl_vx = [p[12] for p in planes_raw]
    pl_vy = [p[13] for p in planes_raw]
    pl_vz = [p[14] for p in planes_raw]
    n_pl = len(planes_raw)

    li_x = [l[0] for l in lights_raw]
    li_y = [l[1] for l in lights_raw]
    li_z = [l[2] for l in lights_raw]
    li_r = [l[3] for l in lights_raw]
    li_g = [l[4] for l in lights_raw]
    li_b = [l[5] for l in lights_raw]

    # material arrays flattened
    m_ar = [c[0] for c in mat_amb]
    m_ag = [c[1] for c in mat_amb]
    m_ab = [c[2] for c in mat_amb]
    m_dr = [c[0] for c in mat_diff]
    m_dg = [c[1] for c in mat_diff]
    m_db = [c[2] for c in mat_diff]
    m_sr = [c[0] for c in mat_spec]
    m_sg = [c[1] for c in mat_spec]
    m_sb = [c[2] for c in mat_spec]

    sqrt = math.sqrt
    floor = math.floor

    # startup banner + scene summary (stdout)
    print("lumen %s \u2014 built by %s on %s" % (VERSION, AUTHOR, DATESTR), flush=True)
    print("scene: %s -> %s \u2014 %dx%d, %dx%d samples, depth %d, %d objects, %d lights" % (
        scene_path, out_path, W, H, ns, ns, max_depth, n_objects, n_lights), flush=True)

    # pixel buffer: bytearray of size W*H*3
    pix = bytearray(W * H * 3)

    inv_n2 = 1.0 / float(ns * ns)
    inv_W = 1.0 / float(W)
    inv_H = 1.0 / float(H)

    t_start = time.time()

    # progress bookkeeping
    update_every = max(1, H // 50)
    # ensure at least 10 updates: if H//update_every < 10, adjust
    if H // update_every < 10 and H >= 10:
        update_every = max(1, H // 10)
    # for tiny images H<10, update every row (H updates) - best effort

    # bind for inner loop speed
    _sph_cx = sph_cx
    _sph_cy = sph_cy
    _sph_cz = sph_cz
    _sph_r = sph_r
    _sph_r2 = sph_r2
    _sph_mat = sph_mat
    _pl_px = pl_px
    _pl_py = pl_py
    _pl_pz = pl_pz
    _pl_nx = pl_nx
    _pl_ny = pl_ny
    _pl_nz = pl_nz
    _pl_m1 = pl_m1
    _pl_m2 = pl_m2
    _pl_sc = pl_sc
    _pl_ux = pl_ux
    _pl_uy = pl_uy
    _pl_uz = pl_uz
    _pl_vx = pl_vx
    _pl_vy = pl_vy
    _pl_vz = pl_vz
    _li_x = li_x
    _li_y = li_y
    _li_z = li_z
    _li_r = li_r
    _li_g = li_g
    _li_b = li_b
    _m_ar = m_ar
    _m_ag = m_ag
    _m_ab = m_ab
    _m_dr = m_dr
    _m_dg = m_dg
    _m_db = m_db
    _m_sr = m_sr
    _m_sg = m_sg
    _m_sb = m_sb
    _m_sh = mat_shine
    _m_rf = mat_reflect

    # define occlusion test inline as local function for speed? We'll inline manually
    # define trace as nested function using closure + recursion
    sys.setrecursionlimit(10000)

    def trace(ox, oy, oz, dx, dy, dz, rem, is_primary):
        # base: secondary ray with no remaining bounces returns background
        if (not is_primary) and rem <= 0:
            return (bg_r, bg_g, bg_b)
        # find nearest hit
        best_t = float("inf")
        hit_kind = -1  # 0 sphere, 1 plane
        hit_idx = -1
        # spheres
        for si in range(n_sph):
            cx = _sph_cx[si]
            cy = _sph_cy[si]
            cz = _sph_cz[si]
            ocx = ox - cx
            ocy = oy - cy
            ocz = oz - cz
            # b = oc . d
            b = ocx * dx + ocy * dy + ocz * dz
            c_ = ocx * ocx + ocy * ocy + ocz * ocz - _sph_r2[si]
            disc = b * b - c_
            if disc < 0.0:
                continue
            sq = sqrt(disc)
            t = -b - sq
            if t <= EPS:
                t = -b + sq
                if t <= EPS:
                    continue
            if t < best_t:
                best_t = t
                hit_kind = 0
                hit_idx = si
        # planes
        for pi in range(n_pl):
            denom = dx * _pl_nx[pi] + dy * _pl_ny[pi] + dz * _pl_nz[pi]
            if denom > -1e-12 and denom < 1e-12:
                continue
            t = ((_pl_px[pi] - ox) * _pl_nx[pi] + (_pl_py[pi] - oy) * _pl_ny[pi] + (_pl_pz[pi] - oz) * _pl_nz[pi]) / denom
            if t <= EPS:
                continue
            if t < best_t:
                best_t = t
                hit_kind = 1
                hit_idx = pi
        if hit_kind == -1:
            return (bg_r, bg_g, bg_b)
        # hit point
        px = ox + dx * best_t
        py = oy + dy * best_t
        pz = oz + dz * best_t
        # normal + material
        if hit_kind == 0:
            rr = _sph_r[hit_idx]
            nx = (px - _sph_cx[hit_idx]) / rr
            ny = (py - _sph_cy[hit_idx]) / rr
            nz = (pz - _sph_cz[hit_idx]) / rr
            mi = _sph_mat[hit_idx]
        else:
            nx = _pl_nx[hit_idx]
            ny = _pl_ny[hit_idx]
            nz = _pl_nz[hit_idx]
            m2 = _pl_m2[hit_idx]
            if m2 != -1:
                # checker
                sc = _pl_sc[hit_idx]
                ux_ = _pl_ux[hit_idx]
                uy_ = _pl_uy[hit_idx]
                uz_ = _pl_uz[hit_idx]
                vx_ = _pl_vx[hit_idx]
                vy_ = _pl_vy[hit_idx]
                vz_ = _pl_vz[hit_idx]
                pu = (px * ux_ + py * uy_ + pz * uz_) / sc
                pv = (px * vx_ + py * vy_ + pz * vz_) / sc
                k = floor(pu) + floor(pv)
                if (k & 1) == 0:
                    mi = _pl_m1[hit_idx]
                else:
                    # odd: handle negative odd correctly: in Python, k&1 works for negatives? -1 & 1 = 1 in Python infinite bits, so odd detection ok.
                    # But to be precise for negative numbers, use k % 2 != 0
                    mi = m2
                    # k&1 already handles; keep mi=m2 for odd
                    # recompute with modulo to be safe:
                    # (k % 2 == 0 -> even)
                    # Python's % yields 0 for even negatives, 1 for odd negatives, so same.
                    pass
                # fix for negative: ensure even/odd via modulo
                # (already correct, but double-check with %)
                # if (k % 2) == 0: mi = m1 else m2 — equivalent to above; keep as is.
                # To avoid any doubt, recompute:
                if (k % 2) == 0:
                    mi = _pl_m1[hit_idx]
                else:
                    mi = m2
            else:
                mi = _pl_m1[hit_idx]
        # orient normal to face incoming ray (N.V > 0)
        d_dot_n = dx * nx + dy * ny + dz * nz
        if d_dot_n > 0.0:
            nx = -nx
            ny = -ny
            nz = -nz
            d_dot_n = -d_dot_n
        # local shading
        amb_r = _m_ar[mi]
        amb_g = _m_ag[mi]
        amb_b = _m_ab[mi]
        cr = amb_r
        cg = amb_g
        cb = amb_b
        dif_r = _m_dr[mi]
        dif_g = _m_dg[mi]
        dif_b = _m_db[mi]
        spc_r = _m_sr[mi]
        spc_g = _m_sg[mi]
        spc_b = _m_sb[mi]
        shine = _m_sh[mi]
        # V = -D
        vx_eye = -dx
        vy_eye = -dy
        vz_eye = -dz
        # shadow origin
        sox = px + nx * EPS
        soy = py + ny * EPS
        soz = pz + nz * EPS
        for li in range(n_lights):
            lxx = _li_x[li]
            lyy = _li_y[li]
            lzz = _li_z[li]
            # vector from P to light (use original P for distance per spec)
            lpx = lxx - px
            lpy = lyy - py
            lpz = lzz - pz
            dist = sqrt(lpx * lpx + lpy * lpy + lpz * lpz)
            if dist < 1e-12:
                continue
            # shadow dir from offset origin to light
            sdx = lxx - sox
            sdy = lyy - soy
            sdz = lzz - soz
            sl = sqrt(sdx * sdx + sdy * sdy + sdz * sdz)
            if sl < 1e-12:
                continue
            sdx /= sl
            sdy /= sl
            sdz /= sl
            # occlusion test: any object with EPS < t < dist
            occluded = False
            # spheres
            for si in range(n_sph):
                cx = _sph_cx[si]
                cy = _sph_cy[si]
                cz = _sph_cz[si]
                ocx = sox - cx
                ocy = soy - cy
                ocz = soz - cz
                b = ocx * sdx + ocy * sdy + ocz * sdz
                c_ = ocx * ocx + ocy * ocy + ocz * ocz - _sph_r2[si]
                disc = b * b - c_
                if disc < 0.0:
                    continue
                sq = sqrt(disc)
                t = -b - sq
                if t > EPS and t < dist:
                    occluded = True
                    break
                t = -b + sq
                if t > EPS and t < dist:
                    occluded = True
                    break
            if occluded:
                continue
            # planes
            for pi in range(n_pl):
                denom = sdx * _pl_nx[pi] + sdy * _pl_ny[pi] + sdz * _pl_nz[pi]
                if denom > -1e-12 and denom < 1e-12:
                    continue
                t = ((_pl_px[pi] - sox) * _pl_nx[pi] + (_pl_py[pi] - soy) * _pl_ny[pi] + (_pl_pz[pi] - soz) * _pl_nz[pi]) / denom
                if t > EPS and t < dist:
                    occluded = True
                    break
            if occluded:
                continue
            # unoccluded: Phong
            # Ldir = (light - P)/dist
            ldx = lpx / dist
            ldy = lpy / dist
            ldz = lpz / dist
            ndotl = nx * ldx + ny * ldy + nz * ldz
            ndotl_c = ndotl if ndotl > 0.0 else 0.0
            # R = 2*ndotl*N - L
            rx_ = 2.0 * ndotl * nx - ldx
            ry_ = 2.0 * ndotl * ny - ldy
            rz_ = 2.0 * ndotl * nz - ldz
            rdotv = rx_ * vx_eye + ry_ * vy_eye + rz_ * vz_eye
            if rdotv > 0.0:
                if shine == 0.0:
                    spec_f = 1.0
                else:
                    spec_f = rdotv ** shine
            else:
                spec_f = 0.0
            lr = _li_r[li]
            lg = _li_g[li]
            lb = _li_b[li]
            cr += lr * (dif_r * ndotl_c + spc_r * spec_f)
            cg += lg * (dif_g * ndotl_c + spc_g * spec_f)
            cb += lb * (dif_b * ndotl_c + spc_b * spec_f)
        # reflection
        refl = _m_rf[mi]
        if rem > 0 and refl > 0.0:
            # reflected dir: D - 2(D.N)N ; D.N = d_dot_n (<=0 after flip? note d_dot_n computed before flip? we flipped, so recompute? d_dot_n was negated if flipped. After flip, d_dot_n <= 0.)
            # Use current nx,ny,nz (flipped) and d_dot_n (<=0)
            rdx = dx - 2.0 * d_dot_n * nx
            rdy = dy - 2.0 * d_dot_n * ny
            rdz = dz - 2.0 * d_dot_n * nz
            # origin offset
            rox = px + nx * EPS
            roy = py + ny * EPS
            roz = pz + nz * EPS
            rr_, rg_, rb_ = trace(rox, roy, roz, rdx, rdy, rdz, rem - 1, False)
            cr += refl * rr_
            cg += refl * rg_
            cb += refl * rb_
        return (cr, cg, cb)

    # main pixel loop
    inv_ns = 1.0 / float(ns)
    for y in range(H):
        # progress handled after row
        for x in range(W):
            acc_r = 0.0
            acc_g = 0.0
            acc_b = 0.0
            for j in range(ns):
                sy = float(y) + (float(j) + 0.5) * inv_ns
                ndc_y = 1.0 - (sy * inv_H) * 2.0
                ty_off = ndc_y * half_h
                for i in range(ns):
                    sx = float(x) + (float(i) + 0.5) * inv_ns
                    ndc_x = (sx * inv_W) * 2.0 - 1.0
                    tx_off = ndc_x * half_w
                    # dir = f + r*tx_off + t*ty_off
                    dx = fx + rx * tx_off + tx * ty_off
                    dy = fy + ry * tx_off + ty * ty_off
                    dz = fz + rz * tx_off + tz * ty_off
                    dl = sqrt(dx * dx + dy * dy + dz * dz)
                    dx /= dl
                    dy /= dl
                    dz /= dl
                    cr, cg, cb = trace(ex, ey, ez, dx, dy, dz, max_depth, True)
                    acc_r += cr
                    acc_g += cg
                    acc_b += cb
            acc_r *= inv_n2
            acc_g *= inv_n2
            acc_b *= inv_n2
            # clamp + quantize
            if acc_r <= 0.0:
                br = 0
            elif acc_r >= 1.0:
                br = 255
            else:
                br = int(acc_r * 255.0 + 0.5)
            if acc_g <= 0.0:
                bg_ = 0
            elif acc_g >= 1.0:
                bg_ = 255
            else:
                bg_ = int(acc_g * 255.0 + 0.5)
            if acc_b <= 0.0:
                bb = 0
            elif acc_b >= 1.0:
                bb = 255
            else:
                bb = int(acc_b * 255.0 + 0.5)
            off = (y * W + x) * 3
            pix[off] = br
            pix[off + 1] = bg_
            pix[off + 2] = bb
        # progress update
        rows_done = y + 1
        if (rows_done % update_every == 0) or (rows_done == H):
            elapsed = time.time() - t_start
            pct = rows_done * 100.0 / float(H)
            if rows_done > 0 and elapsed > 0:
                eta = elapsed * (float(H) / float(rows_done) - 1.0)
            else:
                eta = 0.0
            print("rendering: [%4d/%d rows] %5.1f%%  elapsed %.1fs  eta %.1fs" % (rows_done, H, pct, elapsed, eta), flush=True)

    total = time.time() - t_start
    # write PPM
    header = ("P6\n%d %d\n255\n" % (W, H)).encode("ascii")
    try:
        with open(out_path, "wb") as out:
            out.write(header)
            out.write(pix)
    except OSError as e:
        eprint("error: cannot write output '%s': %s" % (out_path, str(e)))
        sys.exit(1)
    try:
        size = os.path.getsize(out_path)
    except OSError:
        size = len(header) + len(pix)
    ms_per_px = (total * 1000.0 / float(W * H)) if (W * H) > 0 else 0.0
    print("done: %dx%d in %.1fs (%.3f ms/pixel) -> %s (%d bytes)" % (W, H, total, ms_per_px, out_path, size), flush=True)


def main(argv):
    prog = argv[0] if argv else "raytracer.py"
    if len(argv) != 3:
        eprint("usage: python3 %s <scene-file> <output.ppm>" % prog)
        return 2
    scene_path = argv[1]
    out_path = argv[2]
    scene = parse_scene(scene_path)
    render(scene, scene_path, out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
