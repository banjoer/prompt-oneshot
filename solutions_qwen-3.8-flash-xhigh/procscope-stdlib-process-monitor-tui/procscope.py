#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =============================================================================
#  ProcScope — a top-like process monitor TUI in pure Python standard library
# =============================================================================
#
#  Sign-off: produced 2026-10-29 23:14 UTC by Qwen 3.8 Flash (xhigh reasoning)
#            for the prompt-oneshot challenge `procscope-stdlib-process-
#            monitor-tui`.  No curses, no psutil, no third-party packages —
#            only os / sys / time / signal / select / termios / tty / shutil /
#            subprocess / argparse / dataclasses / re / pwd.
#
#  Run live:      python3 procscope.py
#  Snapshot:      python3 procscope.py --once
#
#  Data sources:
#    * Primary   — Linux /proc pseudofiles (/proc/stat, /proc/meminfo,
#                  /proc/<pid>/{stat,status,cmdline}).  CPU% per process is
#                  the delta of (utime+stime) jiffies between refreshes
#                  divided by (wall-time delta x SC_CLK_TCK), as a percentage
#                  of one CPU.  MEM% is VmRSS / MemTotal.  The first frame
#                  shows 0.0 CPU because no delta exists yet.
#    * Fallback  — `ps -Ao pid=,user=,comm=,%cpu=,%mem=,stat=,rss=` parsed
#                  once per refresh; taken automatically (no flags, no user
#                  intervention) whenever /proc/stat cannot be read.  The
#                  per-core section then collapses to one aggregate CPU bar.
#
#  Color discipline: every color/style byte goes through Style.sgr().  With
#  NO_COLOR set, or TERM=dumb/missing, the program emits ZERO escape codes
#  and renders plain monochrome ASCII (frames simply scroll on refresh).
#
#  Key bindings (the in-app `h`/`?` overlay lists them all):
#    c m n p   sort by CPU% / MEM% / NAME / PID   r  toggle asc/desc
#    Up/Down, PgUp/PgDn  select / page through rows
#    /         live filter by name or cmdline, Esc clears
#    k         SIGTERM selected process; press again within 3s => SIGKILL
#    h / ?     help overlay (pauses updates)     q / Ctrl-C  quit cleanly
# =============================================================================

from __future__ import annotations

import argparse
import os
import re
import select
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field

AUTHOR_SIGNOFF = "ProcScope by Qwen 3.8 Flash - produced 2026-10-29 23:14 UTC"
# Compact variant that always fits the footer at >= 76 columns.
SIGNOFF_SHORT = "Qwen 3.8 Flash - 2026-10-29 23:14"

# --- optional Unix-only modules ----------------------------------------------
try:
    import pwd
except ImportError:                     # pragma: no cover
    pwd = None

try:
    import termios
    import tty
except ImportError:                     # pragma: no cover
    termios = None
    tty = None

# SGR codes; the only styling constants the whole program uses.
BOLD, DIM, REV = "1", "2", "7"
GREEN, YELLOW, RED, CYAN, MAGENTA = "32", "33", "31", "36", "35"


# =============================================================================
#  Style helper — single gate for all ANSI color / styling
# =============================================================================

def color_requested():
    """True unless NO_COLOR is set or TERM is 'dumb' / missing."""
    if os.environ.get("NO_COLOR", ""):
        return False
    term = os.environ.get("TERM", "")
    return bool(term) and term != "dumb"


def stdout_can_encode(sample):
    enc = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        sample.encode(enc)
        return True
    except (LookupError, UnicodeEncodeError):
        return False


class Style:
    """Tiny internal helper: wraps text in SGR codes, or passes it through."""

    def __init__(self, enabled):
        self.enabled = enabled

    def sgr(self, text, *codes):
        if not self.enabled or not codes:
            return text
        return "\x1b[" + ";".join(codes) + "m" + text + "\x1b[0m"


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def visible_len(styled):
    """Display width of a string, ignoring ANSI escape sequences."""
    return len(_ANSI_RE.sub("", styled))


# =============================================================================
#  Data model
# =============================================================================

@dataclass
class Proc:
    pid: int
    user: str
    name: str
    cmdline: str
    cpu: float
    mem: float
    state: str


@dataclass
class Sample:
    procs: list = field(default_factory=list)
    per_core: list = field(default_factory=list)   # float | None per CPU
    total_cpu: float = 0.0
    mem_total_kb: int = 0        # 0 => unknown
    mem_used_kb: int = -1        # -1 => unknown
    mem_avail_kb: int = -1
    load: tuple = ()
    uptime: float = -1.0
    multi_core: bool = False


# =============================================================================
#  /proc parsing helpers
# =============================================================================

def split_stat_line(line):
    """(comm, rest-fields) from /proc/<pid>/stat.

    comm (field 2) may contain spaces *and* parentheses, so anchor on the
    first '(' and the LAST ')' before reading fields 3+ (state, ...; utime
    and stime are whole-line fields 14 and 15).
    """
    lp = line.find("(")
    rp = line.rfind(")")
    if lp < 0 or rp <= lp:
        return None, None
    return line[lp + 1:rp], line[rp + 1:].split()


def parse_cpu_line(line):
    """('cpuN', [ints]) from a /proc/stat cpu line, else None."""
    parts = line.split()
    if not parts or not parts[0].startswith("cpu"):
        return None
    try:
        return parts[0], [int(x) for x in parts[1:]]
    except ValueError:
        return None


