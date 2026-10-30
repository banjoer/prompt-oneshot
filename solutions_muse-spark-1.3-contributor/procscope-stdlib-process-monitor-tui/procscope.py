#!/usr/bin/env python3
# ProcScope: A Stdlib Process Monitor TUI
# Produced: 2026-10-29 12:00 UTC by Muse Spark 1.3 Contributor (OpenCode agent)
# Single-file top-like monitor. Stdlib only. Linux /proc primary, ps fallback.
"""ProcScope - self-contained process monitor (stdlib only)."""
import os
import sys
import time
import signal
import select
import shutil
import subprocess
import argparse
import re
from dataclasses import dataclass

SIGNOFF = "ProcScope produced 2026-10-29 12:00 UTC by Muse Spark 1.3 Contributor"
VERSION = "1.0"

REFRESH = 1.0
MIN_COLS = 40
MIN_ROWS = 10

# color state (set at startup)
_COLOR_ENABLED = True

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def _use_color():
    # NO_COLOR set (any value incl. empty) -> no color; TERM dumb/missing -> no color
    if "NO_COLOR" in os.environ:
        return False
    term = os.environ.get("TERM", "")
    if term == "" or term == "dumb":
        return False
    return True


def sty(text, code):
    """Tiny internal helper: ALL color/styling goes through here.

    When color is disabled, returns text unchanged (no ANSI at all).
    code is an ANSI SGR code like '31', '32', '33', '1', '7', '36'.
    """
    if not _COLOR_ENABLED:
        return text
    return "\x1b[" + str(code) + "m" + text + "\x1b[0m"


def visible_len(s):
    return len(ANSI_RE.sub("", s))


def fit_pad(line, width):
    """Pad (visible) to width; if overflow, strip ANSI and truncate plain."""
    v = visible_len(line)
    if v < width:
        return line + " " * (width - v)
    if v == width:
        return line
    # overflow: strip ANSI, truncate, return plain (loses styling but never wraps)
    plain = ANSI_RE.sub("", line)
    return plain[:width]


def truncate_plain(s, w):
    if len(s) <= w:
        return s
    if w <= 0:
        return ""
    return s[:w]


@dataclass
class Proc:
    pid: int
    user: str
    name: str
    cpu: float
    mem: float
    state: str


def get_hz():
    try:
        return os.sysconf("SC_CLK_TCK")
    except Exception:
        return 100


def get_page_size():
    for n in ("SC_PAGE_SIZE", "SC_PAGESIZE"):
        try:
            return os.sysconf(n)
        except Exception:
            continue
    return 4096


def can_use_proc():
    try:
        with open("/proc/stat", "r"):
            pass
        return True
    except Exception:
        return False


def read_meminfo():
    """Returns (total_kb, used_kb) or (None, None)."""
    try:
        total = None
        avail = None
        free = None
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    total = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    avail = int(line.split()[1])
                elif line.startswith("MemFree:"):
                    free = int(line.split()[1])
        if total is None:
            return (None, None)
        if avail is not None:
            used = total - avail
        elif free is not None:
            used = total - free
        else:
            used = 0
        return (total, used)
    except Exception:
        return (None, None)


def read_cpu_times():
    """Returns dict name -> (total, idle_all). Includes 'cpu' aggregate + cpuN."""
    d = {}
    try:
        with open("/proc/stat", "r") as f:
            for line in f:
                if not line.startswith("cpu"):
                    continue
                parts = line.split()
                name = parts[0]
                # only aggregate or cpuN
                if name != "cpu" and not (name.startswith("cpu") and name[3:].isdigit()):
                    continue
                try:
                    nums = [int(x) for x in parts[1:]]
                except ValueError:
                    continue
                if not nums:
                    continue
                total = sum(nums)
                idle = nums[3] if len(nums) > 3 else 0
                iowait = nums[4] if len(nums) > 4 else 0
                d[name] = (total, idle + iowait)
    except Exception:
        pass
    return d


def compute_cpu_usages(prev, cur):
    out = {}
    for k, (ct, ci) in cur.items():
        if prev is not None and k in prev:
            pt, pi = prev[k]
            dt = ct - pt
            di = ci - pi
            if dt > 0 and di >= 0:
                u = 100.0 * (1.0 - float(di) / float(dt))
                if u < 0:
                    u = 0.0
                if u > 100.0:
                    u = 100.0
                out[k] = u
            else:
                out[k] = 0.0
        else:
            out[k] = 0.0
    return out


def parse_pid_stat(pid):
    """Returns (comm, state, total_jiffies, rss_pages). Robust to spaces/parens."""
    with open("/proc/%d/stat" % pid, "r") as f:
        content = f.read()
    l = content.find("(")
    r = content.rfind(")")
    if l == -1 or r == -1 or r < l:
        raise ValueError("bad stat")
    comm = content[l + 1:r]
    rest = content[r + 1:].split()
    # rest[0]=state(3), rest[11]=utime(14), rest[12]=stime(15), rest[21]=rss(24)
    if len(rest) < 13:
        raise ValueError("short stat")
    state = rest[0] if rest[0] else "?"
    try:
        utime = int(rest[11])
        stime = int(rest[12])
    except ValueError:
        raise ValueError("bad times")
    rss_pages = 0
    if len(rest) > 21:
        try:
            rss_pages = int(rest[21])
        except ValueError:
            rss_pages = 0
    return (comm, state, utime + stime, rss_pages)


