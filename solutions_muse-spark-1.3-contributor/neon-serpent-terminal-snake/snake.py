#!/usr/bin/env python3
# Neon Serpent — Terminal Snake
# built 2026-10-29 22:24 UTC · Muse Spark 1.3 Contributor
"""Single-file terminal Snake rendered with raw ANSI escape codes (no curses)."""

import datetime
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

BUILD_STAMP = "built 2026-10-29 22:24 UTC"
BUILD_AUTHOR = "Muse Spark 1.3 Contributor"

# --- Config ---------------------------------------------------------------
W = 30  # playfield interior width  (>=30)
H = 15  # playfield interior height (>=15)
TICK_START = 0.150  # seconds
TICK_STEP = 0.007   # per food
TICK_MIN = 0.060    # floor
SCORE_PER_FOOD = 10
MAX_SCORES = 5

# --- ANSI -----------------------------------------------------------------
ESC = "\x1b"
ALT_ENTER = "\x1b[?1049h"
ALT_EXIT = "\x1b[?1049l"
HIDE = "\x1b[?25l"
SHOW = "\x1b[?25h"
RESET = "\x1b[0m"
HOME = "\x1b[H"
CLEAR = "\x1b[2J"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"

C_BORDER = "\x1b[95m"   # bright magenta (neon)
C_HUD = "\x1b[96m"      # bright cyan
C_SNAKE = "\x1b[92m"    # bright green
C_HEAD = "\x1b[1;92m"   # bold bright green
C_FOOD = "\x1b[93m"     # bright yellow
C_RED = "\x1b[91m"
C_DIM = "\x1b[2m"
C_TITLE = "\x1b[1;95m"  # bold magenta

DIRS = {
    "UP": (0, -1),
    "DOWN": (0, 1),
    "LEFT": (-1, 0),
    "RIGHT": (1, 0),
}
OPPOSITE = {"UP": "DOWN", "DOWN": "UP", "LEFT": "RIGHT", "RIGHT": "LEFT"}


def score_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "snake_scores.json")


def load_scores(path=None):
    """Return (scores_list, warning_or_None). Never raises on bad data."""
    p = path or score_path()
    if not os.path.exists(p):
        return [], None
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        raw = data.get("scores", []) if isinstance(data, dict) else []
        scores = []
        for e in raw:
            if not isinstance(e, dict):
                continue
            try:
                scores.append({
                    "initials": str(e.get("initials", "???"))[:3].upper(),
                    "score": int(e.get("score", 0)),
                    "date": str(e.get("date", "1970-01-01")),
                })
            except (ValueError, TypeError):
                continue
        scores.sort(key=lambda s: -s["score"])
        return scores[:MAX_SCORES], None
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        # Preserve the user's bad file, start fresh, warn with one line.
        try:
            bak = p + ".bak"
            with open(p, "r", encoding="utf-8", errors="replace") as src:
                bad = src.read()
            with open(bak, "w", encoding="utf-8") as dst:
                dst.write(bad)
        except OSError:
            pass
        return [], "warning: %s was invalid JSON (%s); backed up to .bak, starting fresh." % (
            os.path.basename(p), exc.__class__.__name__)


def save_scores(scores, path=None):
    p = path or score_path()
    scores = sorted(scores, key=lambda s: -s["score"])[:MAX_SCORES]
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"scores": scores}, f, indent=2)
        f.write("\n")
    os.replace(tmp, p)
    return scores


def tick_interval(foods_eaten):
    return max(TICK_MIN, TICK_START - TICK_STEP * foods_eaten)


def level_for(foods_eaten):
    return 1 + foods_eaten


def spawn_food(snake, w=W, h=H):
    occupied = set(snake)
    free = [(x, y) for y in range(h) for x in range(w) if (x, y) not in occupied]
    if not free:
        return None
    return random.choice(free)


def new_game():
    cx, cy = W // 2, H // 2
    snake = [(cx, cy), (cx - 1, cy), (cx - 2, cy)]
    food = spawn_food(snake)
    return {
        "snake": snake,
        "dir": "RIGHT",
        "pending": "RIGHT",
        "food": food,
        "score": 0,
        "foods": 0,
        "dead": False,
    }


