# Lumen -- scene description parser and validation.
# Produced: 2026-10-29 23:36 by DeepSeek V4.1 Flash (opencode)

"""Parser for the small line-oriented scene language used by Lumen.

The parser is deliberately strict: every token, keyword, count, and range is
checked before any rendering begins, so a bad scene can never leave a partial
PPM behind.
"""

import math
import re

# Strict numeric token forms.  Python's int()/float() are more permissive than
# the scene language (underscores, "nan", "inf", hex floats), so validate the
# spelling first and convert afterwards.
_INT_RE = re.compile(r"[+-]?[0-9]+\Z")
_FLOAT_RE = re.compile(
    r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z"
)


class SceneError(Exception):
    """A fatal scene error, optionally tied to a 1-based source line."""

    __slots__ = ("message", "line")

    def __init__(self, message, line=None):
        super().__init__(message)
        self.message = message
        self.line = line


class Scene:
    """Validated scene description consumed by the renderer."""

    __slots__ = (
        "width",
        "height",
        "background",
        "eye",
        "look",
        "up",
        "fov",
        "depth",
        "samples",
        "materials",
        "objects",
        "lights",
    )

    def __init__(self):
        self.width = None
        self.height = None
        self.background = (0.0, 0.0, 0.0)
        self.eye = None
        self.look = None
        self.up = None
        self.fov = None
        self.depth = 3
        self.samples = 1
        self.materials = {}
        # Object encodings (tuples, flat and fast to inspect):
        #   sphere: (0, cx, cy, cz, radius, radius^2, material)
        #   plane:  (1, px, py, pz, nx, ny, nz, material, checker)
        #   checker: (material2, 1/scale, ux, uy, uz, vx, vy, vz)
        self.objects = []
        # Lights: (x, y, z, r, g, b)
        self.lights = []


def _need(tokens, count, directive, line):
    if len(tokens) != count:
        raise SceneError(
            "directive '%s' expects %d argument%s, got %d"
            % (directive, count - 1, "" if count == 2 else "s", len(tokens) - 1),
            line,
        )


def _int_token(tok, what, line):
    if not _INT_RE.match(tok):
        raise SceneError("invalid integer for %s: '%s'" % (what, tok), line)
    return int(tok)


def _float_token(tok, what, line):
    if not _FLOAT_RE.match(tok):
        raise SceneError("invalid number for %s: '%s'" % (what, tok), line)
    value = float(tok)
    if not math.isfinite(value):
        raise SceneError("non-finite number for %s: '%s'" % (what, tok), line)
    return value


def _color(tokens, start, what, line):
    r = _float_token(tokens[start], what + " red", line)
    g = _float_token(tokens[start + 1], what + " green", line)
    b = _float_token(tokens[start + 2], what + " blue", line)
    if r < 0.0 or g < 0.0 or b < 0.0:
        raise SceneError("%s components must be >= 0" % what, line)
    return (r, g, b)


def _normalize(x, y, z, what, line):
    length = math.sqrt(x * x + y * y + z * z)
    if length <= 1.0e-12:
        raise SceneError("%s must be non-zero" % what, line)
    inv = 1.0 / length
    return (x * inv, y * inv, z * inv)


def _cross(ax, ay, az, bx, by, bz):
    return (ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx)


def _checker_basis(nx, ny, nz, line):
    """Return (u, v) for requirement 10, with the parallel-to-Y fallback."""
    ux, uy, uz = _cross(nx, ny, nz, 0.0, 1.0, 0.0)
    length = math.sqrt(ux * ux + uy * uy + uz * uz)
    if length <= 1.0e-12:
        ux, uy, uz = 1.0, 0.0, 0.0
    else:
        inv = 1.0 / length
        ux *= inv
        uy *= inv
        uz *= inv
    vx, vy, vz = _cross(nx, ny, nz, ux, uy, uz)
    return (ux, uy, uz, vx, vy, vz)


