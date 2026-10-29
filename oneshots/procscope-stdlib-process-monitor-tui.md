# ProcScope: A Stdlib Process Monitor TUI

**Difficulty:** Hard  |  **Stack:** Python (standard library only)  |  **Estimated time:** 4–7 h

## The Problem

Every developer eventually reaches for `top` or `htop` when a machine starts
feeling slow — but those tools are black boxes. Building one yourself forces
you to confront real systems programming: parsing the kernel's `/proc`
pseudofiles, computing CPU deltas in jiffies, driving a terminal in raw mode
with ANSI escape codes, and handling resize signals without corrupting the
display. Your task is to build **ProcScope**, a self-contained, top-like
process monitor that runs anywhere Python 3 does — no curses, no psutil, no
third-party packages — reading straight from `/proc` on Linux with an
automatic `ps` fallback elsewhere.

## Requirements

1. **Full-screen TUI.** On startup, switch to the terminal's alternate screen,
   hide the cursor, and put the TTY into raw/cbreak mode via `termios`/`tty`.
   Render a layout with three regions: (a) a header bar showing system summary
   (load average if available, total/used memory, running/total process
   count), (b) a per-core CPU meter section, and (c) a process table filling
   the remaining rows.
2. **`/proc` data source (primary).** On Linux, read `/proc/stat`,
   `/proc/meminfo`, and each `/proc/<pid>/stat` (plus `/proc/<pid>/status` for
   RSS/UID when needed). Compute per-process **CPU%** from the delta of
   `utime + stime` jiffies between refreshes, relative to the elapsed wall
   time and jiffy rate (`os.sysconf("SC_CLK_TCK")`), as a percentage of one
   CPU. Compute **MEM%** as the process RSS divided by `MemTotal`. The first
   frame may show `0.0` CPU since no delta exists yet.
3. **Automatic `ps` fallback.** If `/proc/stat` cannot be opened (e.g.
   macOS), fall back — with no flags and no user intervention — to parsing
   `ps -Ao pid=,user=,comm=,%cpu=,%mem=,stat=` (or an equivalent invocation)
   once per refresh. In fallback mode the per-core section may collapse to a
   single aggregate CPU bar; everything else must keep working.
4. **Live refresh.** Redraw approximately once per second. Each tick:
   re-sample all data, re-sort, and repaint the whole frame with a **single
   buffered write** to stdout (build the frame in a list of strings, join,
   write once, flush) so there is no visible flicker or tearing.
5. **Process table.** Columns (left to right): `PID`, `USER`, `NAME`,
   `CPU%`, `MEM%`, `STATE`. `NAME` is the `comm` value, or a truncated
   `cmdline` when `comm` is unhelpful. Percentages are right-aligned with one
   decimal. The header of the currently-sorted column must be visually
   highlighted (e.g. reverse video).
6. **Per-core CPU bars.** One labeled bar per logical CPU (`cpu0`, `cpu1`,
   …) computed from `/proc/stat` line deltas: `usage = 100 × (1 − (idle +
   iowait) / total)` between refreshes. Draw bars with block characters
   (`█`/`░` or `#`/`-` in ASCII fallback) scaled to the available width;
   when the terminal is wide enough, arrange the bars in two or more columns.
   Bars must be colored: green under ~50 %, yellow to ~80 %, red above.
7. **Sort key bindings.** `c` sorts by CPU%, `m` by MEM%, `n` by NAME, `p`
   by PID. `r` toggles ascending/descending on the active key. Default:
   CPU% descending. Name sort must be case-insensitive; the sort must be
   stable.
8. **Help overlay.** `h` or `?` pauses the table and shows a centered overlay
   listing every key binding; any keypress dismisses it and live updates
   resume.
9. **Graceful resize.** Handle `SIGWINCH`: within one refresh cycle of a
   resize, recompute the layout from `shutil.get_terminal_size()`, truncate or
   drop columns that no longer fit, and never crash, wrap, or leave stale
   artifacts on screen. Below ~40 columns or ~10 rows, replace the UI with a
   centered "terminal too small" notice until space returns.
10. **Graceful quit.** `q` and Ctrl-C (SIGINT) behave identically: restore the
    saved termios attributes, show the cursor, leave the alternate screen, and
    exit with status 0 and no traceback — the shell prompt must return on a
    clean line with no escape-sequence garbage.
11. **Non-blocking input.** Read keys with `select` (or equivalent) so the
    display keeps refreshing when no key is pressed, and multiple keys typed
    during one tick are all consumed on the next tick.
12. **Snapshot mode.** `python3 procscope.py --once` prints one complete
    non-interactive frame (header, bars, top rows) to stdout and exits 0 —
    usable in a pipe, so it must emit no cursor-movement codes in this mode.
13. **Color discipline.** All color/styling goes through a tiny internal
    helper; when `NO_COLOR` is set in the environment or `TERM` is `dumb`
    (or missing), render plain monochrome ASCII with no ANSI codes at all.