def step_game(g):
    """Advance one tick. Mutates g. Returns event string: 'ate'|'moved'|'died'."""
    dx, dy = DIRS[g["pending"]]
    g["dir"] = g["pending"]
    hx, hy = g["snake"][0]
    nh = (hx + dx, hy + dy)
    # wall collision
    if nh[0] < 0 or nh[0] >= W or nh[1] < 0 or nh[1] >= H:
        g["dead"] = True
        return "died"
    will_grow = (nh == g["food"])
    body = g["snake"] if will_grow else g["snake"][:-1]
    if nh in body:
        g["dead"] = True
        return "died"
    g["snake"].insert(0, nh)
    if will_grow:
        g["score"] += SCORE_PER_FOOD
        g["foods"] += 1
        g["food"] = spawn_food(g["snake"])
        return "ate"
    else:
        g["snake"].pop()
        return "moved"


def try_set_direction(g, ndir):
    """Apply steering; ignore 180-degree reversals into the neck."""
    if ndir not in DIRS:
        return False
    if OPPOSITE[ndir] == g["dir"]:
        return False
    # Also ignore reversal vs pending (double-turn within one tick).
    if OPPOSITE[ndir] == g["pending"] and len(g["snake"]) > 1:
        # pending may differ from dir after a queued turn; compare against
        # the direction that will actually be used next tick.
        return False
    g["pending"] = ndir
    return True


def qualifies(scores, score):
    if score <= 0:
        return False
    if len(scores) < MAX_SCORES:
        return True
    return score > min(s["score"] for s in scores)


# --- Rendering ------------------------------------------------------------
def _top(w):
    return C_BORDER + "┌" + "─" * w + "┐" + RESET


def _sep(w):
    return C_BORDER + "├" + "─" * w + "┤" + RESET


def _bottom(w):
    return C_BORDER + "└" + "─" * w + "┘" + RESET


def _side(cell):
    return C_BORDER + "│" + RESET + cell + C_BORDER + "│" + RESET


def render_game(g, best, paused=False):
    lvl = level_for(g["foods"])
    hud_text = " SCORE %04d   BEST %04d   LV %d " % (g["score"], max(best, g["score"]), lvl)
    hud_text = hud_text[:W].center(W)
    lines = [_top(W)]
    lines.append(_side(C_HUD + hud_text + RESET))
    lines.append(_sep(W))
    body = set(g["snake"][1:])
    head = g["snake"][0]
    fx, fy = g["food"] if g["food"] else (-1, -1)
    for y in range(H):
        row = []
        for x in range(W):
            if (x, y) == head:
                row.append(C_HEAD + "◉" + RESET)
            elif (x, y) in body:
                row.append(C_SNAKE + "█" + RESET)
            elif (x, y) == (fx, fy):
                row.append(C_FOOD + "●" + RESET)
            else:
                row.append(" ")
        lines.append(_side("".join(row)))
    lines.append(_bottom(W))
    lines.append(C_DIM + " arrows / WASD move · p pause · q quit" + RESET)
    if paused:
        # overlay indicator: replace middle row visually via extra line (no artifact
        # because we redraw from HOME every frame; indicator line is below board)
        lines.append(C_RED + BOLD + "  ** PAUSED — press p to resume **" + RESET)
    return HOME + "\n".join(lines)


def render_start(scores, warning=None):
    lines = [""]
    lines.append(C_TITLE + "  ◆ NEON SERPENT ◆  " + RESET)
    lines.append(C_DIM + "    terminal snake · raw ANSI · no curses" + RESET)
    lines.append("")
    lines.append(C_HUD + "  ── TOP 5 ──" + RESET)
    if not scores:
        lines.append(C_DIM + "   (no scores yet — be the first!)" + RESET)
    else:
        for i, s in enumerate(scores[:5], 1):
            lines.append("   %d. %s  %4d  %s" % (i, s["initials"], s["score"], s["date"]))
    lines.append("")
    if warning:
        lines.append(C_RED + "  " + warning[:78] + RESET)
        lines.append("")
    lines.append("  press any key to start · q to quit")
    lines.append(C_DIM + "  %s · %s" % (BUILD_STAMP, BUILD_AUTHOR) + RESET)
    return HOME + CLEAR + HOME + "\n".join(lines)


def render_gameover(g, scores, initials_buf=None, saved=False):
    lines = [""]
    lines.append(C_RED + BOLD + "  GAME OVER" + RESET)
    lines.append("  FINAL SCORE %04d   LV %d" % (g["score"], level_for(g["foods"])))
    lines.append("")
    if initials_buf is not None and not saved:
        disp = (initials_buf + "___")[:3]
        # pretty slots: show typed chars highlighted
        slots = " ".join("%s" % c for c in disp)
        lines.append(C_FOOD + "  ★ NEW TOP-5! enter initials: [%s]" % slots + RESET)
        lines.append(C_DIM + "  A–Z 0–9 · backspace edits · Enter confirms" + RESET)
    elif saved:
        lines.append(C_SNAKE + "  saved! top scores:" + RESET)
        for i, s in enumerate(scores[:5], 1):
            lines.append("   %d. %s  %4d  %s" % (i, s["initials"], s["score"], s["date"]))
    else:
        lines.append(C_DIM + "  top scores:" + RESET)
        if not scores:
            lines.append(C_DIM + "   (no scores yet)" + RESET)
        for i, s in enumerate(scores[:5], 1):
            lines.append("   %d. %s  %4d  %s" % (i, s["initials"], s["score"], s["date"]))
    lines.append("")
    lines.append("  r restart · q quit")
    return HOME + "\n".join(lines)


