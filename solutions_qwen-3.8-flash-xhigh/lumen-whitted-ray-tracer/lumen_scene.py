# Lumen — a Whitted ray tracer with a scene file format
# File: lumen_scene.py — scene-language parser and validation
# Produced: 2026-10-30 00:10
# Model/Author: Qwen 3.8 Flash (xhigh)
"""Parser for the Lumen scene description language.

The scene file is read line by line.  ``#`` introduces a comment that runs
to the end of the line, blank lines are ignored, and tokens are separated
by whitespace.  Supported directives:

    image <w> <h>
    background <r> <g> <b>
    camera <ex ey ez> <lx ly lz> <ux uy uz> <fov>
    depth <n>
    samples <n>
    material <name> ambient <ar ag ab> diffuse <dr dg db> specular <sr sg sb> shine <s> reflect <t>
    sphere <cx cy cz r> <material-name>
    plane <px py pz> <nx ny nz> <material-name> [checker <material2-name> <scale>]
    light <x y z> <r g b>

Every fatal problem is reported as a :class:`SceneError` carrying the
offending line number (``None`` for whole-file problems such as a missing
required directive).
"""

import math

PROGRAM_NAME = "lumen"
PROGRAM_VERSION = "1.0"
BUILD_DATE = "2026-10-30 00:10"
BUILD_AUTHOR = "Qwen 3.8 Flash (xhigh)"

DEFAULT_BACKGROUND = (0.0, 0.0, 0.0)
DEFAULT_DEPTH = 3
DEFAULT_SAMPLES = 1


class SceneError(Exception):
    """A fatal parse/validation error.  line_no is None for file-wide errors."""

    def __init__(self, line_no, message):
        super().__init__(message)
        self.line_no = line_no
        self.message = message

    def format(self, path):
        if self.line_no is None:
            return "error: %s: %s" % (path, self.message)
        return "error: %s:%d: %s" % (path, self.line_no, self.message)


# ---------------------------------------------------------------------------
# Scene objects
# ---------------------------------------------------------------------------

class Material:
    __slots__ = ("name", "ambient", "diffuse", "specular", "shine", "reflect")

    def __init__(self, name, ambient, diffuse, specular, shine, reflect):
        self.name = name
        self.ambient = ambient      # (r, g, b)
        self.diffuse = diffuse      # (r, g, b)
        self.specular = specular    # (r, g, b)
        self.shine = shine          # float >= 0
        self.reflect = reflect      # 0..1


class Sphere:
    __slots__ = ("c", "r", "material")

    def __init__(self, c, r, material):
        self.c = c
        self.r = r
        self.material = material    # Material instance


class Plane:
    __slots__ = ("p", "n", "material", "checker_material", "checker_scale")

    def __init__(self, p, n, material, checker_material=None, checker_scale=None):
        self.p = p
        self.n = n                  # normalized (unit) normal
        self.material = material
        self.checker_material = checker_material   # Material or None
        self.checker_scale = checker_scale


class Light:
    __slots__ = ("pos", "color")

    def __init__(self, pos, color):
        self.pos = pos
        self.color = color


class Camera:
    __slots__ = ("eye", "look", "up", "fov")

    def __init__(self, eye, look, up, fov):
        self.eye = eye
        self.look = look
        self.up = up
        self.fov = fov


class Scene:
    __slots__ = ("width", "height", "background", "camera", "depth",
                 "samples", "objects", "lights")

    def __init__(self):
        self.width = None
        self.height = None
        self.background = DEFAULT_BACKGROUND
        self.camera = None
        self.depth = DEFAULT_DEPTH
        self.samples = DEFAULT_SAMPLES
        self.objects = []           # Sphere / Plane instances
        self.lights = []            # Light instances

    @property
    def object_count(self):
        return len(self.objects)

    @property
    def light_count(self):
        return len(self.lights)


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def _num(tokens, i, line_no):
    """Parse tokens[i] as a float, raising SceneError on bad input."""
    tok = tokens[i]
    try:
        val = float(tok)
    except ValueError:
        raise SceneError(line_no, "expected a number but got '%s'" % tok)
    if val != val or val in (float("inf"), float("-inf")):
        raise SceneError(line_no, "'%s' is not a finite number" % tok)
    return val


