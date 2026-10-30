#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =============================================================================
#  NEON SERPENT - Terminal Snake
#  -----------------------------------------------------------------------------
#  built : 2026-10-30 00:54 CET (+0100)          <- production date / time
#  by    : Qwen 3.8 Flash (xhigh thinking)       <- model / author
#  stack : Python 3 standard library only - no curses, no third-party code
#  run   : python3 snake.py
#
#  A real-time snake game drawn with hand-rolled ANSI escape codes:
#    * alternate screen buffer, hidden cursor, flicker-free full redraws
#      (one frame = one write, every line cleared in place, nothing scrolls)
#    * raw-ish cbreak input (termios + select), non-blocking, polled per frame
#    * monotonic-clock tick scheduling: 150 ms -> -7 ms per food -> 60 ms floor
#    * buffered steering (arrows + WASD + vim keys); 180 degree neck
#      reversals are ignored both at press time and at tick time
#    * start screen with the saved top-5 table and the sign-off footer
#    * game-over screen with a 3-character initials editor (A-Z 0-9)
#    * persistent scores in snake_scores.json next to this script; a corrupt
#      file is backed up to snake_scores.json.bak(.N) and the run starts fresh
#    * the terminal is restored on every exit path: q, Ctrl+C, SIGTERM, crash
#
#  Stretch goals implemented: wrap-around arena (`w` on the start screen, with
#  its own high-score table), bonus fruit (star, 50 pts, ~25 s cadence, 5 s
#  life, blinking countdown) and a neon head-to-tail ghost-trail colour fade.
# =============================================================================
"""Neon Serpent - a terminal snake game rendered entirely with ANSI escapes."""

import datetime
import json
import os
import random
import re
import select
import shutil
import signal
import sys
import termios
import time
import tty

# -----------------------------------------------------------------------------
# Contract constants (straight from the specification)
# -----------------------------------------------------------------------------
MIN_COLS = 40                    # smallest terminal we will draw in
MIN_ROWS = 20
MIN_INNER_W = 30                 # playfield interior, in cells
MIN_INNER_H = 15
MAX_INNER_W = 76                 # keep huge terminals readable
MAX_INNER_H = 24

TICK_START_MS = 150              # first tick
TICK_STEP_MS = 7                 # subtracted per food eaten
TICK_MIN_MS = 60                 # hard floor
FOOD_POINTS = 10
BONUS_POINTS = 50
BONUS_PERIOD_S = 25.0            # a star shows up about every 25 s
BONUS_LIFETIME_S = 5.0           # ... and lives for 5 s
START_LENGTH = 3
TOP_N = 5                        # high-score table size
INITIALS_LEN = 3

SNAKE_HEAD = "\u2588"                            # █
FADE_GLYPHS = ("\u2588", "\u2593", "\u2592", "\u2591")   # █ ▓ ▒ ░
FOOD_GLYPH = "\u25cf"                            # ●
BONUS_GLYPH = "\u2605"                           # ★
GRID_GLYPH = "\u00b7"                            # ·  (faint field dots)
HLINE, VLINE = "\u2500", "\u2502"
TL, TR, BL, BR = "\u250c", "\u2510", "\u2514", "\u2518"
TEEL, TEER = "\u251c", "\u2524"

BUILT_STAMP = "2026-10-30 00:54 CET"
BUILT_AUTHOR = "Qwen 3.8 Flash (xhigh thinking)"
BUILT_LINE = f"built {BUILT_STAMP} \u00b7 {BUILT_AUTHOR}"

UP, DOWN, LEFT, RIGHT = "up", "down", "left", "right"
VECTORS = {UP: (0, -1), DOWN: (0, 1), LEFT: (-1, 0), RIGHT: (1, 0)}
KEY_DIRS = {                       # arrows are produced as 'up'/'down'/... tokens
    UP: UP, "w": UP, "k": UP,
    DOWN: DOWN, "s": DOWN, "j": DOWN,
    LEFT: LEFT, "a": LEFT, "h": LEFT,
    RIGHT: RIGHT, "d": RIGHT, "l": RIGHT,
}
QUIT_KEYS = frozenset({"q", "Q", "ctrl-c", "ctrl-d", "esc"})

# -----------------------------------------------------------------------------
# ANSI helpers
# -----------------------------------------------------------------------------
ESC = "\x1b"
SGR_RE = re.compile(r"\x1b\[[0-9;]*m")
# Same pattern, but capturing: re.split keeps the delimiters so embedded colour
# codes survive the tokenisation.
SGR_SPLIT_RE = re.compile(r"(\x1b\[[0-9;]*m)")