14. **Sign-off:** the finished solution must display, somewhere easy to spot,
    the date and time it was produced and the model/author that produced it
    (e.g. a header comment in the source, a footer on the page, or an about
    line in the CLI).

## Constraints

- Python 3.8+ **standard library only**. Suggested: `os`, `sys`, `time`,
  `signal`, `select`, `termios`, `tty`, `shutil`, `subprocess`, `argparse`,
  `dataclasses`. Explicitly forbidden: `curses`, `psutil`, `urwid`, `rich`,
  `textual`, and any third-party package.
- Single-file deliverable, from scratch; no downloads, no build step, no
  config files, no network access. `/proc` and `ps` are read-only inputs.
- Must run correctly on Linux (primary) and degrade via the `ps` fallback on
  systems without `/proc`.
- The process table must handle processes that disappear between the scan and
  the per-PID reads (race condition) without crashing — just skip them.
- `/proc/<pid>/stat` parsing must be robust to process names containing
  spaces or parentheses: split on the **last** `)` before reading fields.

## Sample Data / Inputs

Representative `/proc/stat` excerpt your parser must handle (aggregate line
first, then one line per logical CPU; fields are `user nice system idle
iowait irq softirq steal guest guest_nice`):

```
cpu  2255 34 2290 22625563 6290 127 456 0 0 0
cpu0 1132 34 1441 11311718 3675 127 438 0 0 0
cpu1 1123 0  849  11313845 2614 0   18  0 0 0
```

Representative `/proc/meminfo` excerpt (use `MemTotal`; `MemAvailable` is a
nicer "used" basis than `MemFree`):

```
MemTotal:       16331828 kB
MemFree:         1234567 kB
MemAvailable:    7654321 kB
```

Representative `/proc/1234/stat` line — note the parenthesized `comm` (field
2) may contain spaces/parens; fields after it: `state ppid pgrp session
tty_nr tpgid flags minflt cminflt majflt cmajflt utime stime ...`, so `state`
is field 3, `utime` field 14, `stime` field 15:

```
1234 (python3) S 1 1234 1234 0 -1 4194304 1234 0 0 0 12 4 0 0 20 0 1 0 100 12345678 1500 18446744073709551615 1 1 0 0 0 0
```

Representative `ps` fallback output for
`ps -Ao pid=,user=,comm=,%cpu=,%mem=,stat=`:

```
    1 root     /sbin/init   0.0  0.1 Ss
  412 canjou1  /usr/bin/zsh 0.1  0.3 S
 1337 canjou1  python3      47.2 1.8 R+
```

To generate load for manual verification, run in another shell:

```
python3 -c "while True: pass"
```

That busy-loop process should climb to the top of the CPU-sorted table within
two refresh ticks, at ~100 % CPU.

## Deliverable

- Exactly one file: **`procscope.py`**
- Run interactively: `python3 procscope.py`
- Snapshot (pipe-friendly): `python3 procscope.py --once`

## Done When

- [ ] `python3 procscope.py` opens a full-screen live view: header summary,
      one bar per logical CPU, and a process table that visibly updates about
      once per second without flicker.
- [ ] Pressing `c`, `m`, `n`, `p` re-sorts the table and moves the header
      highlight; pressing `r` reverses the order.
- [ ] The busy-loop command from Sample Data drives a `python3` process to the
      top of the CPU-sorted table at ~100 % CPU%, and the corresponding core's
      bar lights up red.
- [ ] Resizing the terminal (drag a corner, or `tmux resize-pane`) re-lays out
      within a second — no crash, no wrapping artifacts; shrinking below ~40
      columns shows the "terminal too small" notice and growing back restores
      the UI.
- [ ] `h` shows the key help overlay; any key dismisses it and updates resume.
- [ ] `q` **and** Ctrl-C each restore the terminal perfectly: cursor visible,
      prompt on a clean line, exit code 0, no traceback.
- [ ] `python3 procscope.py --once | head -20` prints a readable snapshot and
      the command exits 0.
- [ ] With `NO_COLOR=1` (or `TERM=dumb`) the UI renders in plain ASCII with
      zero escape codes, in both interactive and `--once` modes.
- [ ] The code contains an automatic `ps`-based fallback taken whenever
      `/proc/stat` is unreadable, and no forbidden module is imported
      (`grep -E "import (curses|psutil)" procscope.py` finds nothing).
- [ ] The sign-off line (date, time, author/model) is visible when running the
      app and/or in the source header.

## Stretch Goals (optional)

- Arrow keys / `PgUp` / `PgDn` scroll the process table, with the selected row
  highlighted and the view following the selection.
- `/` opens an inline filter prompt; the table narrows to processes whose
  name or cmdline contains the typed substring (case-insensitive), live as you
  type, `Esc` clears.
- `k` prompts for confirmation and sends `SIGTERM` to the selected process
  (second press within the timeout escalates to `SIGKILL`).