def usage_between(prev, cur):
    """100 * (1 - (idle+iowait delta)/(total delta)); None when no base."""
    if not prev or not cur or len(prev) < 4 or len(cur) < 4:
        return None
    total_delta = sum(cur) - sum(prev)
    if total_delta <= 0:
        return None
    idle_delta = cur[3] - prev[3]
    if len(prev) > 4 and len(cur) > 4:
        idle_delta += cur[4] - prev[4]
    return max(0.0, min(100.0, 100.0 * (1.0 - idle_delta / total_delta)))


def name_from(comm, cmdline, pid):
    """comm value, or a truncated cmdline basename when comm is unhelpful."""
    if comm and comm not in ("?", "-"):
        return comm
    if cmdline:
        tok = cmdline.strip().split(" ")[0]
        base = tok.rsplit("/", 1)[-1] if tok else ""
        if base:
            return base
    return "[pid %d]" % pid


# =============================================================================
#  Data sources
# =============================================================================

class LinuxProcSource:
    """Primary source — reads the kernel's /proc pseudofiles (read-only)."""

    name = "/proc"

    def __init__(self, proc="/proc"):
        self.proc = proc
        try:
            self.hz = os.sysconf("SC_CLK_TCK") or 100
        except (ValueError, OSError, KeyError):
            self.hz = 100
        self._prev_cpu_lines = {}
        self._prev_ticks = {}
        self._prev_ticks_t = time.monotonic()
        self._user_cache = {}

    def sample(self):
        now = time.monotonic()
        s = Sample()
        s.multi_core = True

        # ---- /proc/stat: aggregate + per-core usage from line deltas -------
        lines = {}
        try:
            with open(os.path.join(self.proc, "stat")) as f:
                for line in f:
                    parsed = parse_cpu_line(line)
                    if parsed:
                        lines[parsed[0]] = parsed[1]
        except OSError:
            pass
        prev = self._prev_cpu_lines
        agg = usage_between(prev.get("cpu"), lines.get("cpu"))
        s.total_cpu = agg if agg is not None else 0.0
        for key in sorted(k for k in lines if k != "cpu"):
            s.per_core.append(usage_between(prev.get(key), lines.get(key)))
        self._prev_cpu_lines = lines

        # ---- /proc/meminfo ---------------------------------------------------
        try:
            with open(os.path.join(self.proc, "meminfo")) as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        s.mem_total_kb = int(line.split()[1])
                    elif line.startswith("MemAvailable:"):
                        s.mem_avail_kb = int(line.split()[1])
                    elif line.startswith("MemFree:"):
                        if s.mem_avail_kb < 0:
                            s.mem_avail_kb = int(line.split()[1])
                    elif s.mem_total_kb and s.mem_avail_kb >= 0:
                        break
        except (OSError, ValueError, IndexError):
            pass
        if s.mem_total_kb > 0 and s.mem_avail_kb >= 0:
            s.mem_used_kb = max(0, s.mem_total_kb - s.mem_avail_kb)

        # ---- uptime + load average --------------------------------------------
        try:
            with open(os.path.join(self.proc, "uptime")) as f:
                s.uptime = float(f.read().split()[0])
        except (OSError, ValueError, IndexError):
            pass
        try:
            s.load = tuple(round(x, 2) for x in os.getloadavg())
        except (OSError, AttributeError):
            pass

        # ---- per-process rows --------------------------------------------------
        dt = now - self._prev_ticks_t
        fresh = {}
        try:
            pids = sorted(int(e) for e in os.listdir(self.proc)
                          if e.isdigit())
        except OSError:
            pids = []
        for pid in pids:
            pdir = os.path.join(self.proc, str(pid))
            try:
                with open(os.path.join(pdir, "stat")) as f:
                    line = f.read().rstrip("\n")
                comm, rest = split_stat_line(line)
                if not rest or len(rest) < 13:
                    continue
                state = rest[0]
                ticks = int(rest[11]) + int(rest[12])
            except (OSError, ValueError, IndexError):
                # raced with process exit / unreadable — skip, never crash
                continue
            rss_kb = 0
            uid = None
            try:
                with open(os.path.join(pdir, "status")) as f:
                    for l in f:
                        if l.startswith("VmRSS:"):
                            rss_kb = int(l.split()[1])
                        elif l.startswith("Uid:"):
                            uid = int(l.split()[1])
                            break
            except (OSError, ValueError, IndexError):
                pass
            if uid is None:
                try:
                    uid = os.stat(pdir).st_uid
                except OSError:
                    uid = 0
            cmdline = ""
            try:
                with open(os.path.join(pdir, "cmdline"), "rb") as f:
                    cmdline = f.read().replace(b"\0", b" ").decode(
                        "utf-8", "replace")
                cmdline = " ".join(cmdline.split())
            except OSError:
                pass
            cpu = 0.0
            base = self._prev_ticks.get(pid)
            if base is not None and dt > 0:
                d = ticks - base
                if d > 0:
                    cpu = 100.0 * d / (dt * self.hz)
            fresh[pid] = ticks
            mem = (100.0 * rss_kb / s.mem_total_kb) if s.mem_total_kb else 0.0
            s.procs.append(Proc(pid=pid, user=self._pwname(uid),
                                name=name_from(comm, cmdline, pid),
                                cmdline=cmdline, cpu=cpu, mem=mem,
                                state=state))
        self._prev_ticks = fresh
        self._prev_ticks_t = now
        return s

    def _pwname(self, uid):
        cached = self._user_cache.get(uid)
        if cached is not None:
            return cached
        name = str(uid)
        if pwd is not None:
            try:
                name = pwd.getpwuid(uid).pw_name
            except (KeyError, TypeError):
                pass
        self._user_cache[uid] = name
        return name