# --- Input ----------------------------------------------------------------
def parse_bytes(data):
    """Parse raw input bytes into a list of key tokens."""
    toks = []
    try:
        s = data.decode("utf-8", "ignore")
    except Exception:
        return toks
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == "\x1b":
            if i + 2 < n and s[i + 1] == "[" and s[i + 2] in "ABCD":
                m = {"A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT"}[s[i + 2]]
                toks.append(m)
                i += 3
                continue
            elif i + 2 < n and s[i + 1] == "O" and s[i + 2] in "ABCD":
                m = {"A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT"}[s[i + 2]]
                toks.append(m)
                i += 3
                continue
            else:
                # lone ESC (maybe split sequence) — ignore
                i += 1
                continue
        elif c == "\x03":
            toks.append("CTRLC")
            i += 1
        elif c in ("\r", "\n"):
            toks.append("ENTER")
            i += 1
        elif c in ("\x7f", "\x08"):
            toks.append("BACKSPACE")
            i += 1
        elif c == "\t":
            i += 1
        else:
            toks.append(c)
            i += 1
    return toks


def drain_keys(fd):
    toks = []
    # drain everything currently available
    while True:
        r, _, _ = select.select([fd], [], [], 0)
        if not r:
            break
        try:
            data = os.read(fd, 4096)
        except OSError:
            break
        if not data:
            break
        toks.extend(parse_bytes(data))
    return toks


def steer_token_to_dir(tok):
    if tok == "UP":
        return "UP"
    if tok == "DOWN":
        return "DOWN"
    if tok == "LEFT":
        return "LEFT"
    if tok == "RIGHT":
        return "RIGHT"
    low = tok.lower() if len(tok) == 1 else tok
    if low == "w":
        return "UP"
    if low == "s":
        return "DOWN"
    if low == "a":
        return "LEFT"
    if low == "d":
        return "RIGHT"
    return None


# --- Main loop ------------------------------------------------------------
def _check_terminal_size():
    try:
        size = shutil.get_terminal_size()
        cols, rows = size.columns, size.lines
    except Exception:
        return True
    if cols < 40 or rows < 20:
        sys.stdout.write(
            "Neon Serpent needs a terminal of at least 40x20 "
            "(yours: %dx%d). Please enlarge and retry.\n" % (cols, rows)
        )
        sys.stdout.flush()
        return False
    return True


