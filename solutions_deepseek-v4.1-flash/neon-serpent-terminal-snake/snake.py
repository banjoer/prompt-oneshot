#!/usr/bin/env python3
# =============================================================================
#  NEON SERPENT - Terminal Snake
#  Built 2026-10-29 23:53 by DeepSeek V4.1 Flash (OpenCode)
#  Single file, Python 3 standard library only, raw ANSI escape codes.
#  No curses, no third-party packages, no external assets.
# =============================================================================
"""A neon snake game for a real POSIX terminal.

Run with:  python3 snake.py

The playfield is drawn in an alternate screen buffer with a hidden cursor.
All timing uses time.monotonic(); input is polled every frame with select().
"""

import json
import os
import random
import select
import shutil
import signal
import sys
import termios
import time
import tty
from datetime import datetime

# ---------------------------------------------------------------------------
# Sign-off
# ---------------------------------------------------------------------------
BUILT_AT = "2026-10-29 23:53"
AUTHOR = "DeepSeek V4.1 Flash"

SCORE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "snake_scores.json")
MIN_COLS, MIN_ROWS = 40, 20
START_TICK = 0.150
TICK_STEP = 0.007
MIN_TICK = 0.060

# ---------------------------------------------------------------------------
# ANSI
# ---------------------------------------------------------------------------
ESC = "\x1b["


def fg(n):
    return "\x1b[38;5;%dm" % n


RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
HOME = ESC + "H"
CLEAR = ESC + "2J"
ERASE_LINE = ESC + "K"
ERASE_DOWN = ESC + "J"
ALT_ON = ESC + "?1049h"
ALT_OFF = ESC + "?1049l"
CURSOR_HIDE = ESC + "?25l"
CURSOR_SHOW = ESC + "?25h"
SYNC_ON = ESC + "?2026h"
SYNC_OFF = ESC + "?2026l"

CYAN = fg(51)
BLUE = fg(45)
GREEN = fg(46)
MINT = fg(121)
MAGENTA = fg(201)
RED = fg(196)
YELLOW = fg(226)
WHITE = fg(231)
GREY = fg(244)

BORDER = BLUE
SNAKE_GRADIENT = (fg(46), fg(47), fg(48), fg(49), fg(50), fg(51),
                  fg(45), fg(39), fg(33), fg(27))
FOOD_STYLE = BOLD + fg(197)
HEAD_STYLE = BOLD + fg(231)
PAUSE_BG = "\x1b[48;5;17m"
HIGHLIGHT_BG = "\x1b[48;5;90m"

ARROW_KEYS = {
    b"\x1b[A": "UP", b"\x1b[B": "DOWN",
    b"\x1b[C": "RIGHT", b"\x1b[D": "LEFT",
    b"\x1bOA": "UP", b"\x1bOB": "DOWN",
    b"\x1bOC": "RIGHT", b"\x1bOD": "LEFT",
}

_QUIT = [False]


def _on_signal(signum, frame):
    _QUIT[0] = True


def term_size():
    try:
        size = os.get_terminal_size(sys.stdout.fileno())
        return size.columns, size.lines
    except (OSError, ValueError):
        return 80, 24


def _strip_ansi(text):
    """Return the printable width of a string containing ANSI SGR codes."""
    width = 0
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "\x1b" and i + 1 < n and text[i + 1] == "[":
            i += 2
            while i < n and not ("@" <= text[i] <= "~"):
                i += 1
            i += 1
            continue
        width += 1
        i += 1
    return width


def center_styled(text, width):
    """Centre an ANSI-styled line inside width printable columns."""
    n = _strip_ansi(text)
    if n >= width:
        return text
    left = (width - n) // 2
    return " " * left + text + " " * (width - n - left)


def hud_number(value):
    """Four-digit arcade formatting, compact for absurd hand-edited scores."""
    try:
        value = max(0, int(value))
    except (TypeError, ValueError):
        value = 0
    text = str(value)
    if len(text) > 6:
        return text[:5] + "+"
    return "%04d" % value