def _pos_int(tokens, i, line_no):
    tok = tokens[i]
    try:
        val = int(tok)
    except ValueError:
        raise SceneError(line_no, "expected an integer but got '%s'" % tok)
    # int("3.5") fails above; also reject things like int("1_0") == 10? Python
    # accepts underscores in int(); that is still an integer token, fine.
    return val


def _arity(tokens, expected, line_no):
    got = len(tokens) - 1
    if got != expected:
        plural = "s" if expected != 1 else ""
        raise SceneError(line_no,
                         "'%s' expects %d argument%s, got %d"
                         % (tokens[0], expected, plural, got))


# ---------------------------------------------------------------------------
# Directive handlers
# ---------------------------------------------------------------------------

def _do_image(scene, seen, tokens, line_no):
    if scene.width is not None:
        raise SceneError(line_no, "duplicate 'image' directive")
    _arity(tokens, 2, line_no)
    w = _pos_int(tokens, 1, line_no)
    h = _pos_int(tokens, 2, line_no)
    if w < 1 or h < 1:
        raise SceneError(line_no, "image dimensions must be >= 1")
    scene.width, scene.height = w, h
    seen.add("image")


def _do_background(scene, tokens, line_no):
    _arity(tokens, 3, line_no)
    scene.background = (_num(tokens, 1, line_no),
                        _num(tokens, 2, line_no),
                        _num(tokens, 3, line_no))


def _do_camera(scene, seen, tokens, line_no):
    if scene.camera is not None:
        raise SceneError(line_no, "duplicate 'camera' directive")
    _arity(tokens, 10, line_no)
    vals = [_num(tokens, 1 + k, line_no) for k in range(10)]
    fov = vals[9]
    if not (0.0 < fov < 180.0):
        raise SceneError(line_no,
                         "camera fov out of range (0 < fov < 180): %g" % fov)
    scene.camera = Camera(tuple(vals[0:3]), tuple(vals[3:6]),
                          tuple(vals[6:9]), fov)
    seen.add("camera")


def _do_depth(scene, tokens, line_no):
    _arity(tokens, 1, line_no)
    d = _pos_int(tokens, 1, line_no)
    if d < 0:
        raise SceneError(line_no, "depth must be >= 0")
    scene.depth = d


def _do_samples(scene, tokens, line_no):
    _arity(tokens, 1, line_no)
    s = _pos_int(tokens, 1, line_no)
    if s < 1:
        raise SceneError(line_no, "samples must be >= 1")
    scene.samples = s


def _do_material(scene, materials, tokens, line_no):
    _arity(tokens, 17, line_no)
    name = tokens[1]
    if name in materials:
        raise SceneError(line_no, "duplicate material '%s'" % name)
    keywords = ((2, "ambient"), (6, "diffuse"), (10, "specular"),
                (14, "shine"), (16, "reflect"))
    for idx, kw in keywords:
        if tokens[idx] != kw:
            raise SceneError(line_no,
                             "expected keyword '%s' at position %d of material "
                             "'%s', got '%s'" % (kw, idx, name, tokens[idx]))
    ambient = tuple(_num(tokens, i, line_no) for i in (3, 4, 5))
    diffuse = tuple(_num(tokens, i, line_no) for i in (7, 8, 9))
    specular = tuple(_num(tokens, i, line_no) for i in (11, 12, 13))
    shine = _num(tokens, 15, line_no)
    reflect = _num(tokens, 17, line_no)
    if shine < 0.0:
        raise SceneError(line_no,
                         "material '%s': shine must be >= 0, got %g" % (name, shine))
    if not (0.0 <= reflect <= 1.0):
        raise SceneError(line_no,
                         "material '%s': reflect out of range [0, 1]: %g"
                         % (name, reflect))
    materials[name] = Material(name, ambient, diffuse, specular, shine, reflect)


def _lookup(materials, name, line_no, role):
    mat = materials.get(name)
    if mat is None:
        raise SceneError(line_no,
                         "%s references undefined material '%s'" % (role, name))
    return mat


def _do_sphere(scene, materials, tokens, line_no):
    _arity(tokens, 5, line_no)
    c = tuple(_num(tokens, i, line_no) for i in (1, 2, 3))
    r = _num(tokens, 4, line_no)
    if r <= 0.0:
        raise SceneError(line_no, "sphere radius must be > 0, got %g" % r)
    mat = _lookup(materials, tokens[5], line_no, "sphere")
    scene.objects.append(Sphere(c, r, mat))