def run():
    if not sys.stdin.isatty():
        sys.stdout.write("Neon Serpent needs a real POSIX terminal (stdin is not a tty).\n")
        return 1
    if not _check_terminal_size():
        return 1

    fd = sys.stdin.fileno()
    try:
        orig = termios.tcgetattr(fd)
    except termios.error:
        sys.stdout.write("Neon Serpent could not access terminal settings.\n")
        return 1

    # SIGINT must still restore the terminal via finally below.
    def _on_sigint(signum, frame):
        raise KeyboardInterrupt()

    old_handler = signal.getsignal(signal.SIGINT)
    out = sys.stdout

    scores, warning = load_scores()
    best = scores[0]["score"] if scores else 0

    state = "start"   # start | play | over
    paused = False
    g = new_game()
    initials_buf = None
    need_initials = False
    saved_this_run = False
    next_tick = time.monotonic() + TICK_START
    last_start_render = 0.0

    def cleanup():
        try:
            out.write(SHOW + RESET + ALT_EXIT)
            out.flush()
        except Exception:
            pass
        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, orig)
        except Exception:
            pass
        try:
            signal.signal(signal.SIGINT, old_handler)
        except Exception:
            pass

    try:
        signal.signal(signal.SIGINT, _on_sigint)
        tty.setcbreak(fd)
        out.write(ALT_ENTER + HIDE + CLEAR + HOME)
        out.flush()

        while True:
            # --- input (non-blocking poll) ---
            r, _, _ = select.select([fd], [], [], 0.012)
            tokens = []
            if r:
                try:
                    data = os.read(fd, 4096)
                except OSError:
                    data = b""
                if data:
                    tokens = parse_bytes(data)
                    # drain any burst that arrived together
                    tokens += drain_keys(fd)

            quit_req = False
            for tok in tokens:
                if tok == "CTRLC":
                    return 0  # finally restores terminal
                if len(tok) == 1 and tok.lower() == "q":
                    # q quits from gameplay, pause, and menus
                    if state == "over" and initials_buf is not None and not saved_this_run:
                        # allow quitting even mid-initials-entry
                        pass
                    return 0
                if state == "start":
                    if len(tok) == 1 and tok.lower() == "q":
                        return 0
                    # any other key starts
                    if tok in ("ENTER",):
                        pass  # falls through to start below
                    state = "play"
                    paused = False
                    g = new_game()
                    saved_this_run = False
                    initials_buf = None
                    next_tick = time.monotonic() + tick_interval(0)
                    break  # ignore remaining tokens this frame
                elif state == "play":
                    if len(tok) == 1 and tok.lower() == "p":
                        paused = not paused
                        if not paused:
                            # avoid a jump after pause
                            next_tick = time.monotonic() + tick_interval(g["foods"])
                        continue
                    ndir = steer_token_to_dir(tok)
                    if ndir:
                        try_set_direction(g, ndir)
                elif state == "over":
                    if initials_buf is not None and not saved_this_run:
                        if tok == "ENTER":
                            if len(initials_buf) >= 1:
                                # pad short names so table stays aligned
                                name = (initials_buf.upper() + "XXX")[:3] if len(initials_buf) < 3 else initials_buf.upper()
                                # sanitize strictly
                                clean = "".join(c for c in name if c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
                                if not clean:
                                    clean = "AAA"
                                clean = (clean + "XXX")[:3]
                                today = datetime.date.today().isoformat()
                                scores.append({"initials": clean, "score": g["score"], "date": today})
                                scores[:] = sorted(scores, key=lambda s: -s["score"])[:MAX_SCORES]
                                try:
                                    save_scores(scores)
                                except OSError:
                                    pass
                                best = scores[0]["score"] if scores else best
                                saved_this_run = True
                                initials_buf = None
                        elif tok == "BACKSPACE":
                            initials_buf = initials_buf[:-1]
                        elif len(tok) == 1 and tok.upper() in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
                            if len(initials_buf) < 3:
                                initials_buf += tok.upper()
                        # ignore other keys (except q handled above, r ignored until saved? allow r? no—must confirm first; ignore)
                        continue
                    else:
                        if len(tok) == 1 and tok.lower() == "r":
                            state = "play"
                            paused = False
                            g = new_game()
                            saved_this_run = False
                            initials_buf = None
                            next_tick = time.monotonic() + tick_interval(0)
                            break
                        # Enter does nothing on game-over (non-initials) screen

            # --- tick (monotonic clock; input never blocks movement) ---
            if state == "play" and not paused:
                now = time.monotonic()
                if now >= next_tick:
                    ev = step_game(g)
                    interval = tick_interval(g["foods"])
                    # avoid backlog spiral after stalls
                    if next_tick + interval < now:
                        next_tick = now + interval
                    else:
                        next_tick = next_tick + interval
                    if ev == "died":
                        state = "over"
                        saved_this_run = False
                        if qualifies(scores, g["score"]):
                            initials_buf = ""
                            need_initials = True
                        else:
                            initials_buf = None
                            need_initials = False

            # --- render (full redraw from HOME: no flicker/scroll/artifacts) ---
            now = time.monotonic()
            if state == "start":
                # re-render cheaply at ~10fps (blinking not needed; keeps warning fresh)
                if now - last_start_render > 0.1:
                    out.write(render_start(scores, warning))
                    out.flush()
                    last_start_render = now
            elif state == "play":
                out.write(render_game(g, best, paused))
                out.flush()
            elif state == "over":
                if initials_buf is not None and not saved_this_run:
                    out.write(render_gameover(g, scores, initials_buf, saved=False))
                else:
                    out.write(render_gameover(g, scores, None, saved=saved_this_run))
                out.flush()

            if quit_req:
                return 0
    except KeyboardInterrupt:
        return 0
    except Exception:
        # Never leave the shell garbled: restore first, then report.
        raise
    finally:
        cleanup()
    return 0


def main():
    try:
        return run()
    except Exception as exc:
        # terminal already restored by run()'s finally; report plainly
        try:
            sys.stdout.write("\nNeon Serpent crashed: %r\n" % (exc,))
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