def read_cmdline(pid):
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as f:
            data = f.read()
        if not data:
            return ""
        parts = data.split(b"\x00")
        strs = []
        for p in parts:
            if p:
                try:
                    strs.append(p.decode("utf-8", errors="replace"))
                except Exception:
                    pass
        return " ".join(strs)
    except Exception:
        return ""


def get_user_for_pid(pid):
    try:
        st = os.stat("/proc/%d" % pid)
        uid = st.st_uid
    except Exception:
        return "?"
    try:
        import pwd as _pwd
        try:
            return _pwd.getpwuid(uid).pw_name
        except Exception:
            return str(uid)
    except ImportError:
        return str(uid)


def display_name(comm, cmdline):
    if comm and comm.strip():
        return comm
    if cmdline:
        first = cmdline.split()[0] if cmdline.split() else cmdline
        base = os.path.basename(first)
        if base:
            return base[:64]
        return truncate_plain(cmdline, 64)
    if comm:
        return comm
    return "?"


def collect_linux(prev_proc_times, elapsed, mem_total_kb, hz, page_size):
    """Collect processes. prev_proc_times: pid->jiffies. elapsed: seconds.
    Returns (procs, new_prev, running, total)."""
    try:
        entries = os.listdir("/proc")
    except Exception:
        return ([], {}, 0, 0)
    pids = []
    for e in entries:
        if e.isdigit():
            try:
                pids.append(int(e))
            except ValueError:
                continue
    total = len(pids)
    procs = []
    new_prev = {}
    running = 0
    now_missing = 0
    for pid in pids:
        try:
            comm, state, jiffies, rss_pages = parse_pid_stat(pid)
        except (FileNotFoundError, ProcessLookupError, PermissionError, ValueError, OSError):
            continue
        except Exception:
            continue
        new_prev[pid] = jiffies
        # cpu%
        cpu = 0.0
        if prev_proc_times is not None and pid in prev_proc_times and elapsed and elapsed > 0:
            try:
                dj = jiffies - prev_proc_times[pid]
                if dj < 0:
                    dj = 0
                cpu = (float(dj) / float(hz)) / float(elapsed) * 100.0
                if cpu < 0:
                    cpu = 0.0
                # clamp absurd spikes (e.g. pid reuse) to 100*ncpus? allow up to 1000 but cap 999.9 for display
                if cpu > 999.9:
                    cpu = 999.9
            except Exception:
                cpu = 0.0
        # mem%
        mem = 0.0
        try:
            if mem_total_kb and mem_total_kb > 0:
                rss_kb = float(rss_pages) * float(page_size) / 1024.0
                mem = rss_kb / float(mem_total_kb) * 100.0
                if mem < 0:
                    mem = 0.0
                if mem > 100.0:
                    mem = 100.0
        except Exception:
            mem = 0.0
        try:
            user = get_user_for_pid(pid)
        except Exception:
            user = "?"
        try:
            cmdline = read_cmdline(pid)
        except Exception:
            cmdline = ""
        name = display_name(comm, cmdline)
        # state single char
        st = state[0] if state else "?"
        if st == "R":
            running += 1
        procs.append(Proc(pid=pid, user=user, name=name, cpu=cpu, mem=mem, state=st))
    return (procs, new_prev, running, total)


def collect_ps():
    """Fallback via ps. Returns (procs, running, total)."""
    procs = []
    running = 0
    try:
        p = subprocess.run(
            ["ps", "-Ao", "pid=,user=,comm=,%cpu=,%mem=,stat="],
            capture_output=True, text=True, timeout=5)
        out = p.stdout or ""
    except Exception:
        return ([], 0, 0)
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) < 6:
            continue
        # pid user comm cpu mem stat ; comm may contain spaces -> middle join
        # robust: pid=parts[0], user=parts[1], stat=parts[-1], mem=parts[-2], cpu=parts[-3], comm=parts[2:-3]
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        stat = parts[-1]
        try:
            mem = float(parts[-2])
        except ValueError:
            mem = 0.0
        try:
            cpu = float(parts[-3])
        except ValueError:
            cpu = 0.0
        user = parts[1]
        mid = parts[2:-3]
        if mid:
            comm = " ".join(mid)
        else:
            comm = "?"
        # comm from ps may be full path; use basename? keep as-is but basename for consistency
        # keep full? spec NAME is comm value; keep basename to save width
        # Use basename if path-like
        if "/" in comm:
            # keep basename but remember? use basename
            comm = os.path.basename(comm) or comm
        comm = truncate_plain(comm, 64) or "?"
        st = stat[0] if stat else "?"
        if st == "R":
            running += 1
        procs.append(Proc(pid=pid, user=user, name=comm, cpu=cpu, mem=mem, state=st))
    total = len(procs)
    return (procs, running, total)


def sort_procs(procs, key, descending):
    if key == "cpu":
        return sorted(procs, key=lambda p: p.cpu, reverse=descending)
    elif key == "mem":
        return sorted(procs, key=lambda p: p.mem, reverse=descending)
    elif key == "name":
        # case-insensitive, stable
        return sorted(procs, key=lambda p: p.name.lower(), reverse=descending)
    elif key == "pid":
        return sorted(procs, key=lambda p: p.pid, reverse=descending)
    else:
        return sorted(procs, key=lambda p: p.cpu, reverse=True)