# ---------------------------------------------------------------------------
# High scores
# ---------------------------------------------------------------------------
def _backup_bad_scores():
    """Preserve a corrupt score file as snake_scores.json.bak."""
    bak = SCORE_PATH + ".bak"
    try:
        os.replace(SCORE_PATH, bak)
        return True
    except OSError:
        try:
            shutil.copy2(SCORE_PATH, bak)
            return True
        except OSError:
            return False


def _clean_initials(value):
    raw = str(value).upper()
    kept = "".join(ch for ch in raw
                   if ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
    return kept[:3] or "???"


def load_scores():
    """Load the top five. Returns (scores, warning-or-None)."""
    if not os.path.exists(SCORE_PATH):
        return [], None
    try:
        with open(SCORE_PATH, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
        if isinstance(raw, dict):
            entries = raw.get("scores")
        elif isinstance(raw, list):
            entries = raw
        else:
            raise ValueError("unexpected score file shape")
        if not isinstance(entries, list):
            raise ValueError("scores is not a list")

        scores = []
        for item in entries:
            if not isinstance(item, dict):
                continue
            try:
                score = int(item.get("score", 0))
            except (TypeError, ValueError):
                continue
            if score < 0:
                continue
            scores.append({
                "initials": _clean_initials(item.get("initials", "???")),
                "score": score,
                "date": str(item.get("date", ""))[:10],
            })
        scores.sort(key=lambda e: (-e["score"], e["date"], e["initials"]))
        return scores[:5], None
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        backed_up = _backup_bad_scores()
        if backed_up:
            warning = "! bad score file backed up to .bak"
        else:
            warning = "! bad score file not backed up"
        return [], warning


def save_scores(scores):
    """Atomically persist the top five. Returns a warning or None."""
    ordered = sorted(
        scores,
        key=lambda e: (-int(e.get("score", 0)),
                       str(e.get("date", "")),
                       str(e.get("initials", ""))),
    )
    payload = {"scores": ordered[:5]}
    tmp = SCORE_PATH + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(tmp, SCORE_PATH)
        return None
    except OSError:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        return "! could not save high scores"


# ---------------------------------------------------------------------------
# Terminal
# ---------------------------------------------------------------------------
class Terminal:
    def __init__(self):
        self.fd = sys.stdin.fileno()
        self.saved = None
        self.active = False
        self.buffer = b""

    def write(self, text):
        sys.stdout.write(text)
        sys.stdout.flush()

    def setup(self):
        self.saved = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        try:
            termios.tcflush(self.fd, termios.TCIFLUSH)
        except termios.error:
            pass
        self.active = True
        self.write(ALT_ON + CURSOR_HIDE + CLEAR + HOME)

    def restore(self):
        if self.active:
            try:
                self.write(SYNC_OFF + RESET + CURSOR_SHOW + ALT_OFF)
            except (OSError, ValueError):
                pass
        self.active = False
        if self.saved is not None:
            try:
                termios.tcsetattr(self.fd, termios.TCSANOW, self.saved)
            except (termios.error, OSError):
                pass
            self.saved = None

    def present(self, lines):
        """Draw a complete frame with no scrolling and no leftovers."""
        cols, rows = term_size()
        if len(lines) > rows:
            lines = lines[:rows]
        top = max(0, (rows - len(lines)) // 2)
        out = [SYNC_ON, HOME]
        for _ in range(top):
            out.append(ERASE_LINE + "\r\n")
        for idx, line in enumerate(lines):
            out.append(center_styled(line, cols))
            out.append(ERASE_LINE)
            if idx != len(lines) - 1:
                out.append("\r\n")
        out.append(RESET + ERASE_DOWN + SYNC_OFF)
        self.write("".join(out))

    def poll(self, timeout=0.01):
        keys = []
        try:
            ready, _, _ = select.select([self.fd], [], [], timeout)
        except (InterruptedError, OSError):
            ready = []
        if ready:
            try:
                data = os.read(self.fd, 1024)
            except OSError:
                data = b""
            if not data:
                keys.append("EOF")
            self.buffer += data
        self._parse(keys)
        return keys

    def _parse(self, keys):
        buf = self.buffer
        i = 0
        n = len(buf)
        while i < n:
            byte = buf[i]
            if byte == 0x1B:
                remaining = n - i
                if remaining == 1:
                    break  # wait: might be the start of an arrow sequence
                nxt = buf[i + 1]
                if remaining == 2 and nxt in (ord("["), ord("O")):
                    break
                if nxt == ord("[") and remaining >= 3:
                    seq = buf[i:i + 3]
                    if seq in ARROW_KEYS:
                        keys.append(ARROW_KEYS[seq])
                        i += 3
                        continue
                    # Unknown CSI: consume through its final byte.
                    j = i + 2
                    while j < n and not (0x40 <= buf[j] <= 0x7E):
                        j += 1
                    i = j + 1 if j < n else n
                    continue
                if nxt == ord("O") and remaining >= 3:
                    seq = buf[i:i + 3]
                    if seq in ARROW_KEYS:
                        keys.append(ARROW_KEYS[seq])
                        i += 3
                        continue
                    i += 3
                    continue
                i += 1  # lone ESC before an ordinary key
                continue
            if byte in (10, 13):
                keys.append("ENTER")
                i += 1
            elif byte in (8, 127):
                keys.append("BACKSPACE")
                i += 1
            elif byte == 9:
                keys.append("TAB")
                i += 1
            elif 32 <= byte < 127:
                keys.append(chr(byte))
                i += 1
            elif byte >= 0xC0:
                if byte < 0xE0:
                    i += 2
                elif byte < 0xF0:
                    i += 3
                else:
                    i += 4
            else:
                i += 1
        self.buffer = buf[i:]


# ---------------------------------------------------------------------------
# Game model
# ---------------------------------------------------------------------------
class Game:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.reset()

    def reset(self):
        cx, cy = self.width // 2, self.height // 2
        self.snake = [(cx, cy), (cx - 1, cy), (cx - 2, cy)]
        self.direction = (1, 0)
        self.queue = []
        self.score = 0
        self.eaten = 0
        self.dead = False
        self.won = False
        self.food = self._spawn_food()

    @property
    def level(self):
        # Four foods => LV 4, matching the sample HUD.
        return max(1, self.eaten)

    @property
    def interval(self):
        return max(MIN_TICK, START_TICK - TICK_STEP * self.eaten)

    def _spawn_food(self):
        occupied = set(self.snake)
        free = [(x, y) for y in range(self.height)
                for x in range(self.width) if (x, y) not in occupied]
        if not free:
            return None
        return random.choice(free)

    def turn(self, direction):
        """Queue a buffered turn. Reversals into the neck are ignored."""
        last = self.queue[-1] if self.queue else self.direction
        dx, dy = direction
        if (dx, dy) == (-last[0], -last[1]) or (dx, dy) == last:
            return False
        if len(self.queue) >= 2:
            return False
        self.queue.append(direction)
        return True

    def step(self):
        """Advance one tick. Returns 'move', 'wall', 'self' or 'win'."""
        if self.dead:
            return "dead"
        if self.queue:
            self.direction = self.queue.pop(0)

        hx, hy = self.snake[0]
        dx, dy = self.direction
        new_head = (hx + dx, hy + dy)
        growing = new_head == self.food

        nx, ny = new_head
        if nx < 0 or nx >= self.width or ny < 0 or ny >= self.height:
            self.dead = True
            return "wall"

        body = self.snake if growing else self.snake[:-1]
        if new_head in body:
            self.dead = True
            return "self"

        self.snake.insert(0, new_head)
        if growing:
            self.score += 10
            self.eaten += 1
            if len(self.snake) >= self.width * self.height:
                self.food = None
                self.dead = True
                self.won = True
                return "win"
            self.food = self._spawn_food()
            if self.food is None:
                self.dead = True
                self.won = True
                return "win"
        else:
            self.snake.pop()
        return "move"


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
class App:
    def __init__(self):
        self.term = Terminal()
        self.cols, self.rows = term_size()
        self.grid_w = max(30, min(48, self.cols - 4))
        self.grid_h = max(15, min(18, self.rows - 5))
        self.board_w = self.grid_w + 2
        self.board_h = self.grid_h + 4
        self.total_h = self.grid_h + 5

        self.scores, self.warning = load_scores()
        self.best = self.scores[0]["score"] if self.scores else 0
        self.game = None
        self.mode = "start"
        self.initials = ""
        self.final_score = 0
        self.final_level = 1
        self.new_rank = 0
        self.over_message = ""
        self.highlight = None
        self.small = False
        self.running = True
        self.needs_render = True
        self.next_tick = None
        self.blink = True
        self.last_blink = time.monotonic()

    # -- helpers ------------------------------------------------------------
    def _page_width(self):
        cols, _ = term_size()
        return min(48, max(38, cols - 2))

    def _footer_lines(self, width):
        single = "built %s · %s" % (BUILT_AT, AUTHOR)
        if _strip_ansi(single) <= width:
            return [center_styled(DIM + GREY + single + RESET, width)]
        return [
            center_styled(DIM + GREY + "built " + BUILT_AT + RESET, width),
            center_styled(DIM + GREY + AUTHOR + " · OpenCode" + RESET, width),
        ]

    def _score_table(self, width):
        inner = width - 2
        rows = [BORDER + "┌" + "─" * inner + "┐" + RESET]
        for rank in range(5):
            if rank < len(self.scores):
                entry = self.scores[rank]
                text = "  %d   %-3s    %6d    %-10s" % (
                    rank + 1, entry["initials"], entry["score"],
                    entry["date"])
                if len(text) < inner:
                    text += " " * (inner - len(text))
                else:
                    text = text[:inner]
                if entry is self.highlight:
                    style = BOLD + WHITE + HIGHLIGHT_BG
                else:
                    style = GREEN
                rows.append(BORDER + "│" + RESET + style + text + RESET
                            + BORDER + "│" + RESET)
            else:
                text = "  %d   %-3s    %6s    %-10s" % (
                    rank + 1, "---", "---", "----------")
                if len(text) < inner:
                    text += " " * (inner - len(text))
                rows.append(BORDER + "│" + RESET + DIM + GREY + text
                            + RESET + BORDER + "│" + RESET)
        rows.append(BORDER + "└" + "─" * inner + "┘" + RESET)
        return rows

    def _hud(self):
        score = "SCORE " + hud_number(self.game.score)
        best = "BEST " + hud_number(max(self.best, self.game.score))
        level = "LV %d" % self.game.level
        gap = self.grid_w - 2 - len(score) - len(best) - len(level)
        gap = max(2, gap)
        gap1 = gap // 2
        gap2 = gap - gap1
        return (BORDER + "│" + RESET + " " + GREEN + score + RESET
                + " " * gap1 + YELLOW + best + RESET
                + " " * gap2 + MAGENTA + level + RESET
                + " " + BORDER + "│" + RESET)

    def _pause_overlay(self, row):
        box_w = min(30, self.grid_w - 2)
        pad = (self.grid_w - box_w) // 2
        inner = box_w - 2
        if row == 0:
            text = "┌" + "─" * inner + "┐"
            style = BORDER + PAUSE_BG
        elif row == 1:
            label = "PAUSED"
            text = "│" + label.center(inner) + "│"
            style = BOLD + YELLOW + PAUSE_BG
        elif row == 2:
            label = "p resume · q quit"
            text = "│" + label.center(inner) + "│"
            style = MINT + PAUSE_BG
        else:
            text = "└" + "─" * inner + "┘"
            style = BORDER + PAUSE_BG
        line = " " * pad + style + text + RESET + " " * (self.grid_w - pad - box_w)
        return BORDER + "│" + RESET + line + BORDER + "│" + RESET

    def _play_lines(self, now):
        g = self.game
        paused = self.mode == "pause"
        overlay_start = self.grid_h // 2 - 2
        overlay_end = overlay_start + 3

        body = {}
        for idx, pos in enumerate(g.snake):
            body[pos] = idx
        snake_len = len(g.snake)

        lines = []
        lines.append(BORDER + "┌" + "─" * self.grid_w + "┐" + RESET)
        lines.append(self._hud())
        lines.append(BORDER + "├" + "─" * self.grid_w + "┤" + RESET)

        for y in range(self.grid_h):
            if paused and overlay_start <= y <= overlay_end:
                lines.append(self._pause_overlay(y - overlay_start))
                continue
            parts = [BORDER + "│" + RESET]
            for x in range(self.grid_w):
                pos = (x, y)
                if pos in body:
                    idx = body[pos]
                    if idx == 0:
                        parts.append(HEAD_STYLE + "█" + RESET)
                    else:
                        step = int((idx / max(1, snake_len - 1))
                                   * (len(SNAKE_GRADIENT) - 1))
                        parts.append(SNAKE_GRADIENT[step] + "█" + RESET)
                elif pos == g.food:
                    parts.append(FOOD_STYLE + "●" + RESET)
                else:
                    parts.append(" ")
            parts.append(BORDER + "│" + RESET)
            lines.append("".join(parts))

        lines.append(BORDER + "└" + "─" * self.grid_w + "┘" + RESET)
        if paused:
            hint = "p resume · q quit"
        else:
            hint = "arrows / WASD move · p pause · q quit"
        lines.append(center_styled(DIM + CYAN + hint + RESET, self.board_w))
        return lines

    def _start_lines(self, now):
        width = self._page_width()
        lines = [""]
        title = "✦  NEON SERPENT  ✦"
        lines.append(center_styled(BOLD + MAGENTA + title + RESET, width))
        lines.append(center_styled(MINT + "eat · grow · survive · repeat"
                                   + RESET, width))
        lines.append("")
        if self.warning:
            lines.append(center_styled(BOLD + RED + self.warning[:width]
                                       + RESET, width))
        lines.append(center_styled(BOLD + CYAN + "HIGH SCORES" + RESET, width))
        lines.extend(self._score_table(width))
        lines.append("")
        lines.append(center_styled(
            DIM + WHITE + "arrows / WASD steer · p pause · q quit" + RESET,
            width))
        prompt_style = BOLD + GREEN if self.blink else DIM + GREEN
        lines.append(center_styled(prompt_style + "press any key to start"
                                   + RESET, width))
        lines.append("")
        lines.extend(self._footer_lines(width))
        return lines

    def _initials_line(self, width):
        entered = self.initials
        missing = 3 - len(entered)
        cursor_style = BOLD + GREEN if self.blink else DIM + GREEN
        styled = (BOLD + YELLOW + entered + RESET + cursor_style
                  + "_" * missing + RESET)
        return center_styled("initials   " + styled, width)

    def _gameover_lines(self, now):
        width = self._page_width()
        lines = [""]
        lines.append(center_styled(BOLD + RED + "── GAME OVER ──" + RESET,
                                   width))
        score_line = "SCORE %04d   ·   LV %d" % (self.final_score,
                                                   self.final_level)
        lines.append(center_styled(BOLD + WHITE + score_line + RESET, width))
        lines.append("")

        if self.mode == "initials":
            if self.new_rank == 0:
                banner = "NEW BEST!"
            else:
                banner = "TOP 5 SCORE!"
            lines.append(center_styled(BOLD + YELLOW + banner + RESET, width))
            lines.append(self._initials_line(width))
            lines.append(center_styled(
                DIM + WHITE + "A-Z 0-9 · backspace · enter · q quits"
                + RESET, width))
        else:
            if self.over_message:
                lines.append(center_styled(BOLD + MINT + self.over_message
                                           + RESET, width))
            else:
                lines.append(center_styled(
                    DIM + GREY + "the serpent has fallen" + RESET, width))
            lines.append("")

        if self.mode != "initials":
            lines.append(center_styled(BOLD + CYAN + "HIGH SCORES" + RESET,
                                       width))
        else:
            lines.append("")
            lines.append(center_styled(BOLD + CYAN + "HIGH SCORES" + RESET,
                                       width))
        lines.extend(self._score_table(width))
        lines.append("")

        if self.mode == "initials":
            lines.append(center_styled(DIM + GREEN + "finish your initials"
                                       + RESET, width))
        else:
            lines.append(center_styled(
                BOLD + GREEN + "r restart" + RESET + DIM + "   ·   "
                + RESET + BOLD + GREEN + "q quit" + RESET, width))
        return lines

    def _small_lines(self, cols, rows):
        need_w = max(MIN_COLS, self.board_w)
        need_h = max(MIN_ROWS, self.total_h)
        raw = [
            "NEON SERPENT",
            "terminal too small",
            "",
            "need %d x %d" % (need_w, need_h),
            "have %d x %d" % (cols, rows),
            "enlarge the window · q quits",
        ]
        lines = []
        for text in raw:
            if len(text) > cols:
                text = text[:cols]
            lines.append(center_styled(BOLD + YELLOW + text + RESET, cols)
                         if text else "")
        return lines

    # -- state transitions --------------------------------------------------
    def start_game(self):
        self.game = Game(self.grid_w, self.grid_h)
        self.mode = "play"
        self.next_tick = time.monotonic() + self.game.interval
        self.highlight = None
        self.over_message = ""
        self.initials = ""
        self.needs_render = True
        self.last_blink = time.monotonic()

    def rank_for(self, score):
        pos = 0
        for entry in self.scores:
            if score > entry["score"]:
                break
            pos += 1
        return pos

    def enter_game_over(self):
        self.final_score = self.game.score
        self.final_level = self.game.level
        self.next_tick = None
        self.highlight = None
        self.initials = ""
        self.new_rank = self.rank_for(self.final_score)
        qualifies = self.final_score > 0 and self.new_rank < 5
        if self.game.won:
            self.over_message = "PERFECT RUN!"
        else:
            self.over_message = ""
        self.mode = "initials" if qualifies else "gameover"
        if qualifies:
            self.over_message = ""
        self.needs_render = True
        self.last_blink = time.monotonic()

    def confirm_initials(self):
        if not self.initials:
            return
        entry = {
            "initials": self.initials,
            "score": self.final_score,
            "date": datetime.now().strftime("%Y-%m-%d"),
        }
        self.scores.append(entry)
        self.scores.sort(key=lambda e: (-e["score"], e["date"],
                                        e["initials"]))
        self.scores = self.scores[:5]
        self.best = self.scores[0]["score"] if self.scores else 0
        if entry in self.scores:
            self.highlight = entry
        else:
            self.highlight = None
        problem = save_scores(self.scores)
        if problem:
            self.warning = problem
            self.over_message = problem
        else:
            self.over_message = "score saved"
        self.mode = "gameover"
        self.needs_render = True

    # -- input --------------------------------------------------------------
    def _dir_for(self, key):
        low = key.lower() if len(key) == 1 else key
        return {
            "UP": (0, -1), "w": (0, -1),
            "DOWN": (0, 1), "s": (0, 1),
            "LEFT": (-1, 0), "a": (-1, 0),
            "RIGHT": (1, 0), "d": (1, 0),
        }.get(low)

    def handle_key(self, key):
        if key in ("EOF",):
            self.running = False
            return
        low = key.lower() if len(key) == 1 else key

        if self.mode == "start":
            if low == "q":
                self.running = False
            else:
                self.start_game()
            return

        if self.mode == "play":
            if low == "q":
                self.running = False
                return
            if low == "p":
                self.mode = "pause"
                self.next_tick = None
                self.needs_render = True
                return
            direction = self._dir_for(key)
            if direction:
                self.game.turn(direction)
            return

        if self.mode == "pause":
            if low == "q":
                self.running = False
            elif low == "p" or key == " ":
                self.mode = "play"
                self.next_tick = time.monotonic() + self.game.interval
                self.needs_render = True
            return

        if self.mode == "initials":
            if key == "BACKSPACE":
                self.initials = self.initials[:-1]
                self.needs_render = True
            elif key == "ENTER":
                if self.initials:
                    self.confirm_initials()
            elif key == "q":
                # Lowercase q always quits; Shift+Q can be an initial.
                self.running = False
            elif len(key) == 1 and key.isalnum():
                if len(self.initials) < 3:
                    self.initials += key.upper()
                    self.needs_render = True
            return

        if self.mode == "gameover":
            if low == "q":
                self.running = False
            elif low == "r":
                self.start_game()

    # -- rendering / loop ---------------------------------------------------
    def render(self):
        cols, rows = term_size()
        if self.small:
            self.term.present(self._small_lines(cols, rows))
            return
        now = time.monotonic()
        if self.mode == "start":
            self.term.present(self._start_lines(now))
        elif self.mode in ("play", "pause"):
            self.term.present(self._play_lines(now))
        else:
            self.term.present(self._gameover_lines(now))

    def run(self):
        while self.running:
            if _QUIT[0]:
                self.running = False
                break

            for key in self.term.poll(0.01):
                if not self.running:
                    break
                self.handle_key(key)

            if not self.running:
                break

            now = time.monotonic()
            cols, rows = term_size()
            fits = (cols >= MIN_COLS and rows >= MIN_ROWS
                    and cols >= self.board_w and rows >= self.total_h)

            if not fits and not self.small:
                self.small = True
                self.next_tick = None
                self.needs_render = True
            elif fits and self.small:
                self.small = False
                if self.mode == "play":
                    self.next_tick = now + self.game.interval
                self.needs_render = True

            if not self.small and self.mode == "play":
                if self.next_tick is None:
                    self.next_tick = now + self.game.interval
                if now >= self.next_tick:
                    due = self.next_tick
                    self.game.step()
                    if self.game.dead:
                        self.enter_game_over()
                    else:
                        self.next_tick = due + self.game.interval
                        if self.next_tick <= now:
                            self.next_tick = now + self.game.interval
                    self.needs_render = True

            if (not self.small
                    and self.mode in ("start", "gameover", "initials")
                    and now - self.last_blink >= 0.55):
                self.blink = not self.blink
                self.last_blink = now
                self.needs_render = True

            if self.needs_render:
                self.render()
                self.needs_render = False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("NEON SERPENT needs an interactive POSIX terminal "
              "(stdin and stdout must be a TTY).")
        return 1

    cols, rows = term_size()
    if cols < MIN_COLS or rows < MIN_ROWS:
        print("NEON SERPENT needs a terminal of at least %d x %d characters "
              "(yours is %d x %d)." % (MIN_COLS, MIN_ROWS, cols, rows))
        return 1

    app = App()
    try:
        app.term.setup()
        try:
            signal.signal(signal.SIGINT, _on_signal)
            signal.signal(signal.SIGTERM, _on_signal)
        except (ValueError, OSError):
            pass
        app.run()
    except KeyboardInterrupt:
        pass
    finally:
        app.term.restore()
    return 0


if __name__ == "__main__":
    sys.exit(main())
