#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ProcScope - a self-contained, top-like process monitor.

Standard library only.  On Linux all data comes from /proc; when /proc/stat
cannot be read the program automatically falls back to parsing `ps` output.

Produced: 2026-10-30 00:05 CET
Author / model: DeepSeek V4.1 Flash (OpenCode agent)

Usage:
    python3 procscope.py             # interactive full-screen TUI
    python3 procscope.py --once      # one plain snapshot, pipe friendly
"""

import argparse
import os
import select
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

try:  # Unix only; --once still works on platforms without these modules.
    import termios
    import tty
except ImportError:  # pragma: no cover - non-Unix
    termios = None
    tty = None

try:
    import pwd
except ImportError:  # pragma: no cover - non-Unix
    pwd = None


APP_NAME = "ProcScope"
APP_VERSION = "1.0"
PRODUCED_AT = "2026-10-30 00:05 CET"
MODEL_NAME = "DeepSeek V4.1 Flash"
RESET = "\x1b[0m"
PROC_ROOT = "/proc"
PROC_STAT = "/proc/stat"
PROC_MEMINFO = "/proc/meminfo"
PS_FORMAT = "pid=,user=,comm=,%cpu=,%mem=,stat="
PS_COMMANDS = (
    ["ps", "-Ao", PS_FORMAT],
    ["ps", "-A", "-o", PS_FORMAT],
)
MIN_WIDTH = 40
MIN_HEIGHT = 10


# ---------------------------------------------------------------------------
# Small text / styling helpers
# ---------------------------------------------------------------------------


def clean_text(value, ascii_only=False):
    """Make untrusted process text safe for a terminal."""
    if value is None:
        return ""
    chars = []
    for ch in str(value):
        if ch in "\r\n\t" or ch == "\x1b" or ch == "\x7f":
            chars.append(" ")
        elif not ch.isprintable():
            chars.append(" ")
        else:
            chars.append(ch)
    text = "".join(chars).strip()
    if ascii_only:
        text = text.encode("ascii", "replace").decode("ascii")
    return text


def fit_text(value, width, align="left", ascii_only=False):
    """Ellipsize and pad a string to exactly *width* cells."""
    if width <= 0:
        return ""
    text = clean_text(value, ascii_only)
    if len(text) > width:
        text = ("~" if width == 1 else text[: width - 1] + "~")
    if align == "right":
        return text.rjust(width)
    return text.ljust(width)


def cap_percent(value, limit=9999.9):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if number != number:  # NaN
        return 0.0
    return max(0.0, min(limit, number))


def fmt_percent(value):
    return "{:.1f}".format(cap_percent(value))


def fmt_bytes(value):
    if value is None:
        return "n/a"
    number = float(value)
    units = ("B", "K", "M", "G", "T", "P")
    index = 0
    while number >= 1024.0 and index < len(units) - 1:
        number /= 1024.0
        index += 1
    if index == 0:
        return "{:.0f}{}".format(number, units[index])
    return "{:.1f}{}".format(number, units[index])


def fmt_load(load):
    if not load:
        return "load n/a"
    return "load " + " ".join("{:.2f}".format(float(item)) for item in load)


def fmt_memory(used, total):
    if total is None:
        return "mem n/a"
    if used is None:
        return "mem ?/{}".format(fmt_bytes(total))
    percent = (100.0 * used / total) if total else 0.0
    return "mem {}/{} ({:.0f}%)".format(
        fmt_bytes(used), fmt_bytes(total), max(0.0, min(100.0, percent))
    )


def ceil_div(number, divisor):
    if divisor <= 0:
        return 0
    return (number + divisor - 1) // divisor


class Theme:
    """The single place where ANSI styling codes are produced."""

    def __init__(self, enabled):
        self.enabled = bool(enabled)
        self.bold = self._code(1)
        self.dim = self._code(2)
        self.reverse = self._code(7)
        self.title = self._code(1, 36)
        self.header = self._code(1, 37)
        self.sorted_header = self._code(1, 7)
        self.selected = self._code(7)
        self.green = self._code(32)
        self.yellow = self._code(33)
        self.red = self._code(31)
        self.cyan = self._code(36)
        self.flash = self._code(1, 33)
        self.overlay_border = self._code(1, 36)

    def _code(self, *numbers):
        if not self.enabled:
            return ""
        return "\x1b[" + ";".join(str(item) for item in numbers) + "m"

    def load_style(self, usage):
        if usage < 50.0:
            return self.green
        if usage <= 80.0:
            return self.yellow
        return self.red


class Canvas:
    """A tiny cell buffer.  Rendered rows are joined into one write."""

    def __init__(self, width, height):
        self.width = max(1, int(width))
        self.height = max(1, int(height))
        self.rows = [
            [[" ", ""] for _ in range(self.width)] for _ in range(self.height)
        ]

    def fill(self, char=" ", style=""):
        self.rows = [[[char, style] for _ in range(self.width)] for _ in range(self.height)]

    def put(self, x, y, text, style=""):
        if y < 0 or y >= self.height:
            return
        for offset, char in enumerate(str(text)):
            column = x + offset
            if 0 <= column < self.width:
                self.rows[y][column] = [char, style]

    def fill_rect(self, x, y, width, height, style):
        for row in range(y, y + height):
            if row < 0 or row >= self.height:
                continue
            for column in range(x, x + width):
                if 0 <= column < self.width:
                    self.rows[row][column] = [" ", style]

    def render(self):
        lines = []
        for row in self.rows:
            parts = []
            run = []
            run_style = ""
            for char, style in row:
                if style != run_style:
                    if run:
                        text = "".join(run)
                        parts.append((run_style + text + RESET) if run_style else text)
                    run = [char]
                    run_style = style
                else:
                    run.append(char)
            if run:
                text = "".join(run)
                parts.append((run_style + text + RESET) if run_style else text)
            lines.append("".join(parts))
        return lines


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class CpuInfo:
    name: str
    usage: float


@dataclass
class ProcessInfo:
    pid: int
    user: str
    name: str
    cpu: float
    mem: float
    state: str
    rss: int = 0


@dataclass
class Snapshot:
    cpus: List[CpuInfo]
    procs: List[ProcessInfo]
    mem_total: Optional[int]
    mem_used: Optional[int]
    load: Optional[Tuple[float, float, float]]
    running: int
    total: int
    mode: str
    sampled: float
    error: str = ""


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def parse_cpu_line(line):
    """Parse one /proc/stat cpu line into (label, first eight counters)."""
    fields = line.split()
    if not fields or not fields[0].startswith("cpu"):
        return None
    try:
        values = [int(item) for item in fields[1:9]]
    except ValueError:
        return None
    while len(values) < 8:
        values.append(0)
    return fields[0], values


def cpu_usage(previous, current):
    """CPU busy fraction from two counter vectors.

    With no previous vector, use the counters accumulated since boot.  This
    makes the very first frame useful while subsequent frames use deltas.
    """
    if len(current) < 5:
        return 0.0
    if previous is not None and len(previous) >= len(current):
        deltas = [max(0, cur - old) for old, cur in zip(previous, current)]
        total = sum(deltas)
        idle = deltas[3] + deltas[4]
    else:
        total = sum(current)
        idle = current[3] + current[4]
    if total <= 0:
        return 0.0
    usage = 100.0 * (1.0 - float(idle) / float(total))
    return max(0.0, min(100.0, usage))


def parse_pid_stat(line):
    """Parse /proc/<pid>/stat robustly.

    The comm field is enclosed in parentheses and may itself contain spaces,
    parentheses and even a ')'.  Find the last ')' before splitting fields.
    Returns (pid, comm, state, utime, stime, starttime, rss_pages) or None.
    """
    open_paren = line.find("(")
    close_paren = line.rfind(")")
    if open_paren < 0 or close_paren <= open_paren:
        return None
    try:
        pid = int(line[:open_paren].strip())
    except ValueError:
        return None
    comm = line[open_paren + 1 : close_paren]
    fields = line[close_paren + 1 :].split()
    if len(fields) < 13:
        return None
    try:
        state = fields[0]
        utime = int(fields[11])
        stime = int(fields[12])
        starttime = int(fields[19]) if len(fields) > 19 else 0
        rss_pages = int(fields[21]) if len(fields) > 21 else None
    except ValueError:
        return None
    return pid, comm, state, utime, stime, starttime, rss_pages


def read_cmdline(pid):
    try:
        with open("{}/{}/cmdline".format(PROC_ROOT, pid), "rb") as handle:
            data = handle.read(4096)
    except OSError:
        return ""
    pieces = [piece.decode("utf-8", "replace") for piece in data.split(b"\0") if piece]
    return clean_text(" ".join(pieces))[:200]


def read_status(pid):
    info = {}
    try:
        with open("{}/{}/status".format(PROC_ROOT, pid), "r", errors="replace") as handle:
            for line in handle:
                key, separator, rest = line.partition(":")
                if separator and key in ("VmRSS", "Uid"):
                    info[key] = rest.split()
    except OSError:
        pass
    return info


# ---------------------------------------------------------------------------
# Collectors
# ---------------------------------------------------------------------------


class ProcCollector:
    """Collects a Snapshot from /proc, or from `ps` when /proc is unavailable."""

    def __init__(self):
        self.mode = "proc"
        self.prev_ticks = {}
        self.prev_cpu = {}
        self.prev_time = None
        self.user_cache = {}
        self.last_error = ""
        self.clk_tck = self._sysconf("SC_CLK_TCK", 100)
        self.page_size = self._sysconf("SC_PAGE_SIZE", 4096)
        self.cpu_count = os.cpu_count() or 1
        self._mem_total_cache = None
        self._mem_total_checked = False
        self._probe_proc()

    @staticmethod
    def _sysconf(name, default):
        try:
            return int(os.sysconf(name))
        except (ValueError, OSError, AttributeError):
            return default

    def _probe_proc(self):
        try:
            with open(PROC_STAT, "r", errors="replace") as handle:
                first = handle.readline()
            if not first.startswith("cpu"):
                raise OSError("unrecognised /proc/stat")
            self.mode = "proc"
        except OSError:
            self.mode = "ps"

    # -- public -----------------------------------------------------------

    def sample(self):
        wall = time.time()
        monotonic = time.monotonic()
        if self.mode == "proc":
            try:
                return self._sample_proc(monotonic, wall)
            except (OSError, ValueError):
                # /proc vanished or became unreadable: switch for good.
                self.mode = "ps"
                self.prev_ticks.clear()
                self.prev_cpu.clear()
                self.prev_time = None
        return self._sample_ps(wall)

    # -- /proc ------------------------------------------------------------

    def _sample_proc(self, monotonic, wall):
        with open(PROC_STAT, "r", errors="replace") as handle:
            stat_text = handle.read()

        cpus = []
        current_cpu = {}
        for line in stat_text.splitlines():
            parsed = parse_cpu_line(line)
            if parsed is None:
                continue
            label, values = parsed
            usage = cpu_usage(self.prev_cpu.get(label), values)
            cpus.append(CpuInfo(label, usage))
            current_cpu[label] = values
        self.prev_cpu = current_cpu
        if not cpus:
            raise OSError("no cpu lines in /proc/stat")

        mem_total, mem_used = self._read_meminfo()
        elapsed = 0.0
        if self.prev_time is not None:
            elapsed = max(0.0, monotonic - self.prev_time)
        procs = self._scan_procs(elapsed, mem_total)
        self.prev_time = monotonic

        running = sum(1 for proc in procs if proc.state.startswith("R"))
        load = self._load_average()
        return Snapshot(
            cpus=cpus,
            procs=procs,
            mem_total=mem_total,
            mem_used=mem_used,
            load=load,
            running=running,
            total=len(procs),
            mode="proc",
            sampled=wall,
        )

    def _scan_procs(self, elapsed, mem_total):
        entries = []
        try:
            with os.scandir(PROC_ROOT) as iterator:
                for entry in iterator:
                    if entry.name.isdigit():
                        entries.append(entry)
        except OSError:
            raise
        entries.sort(key=lambda item: int(item.name))

        procs = []
        new_ticks = {}
        for entry in entries:
            try:
                pid = int(entry.name)
            except ValueError:
                continue
            try:
                with open(
                    "{}/{}/stat".format(PROC_ROOT, pid), "r", errors="replace"
                ) as handle:
                    line = handle.read()
            except OSError:
                # The process disappeared between the scan and the read.
                continue

            parsed = parse_pid_stat(line)
            if parsed is None:
                continue
            (
                parsed_pid,
                comm,
                state,
                utime,
                stime,
                starttime,
                rss_pages,
            ) = parsed

            ticks = utime + stime
            previous = self.prev_ticks.get(pid)
            cpu = 0.0
            if previous is not None and previous[1] == starttime and elapsed > 0.0:
                delta_ticks = ticks - previous[0]
                if delta_ticks > 0:
                    cpu = 100.0 * delta_ticks / (self.clk_tck * elapsed)
            new_ticks[pid] = (ticks, starttime)

            status = None
            if rss_pages is not None and rss_pages >= 0:
                rss = rss_pages * self.page_size
            else:
                status = read_status(pid)
                rss = self._status_rss(status)

            uid = None
            try:
                uid = entry.stat(follow_symlinks=False).st_uid
            except OSError:
                if status is None:
                    status = read_status(pid)
                uid = self._status_uid(status)

            user = self._username(uid)
            name = clean_text(comm)
            if not name:
                name = read_cmdline(pid)
            if not name:
                name = "?"

            mem = (100.0 * rss / mem_total) if mem_total else 0.0
            procs.append(
                ProcessInfo(
                    pid=pid,
                    user=user,
                    name=name,
                    cpu=cpu,
                    mem=mem,
                    state=clean_text(state) or "?",
                    rss=rss,
                )
            )

        self.prev_ticks = new_ticks
        return procs

    @staticmethod
    def _status_rss(status):
        values = status.get("VmRSS", []) if status else []
        try:
            return int(values[0]) * 1024
        except (IndexError, ValueError):
            return 0

    @staticmethod
    def _status_uid(status):
        values = status.get("Uid", []) if status else []
        try:
            return int(values[0])
        except (IndexError, ValueError):
            return None

    def _username(self, uid):
        if uid is None:
            return "?"
        if uid in self.user_cache:
            return self.user_cache[uid]
        if pwd is None:
            name = str(uid)
        else:
            try:
                name = pwd.getpwuid(uid).pw_name
            except (KeyError, OSError):
                name = str(uid)
        name = clean_text(name) or "?"
        self.user_cache[uid] = name
        return name

    def _read_meminfo(self):
        info = {}
        try:
            with open(PROC_MEMINFO, "r", errors="replace") as handle:
                for line in handle:
                    key, separator, rest = line.partition(":")
                    if not separator:
                        continue
                    values = rest.split()
                    if values:
                        try:
                            info[key] = int(values[0])
                        except ValueError:
                            pass
        except OSError:
            return None, None

        total_kb = info.get("MemTotal")
        if not total_kb:
            return None, None
        available_kb = info.get("MemAvailable")
        if available_kb is None:
            available_kb = (
                info.get("MemFree", 0)
                + info.get("Buffers", 0)
                + info.get("Cached", 0)
            )
        total = total_kb * 1024
        used = max(0, total_kb - available_kb) * 1024
        return total, min(total, used)

    @staticmethod
    def _load_average():
        try:
            return os.getloadavg()
        except (AttributeError, OSError):
            return None

    # -- ps fallback ------------------------------------------------------

    def _run_ps(self):
        errors = []
        for command in PS_COMMANDS:
            try:
                result = subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    encoding="utf-8",
                    errors="replace",
                    timeout=5.0,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                errors.append(str(exc))
                continue
            if result.returncode == 0:
                return result.stdout, ""
            message = (result.stderr or "").strip()
            errors.append(message or "exit {}".format(result.returncode))
        return "", "; ".join(errors) or "ps failed"

    def _sample_ps(self, wall):
        output, error = self._run_ps()
        procs = []
        for raw_line in output.splitlines():
            fields = raw_line.split()
            if len(fields) < 6:
                continue
            try:
                pid = int(fields[0])
            except ValueError:
                continue
            user = fields[1]
            state = fields[-1]
            try:
                mem = float(fields[-2])
                cpu = float(fields[-3])
            except ValueError:
                mem = 0.0
                cpu = 0.0
            name = clean_text(" ".join(fields[2:-3]))
            if not name:
                name = "?"
            procs.append(
                ProcessInfo(
                    pid=pid,
                    user=clean_text(user) or "?",
                    name=name,
                    cpu=cap_percent(cpu),
                    mem=cap_percent(mem),
                    state=clean_text(state) or "?",
                )
            )

        aggregate = sum(proc.cpu for proc in procs)
        usage = min(100.0, aggregate / max(1, self.cpu_count))
        mem_total, mem_used = self._system_memory()
        if mem_total and mem_used is None:
            # No SC_AVPHYS_PAGES (notably macOS).  Summed ps %mem is an
            # over-estimate because shared pages count repeatedly, but it is
            # a useful best-effort header and is clamped to the total.
            percent_sum = sum(proc.mem for proc in procs)
            mem_used = int(mem_total * min(100.0, percent_sum) / 100.0)
        running = sum(1 for proc in procs if proc.state.startswith("R"))
        return Snapshot(
            cpus=[CpuInfo("all", usage)],
            procs=procs,
            mem_total=mem_total,
            mem_used=mem_used,
            load=self._load_average(),
            running=running,
            total=len(procs),
            mode="ps",
            sampled=wall,
            error=error if not output else "",
        )

    def _system_memory(self):
        page_size = self._sysconf("SC_PAGE_SIZE", self.page_size)
        if not self._mem_total_checked:
            total = None
            try:
                candidate = int(os.sysconf("SC_PHYS_PAGES")) * page_size
                if candidate > 0:
                    total = candidate
            except (ValueError, OSError, AttributeError):
                total = None
            if total is None:
                # macOS has no SC_PHYS_PAGES; ask sysctl once and cache it.
                try:
                    result = subprocess.run(
                        ["sysctl", "-n", "hw.memsize"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        encoding="utf-8",
                        errors="replace",
                        timeout=2.0,
                    )
                    if result.returncode == 0:
                        candidate = int(result.stdout.strip())
                        if candidate > 0:
                            total = candidate
                except (OSError, ValueError, subprocess.SubprocessError):
                    total = None
            self._mem_total_cache = total
            self._mem_total_checked = True
        total = self._mem_total_cache
        try:
            available = int(os.sysconf("SC_AVPHYS_PAGES")) * page_size
        except (ValueError, OSError, AttributeError):
            available = None
        if available is not None and available <= 0:
            available = None
        if total is None:
            return None, None
        if available is None:
            return total, None
        return total, max(0, min(total, total - available))


# ---------------------------------------------------------------------------
# Interactive UI
# ---------------------------------------------------------------------------


SORT_KEYS = {"c": "cpu", "m": "mem", "n": "name", "p": "pid"}
HEADERS = {
    "pid": "PID",
    "user": "USER",
    "name": "NAME",
    "cpu": "CPU%",
    "mem": "MEM%",
    "state": "STATE",
}
NUMERIC_COLUMNS = ("pid", "cpu", "mem")
HELP_LINES = [
    "ProcScope - key bindings (any key closes)",
    "q / Ctrl-C    quit",
    "h or ?        toggle this help",
    "c m n p       sort by CPU, MEM, NAME, PID",
    "r             reverse the sort direction",
    "Up/Down       move the selected row",
    "PgUp/PgDn     page through the list",
    "/             filter names; Esc clears",
    "k             SIGTERM selected, again SIGKILL",
    "built {} by {}".format(PRODUCED_AT, MODEL_NAME),
]
HELP_COMPACT = [
    "ProcScope keys (any key closes)",
    "q/Ctrl-C quit   h/? help",
    "c/m/n/p sort    r reverse",
    "Up/Down move    PgUp/Dn page",
    "/ filter  Esc clear  k kill",
    "built {} by {}".format(PRODUCED_AT, MODEL_NAME),
]


class ProcScopeUI:
    def __init__(self, collector, interval=1.0):
        self.collector = collector
        self.interval = max(0.1, float(interval))
        self.snapshot = None
        self.sort_key = "cpu"
        self.ascending = False
        self.selected_pid = None
        self.selection_locked = False
        self.offset = 0
        self.page_rows = 10
        self.help_visible = False
        self.filter_text = ""
        self.filter_mode = False
        self.show_selection = True
        self.flash_message = ""
        self.flash_until = 0.0
        self.kill_pid = None
        self.kill_time = 0.0
        self.resized = False
        self.running = True
        self.need_redraw = True
        self.ascii_only = True
        self.theme = Theme(False)
        self.fd = None
        self.saved_attrs = None
        self.old_handlers = {}

    # -- terminal lifecycle ----------------------------------------------

    @staticmethod
    def _detect_color(stream):
        if "NO_COLOR" in os.environ:
            return False
        term = os.environ.get("TERM", "")
        if not term or term.lower() == "dumb":
            return False
        try:
            if not stream.isatty():
                return False
            encoding = getattr(stream, "encoding", None) or "ascii"
            "\u2588".encode(encoding)
        except (UnicodeEncodeError, LookupError, AttributeError):
            return False
        return True

    def _enter_terminal(self):
        self.fd = sys.stdin.fileno()
        self.saved_attrs = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd, termios.TCSANOW)
        attrs = termios.tcgetattr(self.fd)
        if hasattr(termios, "IXON"):
            attrs[3] &= ~termios.IXON
        if hasattr(termios, "ICRNL"):
            attrs[0] &= ~termios.ICRNL
        attrs[6][termios.VMIN] = 1
        attrs[6][termios.VTIME] = 0
        termios.tcsetattr(self.fd, termios.TCSANOW, attrs)
        if not self.ascii_only:
            sys.stdout.write("\x1b[?1049h\x1b[?25l\x1b[2J\x1b[H")
            sys.stdout.flush()

    def _leave_terminal(self):
        if self.saved_attrs is not None and self.fd is not None:
            try:
                termios.tcsetattr(self.fd, termios.TCSADRAIN, self.saved_attrs)
            except Exception:
                pass
            self.saved_attrs = None
        try:
            if not self.ascii_only:
                sys.stdout.write("\x1b[0m\x1b[?25h\x1b[?1049l")
            else:
                sys.stdout.write("\n")
            sys.stdout.flush()
        except (BrokenPipeError, OSError):
            pass

    def _install_signals(self):
        handlers = (
            (getattr(signal, "SIGWINCH", None), self._on_winch),
            (signal.SIGINT, self._on_interrupt),
            (signal.SIGTERM, self._on_interrupt),
        )
        for sig, handler in handlers:
            if sig is None:
                continue
            try:
                self.old_handlers[sig] = signal.getsignal(sig)
                signal.signal(sig, handler)
            except (ValueError, OSError, AttributeError):
                pass

    def _restore_signals(self):
        for sig, handler in self.old_handlers.items():
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError, AttributeError):
                pass
        self.old_handlers = {}

    def _on_winch(self, _signum, _frame):
        self.resized = True
        self.need_redraw = True

    def _on_interrupt(self, _signum, _frame):
        self.running = False

    # -- main loop -------------------------------------------------------

    def run(self):
        if termios is None or tty is None:
            raise RuntimeError("interactive mode requires termios/tty")
        self.ascii_only = not self._detect_color(sys.stdout)
        self.theme = Theme(not self.ascii_only)
        try:
            self._enter_terminal()
            self._install_signals()
            self.snapshot = self.collector.sample()
            self.need_redraw = False
            self._draw()
            next_tick = time.monotonic() + self.interval
            while self.running:
                try:
                    ready, _, _ = select.select([self.fd], [], [], 0.15)
                except InterruptedError:
                    ready = []
                if ready:
                    try:
                        data = os.read(self.fd, 4096)
                    except OSError:
                        data = b""
                    if not data:
                        self.running = False
                    else:
                        self._handle_input(data)
                if self.resized:
                    self.resized = False
                    self.need_redraw = True
                now = time.monotonic()
                if self.running and not self.help_visible and now >= next_tick:
                    self.snapshot = self.collector.sample()
                    next_tick = now + self.interval
                    self.need_redraw = True
                if self.running and self.need_redraw:
                    self.need_redraw = False
                    self._draw()
        finally:
            self._restore_signals()
            self._leave_terminal()
        return 0

    def _draw(self):
        width, height = shutil.get_terminal_size(fallback=(100, 30))
        width = max(1, int(width))
        height = max(1, int(height))
        canvas = self._build_canvas(self.snapshot, width, height)
        lines = canvas.render()
        if self.ascii_only:
            sys.stdout.write("\n".join(lines) + "\n")
        else:
            sys.stdout.write("\x1b[H" + "\r\n".join(lines))
        sys.stdout.flush()

    # -- input -----------------------------------------------------------

    def _handle_input(self, data):
        text = data.decode("utf-8", "ignore")
        if not text:
            return
        if "\x03" in text:
            # Some terminals deliver Ctrl-C as data even with ISIG enabled.
            self.running = False
            return
        if self.help_visible:
            # Any key closes the overlay; consume the whole burst.
            self.help_visible = False
            self.need_redraw = True
            return
        if self.filter_mode:
            self._handle_filter_input(text)
            return

        index = 0
        length = len(text)
        while index < length:
            char = text[index]
            if char == "\x1b":
                if text.startswith("\x1b[A", index) or text.startswith("\x1bOA", index):
                    self._move_selection(-1)
                    index += 3
                elif text.startswith("\x1b[B", index) or text.startswith("\x1bOB", index):
                    self._move_selection(1)
                    index += 3
                elif text.startswith("\x1b[5~", index):
                    self._move_selection(-self.page_rows)
                    index += 4
                elif text.startswith("\x1b[6~", index):
                    self._move_selection(self.page_rows)
                    index += 4
                elif text.startswith("\x1b[H", index) or text.startswith("\x1b[1~", index):
                    self._move_selection(-10 ** 9)
                    index += 3 if text.startswith("\x1b[H", index) else 4
                elif text.startswith("\x1b[F", index) or text.startswith("\x1b[4~", index):
                    self._move_selection(10 ** 9)
                    index += 3 if text.startswith("\x1b[F", index) else 4
                else:
                    if self.filter_text:
                        self.filter_text = ""
                        self.need_redraw = True
                    index += 1
                continue

            if char == "\x03":
                self.running = False
                return
            lower = char.lower()
            if lower == "q":
                self.running = False
                return
            if lower == "h" or char == "?":
                self.help_visible = True
                self.need_redraw = True
                return
            if lower in SORT_KEYS:
                self._set_sort(SORT_KEYS[lower])
            elif lower == "r":
                self.ascending = not self.ascending
                self.need_redraw = True
            elif char == "/":
                self.filter_mode = True
                self.need_redraw = True
            elif lower == "k":
                self._request_kill()
            elif lower == "j":
                self._move_selection(1)
            elif char == "G":
                self._move_selection(10 ** 9)
            elif lower == "g":
                self._move_selection(-10 ** 9)
            index += 1

    def _handle_filter_input(self, text):
        for char in text:
            if char == "\x1b":
                self.filter_text = ""
                self.filter_mode = False
                self.need_redraw = True
                return
            if char in ("\r", "\n"):
                self.filter_mode = False
                self.need_redraw = True
                return
            if char in ("\x7f", "\b"):
                if self.filter_text:
                    self.filter_text = self.filter_text[:-1]
                    self.need_redraw = True
            elif char == "\x03":
                self.running = False
                return
            elif char.isprintable():
                if len(self.filter_text) < 80:
                    self.filter_text += char
                    self.need_redraw = True

    def _set_sort(self, key):
        if key != self.sort_key:
            self.sort_key = key
            # CPU/MEM look best largest-first; names and PIDs smallest-first.
            self.ascending = key in ("name", "pid")
            self.need_redraw = True

    def _display_procs(self):
        if self.snapshot is None:
            return []
        procs = self.snapshot.procs
        if self.filter_text:
            needle = self.filter_text.casefold()
            procs = [proc for proc in procs if needle in proc.name.casefold()]
        keys = {
            "cpu": lambda proc: proc.cpu,
            "mem": lambda proc: proc.mem,
            "name": lambda proc: proc.name.casefold(),
            "pid": lambda proc: proc.pid,
        }
        key = keys.get(self.sort_key, keys["cpu"])
        # Python's sort is stable, including with reverse=True.
        return sorted(procs, key=key, reverse=not self.ascending)

    def _move_selection(self, delta):
        procs = self._display_procs()
        if not procs:
            return
        current = 0
        if self.selected_pid is not None:
            for index, proc in enumerate(procs):
                if proc.pid == self.selected_pid:
                    current = index
                    break
        target = max(0, min(len(procs) - 1, current + delta))
        self.selected_pid = procs[target].pid
        self.selection_locked = True
        self.need_redraw = True

    def _request_kill(self):
        procs = self._display_procs()
        if not procs:
            self._flash("no process selected")
            return
        target = None
        for proc in procs:
            if proc.pid == self.selected_pid:
                target = proc
                break
        if target is None:
            target = procs[0]
        now = time.monotonic()
        if target.pid in (0, 1, os.getpid()):
            self._flash("refusing to signal PID {}".format(target.pid))
            return
        if self.kill_pid == target.pid and now - self.kill_time <= 3.0:
            signame = "SIGKILL"
            self.kill_pid = None
        else:
            signame = "SIGTERM"
            self.kill_pid = target.pid
            self.kill_time = now
        try:
            os.kill(target.pid, getattr(signal, signame))
        except OSError as exc:
            self.kill_pid = None
            self._flash("{} {} failed: {}".format(signame, target.pid, exc))
            return
        message = "{} sent to {} ({})".format(signame, target.pid, target.name)
        if signame == "SIGTERM":
            message += " - k again within 3s for SIGKILL"
        self._flash(message)

    def _flash(self, message):
        self.flash_message = clean_text(message, self.ascii_only)[:200]
        self.flash_until = time.monotonic() + 3.0
        self.need_redraw = True

    # -- rendering -------------------------------------------------------

    def _build_canvas(self, snapshot, width, height):
        canvas = Canvas(width, height)
        if width < MIN_WIDTH or height < MIN_HEIGHT:
            canvas.fill(" ")
            line1 = "Terminal too small"
            line2 = "Need at least {}x{} (now {}x{})".format(
                MIN_WIDTH, MIN_HEIGHT, width, height
            )
            y = max(0, height // 2 - 1)
            canvas.put(max(0, (width - len(line1)) // 2), y, line1, self.theme.title)
            canvas.put(max(0, (width - len(line2)) // 2), y + 1, line2, self.theme.dim)
            return canvas

        header_height = 2 if height >= 12 else 1
        footer_y = height - 1
        self._draw_header(canvas, snapshot, width, header_height)

        body_top = header_height
        inner_height = footer_y - body_top
        cpus = [cpu for cpu in snapshot.cpus if cpu.name != "cpu"]
        if not cpus:
            cpus = snapshot.cpus

        cpu_title = 1
        max_cpu_rows = max(1, min(8, inner_height - 3))
        cpu_columns = self._cpu_columns(len(cpus), width)
        while (
            cpu_columns < max(1, len(cpus))
            and ceil_div(len(cpus), cpu_columns) > max_cpu_rows
            and width // (cpu_columns + 1) >= 18
        ):
            cpu_columns += 1
        visible_cpus = min(len(cpus), cpu_columns * max_cpu_rows)
        cpu_rows = min(max_cpu_rows, ceil_div(visible_cpus, cpu_columns))
        cpu_height = cpu_title + cpu_rows
        table_height = inner_height - cpu_height
        if table_height < 2:
            reduce = 2 - table_height
            cpu_rows = max(0, cpu_rows - reduce)
            cpu_height = cpu_title + cpu_rows
            table_height = inner_height - cpu_height

        self._draw_cpu(
            canvas,
            body_top,
            width,
            cpus,
            visible_cpus,
            cpu_columns,
            cpu_rows,
            snapshot.mode,
        )
        self._draw_table(
            canvas,
            body_top + cpu_height,
            width,
            table_height,
            snapshot,
        )
        self._draw_footer(canvas, snapshot, width, footer_y)
        if self.help_visible:
            self._draw_help(canvas, width, height)
        return canvas

    def _draw_header(self, canvas, snapshot, width, header_height):
        if width < 50:
            title = " {} ".format(APP_NAME)
        else:
            title = " {} {} ".format(APP_NAME, APP_VERSION)
        canvas.put(0, 0, title, self.theme.title)
        if width >= 100:
            summary = "  ".join(
                (
                    fmt_load(snapshot.load),
                    fmt_memory(snapshot.mem_used, snapshot.mem_total),
                    "{} running / {} total".format(snapshot.running, snapshot.total),
                )
            )
        else:
            load = "load n/a"
            if snapshot.load:
                if width < 50:
                    load = "L{:.1f}".format(float(snapshot.load[0]))
                elif width < 56:
                    load = "load {:.1f}".format(float(snapshot.load[0]))
                else:
                    load = "load " + " ".join(
                        "{:.1f}".format(float(item)) for item in snapshot.load
                    )
            if snapshot.mem_total is None:
                memory = "M n/a"
            elif snapshot.mem_used is None:
                memory = "M ?/{}".format(fmt_bytes(snapshot.mem_total))
            else:
                memory = "M{}/{}".format(
                    fmt_bytes(snapshot.mem_used), fmt_bytes(snapshot.mem_total)
                )
            summary = "{} {} {}/{}".format(
                load, memory, snapshot.running, snapshot.total
            )
        canvas.put(len(title) + 1, 0, summary, self.theme.bold)
        if header_height < 2:
            return
        signoff = "built {} by {}".format(PRODUCED_AT, MODEL_NAME)
        canvas.put(0, 1, signoff, self.theme.dim)
        right = "src {}  tick {:g}s".format(snapshot.mode, self.interval)
        if width >= len(signoff) + len(right) + 2:
            canvas.put(width - len(right) - 1, 1, right, self.theme.dim)

    @staticmethod
    def _cpu_columns(count, width):
        if count <= 1:
            return 1
        if width < 70:
            return 1
        return max(1, min(count, width // 30, 4))

    def _draw_cpu(
        self,
        canvas,
        y,
        width,
        cpus,
        visible,
        columns,
        rows,
        mode,
    ):
        canvas.put(0, y, "CPU", self.theme.title)
        note = "system aggregate (ps fallback)" if mode == "ps" else "per-core utilisation"
        if visible < len(cpus):
            note += "  ({} of {} shown)".format(visible, len(cpus))
        canvas.put(4, y, note, self.theme.dim)
        y += 1
        if not cpus or rows <= 0:
            return

        label_width = max(5, min(7, max(len(cpu.name) for cpu in cpus[:visible])))
        cell_width = max(1, width // max(1, columns))
        bar_width = cell_width - label_width - 8
        # Very narrow panels collapse to one column; at MIN_WIDTH this is 27.
        if bar_width < 5:
            return
        filled_char = "#" if self.ascii_only else "\u2588"
        empty_char = "-" if self.ascii_only else "\u2591"

        for index in range(visible):
            row = index // columns
            column = index % columns
            if row >= rows:
                break
            x = column * cell_width
            yy = y + row
            cpu = cpus[index]
            usage = cap_percent(cpu.usage, 100.0)
            style = self.theme.load_style(usage)
            canvas.put(x, yy, cpu.name.rjust(label_width), self.theme.bold)
            bar_x = x + label_width + 1
            filled = int(round(bar_width * usage / 100.0))
            filled = max(0, min(bar_width, filled))
            canvas.put(bar_x, yy, filled_char * filled, style)
            canvas.put(
                bar_x + filled,
                yy,
                empty_char * (bar_width - filled),
                self.theme.dim,
            )
            canvas.put(
                bar_x + bar_width + 1,
                yy,
                fmt_percent(usage).rjust(5) + "%",
                style,
            )

    def _table_columns(self, width, procs):
        widths = {
            "pid": max(4, min(7, max([len("PID")] + [len(str(p.pid)) for p in procs]))),
            "user": max(6, min(10, max([len("USER")] + [len(p.user) for p in procs]))),
            "name": 0,
            "cpu": 6,
            "mem": 6,
            "state": max(6, min(8, max([len("STATE")] + [len(p.state) for p in procs]))),
        }
        present = ["pid", "user", "name", "cpu", "mem", "state"]
        minimum_name = 5

        def minimum_width(columns):
            total = 1 + (len(columns) - 1)  # gutter + separators
            for column in columns:
                total += minimum_name if column == "name" else widths[column]
            return total

        while minimum_width(present) > width and len(present) > 3:
            removed = False
            for column in ("state", "user", "mem"):
                if column in present:
                    present.remove(column)
                    removed = True
                    break
            if not removed:
                break

        fixed = 1 + (len(present) - 1)
        for column in present:
            if column != "name":
                fixed += widths[column]
        widths["name"] = max(1, width - fixed)
        return present, widths

    @staticmethod
    def _cell_value(proc, column):
        if column == "pid":
            return str(proc.pid)
        if column == "user":
            return proc.user
        if column == "name":
            return proc.name
        if column == "cpu":
            return fmt_percent(proc.cpu)
        if column == "mem":
            return fmt_percent(proc.mem)
        return proc.state

    def _draw_table(self, canvas, y, width, height, snapshot):
        if height <= 0:
            return
        procs = self._display_procs()
        columns, widths = self._table_columns(width, procs)

        x = 1
        for column in columns:
            header = HEADERS[column]
            if column == self.sort_key:
                header += "^" if self.ascending else "v"
            align = "right" if column in NUMERIC_COLUMNS else "left"
            style = (
                self.theme.sorted_header
                if column == self.sort_key
                else self.theme.header
            )
            canvas.put(
                x,
                y,
                fit_text(header, widths[column], align, self.ascii_only),
                style,
            )
            x += widths[column] + 1

        visible = max(1, height - 1)
        self.page_rows = visible
        total = len(procs)
        if total == 0:
            message = (
                "no matching processes"
                if self.filter_text
                else "no processes found"
            )
            canvas.put(
                max(0, (width - len(message)) // 2),
                min(y + 2, y + height - 1),
                message,
                self.theme.dim,
            )
            return

        if not self.selection_locked:
            self.selected_pid = procs[0].pid
        elif self.selected_pid is None:
            self.selected_pid = procs[0].pid
        selected_index = 0
        for index, proc in enumerate(procs):
            if proc.pid == self.selected_pid:
                selected_index = index
                break
        else:
            self.selected_pid = procs[0].pid
            selected_index = 0

        maximum_offset = max(0, total - visible)
        if selected_index < self.offset:
            self.offset = selected_index
        elif selected_index >= self.offset + visible:
            self.offset = selected_index - visible + 1
        self.offset = max(0, min(self.offset, maximum_offset))

        for row in range(visible):
            index = self.offset + row
            if index >= total:
                break
            proc = procs[index]
            yy = y + 1 + row
            selected = self.show_selection and proc.pid == self.selected_pid
            if selected:
                canvas.fill_rect(0, yy, width, 1, self.theme.selected)
            canvas.put(
                0,
                yy,
                ">" if selected else " ",
                self.theme.selected if selected else self.theme.dim,
            )
            x = 1
            for column in columns:
                text = self._cell_value(proc, column)
                align = "right" if column in NUMERIC_COLUMNS else "left"
                style = ""
                if selected:
                    style = self.theme.selected
                elif column == "cpu":
                    style = self.theme.load_style(cap_percent(proc.cpu, 100.0))
                elif column == "name":
                    style = self.theme.bold
                canvas.put(
                    x,
                    yy,
                    fit_text(text, widths[column], align, self.ascii_only),
                    style,
                )
                x += widths[column] + 1

    def _draw_footer(self, canvas, snapshot, width, y):
        now = time.monotonic()
        right = ""
        if self.flash_message and now < self.flash_until:
            text = self.flash_message
            style = self.theme.flash
        elif self.filter_mode:
            text = "Filter: {}_".format(
                clean_text(self.filter_text, self.ascii_only)
            )
            style = self.theme.bold
            right = "Enter apply  Esc clear"
        elif snapshot.error:
            text = "error: {}".format(clean_text(snapshot.error, self.ascii_only))
            style = self.theme.red
        else:
            procs = self._display_procs()
            total = len(procs)
            start = min(self.offset + 1, total) if total else 0
            end = min(self.offset + self.page_rows, total)
            text = "[{}-{}/{}] q quit  h help  c/m/n/p sort  r reverse  / filter  k kill".format(
                start, end, total
            )
            style = self.theme.dim
        canvas.put(0, y, text, style)
        if right and width > len(text) + len(right) + 2:
            canvas.put(width - len(right) - 1, y, right, self.theme.dim)

    def _draw_help(self, canvas, width, height):
        lines = list(HELP_LINES if height >= 14 else HELP_COMPACT)
        box_height = min(height - 1, len(lines) + 2)
        use_columns = 1
        if box_height < len(lines) + 2 and width >= 64:
            use_columns = 2

        if use_columns == 1:
            content = lines
            inner_width = max(len(line) for line in content)
            box_width = min(width - 2, max(44, inner_width + 4))
        else:
            rows = ceil_div(len(lines), 2)
            content = []
            half = rows
            left = lines[:half]
            right = lines[half:]
            left_width = max(len(line) for line in left)
            for index in range(rows):
                lhs = left[index] if index < len(left) else ""
                rhs = right[index] if index < len(right) else ""
                content.append(lhs.ljust(left_width) + "  " + rhs)
            inner_width = max(len(line) for line in content)
            box_width = min(width - 2, max(44, inner_width + 4))
            box_height = min(height - 1, len(content) + 2)

        box_width = max(4, box_width)
        box_height = max(3, box_height)
        x = max(0, (width - box_width) // 2)
        y = max(0, (height - box_height) // 2)

        canvas.fill_rect(x, y, box_width, box_height, "")
        border = "+" + "-" * (box_width - 2) + "+"
        canvas.put(x, y, border, self.theme.overlay_border)
        canvas.put(x, y + box_height - 1, border, self.theme.overlay_border)
        for row in range(1, box_height - 1):
            canvas.put(x, y + row, "|", self.theme.overlay_border)
            canvas.put(x + box_width - 1, y + row, "|", self.theme.overlay_border)

        room = box_height - 2
        for index, line in enumerate(content[:room]):
            style = self.theme.title if index == 0 else ""
            if index == len(content) - 1:
                style = self.theme.dim
            canvas.put(
                x + 2,
                y + 1 + index,
                fit_text(line, box_width - 4, "left", self.ascii_only),
                style,
            )

    # -- one-shot snapshot ----------------------------------------------

    def render_snapshot(self, width, height):
        self.snapshot = self.collector.sample()
        self.ascii_only = True  # snapshots are always plain, pipe-safe text
        self.theme = Theme(False)
        self.show_selection = False
        canvas = self._build_canvas(self.snapshot, int(width), int(height))
        return "\n".join(canvas.render()) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def write_stdout(text):
    try:
        sys.stdout.write(text)
        sys.stdout.flush()
        return True
    except BrokenPipeError:
        # `procscope.py --once | head` closed the pipe early.  Silence the
        # interpreter's final flush as well.
        try:
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stdout.fileno())
        except OSError:
            pass
        return False


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="ProcScope - a top-like process monitor using only the Python standard library.",
        epilog="Built {} by {}.".format(PRODUCED_AT, MODEL_NAME),
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="print one non-interactive snapshot and exit",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        metavar="SECONDS",
        help="refresh interval in interactive mode (default: 1.0)",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=None,
        metavar="COLS",
        help="override snapshot width (mostly useful for testing)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=None,
        metavar="ROWS",
        help="override snapshot height (mostly useful for testing)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="{} {} - built {} by {}".format(
            APP_NAME, APP_VERSION, PRODUCED_AT, MODEL_NAME
        ),
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    collector = ProcCollector()
    ui = ProcScopeUI(collector, interval=args.interval)

    interactive = (
        not args.once
        and sys.stdin.isatty()
        and sys.stdout.isatty()
        and termios is not None
        and tty is not None
    )
    try:
        if not interactive:
            width = args.width
            height = args.height
            if width is None or height is None:
                size = shutil.get_terminal_size(fallback=(100, 30))
                if width is None:
                    width = size.columns
                if height is None:
                    height = size.lines
            width = max(1, int(width))
            height = max(1, int(height))
            write_stdout(ui.render_snapshot(width, height))
            return 0
        return ui.run()
    except KeyboardInterrupt:
        # Belt and braces: the SIGINT handler normally handles this.
        return 0
    except Exception as exc:  # never dump a traceback at the user
        try:
            sys.stderr.write("procscope: {}\n".format(exc))
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