def fmt_mem(kb):
    if kb is None:
        return "N/A"
    try:
        kb = float(kb)
    except Exception:
        return "N/A"
    if kb >= 1024 * 1024:
        return "%.1fG" % (kb / 1024.0 / 1024.0)
    elif kb >= 1024:
        return "%.0fM" % (kb / 1024.0)
    else:
        return "%.0fk" % kb


def bar_for(usage, w):
    if w < 1:
        w = 1
    filled = int(round(usage / 100.0 * w))
    if filled < 0:
        filled = 0
    if filled > w:
        filled = w
    if _COLOR_ENABLED:
        full = "\u2588"
        empty = "\u2591"
    else:
        full = "#"
        empty = "-"
    bar = full * filled + empty * (w - filled)
    if not _COLOR_ENABLED:
        return bar
    if usage < 50:
        code = "32"
    elif usage < 80:
        code = "33"
    else:
        code = "31"
    return sty(bar, code)


def render_frame(width, height, header_info, cpu_usages_ordered, procs_sorted,
                 sort_key, descending, help_active, use_proc, pad=True):
    """Build list of lines (strings, may contain ANSI if enabled).
    header_info: dict with load, mem_total, mem_used, running, total, ncpu, mode
    cpu_usages_ordered: list of (name, usage) in order (cpu0..), aggregate excluded or separate
    """
    if width < MIN_COLS or height < MIN_ROWS:
        lines = []
        # fill with blanks
        for _ in range(height):
            lines.append(" " * width if pad else "")
        mid = height // 2
        msg1 = "terminal too small"
        msg2 = "%dx%d (need %dx%d)" % (width, height, MIN_COLS, MIN_ROWS)
        msg3 = "resize to continue"
        # center (plain, no color when too small? keep plain to avoid issues)
        def center(msg, row):
            if row < 0 or row >= height:
                return
            m = truncate_plain(msg, width)
            start = max(0, (width - len(m)) // 2)
            if pad:
                lines[row] = " " * start + m + " " * (width - start - len(m))
            else:
                lines[row] = " " * start + m
        center(msg1, mid - 1)
        center(msg2, mid)
        center(msg3, mid + 1)
        return lines

    lines = []

    # ---- header (2 lines) ----
    load = header_info.get("load")
    if load is None:
        load_str = "N/A"
    else:
        try:
            load_str = "%.2f %.2f %.2f" % (load[0], load[1], load[2])
        except Exception:
            load_str = "N/A"
    mem_total = header_info.get("mem_total")
    mem_used = header_info.get("mem_used")
    if mem_total is None:
        mem_str = "N/A"
    else:
        mem_str = "%s/%s" % (fmt_mem(mem_used), fmt_mem(mem_total))
    running = header_info.get("running", 0)
    totalp = header_info.get("total", 0)
    ncpu = header_info.get("ncpu", 0)
    mode = header_info.get("mode", "/proc")

    h0_plain = "ProcScope %s  Load %s  Tasks %d/%d  CPUs %s  %s" % (
        VERSION, load_str, running, totalp, str(ncpu), mode)
    h1_plain = "Mem %s  Sort %s %s" % (
        mem_str,
        {"cpu": "CPU%", "mem": "MEM%", "name": "NAME", "pid": "PID"}.get(sort_key, "CPU%"),
        "DESC" if descending else "ASC")
    # truncate plain to width before styling
    h0_plain = truncate_plain(h0_plain, width)
    h1_plain = truncate_plain(h1_plain, width)
    if _COLOR_ENABLED:
        # header bar reverse/bold
        h0 = sty(h0_plain, "7")
        h1 = sty(h1_plain, "1")
    else:
        h0 = h0_plain
        h1 = h1_plain
    if pad:
        h0 = fit_pad(h0, width)
        h1 = fit_pad(h1, width)
    lines.append(h0)
    lines.append(h1)

    # ---- cpu section ----
    # title
    cpu_title = "CPU:"
    if pad:
        lines.append(fit_pad(cpu_title, width))
    else:
        lines.append(cpu_title)
    # determine columns
    # cpu_usages_ordered excludes aggregate 'cpu'; if empty (ps fallback single), handle separately
    per_core = [(k, v) for (k, v) in cpu_usages_ordered if k != "cpu"]
    agg = None
    for (k, v) in cpu_usages_ordered:
        if k == "cpu":
            agg = v
            break
    # ps fallback: cpu_usages_ordered may contain single ('cpu', agg)
    if not per_core and agg is not None:
        # single aggregate bar
        # line: "cpu  [bar]  xx.x%"
        avail = width - len("cpu  []  100.0%")  # overhead approx 14?
        # compute bar width
        label = "cpu"
        # format: label + space + [ + bar + ] + space + pct
        overhead = len(label) + 1 + 1 + 1 + 1 + 6  # label,sp,[,],sp, "100.0%"
        bw = width - overhead
        if bw < 5:
            bw = 5
        if bw > width - overhead:
            bw = width - overhead
        bar = bar_for(agg, bw)
        pct = "%5.1f%%" % agg
        # build visible then color? bar already colored
        # construct line without extra color for label/pct
        line_plain_len = len(label) + 1 + 1 + bw + 1 + 1 + 6
        # build
        line = label + " [" + bar + "] " + pct
        if pad:
            line = fit_pad(line, width)
        lines.append(line)
        cpu_lines = 1
    elif not per_core and agg is None:
        # no cpu data
        l = "CPU N/A"
        lines.append(fit_pad(l, width) if pad else l)
        cpu_lines = 1
    else:
        # multi-core layout
        n = len(per_core)
        if width >= 150:
            ncols = 4
        elif width >= 110:
            ncols = 3
        elif width >= 70:
            ncols = 2
        else:
            ncols = 1
        if ncols > n:
            ncols = n
        if ncols < 1:
            ncols = 1
        col_w = width // ncols
        rows_needed = (n + ncols - 1) // ncols
        cpu_lines = rows_needed
        for r in range(rows_needed):
            cells = []
            for c in range(ncols):
                idx = r * ncols + c
                # for column-major? row-major is fine
                # use row-major: idx = r*ncols + c
                if idx >= n:
                    # empty cell pad
                    cells.append(" " * col_w)
                    continue
                label, usage = per_core[idx]
                # col width for last col may include remainder
                cw = col_w
                if c == ncols - 1:
                    cw = width - col_w * (ncols - 1)
                overhead = len(label) + 1 + 1 + 1 + 1 + 6
                bw = cw - overhead
                # leave 1-char gap between columns (except last)
                if c != ncols - 1:
                    bw -= 1
                if bw < 4:
                    bw = 4
                bar = bar_for(usage, bw)
                pct = "%5.1f%%" % usage
                cell = label + " [" + bar + "] " + pct
                # pad cell to cw (visible)
                v = visible_len(cell)
                if v < cw:
                    cell = cell + " " * (cw - v)
                elif v > cw:
                    # truncate: fallback plain
                    plain = ANSI_RE.sub("", cell)
                    cell = plain[:cw]
                cells.append(cell)
            line = "".join(cells)
            # ensure width
            if pad:
                line = fit_pad(line, width)
            else:
                # strip trailing spaces for pipe? keep as is but truncate visible
                if visible_len(line) > width:
                    line = ANSI_RE.sub("", line)[:width]
            lines.append(line)

    # ---- process table ----
    # decide columns
    show_state = width >= 50
    if width >= 70:
        user_w = 10
    elif width >= 50:
        user_w = 8
    else:
        user_w = 6
    pid_w = 7
    cpu_w = 6
    mem_w = 6
    state_w = 5
    # header labels
    # compute name width
    if show_state:
        fixed = pid_w + 1 + user_w + 1 + cpu_w + 1 + mem_w + 1 + state_w
        # spaces = 5
        name_w = width - fixed - 5 + 1  # careful: fixed already includes? let's recompute clearly
        # columns joined with single space: total = pid+1+user+1+name+1+cpu+1+mem+1+state = pid+user+name+cpu+mem+state+5
        name_w = width - (pid_w + user_w + cpu_w + mem_w + state_w + 5)
    else:
        # PID USER NAME CPU% MEM% => total = pid+user+name+cpu+mem+4
        name_w = width - (pid_w + user_w + cpu_w + mem_w + 4)
    if name_w < 8:
        name_w = 8
        # if still overflow, truncate user further? but width>=40 guarantees fit as computed; keep 8 and allow overflow truncate later
        # adjust: if overflow, reduce user_w? already minimal. Just let fit_pad truncate.
        pass

    def hdr(label, key, w, align_right=False):
        is_sorted = (sort_key == key)
        arrow = ""
        if is_sorted:
            # direction indicator
            if _COLOR_ENABLED:
                arrow = "\u25bc" if descending else "\u25b2"
            else:
                arrow = "v" if descending else "^"
        # label + arrow must fit w
        base = label
        # for sorted, append arrow if fits, else replace last char?
        if is_sorted and arrow:
            if len(base) + len(arrow) <= w:
                base = base + arrow
            else:
                base = base[:max(0, w - len(arrow))] + arrow if w > 0 else ""
        # mono highlight: surround with * if sorted? use arrow already as highlight; also add *? keep arrow as highlight
        # for mono, also uppercase? already upper. Arrow suffices.
        if align_right:
            txt = base.rjust(w)
        else:
            txt = base.ljust(w)
            txt = truncate_plain(txt, w)
            if len(txt) < w:
                txt = txt + " " * (w - len(txt))
        if is_sorted and _COLOR_ENABLED:
            return sty(txt, "7")
        else:
            # mono: if sorted, mark with *? arrow already; return plain
            return txt

    # widths: PID right? left? use right for pid numbers, header right too
    h_pid = hdr("PID", "pid", pid_w, align_right=True)
    h_user = hdr("USER", "_user", user_w, align_right=False)  # never sorted, so plain
    # USER never sorted key, so key mismatch -> plain
    h_name = hdr("NAME", "name", name_w, align_right=False)
    h_cpu = hdr("CPU%", "cpu", cpu_w, align_right=True)
    h_mem = hdr("MEM%", "mem", mem_w, align_right=True)
    h_state = hdr("STATE", "_state", state_w, align_right=False) if show_state else None

    if show_state:
        header_line = h_pid + " " + h_user + " " + h_name + " " + h_cpu + " " + h_mem + " " + h_state
    else:
        header_line = h_pid + " " + h_user + " " + h_name + " " + h_cpu + " " + h_mem
    if pad:
        header_line = fit_pad(header_line, width)
    else:
        if visible_len(header_line) > width:
            header_line = ANSI_RE.sub("", header_line)[:width]
    lines.append(header_line)

    # rows available
    # total height: header 2 + cpu title 1 + cpu_lines + table header 1 + footer 1 = overhead
    overhead_lines = 2 + 1 + cpu_lines + 1 + 1
    avail_rows = height - overhead_lines
    if avail_rows < 1:
        avail_rows = 1
    # for snapshot (pad=False), avail_rows based on height but don't pad blanks; just show up to avail_rows
    # for interactive (pad=True), show avail_rows, pad blanks if fewer procs
    n_show = min(len(procs_sorted), avail_rows)
    for i in range(n_show):
        p = procs_sorted[i]
        pid_s = str(p.pid).rjust(pid_w)[:pid_w]
        user_s = truncate_plain(p.user, user_w).ljust(user_w)
        name_s = truncate_plain(p.name, name_w).ljust(name_w)
        # percentages right-aligned one decimal with %? use 5.1f + %? width 6
        # cpu_w=6, e.g. "  0.0%"? format "%5.1f%%" gives 6? 0.0 -> "  0.0%" (6). 100.0 -> "100.0%" (6). 999.9 -> "999.9%" (6). good
        try:
            cpu_s = "%5.1f%%" % p.cpu
        except Exception:
            cpu_s = "  0.0%"
        try:
            mem_s = "%5.1f%%" % p.mem
        except Exception:
            mem_s = "  0.0%"
        # ensure width
        cpu_s = cpu_s[-cpu_w:] if len(cpu_s) > cpu_w else cpu_s.rjust(cpu_w)
        mem_s = mem_s[-mem_w:] if len(mem_s) > mem_w else mem_s.rjust(mem_w)
        if show_state:
            state_s = truncate_plain(p.state, state_w).ljust(state_w)
            row = pid_s + " " + user_s + " " + name_s + " " + cpu_s + " " + mem_s + " " + state_s
        else:
            row = pid_s + " " + user_s + " " + name_s + " " + cpu_s + " " + mem_s
        if pad:
            row = fit_pad(row, width)
        else:
            if len(row) > width:
                row = row[:width]
        lines.append(row)
    if pad:
        # pad remaining rows with blanks to fill to height-1 (reserve footer)
        # currently lines = 2+1+cpu_lines+1+n_show ; need height-1 lines before footer
        while len(lines) < height - 1:
            lines.append(" " * width)
        # if overflow (too many lines due to large cpu_lines?), truncate? shouldn't happen because avail_rows computed; but if procs many, lines == height-1 exactly. If cpu_lines large, avail small. Good.
        # ensure exactly height-1 before footer
        if len(lines) > height - 1:
            lines = lines[:height - 1]

    # footer (short sign-off guaranteed to fit 80 cols; responsive for narrow)
    if width >= 72:
        foot_plain = "c:CPU m:MEM n:NAME p:PID r:rev h:help q:quit | 2026-10-29 Muse Spark 1.3"
    else:
        # narrow: keep sign-off visible, shorten hints
        foot_plain = "h:help q:quit | 2026-10-29 Muse Spark"
    foot_plain = truncate_plain(foot_plain, width)
    if _COLOR_ENABLED:
        foot = sty(foot_plain, "36")
    else:
        foot = foot_plain
    if pad:
        foot = fit_pad(foot, width)
    lines.append(foot)
    # for interactive, ensure exactly height lines
    if pad:
        if len(lines) > height:
            lines = lines[:height]
        while len(lines) < height:
            lines.append(" " * width)

    # help overlay
    if help_active:
        help_lines = [
            "ProcScope Help",
            "",
            "c      sort by CPU%",
            "m      sort by MEM%",
            "n      sort by NAME",
            "p      sort by PID",
            "r      toggle ascending/descending",
            "h or ? show/hide this help",
            "q      quit",
            "Ctrl-C quit",
            "",
            "any key dismisses help",
        ]
        box_w = max([len(l) for l in help_lines]) + 4
        box_w = max(box_w, 30)
        box_w = min(box_w, width - 4 if width > 8 else width)
        box_h = len(help_lines) + 2
        if box_h > height - 2:
            box_h = height - 2
            help_lines = help_lines[:box_h - 2]
            box_h = len(help_lines) + 2
        # build box
        top = "+" + "-" * (box_w - 2) + "+"
        bottom = top
        box = [top]
        for hl in help_lines:
            hl_t = truncate_plain(hl, box_w - 4)
            # center title? left others
            content = " " + hl_t.ljust(box_w - 4) + " "
            # hmm width: 1 + (box_w-2) +1? Actually "|"+content+"|"? Let's use "|"
            # content len = box_w-2? " "+hl+(pad)+" " = box_w-2? Check: 1 + (box_w-4) +1 = box_w-2. Good.
            box.append("|" + content + "|")
        box.append(bottom)
        # overlay centered
        start_row = (height - len(box)) // 2
        start_col = (width - box_w) // 2
        if start_row < 0:
            start_row = 0
        if start_col < 0:
            start_col = 0
        for bi, bline in enumerate(box):
            r = start_row + bi
            if r < 0 or r >= len(lines):
                continue
            base = lines[r]
            # base may contain ANSI; strip for overlay? Simplify: use plain base visible
            base_plain = ANSI_RE.sub("", base)
            if len(base_plain) < width:
                base_plain = base_plain + " " * (width - len(base_plain))
            # replace segment
            # bline plain (no ANSI)
            new_plain = base_plain[:start_col] + bline + base_plain[start_col + box_w:]
            new_plain = truncate_plain(new_plain, width)
            if pad:
                # pad to width (already width)
                if len(new_plain) < width:
                    new_plain = new_plain + " " * (width - len(new_plain))
            lines[r] = new_plain
            # Note: overlay lines plain, no color (works in mono too). If color enabled, could highlight border? Keep plain for simplicity + zero-escape in mono.
    return lines


def run_once():
    global _COLOR_ENABLED
    _COLOR_ENABLED = _use_color()
    use_proc = can_use_proc()
    width, height = shutil.get_terminal_size(fallback=(80, 24))
    # clamp width/height sane
    if width <= 0:
        width = 80
    if height <= 0:
        height = 24
    hz = get_hz()
    page_size = get_page_size()
    sort_key = "cpu"
    descending = True

    if use_proc:
        # double-sample for meaningful deltas
        try:
            prev_cpu = read_cpu_times()
        except Exception:
            prev_cpu = {}
        # prime proc times
        try:
            _, prime_prev, _, _ = collect_linux({}, 0.0001, None, hz, page_size)
            # Actually need mem_total for second? get mem now
        except Exception:
            prime_prev = {}
        prev_wall = time.monotonic()
        mem_total, mem_used = read_meminfo()
        # if mem_total None, still proceed
        time.sleep(0.5)
        cur_wall = time.monotonic()
        elapsed = cur_wall - prev_wall
        if elapsed <= 0:
            elapsed = 0.5
        cur_cpu = read_cpu_times()
        usages = compute_cpu_usages(prev_cpu, cur_cpu)
        # ordered list: aggregate first? keep aggregate + sorted per-core
        ordered = []
        if "cpu" in usages:
            ordered.append(("cpu", usages["cpu"]))
        for k in sorted([k for k in usages if k != "cpu"]):
            # sort cpu0, cpu1 numerically
            ordered.append((k, usages[k]))
        # fix numeric sort: cpu10 after cpu2? sort by int suffix
        def cpu_key(x):
            n = x[0]
            if n == "cpu":
                return -1
            try:
                return int(n[3:])
            except Exception:
                return 9999
        ordered = sorted([p for p in ordered if p[0] != "cpu"], key=cpu_key)
        # re-add aggregate at front for render (render expects aggregate included)
        agg_list = []
        if "cpu" in usages:
            agg_list.append(("cpu", usages["cpu"]))
        ordered = agg_list + ordered
        # collect procs with prime_prev and elapsed
        # need mem_total for mem%
        if mem_total is None:
            mem_total2, _ = read_meminfo()
            if mem_total2 is not None:
                mem_total = mem_total2
        try:
            procs, _, running, totalp = collect_linux(prime_prev, elapsed, mem_total, hz, page_size)
        except Exception:
            procs, running, totalp = [], 0, 0
        mem_total, mem_used = read_meminfo()
        try:
            load = os.getloadavg()
        except Exception:
            load = None
        try:
            ncpu = os.cpu_count() or len([k for k in ordered if k[0] != "cpu"]) or len(procs) and 1 or 1
        except Exception:
            ncpu = len([k for k in ordered if k[0] != "cpu"]) or 1
        # if ordered per-core empty? fallback to ncpu count?
        header_info = {"load": load, "mem_total": mem_total, "mem_used": mem_used,
                       "running": running, "total": totalp, "ncpu": ncpu if ncpu else len(ordered),
                       "mode": "/proc"}
        procs_sorted = sort_procs(procs, sort_key, descending)
        lines = render_frame(width, height, header_info, ordered, procs_sorted,
                             sort_key, descending, False, True, pad=False)
    else:
        # ps fallback single sample
        try:
            load = os.getloadavg()
        except Exception:
            load = None
        mem_total, mem_used = read_meminfo()
        procs, running, totalp = collect_ps()
        try:
            ncpu = os.cpu_count() or 1
        except Exception:
            ncpu = 1
        # aggregate usage approx
        try:
            total_cpu = sum(p.cpu for p in procs)
            agg = min(100.0, total_cpu / float(ncpu)) if ncpu else min(100.0, total_cpu)
        except Exception:
            agg = 0.0
        ordered = [("cpu", agg)]
        header_info = {"load": load, "mem_total": mem_total, "mem_used": mem_used,
                       "running": running, "total": totalp, "ncpu": ncpu,
                       "mode": "ps fallback"}
        procs_sorted = sort_procs(procs, sort_key, descending)
        lines = render_frame(width, height, header_info, ordered, procs_sorted,
                             sort_key, descending, False, False, pad=False)
    # emit no cursor-movement codes: just lines + newline
    # ensure zero escapes when color disabled (render already respects)
    # when color enabled, lines may contain color codes (allowed) but no movement codes (we never add them in pad=False path)
    sys.stdout.write("\n".join(lines) + "\n")
    sys.stdout.flush()
    return 0


_resize_flag = False


def _sigwinch_handler(signum, frame):
    global _resize_flag
    _resize_flag = True


def wait_keys(timeout):
    """Wait up to timeout secs, return string of keys pressed (may be '')."""
    try:
        r, _, _ = select.select([sys.stdin], [], [], timeout)
    except (select.error, OSError, ValueError):
        return ""
    except InterruptedError:
        return ""
    if not r:
        return ""
    data = ""
    # consume all available without blocking
    # first read
    try:
        # read available bytes
        chunk = os.read(sys.stdin.fileno(), 4096)
        if chunk:
            try:
                data += chunk.decode("utf-8", errors="ignore")
            except Exception:
                pass
    except (OSError, ValueError):
        return data
    # drain additional pending within same tick (non-blocking)
    while True:
        try:
            r2, _, _ = select.select([sys.stdin], [], [], 0)
        except Exception:
            break
        if not r2:
            break
        try:
            chunk = os.read(sys.stdin.fileno(), 4096)
            if not chunk:
                break
            try:
                data += chunk.decode("utf-8", errors="ignore")
            except Exception:
                pass
        except (OSError, ValueError):
            break
    return data


def run_interactive():
    global _COLOR_ENABLED, _resize_flag
    _COLOR_ENABLED = _use_color()
    use_proc = can_use_proc()
    # if stdin not a tty, fallback to once (pipe-friendly)
    try:
        is_tty = sys.stdin.isatty()
    except Exception:
        is_tty = False
    if not is_tty:
        return run_once()

    fd = sys.stdin.fileno()
    # save termios
    try:
        import termios as _termios
        import tty as _tty
    except ImportError:
        # no termios (e.g. Windows): just run once
        return run_once()
    try:
        old_attrs = _termios.tcgetattr(fd)
    except Exception:
        # can't get attrs, fallback
        return run_once()

    # signal for resize
    try:
        if hasattr(signal, "SIGWINCH"):
            signal.signal(signal.SIGWINCH, _sigwinch_handler)
    except Exception:
        pass

    sort_key = "cpu"
    descending = True
    help_active = False

    hz = get_hz()
    page_size = get_page_size()

    prev_cpu = read_cpu_times()
    # prime proc times for first-frame delta? first frame shows 0.0 per spec, so start empty
    prev_proc = {}
    prev_wall = time.monotonic()

    # enter alt screen / hide cursor only if color enabled (to guarantee zero escapes in dumb mode)
    entered_alt = False
    hid_cursor = False
    made_raw = False
    try:
        _tty.setcbreak(fd)
        made_raw = True
    except Exception:
        pass

    try:
        if _COLOR_ENABLED:
            try:
                sys.stdout.write("\x1b[?1049h")
                sys.stdout.flush()
                entered_alt = True
            except Exception:
                entered_alt = False
            try:
                sys.stdout.write("\x1b[?25l")
                sys.stdout.flush()
                hid_cursor = True
            except Exception:
                hid_cursor = False
        # main loop
        # for ps fallback, no prev needed
        while True:
            keys = wait_keys(REFRESH)
            # handle resize flag (recompute anyway each tick)
            if _resize_flag:
                _resize_flag = False
            # help dismiss
            if help_active:
                if keys:
                    help_active = False
                    # dismiss, ignore those keys, fall through to refresh
                    keys = ""
                # pause table: skip sampling? we still need to repaint overlay; keep old data?
                # To pause, we reuse last data; simplest: keep prev data variables from last tick.
                # We'll store last frame data; if help_active and no new data, re-render same data.
                # For simplicity, if help_active (still active, no dismiss), just re-render last frame with same data?
                # Implement by skipping collect and reusing cached.
                pass

            # process keys if not in help (or just dismissed)
            quit_req = False
            if not help_active and keys:
                for ch in keys:
                    if ch == "\x03":  # Ctrl-C byte in raw mode
                        quit_req = True
                        break
                    elif ch == "q" or ch == "Q":
                        quit_req = True
                        break
                    elif ch == "h" or ch == "?":
                        help_active = True
                        break
                    elif ch == "c":
                        sort_key = "cpu"
                        descending = True
                    elif ch == "m":
                        sort_key = "mem"
                        descending = True
                    elif ch == "n":
                        sort_key = "name"
                        descending = False
                    elif ch == "p":
                        sort_key = "pid"
                        descending = False
                    elif ch == "r":
                        descending = not descending
                    else:
                        # ignore (including escape sequences, arrows)
                        # ESC is \x1b, [ , A etc. ignore
                        pass
                    if help_active:
                        break
            if quit_req:
                break

            # sample data (skip if help_active and we want pause? still sample but overlay hides; to truly pause, skip)
            # We'll skip sampling while help_active to pause table.
            if help_active:
                # need cached data from last tick; if first tick help? use current sample once
                if not hasattr(run_interactive, "_cached"):
                    # first time, collect once to have something
                    pass
                else:
                    cached = run_interactive._cached
                    # re-render cached with help overlay, new size
                    try:
                        sz = shutil.get_terminal_size(fallback=(80, 24))
                        w, h = sz.columns, sz.lines
                    except Exception:
                        w, h = 80, 24
                    if w <= 0:
                        w = 80
                    if h <= 0:
                        h = 24
                    lines = render_frame(w, h, cached[0], cached[1], cached[2],
                                         sort_key, descending, True, use_proc, pad=True if _COLOR_ENABLED else False)
                    # write frame
                    if _COLOR_ENABLED:
                        frame = "\x1b[H\x1b[J" + "\n".join(lines)
                        # ensure single buffered write
                        sys.stdout.write(frame)
                        sys.stdout.flush()
                    else:
                        sys.stdout.write("\n".join(lines) + "\n")
                        sys.stdout.flush()
                    continue

            cur_wall = time.monotonic()
            elapsed = cur_wall - prev_wall
            if elapsed <= 0:
                elapsed = REFRESH
            # guard absurd elapsed (e.g. after help pause long): clamp? if help paused, elapsed large -> cpu spikes? but we skip sampling in help so elapsed includes pause; on resume, elapsed large -> cpu underestimated. Clamp elapsed to REFRESH*2? Better: if elapsed > 5, set elapsed to REFRESH? Actually jiffies delta over long pause still correct / elapsed -> correct avg. But if we skipped sampling, prev is old, elapsed large, still correct avg over pause. Okay keep.
            # clamp tiny?
            if elapsed < 0.2:
                elapsed = 0.2

            # automatic fallback whenever /proc/stat unreadable
            if use_proc:
                _probe = read_cpu_times()
                if not _probe:
                    use_proc = False
                else:
                    cur_cpu = _probe
            if use_proc:
                usages = compute_cpu_usages(prev_cpu, cur_cpu)
                ordered = []
                # aggregate + per-core sorted numerically
                per = [(k, v) for (k, v) in usages.items() if k != "cpu"]
                def ck(x):
                    try:
                        return int(x[0][3:])
                    except Exception:
                        return 9999
                per = sorted(per, key=ck)
                if "cpu" in usages:
                    ordered = [("cpu", usages["cpu"])] + per
                else:
                    ordered = per
                mem_total, mem_used = read_meminfo()
                try:
                    procs, new_prev, running, totalp = collect_linux(prev_proc, elapsed, mem_total, hz, page_size)
                except Exception:
                    procs, new_prev, running, totalp = [], prev_proc, 0, 0
                try:
                    load = os.getloadavg()
                except Exception:
                    load = None
                try:
                    ncpu_count = os.cpu_count()
                    if not ncpu_count:
                        ncpu_count = len(per) or 1
                except Exception:
                    ncpu_count = len(per) or 1
                header_info = {"load": load, "mem_total": mem_total, "mem_used": mem_used,
                               "running": running, "total": totalp, "ncpu": ncpu_count,
                               "mode": "/proc"}
                # update prev for next tick
                prev_cpu = cur_cpu
                prev_proc = new_prev
                prev_wall = cur_wall
            else:
                mem_total, mem_used = read_meminfo()
                try:
                    load = os.getloadavg()
                except Exception:
                    load = None
                procs, running, totalp = collect_ps()
                try:
                    ncpu_count = os.cpu_count() or 1
                except Exception:
                    ncpu_count = 1
                try:
                    total_cpu = sum(p.cpu for p in procs)
                    agg = min(100.0, total_cpu / float(ncpu_count)) if ncpu_count else 0.0
                except Exception:
                    agg = 0.0
                ordered = [("cpu", agg)]
                header_info = {"load": load, "mem_total": mem_total, "mem_used": mem_used,
                               "running": running, "total": totalp, "ncpu": ncpu_count,
                               "mode": "ps fallback"}
                prev_wall = cur_wall

            procs_sorted = sort_procs(procs, sort_key, descending)
            # cache for help pause
            run_interactive._cached = (header_info, ordered, procs_sorted)

            try:
                sz = shutil.get_terminal_size(fallback=(80, 24))
                w, h = sz.columns, sz.lines
            except Exception:
                w, h = 80, 24
            if w <= 0:
                w = 80
            if h <= 0:
                h = 24
            lines = render_frame(w, h, header_info, ordered, procs_sorted,
                                 sort_key, descending, help_active, use_proc,
                                 pad=True if _COLOR_ENABLED else False)
            if _COLOR_ENABLED:
                frame = "\x1b[H\x1b[J" + "\n".join(lines)
                sys.stdout.write(frame)
                sys.stdout.flush()
            else:
                # plain scrolling, no escapes
                sys.stdout.write("\n".join(lines) + "\n")
                sys.stdout.flush()

    except KeyboardInterrupt:
        # graceful, no traceback
        pass
    finally:
        # restore terminal perfectly
        try:
            _termios.tcsetattr(fd, _termios.TCSADRAIN, old_attrs)
        except Exception:
            pass
        try:
            if hid_cursor:
                sys.stdout.write("\x1b[?25h")
        except Exception:
            pass
        try:
            if entered_alt:
                sys.stdout.write("\x1b[?1049l")
        except Exception:
            pass
        try:
            # clean line: ensure prompt on fresh line, no garbage
            # only emit newline (no escapes) to move to clean line
            sys.stdout.write("\n")
            sys.stdout.flush()
        except Exception:
            pass
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="ProcScope - stdlib process monitor TUI (%s)" % SIGNOFF)
    ap.add_argument("--once", action="store_true", help="print one snapshot frame and exit")
    args = ap.parse_args(argv)
    if args.once:
        try:
            return run_once()
        except KeyboardInterrupt:
            return 0
        except BrokenPipeError:
            # pipe closed (e.g. | head): exit 0 quietly
            try:
                devnull = os.open(os.devnull, os.O_WRONLY)
                os.dup2(devnull, sys.stdout.fileno())
            except Exception:
                pass
            return 0
    else:
        try:
            return run_interactive()
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    sys.exit(main())