def parse_scene(path):
    """Parse and validate *path*, returning a Scene or raising SceneError."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
    except OSError as exc:
        reason = exc.strerror or str(exc)
        raise SceneError("cannot read scene file: %s" % reason)
    except UnicodeError:
        raise SceneError("scene file is not valid UTF-8 text")

    scene = Scene()
    seen_image = False
    seen_camera = False

    for line_number, raw in enumerate(lines, 1):
        comment = raw.find("#")
        if comment >= 0:
            raw = raw[:comment]
        tokens = raw.split()
        if not tokens:
            continue

        directive = tokens[0]

        if directive == "image":
            _need(tokens, 3, directive, line_number)
            if seen_image:
                raise SceneError("duplicate 'image' directive", line_number)
            width = _int_token(tokens[1], "image width", line_number)
            height = _int_token(tokens[2], "image height", line_number)
            if width <= 0 or height <= 0:
                raise SceneError("image dimensions must be positive", line_number)
            scene.width = width
            scene.height = height
            seen_image = True

        elif directive == "background":
            _need(tokens, 4, directive, line_number)
            scene.background = _color(tokens, 1, "background", line_number)

        elif directive == "camera":
            _need(tokens, 11, directive, line_number)
            if seen_camera:
                raise SceneError("duplicate 'camera' directive", line_number)
            eye = (
                _float_token(tokens[1], "camera eye x", line_number),
                _float_token(tokens[2], "camera eye y", line_number),
                _float_token(tokens[3], "camera eye z", line_number),
            )
            look = (
                _float_token(tokens[4], "camera look x", line_number),
                _float_token(tokens[5], "camera look y", line_number),
                _float_token(tokens[6], "camera look z", line_number),
            )
            up = (
                _float_token(tokens[7], "camera up x", line_number),
                _float_token(tokens[8], "camera up y", line_number),
                _float_token(tokens[9], "camera up z", line_number),
            )
            fov = _float_token(tokens[10], "camera fov", line_number)
            if not (0.0 < fov < 180.0):
                raise SceneError("camera fov must satisfy 0 < fov < 180", line_number)

            fx = look[0] - eye[0]
            fy = look[1] - eye[1]
            fz = look[2] - eye[2]
            if fx * fx + fy * fy + fz * fz <= 1.0e-12:
                raise SceneError("camera eye and look-at point must differ", line_number)
            if up[0] * up[0] + up[1] * up[1] + up[2] * up[2] <= 1.0e-12:
                raise SceneError("camera up vector must be non-zero", line_number)
            flen = math.sqrt(fx * fx + fy * fy + fz * fz)
            fx /= flen
            fy /= flen
            fz /= flen
            rx, ry, rz = _cross(fx, fy, fz, up[0], up[1], up[2])
            if rx * rx + ry * ry + rz * rz <= 1.0e-12:
                raise SceneError("camera up vector must not be parallel to view direction", line_number)

            scene.eye = eye
            scene.look = look
            scene.up = up
            scene.fov = fov
            seen_camera = True

        elif directive == "depth":
            _need(tokens, 2, directive, line_number)
            depth = _int_token(tokens[1], "depth", line_number)
            if depth < 0:
                raise SceneError("depth must be >= 0", line_number)
            scene.depth = depth

        elif directive == "samples":
            _need(tokens, 2, directive, line_number)
            samples = _int_token(tokens[1], "samples", line_number)
            if samples < 1:
                raise SceneError("samples must be >= 1", line_number)
            scene.samples = samples

        elif directive == "material":
            _need(tokens, 18, directive, line_number)
            if tokens[2] != "ambient":
                raise SceneError("material expects keyword 'ambient' at position 3", line_number)
            if tokens[6] != "diffuse":
                raise SceneError("material expects keyword 'diffuse' at position 7", line_number)
            if tokens[10] != "specular":
                raise SceneError("material expects keyword 'specular' at position 11", line_number)
            if tokens[14] != "shine":
                raise SceneError("material expects keyword 'shine' at position 15", line_number)
            if tokens[16] != "reflect":
                raise SceneError("material expects keyword 'reflect' at position 17", line_number)

            name = tokens[1]
            if name in scene.materials:
                raise SceneError("duplicate material name '%s'" % name, line_number)
            ambient = _color(tokens, 3, "ambient", line_number)
            diffuse = _color(tokens, 7, "diffuse", line_number)
            specular = _color(tokens, 11, "specular", line_number)
            shine = _float_token(tokens[15], "shine", line_number)
            reflect = _float_token(tokens[17], "reflect", line_number)
            if shine < 0.0:
                raise SceneError("shine must be >= 0", line_number)
            if reflect < 0.0 or reflect > 1.0:
                raise SceneError("reflect must satisfy 0 <= reflect <= 1", line_number)

            # Flat tuple: ambient(3), diffuse(3), specular(3), shine, reflect.
            scene.materials[name] = (
                ambient[0], ambient[1], ambient[2],
                diffuse[0], diffuse[1], diffuse[2],
                specular[0], specular[1], specular[2],
                shine, reflect,
            )

        elif directive == "sphere":
            _need(tokens, 6, directive, line_number)
            cx = _float_token(tokens[1], "sphere center x", line_number)
            cy = _float_token(tokens[2], "sphere center y", line_number)
            cz = _float_token(tokens[3], "sphere center z", line_number)
            radius = _float_token(tokens[4], "sphere radius", line_number)
            if radius <= 0.0:
                raise SceneError("sphere radius must be > 0", line_number)
            material_name = tokens[5]
            if material_name not in scene.materials:
                raise SceneError(
                    "unknown material '%s' (materials must be defined before use)"
                    % material_name,
                    line_number,
                )
            scene.objects.append(
                (0, cx, cy, cz, radius, radius * radius, scene.materials[material_name])
            )

        elif directive == "plane":
            if len(tokens) not in (8, 11):
                raise SceneError(
                    "directive 'plane' expects 7 or 10 arguments (plus optional "
                    "'checker <material> <scale>'), got %d" % (len(tokens) - 1),
                    line_number,
                )
            px = _float_token(tokens[1], "plane point x", line_number)
            py = _float_token(tokens[2], "plane point y", line_number)
            pz = _float_token(tokens[3], "plane point z", line_number)
            nx = _float_token(tokens[4], "plane normal x", line_number)
            ny = _float_token(tokens[5], "plane normal y", line_number)
            nz = _float_token(tokens[6], "plane normal z", line_number)
            nx, ny, nz = _normalize(nx, ny, nz, "plane normal", line_number)

            material_name = tokens[7]
            if material_name not in scene.materials:
                raise SceneError(
                    "unknown material '%s' (materials must be defined before use)"
                    % material_name,
                    line_number,
                )
            material = scene.materials[material_name]

            checker = None
            if len(tokens) == 11:
                if tokens[8] != "checker":
                    raise SceneError(
                        "plane expects keyword 'checker' after the material", line_number
                    )
                checker_name = tokens[9]
                if checker_name not in scene.materials:
                    raise SceneError(
                        "unknown checker material '%s' (materials must be defined "
                        "before use)" % checker_name,
                        line_number,
                    )
                scale = _float_token(tokens[10], "checker scale", line_number)
                if scale <= 0.0:
                    raise SceneError("checker scale must be > 0", line_number)
                ux, uy, uz, vx, vy, vz = _checker_basis(nx, ny, nz, line_number)
                checker = (
                    scene.materials[checker_name], 1.0 / scale,
                    ux, uy, uz, vx, vy, vz,
                )

            scene.objects.append(
                (1, px, py, pz, nx, ny, nz, material, checker)
            )

        elif directive == "light":
            _need(tokens, 7, directive, line_number)
            lx = _float_token(tokens[1], "light x", line_number)
            ly = _float_token(tokens[2], "light y", line_number)
            lz = _float_token(tokens[3], "light z", line_number)
            color = _color(tokens, 4, "light color", line_number)
            scene.lights.append((lx, ly, lz, color[0], color[1], color[2]))

        else:
            raise SceneError("unknown directive '%s'" % directive, line_number)

    if not seen_image:
        raise SceneError("missing required 'image' directive")
    if not seen_camera:
        raise SceneError("missing required 'camera' directive")

    return scene