def _do_plane(scene, materials, tokens, line_no):
    """plane <px py pz> <nx ny nz> <mat> [checker <mat2-name> <scale>]"""
    ntok = len(tokens)
    if ntok == 8:
        args = 7
    elif ntok == 11:
        if tokens[8] != "checker":
            raise SceneError(line_no,
                             "expected 'checker' in plane clause, got '%s'"
                             % tokens[8])
        args = 10
    else:
        raise SceneError(line_no,
                         "'plane' expects 7 arguments (plus optional 'checker "
                         "<material> <scale>'), got %d" % (ntok - 1))
    p = tuple(_num(tokens, i, line_no) for i in (1, 2, 3))
    n = tuple(_num(tokens, i, line_no) for i in (4, 5, 6))
    length = math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2])
    if length < 1e-12:
        raise SceneError(line_no, "plane normal has zero length")
    n = (n[0] / length, n[1] / length, n[2] / length)
    mat = _lookup(materials, tokens[7], line_no, "plane")
    cmat = None
    cscale = None
    if args == 10:
        cmat = _lookup(materials, tokens[9], line_no, "plane checker")
        cscale = _num(tokens, 10, line_no)
        if cscale <= 0.0:
            raise SceneError(line_no,
                             "checker scale must be > 0, got %g" % cscale)
    scene.objects.append(Plane(p, n, mat, cmat, cscale))


def _do_light(scene, tokens, line_no):
    _arity(tokens, 6, line_no)
    pos = tuple(_num(tokens, i, line_no) for i in (1, 2, 3))
    color = tuple(_num(tokens, i, line_no) for i in (4, 5, 6))
    for ch, v in zip("rgb", color):
        if v < 0.0:
            raise SceneError(line_no,
                             "light color %s must be >= 0, got %g" % (ch, v))
    scene.lights.append(Light(pos, color))


# ---------------------------------------------------------------------------
# Top-level parse
# ---------------------------------------------------------------------------

def parse_scene(path):
    """Parse `path` and return a Scene, or raise SceneError."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        raise SceneError(None, "cannot read scene file: %s"
                         % (exc.strerror or str(exc)))
    except UnicodeDecodeError:
        raise SceneError(None, "scene file is not valid UTF-8 text")

    scene = Scene()
    materials = {}
    seen = set()

    for line_no, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        tokens = line.split()
        kw = tokens[0]

        if kw == "image":
            _do_image(scene, seen, tokens, line_no)
        elif kw == "background":
            _do_background(scene, tokens, line_no)
        elif kw == "camera":
            _do_camera(scene, seen, tokens, line_no)
        elif kw == "depth":
            _do_depth(scene, tokens, line_no)
        elif kw == "samples":
            _do_samples(scene, tokens, line_no)
        elif kw == "material":
            _do_material(scene, materials, tokens, line_no)
        elif kw == "sphere":
            _do_sphere(scene, materials, tokens, line_no)
        elif kw == "plane":
            _do_plane(scene, materials, tokens, line_no)
        elif kw == "light":
            _do_light(scene, tokens, line_no)
        else:
            raise SceneError(line_no, "unknown directive '%s'" % kw)

    if "image" not in seen:
        raise SceneError(None, "missing required 'image' directive")
    if "camera" not in seen:
        raise SceneError(None, "missing required 'camera' directive")

    # Sanity-check the camera basis up front so rendering never divides by 0.
    cam = scene.camera
    fwd = (cam.look[0] - cam.eye[0],
           cam.look[1] - cam.eye[1],
           cam.look[2] - cam.eye[2])
    flen = math.sqrt(fwd[0] * fwd[0] + fwd[1] * fwd[1] + fwd[2] * fwd[2])
    if flen < 1e-12:
        raise SceneError(None, "camera eye and look-at points coincide")
    f = (fwd[0] / flen, fwd[1] / flen, fwd[2] / flen)
    rx = f[1] * cam.up[2] - f[2] * cam.up[1]
    ry = f[2] * cam.up[0] - f[0] * cam.up[2]
    rz = f[0] * cam.up[1] - f[1] * cam.up[0]
    rlen = math.sqrt(rx * rx + ry * ry + rz * rz)
    if rlen < 1e-12:
        raise SceneError(None,
                         "camera up hint is parallel to the view direction")

    return scene