class PsSource:
    """Fallback source — parses `ps` once per refresh when /proc is absent."""

    name = "ps"
    ARGS = ["ps", "-Ao", "pid=,user=,comm=,%cpu=,%mem=,stat=,rss="]
    LINE = re.compile(
        r"^\s*(\d+)\s+(\S+)\s+(.*?)\s+([\d.]+)\s+([\d.]+)\s+(\S+)\s+(\d+)\s*$")

    def __init__(self):
        self.mem_total_kb = self._sysctl_memtotal()

    @staticmethod
    def _sysctl_memtotal():
        for key in ("hw.memsize", "hw.physmem64", "hw.physmem"):
            try:
                out = subprocess.run(["sysctl", "-n", key],
                                     capture_output=True, timeout=2)
                if out.returncode == 0:
                    kb = int(out.stdout.strip()) // 1024
                    if kb > 0:
                        return kb
            except (OSError, ValueError, subprocess.SubprocessError):
                continue
        return 0

    def sample(self):
        s = Sample()
        s.multi_core = False
        try:
            out = subprocess.run(self.ARGS, capture_output=True,
                                 timeout=5).stdout.decode("utf-8", "replace")
        except (OSError, subprocess.SubprocessError):
            return s
        rss_sum_kb = 0
        for line in out.splitlines():      # `=` labels suppress the header
            m = self.LINE.match(line)
            if not m:
                continue
            pid = int(m.group(1))
            if pid == 0:
                continue
            comm = m.group(3).strip()
            rss_sum_kb += int(m.group(7))
            s.procs.append(Proc(
                pid=pid, user=m.group(2),
                name=name_from(comm, comm, pid),
                cmdline=comm, cpu=float(m.group(4)),
                mem=float(m.group(5)), state=m.group(6)[0]))
        # `ps` %cpu is a lifetime average, not a delta; summing is the best
        # aggregate available without /proc.
        s.total_cpu = min(100.0, sum(p.cpu for p in s.procs))
        s.mem_total_kb = self.mem_total_kb
        if self.mem_total_kb:
            s.mem_used_kb = rss_sum_kb
            s.mem_avail_kb = max(0, self.mem_total_kb - rss_sum_kb)
        try:
            s.load = tuple(round(x, 2) for x in os.getloadavg())
        except (OSError, AttributeError):
            pass
        return s


def make_source(force_ps=False):
    """Pick /proc when it can be opened, else fall back to ps automatically."""
    if not force_ps:
        try:
            with open("/proc/stat"):
                pass
            return LinuxProcSource()
        except OSError:
            pass
    return PsSource()


# =============================================================================
#  Formatting helpers
# =============================================================================