def color_supported() -> bool:
    """Colour is a nicety: stay readable under TERM=dumb / NO_COLOR."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return sys.stdout.isatty()


USE_COLOR = color_supported()


def sgr(*codes) -> str:
    return ("\x1b[" + ";".join(str(c) for c in codes) + "m") if USE_COLOR else ""


RESET = sgr(0)
BOLD = sgr(1)
DIM = sgr(2)
BLINK = sgr(5)
REVERSE = sgr(7)
ITALIC = sgr(3)


def fg(n: int) -> str:
    """256-colour foreground: broader support than truecolor."""
    return sgr("38;5;", n) if USE_COLOR else ""


def bg(n: int) -> str:
    return sgr("48;5;", n) if USE_COLOR else ""


def _cube(v: int) -> int:
    return max(0, min(5, int(round(v * 5 / 255.0))))


def rgb_to_256(r, g, b) -> int:
    """Nearest colour on the 6x6x6 cube: 16 + 36*r + 6*g + b."""
    return 16 + 36 * _cube(r) + 6 * _cube(g) + _cube(b)


NEON_STOPS = [(0, 255, 255), (70, 110, 255), (160, 40, 255), (255, 30, 215)]


def neon(index: int, length: int) -> str:
    """Head-to-tail neon ramp; index 0 is the head.  (stretch: ghost trail)"""
    if not USE_COLOR:
        return ""
    if length <= 1:
        return fg(rgb_to_256(*NEON_STOPS[0]))
    t = min(1.0, index / (length - 1))
    span = t * (len(NEON_STOPS) - 1)
    k = min(len(NEON_STOPS) - 2, int(span))
    frac = span - k
    a, b = NEON_STOPS[k], NEON_STOPS[k + 1]
    col = tuple(int(round(x + (y - x) * frac)) for x, y in zip(a, b))
    return fg(rgb_to_256(*col))


def palette_for(mode: str) -> dict:
    """Arena colours differ so the active mode is obvious at a glance."""
    if mode == "wrap":
        return {"border": fg(46), "accent": fg(226), "hud": fg(85), "label": "WRAP"}
    return {"border": fg(39), "accent": fg(201), "hud": fg(51), "label": "CLASSIC"}


# -----------------------------------------------------------------------------
# Terminal ownership
# -----------------------------------------------------------------------------
class Terminal:
    """Alternate screen + cbreak input, restored on every exit path."""

    def __init__(self, stream=None):
        self.stream = stream if stream is not None else sys.stdout
        self.out_fd = self.stream.fileno()
        self.in_fd = sys.stdin.fileno()
        self._saved_attrs = None
        self._in_alt_screen = False
        self._closed = False
        self.interrupted = False

    # -- signals -----------------------------------------------------------
    def install_signal_handlers(self):
        signal.signal(signal.SIGINT, self._on_signal)
        signal.signal(signal.SIGTERM, self._on_signal)
        signal.signal(signal.SIGHUP, self._on_signal)

    def _on_signal(self, signum, frame):
        # cbreak keeps ISIG enabled, so Ctrl+C arrives here as a real SIGINT.
        # Flag it and let the frame loops unwind into `finally`.
        self.interrupted = True

    # -- enter / leave -----------------------------------------------------
    def enter(self):
        try:
            self._saved_attrs = termios.tcgetattr(self.in_fd)
            # setcbreak: ECHO/ICANON off, VMIN=1/VTIME=0 - but ISIG stays ON,
            # so Ctrl+C really delivers SIGINT to our handler (req. 8).  We
            # additionally switch off IXON so Ctrl-S cannot stall the renderer.
            tty.setcbreak(self.in_fd, termios.TCSANOW)
            mode = termios.tcgetattr(self.in_fd)
            mode[0] &= ~termios.IXON
            mode[3] &= ~termios.IEXTEN
            termios.tcsetattr(self.in_fd, termios.TCSANOW, mode)
        except (termios.error, OSError, ValueError):
            self._saved_attrs = None
        self._write(ESC + "[?1049h"          # alternate screen buffer
                    + ESC + "[r"             # reset scroll region to full size
                    + ESC + "[?25l"          # hide the cursor
                    + ESC + "[0m"            # reset attributes
                    + ESC + "[2J")           # clear once
        self._in_alt_screen = True
        self.flush()

    def close(self):
        """Idempotent teardown: cursor, colours, alt screen, termios."""
        if self._closed:
            return
        self._closed = True
        try:
            self._write(ESC + "[0m" + ESC + "[?25h" + ESC + "[?1049l" + ESC + "[0m")
            self.flush()
        except Exception:
            pass
        try:
            sys.stdout.flush()
        except Exception:
            pass
        if self._saved_attrs is not None:
            try:
                termios.tcsetattr(self.in_fd, termios.TCSAFLUSH, self._saved_attrs)
            except Exception:
                pass

    # -- output ------------------------------------------------------------
    def _write(self, text: str):
        raw = getattr(self.stream, "buffer", None)
        data = text.encode("utf-8", "replace")
        if raw is not None:
            raw.write(data)                 # always UTF-8 to the tty
        else:
            self.stream.write(text)

    def flush(self):
        try:
            raw = getattr(self.stream, "buffer", None)
            (raw or self.stream).flush()
        except Exception:
            pass

    def draw(self, frame: str):
        """One frame = one write = no flicker, no tearing."""
        self._write(frame)
        self.flush()

    # -- geometry ----------------------------------------------------------
    def size(self):
        cols = rows = 0
        try:
            import fcntl
            import struct
            packed = fcntl.ioctl(self.out_fd, termios.TIOCGWINSZ, b"\0" * 8)
            rows, cols = struct.unpack("HHHH", packed)[:2]
        except Exception:
            pass
        if not cols or not rows:
            guess = shutil.get_terminal_size()
            cols, rows = guess.columns, guess.lines
        return max(1, int(cols)), max(1, int(rows))

    # -- non-blocking input ------------------------------------------------
    def poll(self, timeout: float, inbuf: str):
        """Read whatever keys are available within `timeout`. -> (keys, inbuf)"""
        keys = []
        end = time.monotonic() + max(0.0, timeout)
        while True:
            remaining = end - time.monotonic()
            if remaining < 0:
                remaining = 0.0
            try:
                ready = select.select([self.in_fd], [], [], remaining)[0]
            except (OSError, ValueError):
                ready = []
            if not ready:
                break
            try:
                chunk = os.read(self.in_fd, 256)
            except OSError:
                break
            if not chunk:                       # stdin hit EOF
                keys.append("ctrl-d")
                break
            inbuf += chunk.decode("utf-8", "replace")
            got, inbuf = consume_keys(inbuf)
            keys.extend(got)
            if remaining > 0:
                continue                        # drain everything pending
        if inbuf == ESC:                        # a lone, finished Escape press
            inbuf = ""
            keys.append("esc")
        if self.interrupted:
            if "ctrl-c" not in keys:
                keys.append("ctrl-c")
        return keys, inbuf


CSI_KEYS = {"A": UP, "B": DOWN, "C": RIGHT, "D": LEFT, "H": "home", "F": "end"}
SS3_KEYS = {"A": UP, "B": DOWN, "C": RIGHT, "D": LEFT, "P": "unknown"}
TILDE_KEYS = {"1": "home", "2": "insert", "3": "backspace", "4": "end",
              "5": "pgup", "6": "pgdn", "7": "home", "8": "end"}


def consume_keys(buf: str):
    """Split a raw input buffer into key tokens; incomplete sequences stay
    buffered so the next poll can finish them.  -> (tokens, remainder)"""
    out = []
    i, n = 0, len(buf)
    while i < n:
        ch = buf[i]
        if ch == ESC:
            if i + 1 >= n:
                break                           # lone ESC: wait for a follow-up
            nxt = buf[i + 1]
            if nxt == "O":
                if i + 2 >= n:
                    break
                out.append(SS3_KEYS.get(buf[i + 2], "unknown"))
                i += 3
                continue
            if nxt == "[":
                j = i + 2
                params = ""
                while j < n and (buf[j].isdigit() or buf[j] in "?;<>"):
                    params += buf[j]
                    j += 1
                if j >= n:
                    break                       # incomplete CSI
                final = buf[j]
                if params and final == "M":       # mouse report: skip 2 more
                    i = min(n, j + 3)
                    continue
                if final in CSI_KEYS and not params:
                    out.append(CSI_KEYS[final])
                elif final == "~":
                    out.append(TILDE_KEYS.get(params, "unknown"))
                elif final in "m":                # device status reply
                    pass
                else:
                    out.append("unknown")
                i = j + 1
                continue
            out.append("esc")                   # Alt+<char>: Escape, then char
            i += 1
            continue
        if ch in ("\r", "\n"):
            out.append("enter")
        elif ch in ("\x7f", "\b"):
            out.append("backspace")
        elif ch == "\x03":
            out.append("ctrl-c")
        elif ch == "\x04":
            out.append("ctrl-d")
        elif ch == "\x1a":
            out.append("ctrl-z")
        elif ord(ch) < 0x20:
            pass                                # ignore other control bytes
        else:
            out.append(ch)
        i += 1
    return out, buf[i:]


# -----------------------------------------------------------------------------
# Frame buffer - full redraw every frame, so nothing lingers and nothing wraps
# -----------------------------------------------------------------------------
class Buffer:
    def __init__(self, cols: int, rows: int):
        self.cols, self.rows = cols, rows
        self.clear()

    def clear(self):
        self.cells = [[[" ", ""] for _ in range(self.cols)] for _ in range(self.rows)]

    def _valid(self, x: int, y: int) -> bool:
        return 0 <= x < self.cols and 0 <= y < self.rows

    def put(self, x: int, y: int, text: str, style: str = "") -> int:
        """Draw text (embedded SGR codes are honoured); -> next column."""
        cx = x
        current = style
        for token in SGR_SPLIT_RE.split(text):
            if not token:
                continue
            if SGR_RE.fullmatch(token):
                current = token
                continue
            for ch in token:
                if self._valid(cx, y):
                    self.cells[y][cx] = [ch, current]
                cx += 1
        return cx

    def rich(self, x: int, y: int, parts) -> int:
        cx = x
        for text, style in parts:
            cx = self.put(cx, y, text, style)
        return cx

    def center(self, y: int, content, style: str = "", x0: int = 0, width: int = None):
        """Center a plain string or a list of (text, style) parts."""
        width = width if width is not None else self.cols - x0
        if isinstance(content, str):
            text = content
            if len(text) > width:
                text = text[: max(0, width - 1)] + "\u2026"
            x = x0 + max(0, (width - len(text)) // 2)
            return self.put(x, y, text, style)
        length = sum(len(t) for t, _ in content)
        if length > width:
            content = truncate_parts(content, width)
            length = width
        x = x0 + max(0, (width - length) // 2)
        return self.rich(x, y, content)

    def box(self, x: int, y: int, width: int, height: int, style: str = ""):
        if width < 2 or height < 2:
            return
        self.put(x, y, TL + HLINE * (width - 2) + TR, style)
        self.put(x, y + height - 1, BL + HLINE * (width - 2) + BR, style)
        for row in range(y + 1, y + height - 1):
            self.put(x, row, VLINE, style)
            self.put(x + width - 1, row, VLINE, style)

    def frame(self) -> str:
        """Whole-screen string.  Every line is anchored and cleared in place:
        no scrolling, no leftovers, and trailing blanks are trimmed to keep
        the frame small."""
        parts = [ESC + "[H", RESET]
        last_row = self.rows - 1
        for y in range(self.rows):
            row = self.cells[y]
            end = self.cols
            while end > 0 and row[end - 1][0] == " " and not row[end - 1][1]:
                end -= 1
            out = []
            current = ""
            for x in range(end):
                ch, style = row[x]
                if style != current:
                    out.append(style or RESET)
                    current = style
                out.append(ch)
            out.append(ESC + "[K")
            if y != last_row:
                out.append("\r\n")
            parts.append("".join(out))
        parts.append(RESET)
        return "".join(parts)


def truncate_parts(parts, width: int):
    """Trim (text, style) parts to at most `width` chars, marking the cut."""
    total = sum(len(t) for t, _ in parts)
    if total <= width:
        return list(parts)
    out = []
    used = 0
    limit = max(0, width - 1)               # reserve one cell for the ellipsis
    for text, style in parts:
        if used >= limit:
            break
        room = limit - used
        if len(text) <= room:
            out.append((text, style))
            used += len(text)
        else:
            out.append((text[:room], style))
            used = limit
            break
    out.append(("\u2026", DIM))
    return out


# -----------------------------------------------------------------------------
# Persistent high scores
# -----------------------------------------------------------------------------
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ALNUM_RE = re.compile(r"[^A-Z0-9]")
MODE_KEYS = {"classic": "scores", "wrap": "wrap_scores"}


def score_path_for(script: str) -> str:
    """snake_scores.json always lives next to the script (req. 7)."""
    return os.path.join(os.path.dirname(os.path.abspath(script)), "snake_scores.json")


class ScoreStore:
    """Top-5 initials tables in snake_scores.json.

    missing file      -> empty table, no noise
    invalid JSON/data -> one-line warning, bad file preserved as .bak(.N),
                         fresh empty table; never a crash, never silent loss
    """

    def __init__(self, path: str = None):
        self.path = path or score_path_for(__file__)
        self.data = {"scores": [], "wrap_scores": []}
        self.warning = None
        self.load()

    # -- load --------------------------------------------------------------
    def load(self):
        self.data = {"scores": [], "wrap_scores": []}
        self.warning = None
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                raw = handle.read()
        except FileNotFoundError:
            return
        except (OSError, UnicodeDecodeError) as exc:
            note = exc.strerror if isinstance(exc, OSError) else "undecodable text"
            self.warning = f"warning: could not read {os.path.basename(self.path)} ({note})"
            return
        try:
            parsed = json.loads(raw)
        except ValueError:
            self._quarantine("not valid JSON")
            return
        shaped = self._shape(parsed)
        if shaped is None:
            self._quarantine("not a score table")
            return
        self.data = shaped

    def _quarantine(self, why: str):
        backup = self._backup_bad_file()
        self.data = {"scores": [], "wrap_scores": []}
        note = f"warning: {os.path.basename(self.path)} was {why}"
        note += " - " + (f"kept as {os.path.basename(backup)}"
                         if backup else "left untouched")
        note += ", starting fresh"
        self.warning = note

    def _backup_bad_file(self):
        """Move the unreadable file aside so nothing is lost, then start over."""
        base = self.path + ".bak"
        target, index = base, 1
        while os.path.exists(target):
            target, index = f"{base}.{index}", index + 1
        try:
            os.replace(self.path, target)
            return target
        except OSError:
            try:
                shutil.copyfile(self.path, target)
                return target
            except OSError:
                return None

    def _shape(self, parsed):
        """Normalise + validate; None means the whole file is unusable."""
        if isinstance(parsed, list):
            parsed = {"scores": parsed}
        if not isinstance(parsed, dict):
            return None
        if "scores" in parsed and not isinstance(parsed["scores"], list):
            return None
        out = {}
        for key in MODE_KEYS.values():
            entries = parsed.get(key)
            if entries is None:
                entries = []
            if not isinstance(entries, list):
                entries = []
            clean = []
            for entry in entries:
                fixed = self._sanitize(entry)
                if fixed is not None:
                    clean.append(fixed)
            out[key] = sorted(clean, key=lambda e: -e["score"])[:TOP_N]
        for key, value in parsed.items():            # keep unrelated user keys
            if key not in MODE_KEYS.values():
                out[key] = value
        return out

    @staticmethod
    def _sanitize(entry):
        if not isinstance(entry, dict):
            return None
        raw_score = entry.get("score")
        if isinstance(raw_score, bool):
            return None
        try:
            score = int(raw_score)
        except (TypeError, ValueError):
            return None
        initials = ALNUM_RE.sub("", str(entry.get("initials", "")).upper())[:INITIALS_LEN]
        if not initials:
            initials = "AAA"
        date = str(entry.get("date", ""))
        if not DATE_RE.match(date):
            date = datetime.date.today().isoformat()
        return {"initials": initials, "score": max(0, score), "date": date}

    # -- save --------------------------------------------------------------
    def table(self, mode: str):
        return self.data.setdefault(MODE_KEYS[mode], [])

    def best(self, mode: str) -> int:
        table = self.table(mode)
        return table[0]["score"] if table else 0

    def qualifies(self, mode: str, score: int) -> bool:
        if score <= 0:
            return False
        table = self.table(mode)
        if len(table) < TOP_N:
            return True
        return score > table[-1]["score"]

    def rank_after(self, mode: str, score: int) -> int:
        return 1 + sum(1 for e in self.table(mode) if e["score"] > score)

    def record(self, mode: str, initials: str, score: int):
        entry = {"initials": (ALNUM_RE.sub("", initials.upper())[:INITIALS_LEN]
                              or "AAA"),
                 "score": int(score),
                 "date": datetime.date.today().isoformat()}
        table = self.table(mode)
        index = len(table)
        for pos, existing in enumerate(table):       # ties keep the veteran first
            if existing["score"] < entry["score"]:
                index = pos
                break
        table.insert(index, entry)
        self.data[MODE_KEYS[mode]] = table[:TOP_N]
        self.save()
        return entry

    def save(self) -> bool:
        directory = os.path.dirname(self.path) or "."
        tmp = os.path.join(directory, ".snake_scores.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(self.data, indent=2) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.path)               # atomic: no half-written table
            return True
        except OSError as exc:
            self.warning = f"warning: could not save scores ({exc.strerror})"
            try:
                os.unlink(tmp)
            except OSError:
                pass
            return False

    def table_parts(self, mode: str, pal: dict):
        """List of (text, style) rows for the start screen, ready to centre."""
        table = self.table(mode)
        rows = []
        for pos, entry in enumerate(table, start=1):
            rows.append([
                (f"  {pos}. ", DIM + pal["border"]),
                (f"{entry['initials']:<{INITIALS_LEN}}", BOLD + pal["accent"]),
                ("  ", ""),
                (f"{entry['score']:>5}", BOLD + pal["hud"]),
                ("  ", ""),
                (entry["date"], DIM + fg(245)),
            ])
        return rows


# -----------------------------------------------------------------------------
# Game model (pure logic: no I/O, so it is unit-testable headlessly)
# -----------------------------------------------------------------------------
class Snake:
    """Bordered playfield: movement, growth, collisions, speed ramp."""

    def __init__(self, width: int = None, height: int = None, mode: str = "classic",
                 rng: random.Random = None):
        width = width if width is not None else MIN_INNER_W
        height = height if height is not None else MIN_INNER_H
        self.width, self.height = width, height
        self.mode = mode
        self.wrap = mode == "wrap"
        self.rng = rng if rng is not None else random.Random()
        self.reset()

    def reset(self):
        cx, cy = self.width // 2, self.height // 2
        self.body = [(cx - i, cy) for i in range(START_LENGTH)]   # head first
        self.direction = VECTORS[RIGHT]          # movement is stored as (dx, dy)
        self.pending = []
        self.alive = True
        self.score = 0
        self.eaten = 0
        self.death_reason = None
        self.food = None
        self.bonus = None                  # (x, y, expires_at_run_seconds)
        self.next_bonus_at = BONUS_PERIOD_S
        self.spawn_food()

    # -- speed ramp --------------------------------------------------------
    @property
    def tick_ms(self) -> int:
        return max(TICK_MIN_MS, TICK_START_MS - TICK_STEP_MS * self.eaten)

    @property
    def level(self) -> int:
        """HUD speed level: one per food eaten, floored at LV 1."""
        return max(1, self.eaten)

    # -- board -------------------------------------------------------------
    def occupied(self) -> set:
        """Every cell something already sits on (snake, food, star)."""
        taken = set(self.body)
        if self.food is not None:
            taken.add(self.food)
        if self.bonus is not None:
            taken.add((self.bonus[0], self.bonus[1]))
        return taken

    def free_cells(self) -> list:
        taken = self.occupied()
        return [(x, y) for y in range(self.height) for x in range(self.width)
                if (x, y) not in taken]

    def spawn_food(self) -> bool:
        free = self.free_cells()
        if not free:
            self.food = None
            return False
        self.food = self.rng.choice(free)          # never on the snake or the star
        return True

    # -- input -------------------------------------------------------------
    def queue_direction(self, key) -> bool:
        """Buffer a steering key.  Reversals into the neck are ignored."""
        name = KEY_DIRS.get(key)
        if name is None:
            return False
        want = VECTORS[name]
        last_name = self.pending[-1] if self.pending else self.direction
        last = last_name if isinstance(last_name, tuple) else VECTORS[last_name]
        if want == last:
            return False
        if (want[0] + last[0], want[1] + last[1]) == (0, 0):
            return False                           # 180 degrees: refuse
        if len(self.pending) >= 3:
            return False
        self.pending.append(want)
        return True

    # -- one tick ----------------------------------------------------------
    def step(self) -> str:
        if not self.alive:
            return "dead"
        while self.pending:
            candidate = self.pending.pop(0)
            if candidate == self.direction:
                continue
            if (candidate[0] + self.direction[0],
                    candidate[1] + self.direction[1]) == (0, 0):
                continue                           # reversal at tick time too
            self.direction = candidate
            break

        head_x, head_y = self.body[0]
        nx = head_x + self.direction[0]
        ny = head_y + self.direction[1]
        if self.wrap:
            nx %= self.width
            ny %= self.height
        elif not (0 <= nx < self.width and 0 <= ny < self.height):
            self.alive = False
            self.death_reason = "hit the wall"
            return "dead"

        eats_food = self.food is not None and (nx, ny) == self.food
        eats_bonus = (self.bonus is not None
                      and (nx, ny) == (self.bonus[0], self.bonus[1]))

        # The tail cell is vacated this tick unless we grow, so tail-following
        # is legal - that is what makes tight spirals feel fair.
        blocked = self.body if eats_food else self.body[:-1]
        if (nx, ny) in blocked:
            self.alive = False
            self.death_reason = "bit itself"
            return "dead"

        self.body.insert(0, (nx, ny))
        event = "moved"
        if eats_food:
            self.score += FOOD_POINTS
            self.eaten += 1
            event = "ate"
            if not self.spawn_food():
                if eats_bonus:
                    self.bonus = None
                    self.score += BONUS_POINTS
                self.alive = False
                self.death_reason = "the arena is full"
                return "win"
        else:
            self.body.pop()

        if eats_bonus:
            self.bonus = None
            self.score += BONUS_POINTS
            event = "bonus"
        return event

    # -- bonus fruit (stretch) ---------------------------------------------
    def update_bonus(self, run_seconds: float):
        if self.bonus is not None:
            if run_seconds >= self.bonus[2]:
                self.bonus = None
                self.next_bonus_at = run_seconds + BONUS_PERIOD_S
            return
        if self.alive and run_seconds >= self.next_bonus_at:
            free = self.free_cells()
            if free:
                spot = self.rng.choice(free)
                self.bonus = (spot[0], spot[1], run_seconds + BONUS_LIFETIME_S)
                self.next_bonus_at = run_seconds + BONUS_PERIOD_S

    def bonus_left(self, run_seconds: float) -> float:
        if self.bonus is None:
            return 0.0
        return max(0.0, self.bonus[2] - run_seconds)


# -----------------------------------------------------------------------------
# Application: layout, screens, frame loop
# -----------------------------------------------------------------------------
class App:
    IDLE_POLL = 0.035            # keeps blink animation + input responsive

    def __init__(self, term: Terminal, store: ScoreStore):
        self.term = term
        self.store = store
        self.cols, self.rows = term.size()
        self.buf = Buffer(self.cols, self.rows)
        self.inbuf = ""
        self.mode = "classic"
        self.palette = palette_for(self.mode)
        self.tick_count = 0
        self.last_frame = ""
        self.snake = None
        self.lay = {}
        self.too_small = False
        self.size_changed = False

    # -- helpers -----------------------------------------------------------
    def wait(self, timeout=None):
        if self.term.interrupted:
            return ["ctrl-c"]
        keys, self.inbuf = self.term.poll(
            timeout if timeout is not None else self.IDLE_POLL, self.inbuf)
        return keys

    def drain(self):
        """Forget held/repeated keys so a screen change cannot double-fire."""
        self.inbuf = ""
        self.term.poll(0.0, "")

    def quit_requested(self, keys) -> bool:
        return any(k in QUIT_KEYS for k in keys)

    def show(self):
        frame = self.buf.frame()
        if frame != self.last_frame:
            self.term.draw(frame)
            self.last_frame = frame

    def refresh_size(self) -> bool:
        """Re-measure the tty.  Returns True when it is now too small to draw.

        Cells outside the live size are dropped by Buffer, so a mid-run resize
        can never wrap a line or scroll the user's screen; the run simply ends
        and the shell comes back clean.
        """
        cols, rows = self.term.size()
        if (cols, rows) != (self.cols, self.rows):
            self.cols, self.rows = cols, rows
            self.buf = Buffer(cols, rows)
            self.last_frame = ""
            self.size_changed = True
        self.too_small = cols < MIN_COLS or rows < MIN_ROWS
        return self.too_small

    def blink(self, rate: float = 2.0) -> bool:
        return int(time.monotonic() * rate) % 2 == 0

    # -- layout ------------------------------------------------------------
    def layout(self):
        inner_w = max(MIN_INNER_W, min(self.cols - 2, MAX_INNER_W))
        inner_h = max(MIN_INNER_H, min(self.rows - 5, MAX_INNER_H))
        box_h = inner_h + 4                      # top + HUD + separator + bottom
        top = max(0, (self.rows - (box_h + 1)) // 2)
        left = max(0, (self.cols - (inner_w + 2)) // 2)
        return {
            "inner_w": inner_w, "inner_h": inner_h,
            "box_x": left, "box_y": top, "box_w": inner_w + 2,
            "field_x": left + 1, "field_y": top + 3,
            "bottom_y": top + 3 + inner_h,
            "hint_y": min(self.rows - 1, top + box_h + 1),
        }

    # ------------------------------------------------------------------
    # Start screen: title, saved table, sign-off footer
    # ------------------------------------------------------------------
    def start_screen(self) -> str:
        self.drain()
        while True:
            if self.refresh_size() and self.too_small:
                return "quit"
            self.draw_start()
            self.show()
            keys = self.wait(0.09)
            if self.quit_requested(keys):
                return "quit"
            if "w" in keys or "W" in keys:
                self.mode = "wrap" if self.mode == "classic" else "classic"
                self.palette = palette_for(self.mode)
                continue
            if keys:
                self.drain()
                return "start"

    def draw_start(self):
        self.buf.clear()
        pal = self.palette
        footer_y = self.rows - 1               # sign-off, always bottom line
        press_y = self.rows - 2                # "press any key", always above it
        y = max(1, (press_y - 11) // 2)        # centre the block above them

        def emit(content, style=""):
            nonlocal y
            if y < press_y:
                self.buf.center(y, content, style)
            y += 1

        def emit_gap():
            nonlocal y
            y += 1

        title = [("\u2588", BOLD + pal["accent"]),
                 (" NEON SERPENT ", BOLD + pal["hud"]),
                 ("\u2588", BOLD + pal["accent"])]
        emit(title)
        emit("t e r m i n a l   s n a k e", DIM + fg(45))
        emit("pure ANSI \u00b7 no curses \u00b7 stdlib only", DIM + fg(245))
        emit_gap()
        deco = HLINE * 3
        emit([(deco + "  ", DIM + pal["border"]),
              (f"TOP {TOP_N} \u00b7 {pal['label']} ARENA", BOLD + pal["accent"]),
              ("  " + deco, DIM + pal["border"])])
        table = self.store.table_parts(self.mode, pal)
        if table:
            for parts in table:
                emit(parts)
        else:
            emit("no scores yet \u2014 be the first", ITALIC + fg(245))
        if self.store.warning:                 # one-line warning (req. 7)
            emit("! " + self.store.warning, BOLD + fg(214))
            emit("the old file was preserved \u2014 the game still plays",
                 DIM + fg(214))
        emit_gap()
        if self.cols >= 56:
            emit([("\u2191\u2193\u2190\u2192 / wasd", fg(141)), (" move \u00b7 ", DIM),
                  ("p", fg(141)), (" pause \u00b7 ", DIM),
                  ("q", fg(141)), (" quit \u00b7 ", DIM),
                  ("w", fg(141)), (f" arena: {pal['label']}", DIM)])
        else:                              # 40 chars: fits the smallest tty
            emit([("\u2191\u2193\u2190\u2192/wasd", fg(141)), (" \u00b7 ", DIM),
                  ("p", fg(141)), (" pause", DIM), (" \u00b7 ", DIM),
                  ("q", fg(141)), (" quit", DIM),
                  (" \u00b7 w:", fg(141)), (pal["label"], DIM + fg(141))])
        if y < press_y - 1:
            emit("every food: +10 pts \u00b7 tick -7 ms (floor 60 ms)",
                 DIM + fg(245))
        pulse = BLINK if self.blink(2.0) else ""
        self.buf.center(press_y, "press any key to start", BOLD + fg(226) + pulse)
        if self.cols >= len(BUILT_LINE):
            self.buf.center(footer_y, BUILT_LINE, DIM + fg(244))
        else:                       # narrow tty: keep the whole sign-off visible
            self.buf.center(footer_y - 1 if footer_y - 1 < press_y else
                            press_y - 1, f"built {BUILT_STAMP}", DIM + fg(244))
            self.buf.center(footer_y, BUILT_AUTHOR, DIM + fg(244))

    # ------------------------------------------------------------------
    # Gameplay
    # ------------------------------------------------------------------
    def play(self):
        """One run.  -> ('quit', None) | ('done', info)

        All timing comes from time.monotonic().  `run_seconds` is game time:
        paused wall-clock is subtracted, and the tick schedule is rebuilt after
        a resume so neither input nor the clock ever has to "catch up".
        """
        lay = self.layout()
        snake = Snake(lay["inner_w"], lay["inner_h"], self.mode)
        self.snake, self.lay = snake, lay
        pal = self.palette

        run_start = time.monotonic()
        paused_total = 0.0
        next_step = run_start + snake.tick_ms / 1000.0
        death_at = None
        dirty = True
        last_blink = None
        last_bonus = snake.bonus is not None

        def game_time():
            return time.monotonic() - run_start - paused_total

        while True:
            if self.refresh_size():                  # shrunk below the minimum
                return "quit", None
            now = time.monotonic()
            wait_for = self.IDLE_POLL
            if snake.alive:
                wait_for = max(0.0, next_step - now)
            elif death_at is not None:
                wait_for = max(0.0, death_at - now)
            keys = self.wait(wait_for)
            if self.quit_requested(keys):
                return "quit", None

            for key in keys:
                if key in ("p", "P") and snake.alive:
                    outcome, pause_start = self.paused(snake, lay, pal, game_time)
                    if outcome == "quit":
                        return "quit", None
                    paused_total += time.monotonic() - pause_start
                    next_step = time.monotonic() + snake.tick_ms / 1000.0
                    dirty = True
                    break
                name = KEY_DIRS.get(key)
                if name:
                    if snake.queue_direction(name):
                        dirty = True

            if snake.alive:
                guard = 0
                while time.monotonic() >= next_step and guard < 8:
                    event = snake.step()
                    guard += 1
                    dirty = True                      # every move redraws
                    if event in ("dead", "win"):
                        death_at = time.monotonic() + 0.45
                        break
                    next_step += snake.tick_ms / 1000.0
                if guard and snake.alive and next_step <= time.monotonic():
                    next_step = time.monotonic() + snake.tick_ms / 1000.0
                if snake.alive:
                    snake.update_bonus(game_time())

            elapsed = game_time()
            if death_at is not None and time.monotonic() >= death_at:
                return "done", {"score": snake.score, "eaten": snake.eaten,
                                "reason": snake.death_reason or "hit the wall",
                                "seconds": elapsed, "length": len(snake.body),
                                "mode": snake.mode}

            blink = self.blink(2.0)
            bonus_now = snake.bonus is not None
            if blink != last_blink or bonus_now != last_bonus or self.size_changed:
                last_blink, last_bonus = blink, bonus_now
                self.size_changed = False
                dirty = True
            self.tick_count += 1

            if dirty:
                self.render_play(snake, lay, pal, elapsed, blink)
                self.show()
                dirty = False

    def render_play(self, snake: Snake, lay, pal, run_seconds: float, blink: bool):
        self.buf.clear()
        box_x, box_y = lay["box_x"], lay["box_y"]
        inner_w, inner_h = lay["inner_w"], lay["inner_h"]
        flash = not snake.alive
        border = (BOLD + fg(196)) if flash else (BOLD + pal["border"])

        # ---- frame -----------------------------------------------------
        self.buf.put(box_x, box_y, TL + HLINE * inner_w + TR, border)
        hud_y = box_y + 1
        self.buf.put(box_x, hud_y, VLINE, border)
        self.buf.put(box_x + inner_w + 1, hud_y, VLINE, border)
        sep_y = box_y + 2
        self.buf.put(box_x, sep_y, TEEL + HLINE * inner_w + TEER, border)
        self.buf.put(box_x, lay["bottom_y"], BL + HLINE * inner_w + BR, border)

        # ---- HUD -------------------------------------------------------
        best = max(self.store.best(self.mode), snake.score)
        hud = [("  SCORE", DIM + pal["hud"]), (f" {snake.score:04d}", BOLD + pal["hud"]),
               ("   BEST", DIM + pal["hud"]), (f" {best:04d}", pal["hud"]),
               ("   LV", DIM + pal["accent"]),
               (f" {snake.level}", BOLD + pal["accent"])]
        if inner_w >= 42:                    # ms readout only when there is room
            hud.append((f" \u00b7 {snake.tick_ms}ms", DIM + pal["accent"]))
        if snake.mode == "wrap":
            hud.append(("   WRAP", BOLD + fg(46)))
        if snake.bonus:
            left = snake.bonus_left(run_seconds)
            mark = BLINK if left <= 2.5 and blink else ""
            hud.append((f"   {BONUS_GLYPH} {int(left + 0.999)}s", BOLD + fg(226) + mark))
        self.buf.rich(box_x + 1, hud_y, truncate_parts(hud, inner_w))

        # ---- field -----------------------------------------------------
        field_x, field_y = lay["field_x"], lay["field_y"]
        dot = (GRID_GLYPH, DIM + fg(236)) if USE_COLOR else (" ", "")
        for row in range(inner_h):
            ry = field_y + row
            if ry >= self.buf.rows:               # tty shrank mid-run: clamp
                break
            cells = self.buf.cells[ry]
            base = field_x
            for col in range(inner_w):
                if base + col < self.buf.cols:
                    cells[base + col] = list(dot)

        if snake.food:
            fx, fy = snake.food
            pulse = fg(203) if blink else fg(197)
            self.buf.put(field_x + fx, field_y + fy, FOOD_GLYPH, BOLD + pulse)

        if snake.bonus:
            bx, by, _expires = snake.bonus
            left = snake.bonus_left(run_seconds)
            mark = BLINK if left <= 2.5 and blink else ""
            self.buf.put(field_x + bx, field_y + by, BONUS_GLYPH,
                         BOLD + fg(226) + mark)

        body = snake.body
        length = len(body)
        for index in range(length - 1, -1, -1):        # tail first, head on top
            x, y = body[index]
            depth = index / max(1, length - 1)
            if index == 0:
                glyph = SNAKE_HEAD
                style = BOLD + (fg(231) + bg(38) if not flash else fg(231) + bg(1))
            else:
                glyph = FADE_GLYPHS[min(len(FADE_GLYPHS) - 1, int(depth * 4))]
                style = neon(index, length) + (DIM if depth > 0.8 else "")
                if flash:
                    style = BOLD + fg(231) + bg(1)
            self.buf.put(field_x + x, field_y + y, glyph, style)

        hint = "arrows / WASD move \u00b7 p pause \u00b7 q quit"
        if snake.mode == "wrap":
            hint += " \u00b7 wrap arena, no walls"
        self.buf.center(lay["hint_y"], hint, DIM)

    # ------------------------------------------------------------------
    # Pause: the board freezes, PAUSED blinks, input still steers ahead
    # ------------------------------------------------------------------
    def paused(self, snake: Snake, lay, pal, game_time):
        """Returns ('resume'|'quit', pause_start_monotonic)."""
        self.drain()                           # drop key repeats from the 'p'
        pause_start = time.monotonic()
        frozen_time = game_time()          # game clock stops while paused
        while True:
            self.refresh_size()          # a resize while paused stays in-bounds
            self.buf.clear()
            self.render_play(snake, lay, pal, frozen_time, self.blink(2.0))
            banner = [("PAUSED", BOLD + fg(226) + (BLINK if self.blink(2.0) else ""))]
            self.draw_panel([banner, [("press p to resume", DIM + fg(245))]], lay)
            self.buf.center(lay["hint_y"], "p resume \u00b7 q quit", DIM)
            self.show()
            keys = self.wait(0.1)
            if self.quit_requested(keys):
                return "quit", pause_start
            for key in keys:
                if key in ("p", "P"):
                    self.drain()
                    return "resume", pause_start
                name = KEY_DIRS.get(key)
                if name:
                    snake.queue_direction(name)

    # ------------------------------------------------------------------
    # Game over: final score, initials entry when it makes the top 5
    # ------------------------------------------------------------------
    def game_over(self, info) -> str:
        """-> 'restart' | 'quit'"""
        snake, lay, pal = self.snake, self.lay, self.palette
        score = info["score"]
        qualifies = self.store.qualifies(self.mode, score)
        rank = self.store.rank_after(self.mode, score) if qualifies else None
        initials = list("AAA")
        cursor = 0
        saved = None
        editing = qualifies                 # prompt first, then settle down

        while True:
            self.refresh_size()          # keep the overlay inside the live tty
            self.buf.clear()
            self.render_play(snake, lay, pal, info["seconds"], self.blink(2.0))
            won = info["reason"] == "the arena is full"
            lines = [
                [("PERFECT! ARENA FULL" if won else "GAME OVER",
                  BOLD + (fg(46) if won else fg(196)))],
                [(info["reason"].upper() if not won else "YOU FILLED THE ARENA",
                  DIM + fg(231))],
                [(f"SCORE {score:04d}", BOLD + fg(51)),
                 (f"   {info['eaten']} food \u00b7 LV {max(1, info['eaten'])}"
                  f" \u00b7 len {info['length']} \u00b7 {info['seconds']:.1f}s", DIM)],
            ]
            if qualifies:
                if saved:
                    lines.append([(f"saved  {saved['initials']}  {score:04d}  "
                                   f"{saved['date']}   (# {rank})", BOLD + fg(46))])
                else:
                    lines.append([("NEW BEST!" if rank == 1
                                   else f"MAKES TOP {TOP_N}  (# {rank})",
                                   BOLD + fg(226))])
                    lines.append(self.initials_row(initials, cursor))
                    lines.append([("type A\u2013Z 0\u20139 \u00b7 \u2190 / bs move"
                                   " \u00b7 enter save \u00b7 q skip", DIM + fg(245))])
            else:
                lines.append([(f"best {self.store.best(self.mode):04d} \u00b7 "
                               f"not a top-{TOP_N} score", DIM + fg(245))])
            lines.append([("r restart \u00b7 q quit", DIM + fg(141))])
            self.draw_panel(lines, lay)
            self.show()

            keys = self.wait(0.1)
            if self.quit_requested(keys):
                return "quit"
            if editing:
                for key in keys:
                    if key == "enter":
                        entry = self.store.record(self.mode, "".join(initials), score)
                        saved = {"initials": entry["initials"],
                                 "date": entry["date"]}
                        editing = False
                        self.drain()
                        break
                    if key in ("left", "backspace"):
                        cursor = max(0, cursor - 1)
                        continue
                    if key == "right":
                        cursor = min(INITIALS_LEN - 1, cursor + 1)
                        continue
                    if len(key) == 1 and re.match(r"^[A-Za-z0-9]$", key):
                        initials[cursor] = key.upper()
                        if cursor < INITIALS_LEN - 1:
                            cursor += 1
                continue
            if any(k in ("r", "R", "enter") for k in keys):
                self.drain()
                return "restart"

    @staticmethod
    def initials_row(initials, cursor):
        """Three editable slots, the active one in reverse video."""
        row = []
        for index, ch in enumerate(initials):
            style = BOLD + fg(226) + (REVERSE if index == cursor else "")
            row.append((f"[{ch}]", style))
            if index != INITIALS_LEN - 1:
                row.append((" ", DIM))
        return row

    # ------------------------------------------------------------------
    # Overlays
    # ------------------------------------------------------------------
    def draw_panel(self, lines, lay):
        """Opaque centred panel over the frozen board."""
        width = max(sum(len(t) for t, _ in row) for row in lines) + 4
        width = min(max(width, 24), max(8, self.cols - 2))
        height = len(lines) + 2
        x = max(0, (self.cols - width) // 2)
        y = max(0, min(lay["field_y"] + lay["inner_h"] // 2 - height // 2,
                       self.rows - height))
        shade = bg(16) if USE_COLOR else ""
        for row in range(y, min(y + height, self.buf.rows)):   # fill a clean rect
            cells = self.buf.cells[row]
            for col in range(x, min(self.cols, x + width)):
                cells[col] = [" ", shade]
        self.buf.box(x, y, width, height, BOLD + fg(255) + (bg(16) if USE_COLOR else ""))
        row = y + 1
        for parts in lines:
            parts = [(t, style + shade) for t, style in truncate_parts(parts, width - 2)]
            self.buf.center(row, parts, x0=x + 1, width=width - 2)
            row += 1

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self) -> int:
        """Menu -> run -> game over -> (restart | menu | quit)."""
        while True:
            if self.start_screen() == "quit":
                return 0
            while True:
                outcome, info = self.play()
                if outcome == "quit":
                    return 0
                if self.game_over(info) == "quit":
                    return 0


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------
def main() -> int:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        sys.stderr.write("Neon Serpent needs a real POSIX terminal "
                         "(run it from a shell: python3 snake.py)\n")
        return 1

    term = Terminal()
    cols, rows = term.size()
    if cols < MIN_COLS or rows < MIN_ROWS:
        sys.stderr.write(
            f"Neon Serpent needs a terminal at least {MIN_COLS}x{MIN_ROWS} "
            f"characters - this one is {cols}x{rows}.\n"
            "Make the window bigger (or `stty rows 24 columns 80`) and run "
            "python3 snake.py again.\n")
        return 1

    store = ScoreStore()
    term.install_signal_handlers()
    try:
        term.enter()
        app = App(term, store)
        return app.run()
    except Exception:                       # req. 8: restore first, then crash
        term.close()
        raise
    finally:
        term.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:               # pragma: no cover - safety net
        sys.exit(0)