def fmt_kb(kb):
    if kb is None or kb < 0:
        return "n/a"
    if kb >= 1048576:
        return "%.1fG" % (kb / 1048576)
    if kb >= 1024:
        return "%dM" % (kb // 1024)
    return "%dK" % kb


def fmt_uptime(secs):
    if secs is None or secs < 0:
        return "n/a"
    secs = int(secs)
    d, rem = divmod(secs, 86400)
    h, m = divmod(rem, 3600)
    return "%dd %02d:%02d" % (d, h, m // 60) if d else "%d:%02d" % (h, m // 60)


def sanitize(text, ascii_only):
    """Strip control chars; optionally clamp to plain printable ASCII."""
    if ascii_only:
        return "".join(c if 32 <= ord(c) < 127 else "?" for c in text)
    return "".join(c if (c == " " or c.isprintable()) else "?" for c in text)


def truncate(text, width):
    if width <= 0:
        return ""
    return text if len(text) <= width else text[:width - 1] + ">"


def pad(text, width, align):
    if len(text) > width:
        return text[:width]
    return text.rjust(width) if align == ">" else text.ljust(width)


def usage_color(pct):
    if pct is None:
        return DIM
    if pct < 50:
        return GREEN
    if pct < 80:
        return YELLOW
    return RED


def trim_styled(styled, width):
    """Cut a styled string down to `width` visible characters."""
    if visible_len(styled) <= width:
        return styled
    out, seen, i, n = [], 0, 0, len(styled)
    while i < n and seen < width:
        if styled[i] == "\x1b":
            m = _ANSI_RE.match(styled, i)
            if m:
                out.append(m.group(0))
                i = m.end()
                continue
        out.append(styled[i])
        seen += 1
        i += 1
    if "\x1b" in styled[:i]:          # don't let color bleed past the cut
        out.append("\x1b[0m")
    return "".join(out)


# =============================================================================
#  Sort keys and table columns
# =============================================================================

SORTS = {                                # key -> (column title, sort fn)
    "c": ("CPU%", lambda p: p.cpu),
    "m": ("MEM%", lambda p: p.mem),
    "n": ("NAME", lambda p: p.name.lower()),     # case-insensitive
    "p": ("PID", lambda p: p.pid),
}

# (title, fixed width | None = flex column, alignment, value fn)
COLUMNS = [
    ("PID", 7, ">", lambda p: str(p.pid)),
    ("USER", 9, "<", lambda p: p.user),
    ("NAME", None, "<", lambda p: p.name),
    ("CPU%", 6, ">", lambda p: p.cpu),
    ("MEM%", 6, ">", lambda p: p.mem),
    ("STATE", 5, "<", lambda p: p.state),
]
DROP_ORDER = ["STATE", "USER", "MEM%"]   # dropped first when too narrow


def table_layout(width):
    """Fit the columns to `width`; returns (active columns, flex width)."""
    excluded = []
    while True:
        active = [c for c in COLUMNS if c[0] not in excluded]
        fixed = sum(c[1] for c in active if c[1] is not None)
        seps = len(active) - 1
        flex_w = width - 1 - fixed - seps
        if flex_w >= 4 or len(excluded) >= len(DROP_ORDER):
            return active, max(4, flex_w)
        excluded.append(DROP_ORDER[len(excluded)])


# =============================================================================
#  Application
# =============================================================================

class App:
    def __init__(self, interval=1.0, force_ps=False, force_ascii=False,
                 force_mono=False):
        self.interval = max(0.2, min(float(interval), 10.0))
        self.source = make_source(force_ps)

        self.style = Style(color_requested() and not force_mono)
        # When styling is off we emit zero control codes as well: plain
        # monochrome ASCII everywhere (color-discipline rule).
        self.ansi = self.style.enabled
        self.ascii_only = force_ascii or not self.style.enabled
        self.unicode = (not self.ascii_only
                        and stdout_can_encode("\u2588\u2591\u2502\u25bc"))
        self.fill_ch = "\u2588" if self.unicode else "#"
        self.empty_ch = "\u2591" if self.unicode else "-"
        self.arrow_down = "\u25bc" if self.unicode else "v"
        self.arrow_up = "\u25b2" if self.unicode else "^"

        self.sample_ = Sample()
        self.sample_.multi_core = (self.source.name == "/proc")
        self.width, self.height = 80, 24
        self.sort_key = "c"             # default: CPU% ...
        self.reverse = True             # ... descending
        self.sel_pid = None
        self.sel_index = 0
        self.top = 0
        self.filter_text = ""
        self.mode = "normal"            # normal | filter | confirm
        self.paused = False
        self.running = True
        self.resized = True
        self.cleared = False
        self.message = ""
        self.msg_deadline = 0.0
        self.needs_draw = False
        self.armed = None               # (pid, deadline) after SIGTERM
        self.confirm_pid = None
        self.visible = []
        self.stdin_fd = sys.stdin.fileno()
        self._saved_term = None
        self._tty_ready = False

    # ------------------------------------------------------------- terminal --
    def setup_tty(self):
        if termios is not None and tty is not None:
            try:
                self._saved_term = termios.tcgetattr(self.stdin_fd)
                tty.setcbreak(self.stdin_fd, termios.TCSAFLUSH)
                self._tty_ready = True
            except (termios.error, OSError):
                self._saved_term = None
        if self.ansi:
            self._raw("\x1b[?1049h\x1b[?25l")   # alt screen + hide cursor

    def cleanup_tty(self):
        if self._tty_ready and self._saved_term is not None:
            try:
                termios.tcsetattr(self.stdin_fd, termios.TCSAFLUSH,
                                  self._saved_term)
            except (termios.error, OSError):
                pass
            self._tty_ready = False
        if self.ansi:
            self._raw("\x1b[0m\x1b[?25h\x1b[?1049l")
        else:
            self._raw("\n")

    def _raw(self, text):
        try:
            sys.stdout.write(text)
            sys.stdout.flush()
        except (OSError, ValueError):
            pass

    def update_size(self):
        w, h = shutil.get_terminal_size((80, 24))
        self.resized = False
        if (w, h) != (self.width, self.height):
            self.width, self.height = w, h
            self.cleared = False

    # ---------------------------------------------------------------- input --
    @staticmethod
    def decode_keys(data):
        """Yield key tokens from a raw stdin chunk, parsing CSI sequences."""
        i, n = 0, len(data)
        while i < n:
            b = data[i]
            if b == 0x1B:                                   # ESC ...
                if i + 2 < n and data[i + 1] == 0x5B:       # ESC [
                    j = i + 2
                    while j < n and not (0x40 <= data[j] <= 0x7E):
                        j += 1
                    if j < n:
                        final = data[j]
                        params = bytes(data[i + 2:j])
                        if final == 0x41:
                            yield "up"
                        elif final == 0x42:
                            yield "down"
                        elif final == 0x43:
                            yield "right"
                        elif final == 0x44:
                            yield "left"
                        elif final == 0x48:
                            yield "home"
                        elif final == 0x46:
                            yield "end"
                        elif final == 0x7E:                 # <n>~ keys
                            if params.startswith(b"5"):
                                yield "pgup"
                            elif params.startswith(b"6"):
                                yield "pgdn"
                        i = j + 1
                        continue
                yield "esc"
                i += 1
                continue
            if b == 3:
                yield "ctrl-c"
            elif b in (13, 10):
                yield "enter"
            elif b in (127, 8):
                yield "bs"
            elif b == 9:
                yield "tab"
            elif 32 <= b < 127:
                yield chr(b)
            i += 1

    def read_keys(self, timeout):
        """Non-blocking: all pending bytes, '' when none, 'eof' on stdin EOF."""
        try:
            ready, _, _ = select.select([self.stdin_fd], [], [], timeout)
        except (OSError, ValueError):
            return "eof"
        if not ready:
            return ""
        chunks, total = [], 0
        while True:
            try:
                d = os.read(self.stdin_fd, 512)
            except InterruptedError:
                continue
            except OSError:
                return "eof"
            if not d:
                return "eof"
            chunks.append(d)
            total += len(d)
            more, _, _ = select.select([self.stdin_fd], [], [], 0)
            if not more or total > 4096:
                break
        return b"".join(chunks)

    def feed(self, data):
        """Push a pending byte block through the key handler."""
        for key in self.decode_keys(data):
            self.handle_key(key)
            if not self.running or self.paused:
                return      # rest of the burst waits for the overlay to close

    def handle_key(self, key):
        self.needs_draw = True           # every binding repaints promptly
        if self.mode == "confirm":
            if key in ("y", "Y"):
                self.send_signal(self.confirm_pid, signal.SIGTERM)
                self.armed = (self.confirm_pid, time.monotonic() + 3.0)
                self.flash("SIGTERM sent to %s" % self.confirm_pid)
            else:
                self.flash("kill cancelled")
            self.mode = "normal"
            self.confirm_pid = None
            return

        if self.mode == "filter":
            if key == "esc":
                self.filter_text = ""
                self.mode = "normal"
            elif key == "enter":
                self.mode = "normal"
            elif key == "bs":
                self.filter_text = self.filter_text[:-1]
                if not self.filter_text:
                    self.mode = "normal"
            elif len(key) == 1 and key.isprintable():
                self.filter_text += key
            else:
                return
            self.sel_index = 0
            self.top = 0
            return

        # ---- normal mode ----
        if key in ("q", "ctrl-c"):
            self.running = False
        elif key in ("h", "?"):
            self.paused = True
            self.needs_draw = True         # repaint immediately with overlay
        elif key == "/":
            self.mode = "filter"
            self.filter_text = ""
        elif key == "k":
            if (self.armed and self.armed[0] == self.sel_pid
                    and time.monotonic() < self.armed[1]):
                self.send_signal(self.sel_pid, signal.SIGKILL)
                self.flash("SIGKILL sent to %s" % self.sel_pid)
                self.armed = None
            elif self.sel_pid is not None:
                self.mode = "confirm"
                self.confirm_pid = self.sel_pid
        elif key in SORTS:
            self.sort_key = key
            self.reverse = True            # fresh sort keys start descending
            self.sel_index = 0
            self.top = 0
        elif key == "r":
            self.reverse = not self.reverse
        elif key in ("up", "down", "pgup", "pgdn"):
            page = max(1, self.table_rows() - 1)
            if key == "up":
                self.sel_index -= 1
            elif key == "down":
                self.sel_index += 1
            elif key == "pgup":
                self.sel_index -= page
            else:
                self.sel_index += page
            self.sel_index = max(0,
                                 min(self.sel_index,
                                     max(0, len(self.visible) - 1)))
        elif key == "esc" and self.filter_text:
            self.filter_text = ""

    def flash(self, msg, secs=2.5):
        self.message = msg
        self.msg_deadline = time.monotonic() + secs

    def send_signal(self, pid, sig):
        if pid is None:
            return
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            self.flash("pid %s already gone" % pid)
        except PermissionError:
            self.flash("permission denied signalling %s" % pid)
        except OSError as exc:
            self.flash("kill failed: %s" % exc)

    # -------------------------------------------------------------- sampling -
    def do_sample(self):
        try:
            self.sample_ = self.source.sample()
        except Exception as exc:            # transient read errors: survive
            self.flash("sample failed: %s" % exc, 1.0)

    def visible_procs(self):
        procs = self.sample_.procs
        if self.filter_text:
            needle = self.filter_text.lower()
            procs = [p for p in procs
                     if needle in p.name.lower()
                     or needle in p.cmdline.lower()
                     or needle in str(p.pid)]
        _, keyfn = SORTS[self.sort_key]
        # sorted() is stable: equal keys keep their scan order.
        return sorted(procs, key=keyfn, reverse=self.reverse)

    # --------------------------------------------------------------- layout --
    def too_small(self):
        return self.width < 40 or self.height < 10

    def bars_max_rows(self):
        return max(1, min(8, self.height - 9))

    def bars_cols(self):
        """Column count for the per-core bar grid that fits the width.

        Never forces more columns than fit: if the grid cannot show every
        core within the row budget, extras are clipped and counted by the
        "(+N more)" note instead.
        """
        if not self.sample_.multi_core:
            return 1
        n = 1 + len(self.sample_.per_core)
        max_rows = self.bars_max_rows()
        for bar_len in (10, 6):
            cell = 15 + bar_len                 # "cpu0 [#..#] 100.0 "
            cols = max(1, min(self.width // cell, 8))
            if -(-n // cols) <= max_rows:
                return min(cols, n)
        return max(1, min(self.width // 21, 8, n))

    def bar_len(self):
        cols = max(1, self.bars_cols())
        cell = self.width // cols
        return max(4, min(10, cell - 15))

    def bars_rows(self):
        if not self.sample_.multi_core:
            return 1
        n = 1 + len(self.sample_.per_core)
        return max(1, min(-(-n // max(1, self.bars_cols())),
                          self.bars_max_rows()))

    def table_rows(self):
        return max(1, self.height - 2 - self.bars_rows() - 1 - 1)

    # ------------------------------------------------------------- rendering -
    def render(self):
        """One frame as exactly `height` rows of exactly `width` columns.

        Contains no cursor-movement codes; the interactive loop prepends
        \x1b[H so --once output stays pipe-friendly.
        """
        if self.too_small():
            return self._frame_too_small()
        if self.paused:
            return self._frame_overlay()

        self.visible = self.visible_procs()
        self.sync_selection()

        s = self.sample_
        out = [self._header_line1(), self._header_line2()]
        out.extend(self._bar_lines())
        out.append(self._table_header_row())
        rows = self.table_rows()
        self.clamp_view(rows)
        shown = self.visible[self.top:self.top + rows]
        for i, p in enumerate(shown):
            out.append(self._proc_row(p, self.top + i == self.sel_index))
        out.extend(" " * self.width for _ in range(rows - len(shown)))
        out.append(self._footer_line())
        while len(out) < self.height:
            out.append(" " * self.width)
        return out[:self.height]

    def render_and_write(self):
        frame = self.render()
        prefix = ""
        sep = "\r\n"
        if self.ansi:
            prefix = "\x1b[H"
            if not self.cleared:
                prefix = "\x1b[2J\x1b[H"
                self.cleared = True
        self._raw(prefix + sep.join(frame) + ("" if self.ansi else "\n"))

    def _seg_line(self, segs, gap="   "):
        """segs: [(text, codes tuple)] joined by `gap`, padded to width."""
        parts = []
        for i, (text, codes) in enumerate(segs):
            chunk = (gap if i else "") + sanitize(text, self.ascii_only)
            parts.append(self.style.sgr(chunk, *codes))
        return self._pad_styled("".join(parts))

    def _header_line1(self):
        s = self.sample_
        running = sum(1 for p in s.procs if p.state[:1] == "R")
        load = " ".join("%.2f" % x for x in s.load[:3]) if s.load else "n/a"
        segs = [(" ProcScope ", (BOLD, CYAN)),
                ("up " + fmt_uptime(s.uptime), (DIM,)),
                ("load " + load, (BOLD,)),
                ("procs R:%d/%d" % (running, len(s.procs)),
                 (YELLOW,) if running >= 8 else (GREEN,)),
                ]
        if self.source.name != "/proc":
            segs.append(("[ps fallback]", (MAGENTA,)))
        segs.append(("pid %d" % os.getpid(), (DIM,)))
        return self._seg_line(segs)

    def _header_line2(self):
        s = self.sample_
        if s.mem_total_kb > 0:
            used = s.mem_used_kb if s.mem_used_kb >= 0 else 0
            pct = 100.0 * used / s.mem_total_kb
            segs = [(" Mem  " + fmt_kb(s.mem_total_kb) + " total", (BOLD,)),
                    ("  " + fmt_kb(used) + " used (%d%%)" % pct,
                     (usage_color(pct),)),
                    ("  " + fmt_kb(s.mem_avail_kb) + " avail", (DIM,))]
        else:
            segs = [(" Mem  n/a", (DIM,))]
        segs.append(("  CPU %5.1f%%" % s.total_cpu,
                     (usage_color(s.total_cpu),)))
        return self._seg_line(segs, gap="")

    def _bar_lines(self):
        s = self.sample_
        if not s.multi_core:
            blen = max(4, min(60, self.width - 22))
            return [self._pad_styled(
                self._bar_cell("cpu", s.total_cpu, blen))]
        items = [("cpu", s.total_cpu)]
        for i, u in enumerate(s.per_core):
            items.append(("cpu%d" % i, u))
        cols = max(1, self.bars_cols())
        blen = self.bar_len()
        rows = self.bars_rows()
        cap = cols * rows
        total = len(items)
        hidden = max(0, total - cap)
        if hidden:                    # keep one slot on the last line free
            items = items[:cap - 1]
        cells = [self._bar_cell(label, u if u is not None else 0.0, blen)
                 for label, u in items]
        if hidden:
            extra = total - len(items)
            cells.append(self.style.sgr("(+%d more)" % extra, DIM))
        lines = []
        for r in range(rows):
            chunk = cells[r * cols:(r + 1) * cols]
            if not chunk:
                break
            lines.append(self._pad_styled(" ".join(chunk)))
        return lines

    def _bar_cell(self, label, pct, blen):
        filled = int(round(pct / 100.0 * blen))
        bar = self.fill_ch * filled + self.empty_ch * (blen - filled)
        col = usage_color(pct)
        return (self.style.sgr("%-5s [" % label, DIM)
                + self.style.sgr(bar, col, BOLD)
                + self.style.sgr("] %5.1f" % pct, col))

    def _pad_styled(self, styled):
        vis = visible_len(styled)
        if vis > self.width:
            return trim_styled(styled, self.width)
        return styled + " " * (self.width - vis)

    def _table_header_row(self):
        active, flex_w = table_layout(max(4, self.width - 2))
        sort_title = SORTS[self.sort_key][0]
        parts = []
        for title, w_, align, _ in active:
            cw = flex_w if w_ is None else w_
            if title == sort_title:
                arrow = self.arrow_down if self.reverse else self.arrow_up
                label = pad(truncate(sanitize(title + arrow,
                                              self.ascii_only), cw),
                            cw, align)
                parts.append(self.style.sgr(label, REV, BOLD))
            else:
                parts.append(self.style.sgr(
                    pad(sanitize(title, self.ascii_only), cw, align), BOLD))
        return self._pad_styled("  " + " ".join(parts))

    def _proc_row(self, p, selected):
        active, flex_w = table_layout(max(4, self.width - 2))
        plain_cells, styled_cells = [], []
        for title, w_, align, getter in active:
            cw = flex_w if w_ is None else w_
            if title in ("CPU%", "MEM%"):
                val = getter(p)
                txt = "%.1f" % val
                if len(txt) > cw:
                    txt = "%.0f" % val
                codes = ((usage_color(val),) if title == "CPU%"
                         else (CYAN,))
            elif title == "STATE":
                st = getter(p)
                txt = st
                if not self.ansi:
                    codes = ()
                elif st[:1] == "R":
                    codes = (BOLD, YELLOW)
                elif st[:1] == "D":
                    codes = (RED,)
                elif st[:1] == "Z":
                    codes = (DIM,)
                else:
                    codes = ()
            else:
                txt = truncate(sanitize(getter(p), self.ascii_only), cw)
                codes = ()
            text = pad(txt, cw, align)
            plain_cells.append(text)
            if codes and self.ansi:
                styled_cells.append(self.style.sgr(text, *codes))
            else:
                styled_cells.append(text)
        gutter = ">" if selected else " "
        gutter += " "
        if selected and self.ansi:
            # reverse the whole row (gutter, gaps and padding included)
            plain = gutter + " ".join(plain_cells)
            plain = plain[:self.width].ljust(self.width)
            return self.style.sgr(plain, REV, BOLD)
        return self._pad_styled(gutter + " ".join(styled_cells))

    def _footer_line(self):
        now = time.monotonic()
        if self.message and now > self.msg_deadline:
            self.message = ""
        if self.armed and now > self.armed[1]:
            self.armed = None

        if self.mode == "filter":
            left = (" /%s_" % self.filter_text, (BOLD, MAGENTA))
            right = ("  live filter: enter keeps, esc clears", (DIM,))
        elif self.mode == "confirm":
            sel = self.current_selection()
            who = ("%s %s" % (sel.pid, truncate(sel.name, 12))
                   if sel else "?")
            left = (" k kill %s? [y/N] " % who, (BOLD, RED))
            right = ("  y sends SIGTERM", (DIM,))
        elif self.armed:
            left = (" armed: k again within %ds SIGKILLs %d "
                    % (max(0, int(self.armed[1] - now)), self.armed[0]),
                    (BOLD, RED))
            right = ("", ())
        elif self.message:
            left = (" %s " % self.message, (BOLD, YELLOW))
            right = ("", ())
        else:
            flt = (" /%s " % self.filter_text) if self.filter_text else ""
            arrow = self.arrow_down if self.reverse else self.arrow_up
            left = (" %ssort %s%s  r reverse  h help  q quit "
                    % (flt, SORTS[self.sort_key][0], arrow), ())
            right = (" " + SIGNOFF_SHORT, (DIM,))
        return self._seg_line([left, right], gap="")

    # ------------------------------------------------------------- selection -
    def current_selection(self):
        if 0 <= self.sel_index < len(self.visible):
            return self.visible[self.sel_index]
        return None

    def sync_selection(self):
        vis = self.visible
        if not vis:
            self.sel_pid = None
            self.sel_index = 0
            return
        idx = -1
        if self.sel_pid is not None:
            for i, p in enumerate(vis):
                if p.pid == self.sel_pid:
                    idx = i
                    break
        if idx < 0:
            idx = self.sel_index
        idx = max(0, min(idx, len(vis) - 1))
        self.sel_index = idx
        self.sel_pid = vis[idx].pid

    def clamp_view(self, rows):
        if self.sel_index < self.top:
            self.top = self.sel_index
        elif self.sel_index >= self.top + rows:
            self.top = self.sel_index - rows + 1
        self.top = max(0, min(self.top,
                              max(0, len(self.visible) - rows)))

    # -------------------------------------------------------- small + help ---
    def _frame_too_small(self):
        msg = "terminal too small - need >= 40x10"
        mid = self.height // 2
        rows = []
        for r in range(self.height):
            if r == mid:
                left = max(0, (self.width - len(msg)) // 2)
                line = " " * left + msg
                line = line + " " * max(0, self.width - len(line))
                rows.append(self.style.sgr(line, REV, BOLD))
            else:
                rows.append(" " * self.width)
        return rows

    HELP = [
        ("ProcScope key bindings", (BOLD, CYAN)),
        ("", ()),
        ("  c          sort by CPU%        (default descending)", ()),
        ("  m          sort by MEM%", ()),
        ("  n          sort by NAME        (case-insensitive)", ()),
        ("  p          sort by PID", ()),
        ("  r          toggle ascending / descending", ()),
        ("  Up/Down    select a process row", ()),
        ("  PgUp/PgDn  jump one page through the table", ()),
        ("  /          filter by name or cmdline (live)", ()),
        ("  Esc        clear the filter", ()),
        ("  k          SIGTERM the selected process;", ()),
        ("             press again within 3s => SIGKILL", ()),
        ("  h / ?      this help (pauses updates)", ()),
        ("  q / Ctrl-C quit and restore the terminal", ()),
        ("", ()),
        ("  " + AUTHOR_SIGNOFF, (DIM,)),
        ("  any key closes this overlay", (DIM,)),
    ]

    def _frame_overlay(self):
        w, h = self.width, self.height
        lines = [(sanitize(t, self.ascii_only), c) for t, c in self.HELP]
        box_w = min(max(len(t) for t, _ in lines) + 4, w)
        box_h = len(lines) + 2
        top = max(0, (h - box_h) // 2)
        left = max(0, (w - box_w) // 2)
        if self.unicode:
            tl, tr, bl, br, hr, vr = "┌┐└┘─│"
        else:
            tl, tr, bl, br, hr, vr = "++++-|"
        box = [tl + hr * (box_w - 2) + tr]
        for text, codes in lines:
            body = " " + truncate(text, box_w - 4).ljust(box_w - 4) + " "
            box.append(vr + self.style.sgr(body, *codes) + vr)
        box.append(bl + hr * (box_w - 2) + br)
        rows = []
        for r in range(h):
            if top <= r < top + len(box) and len(box[0]) <= w:
                rows.append(self._pad_styled(" " * left + box[r - top]))
            else:
                rows.append(" " * w)
        return rows


# =============================================================================
#  Main loop
# =============================================================================

def install_signals(app):
    def on_winch(signum, frame):
        app.resized = True

    def on_quit(signum, frame):
        app.running = False

    winch = getattr(signal, "SIGWINCH", None)
    if winch is not None:
        try:
            signal.signal(winch, on_winch)
        except (ValueError, OSError):
            pass
    for sig in (getattr(signal, "SIGINT", None),
                getattr(signal, "SIGTERM", None)):
        if sig is not None:
            try:
                signal.signal(sig, on_quit)
            except (ValueError, OSError):
                pass


def run_interactive(app):
    app.update_size()
    install_signals(app)
    try:
        app.setup_tty()
    except Exception:
        app.cleanup_tty()
        raise
    try:
        app.do_sample()                     # first frame: CPU deltas are 0
        app.needs_draw = True
        next_t = time.monotonic()
        while app.running:
            timeout = 0.2 if app.paused else \
                min(max(next_t - time.monotonic(), 0.0), 0.2)
            data = app.read_keys(timeout)
            if data == "eof":
                break
            if app.paused:
                if data:                    # any key dismisses the overlay
                    app.paused = False
                    app.needs_draw = True
            elif data:
                app.feed(data)              # every key typed so far
                while app.running:
                    extra = app.read_keys(0)
                    if not extra:
                        break
                    if extra == "eof":
                        app.running = False
                        break
                    app.feed(extra)
            if app.resized:
                app.update_size()
                app.needs_draw = True
            if not app.paused:
                now = time.monotonic()
                if now >= next_t - 0.005:
                    app.do_sample()
                    next_t = now + app.interval
                    app.needs_draw = True
            if app.needs_draw:
                app.render_and_write()
                app.needs_draw = False
    except KeyboardInterrupt:
        pass                                   # Ctrl-C behaves like q
    finally:
        app.cleanup_tty()
    return 0


def run_once(app):
    """--once: one complete frame, zero cursor-movement codes, exit 0."""
    if not sys.stdout.isatty():
        # piped: plain monochrome ASCII, no ANSI at all
        app.style.enabled = False
        app.ansi = False
        app.ascii_only = True
        app.unicode = False
    if not app.unicode:
        app.fill_ch, app.empty_ch = "#", "-"
        app.arrow_down, app.arrow_up = "v", "^"
    else:
        app.fill_ch, app.empty_ch = "\u2588", "\u2591"
        app.arrow_down, app.arrow_up = "\u25bc", "\u25b2"
    if sys.stdout.isatty():
        w, h = shutil.get_terminal_size((80, 24))
    else:
        w, h = 80, 24
    app.width, app.height = w, min(h, 30)
    app.do_sample()
    time.sleep(0.4)                            # window so CPU% is meaningful
    app.do_sample()
    try:
        sys.stdout.write("\n".join(app.render()) + "\n")
    except BrokenPipeError:
        return 0
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="procscope",
        description="ProcScope — a top-like process monitor in pure stdlib. "
                    + AUTHOR_SIGNOFF,
        epilog="Primary data source: /proc on Linux; automatic `ps` fallback "
               "elsewhere. Honors NO_COLOR and TERM=dumb. Press h inside "
               "the app for the full key list.")
    parser.add_argument("--once", action="store_true",
                        help="print one complete frame to stdout and exit "
                             "(pipe-friendly: no cursor-movement codes)")
    parser.add_argument("--interval", type=float, default=1.0, metavar="SEC",
                        help="live refresh period in seconds (default 1.0)")
    parser.add_argument("--force-ps", action="store_true",
                        help="use the ps fallback even when /proc exists")
    parser.add_argument("--no-color", action="store_true",
                        help="force monochrome ASCII rendering")
    parser.add_argument("--ascii", action="store_true",
                        help="force ASCII glyphs instead of Unicode blocks")
    parser.add_argument("--about", action="store_true",
                        help="print the sign-off line and exit")
    args = parser.parse_args(argv)

    if args.about:
        sys.stdout.write(AUTHOR_SIGNOFF + "\n")
        return 0

    force_ps = args.force_ps or bool(os.environ.get("PROCSCOPE_FORCE_PS"))
    interactive = sys.stdout.isatty() and sys.stdin.isatty()

    app = App(args.interval, force_ps=force_ps, force_ascii=args.ascii,
              force_mono=args.no_color)
    if args.once or not interactive:
        return run_once(app)
    return run_interactive(app)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        os._exit(0)
    except KeyboardInterrupt:
        sys.exit(0)
