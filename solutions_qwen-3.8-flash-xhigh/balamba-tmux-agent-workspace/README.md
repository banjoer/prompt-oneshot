# Balamba — the "textualize" build

**Projects → tasks (git worktrees) → terminals, rebuilt entirely in Python +
Textual.**

> Sign-off (spec requirement 15): produced **2026-11-25** by **Qwen 3.8 Flash
> (thinking effort: xhigh)**. The same line lives in the `bin/balamba` header,
> in `balamba doctor`, and behind the `C-a ?` help screen (`about` section).

```
┌──────────────────┬───────────────────────────────┬──────────────────┐
│ tree        (~30)│ tab content (live terminal)   │ git         (~34)│
│ ▾ widget         │  $ echo hi                    │ ── git: fix ──   │
│   ▾ fix login    │  hi                           │ ↑2 ↓0 vs main    │
│     ◈ opencode ●│  …                             │ [M ] app.py      │
│   ◇ sh:widget    │                               │ [??] notes.md    │
├──────────────────┴───────────────────────────────┴──────────────────┤
│ balamba · widget/fix-login   [1:opencode ●] [2:sh:widget]    C-a?   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## The twist

The original challenge mandates a Bash + tmux implementation whose chrome is
tmux panes driven by one stdlib-Python renderer. **This build keeps the
*behavioral* specification — projects, tasks, worktrees, terminals, restore,
git panel, close flows, bindings, state — but implements the entire interface
in Python + Textual.** Per the twist:

* every piece of chrome (layout, tree pane, git pane, status bar, tabs,
  dialogs, key bindings, mouse clicks & wheel) is a Textual widget, screen,
  binding or event;
* tmux or plain terminal sessions may only host *terminal content* — this
  build uses **plain PTY sessions** (`os.openpty` + `subprocess.Popen`) with
  an embedded stdlib VT/xterm emulator, so **tmux is not used at all**;
* there are no tmux-driven chrome panes and no tmux mouse bindings anywhere.

## Quick start

Requirements: Linux/macOS, Python ≥ 3.10 with **Textual** (`pip install
textual` — the one allowed dependency of the twist; everything else is
stdlib), `git`, and `opencode` on `PATH` for agent tabs. No network, no other
installs.

```bash
bin/balamba                 # launch the workspace UI
bin/balamba doctor          # health check (+ sign-off line)
bin/balamba project add ~/src/widget
bin/balamba task list
bin/balamba save
```

First run writes `~/.config/balamba/config` (sourced-bash *style* — parsed,
never executed) if missing. On an empty tree press `p` and pick a git **main
checkout**. `n` starts the new-task flow; `t` opens a terminal; the terminal
you see *is* a live PTY (try `vim`, `htop`, or the configured agent).

Tests: `python3 -m pytest tests/` (65 tests: VT emulator, config/state/locks,
git + worktree flows, and full Textual-pilot UI flows including dialogs, tabs
and mouse hit-testing).

---

## File-layout reinterpretation

The spec's layout (`lib/*.sh`, `pane/ui.py`, `tmux.conf`) belonged to a Bash +
tmux program; the twist makes the interface (and in practice everything)
Python + Textual, so each spec file maps to a module:

| spec file (original)      | this build                                   | role |
|---------------------------|----------------------------------------------|------|
| `bin/balamba`             | `bin/balamba` (Python, executable)           | entry point: UI or subcommands; sign-off header |
| `lib/common.sh`           | `lib/balamba/common.py`                      | config parse, state.json read/write, `fcntl.flock` locking, slugs, uuids |
| `lib/tmux.sh`             | `lib/balamba/term.py` + `lib/balamba/vt.py`  | session hosting: PTY children + screen model (was: tmux server, windows, panes, chrome, restore) |
| `lib/git.sh`              | `lib/balamba/gitops.py`                      | project validation, worktree add/list/remove, status/rev-list/diff |
| `lib/task.sh`             | `lib/balamba/task.py`                        | new task (slug/collision), close task, terminal specs, reconcile |
| `pane/ui.py` (stdlib renderer) | `lib/balamba/ui*` — `app.py`, `panes.py`, `twidget.py`, `dialogs.py` | all rendering & interaction, as Textual widgets/screens |
| `tmux.conf`               | **dropped**                                   | no tmux server exists in this build; bindings live in `BalambaApp.BINDINGS` + config |
| `SPEC.md`                 | this README + the original oneshot           | deviations documented here instead |

`BALAMBA_CONFIG_DIR` / `BALAMBA_STATE_DIR` env vars relocate config/state
(used by the test-suite; handy for side-by-side instances).

---

## Requirement-by-requirement reinterpretations

### 1. Dedicated tmux server → single-instance PTY host

No tmux server is created (`doctor` explains). The running Textual process
*is* the "server": it owns every hosted PTY session and holds
`~/.local/state/balamba/balamba.lock` via a non-blocking `fcntl.flock`.
**Deviation:** a second `bin/balamba` cannot "attach" to the first one's
screens (you cannot share one terminal between two apps), so instead of
attaching it refuses to start with an explanation. Everything the spec
promised about `tmux -L balamba -f …tmux.conf`, prefix C-a *in tmux*, and
server persistence is therefore re-implemented at application level:
the prefix key (`C-a`, configurable) is intercepted by the Textual app
itself.

### 2. Three-column chrome → Textual layout

`TreePane | ContentStack | GitPane` above a `StatusBar`, all Textual widgets
(`compose()` + CSS). Widths come from config (`BALAMBA_TREE_WIDTH`,
`BALAMBA_GIT_WIDTH`), reasserted on start (the "attach" moment), on every
context activation, and on `C-a r`. **Deviations:**

* *"Chrome replicated per window / panes in inactive windows poll at 0.2 Hz"*
  — irrelevant: there is one chrome instance, not a per-window copy; it is
  always coherent. Inactive tabs keep running (their output is buffered into
  their own VT screens) and activity is push-based from the reader thread,
  strictly better than tmux's focus-event hack.
* *"Splits are native tmux"* — **not reimplemented** (see 6). Each tab hosts
  exactly one PTY. You can still run tmux *inside* a shell tab; that is the
  spec's "plain terminal session hosting content", and balamba neither drives
  nor renders it.
* The tmux status bar's clickable tab list becomes a custom `StatusBar`
  widget: `balamba · <context>` + `[1:name] [2:name ●] …` segments hit-tested
  from `MouseUp` (click switches tab; wheel over the bar cycles tabs).

### 3. Tree hierarchy & navigation

Everything from the spec is kept, now as Textual machinery:
project → tasks → terminals, scratch terminals under a project, active
project expanded / others collapsed, manual expand state persisted in
state.json (extra `expanded` per task — a documented state-schema addition,
ignored by other tools), and the key set `j/k ↑/↓ h/l Enter n t d e p g/G
PgUp/PgDn` bound **on the TreePane** (they act only while it has focus, like
"tree-level keys work while the tree pane is focused").

Mouse (pure Textual events, zero tmux bindings):

* left click on a row: select + activate (first click on the unfocused pane
  both focuses and activates — `on_mouse_down` focuses, `on_mouse_up` does
  the work in the same gesture);
* click on the chevron columns (x < 3): collapse/expand;
* right-click: context menu — `ChoiceScreen` anchored at the pointer
  (activate / new task / new terminal / close / editor / remove / copy path /
  restart);
* wheel: in-app scrolling of the tree (custom `view_top`, no container
  needed); with `C-a [` select mode you can also drag-select the rendered
  text (Textual screen selection).
* **Unread dot:** each session tracks `unread`; the reader thread marks it
  whenever bytes arrive while that tab is not the viewed one (same semantics
  as `window_activity_flag`), cleared when you activate the tab. Dots bubble
  up to task and project rows. No bells, no desktop notifications, no agent
  plugins (the bell byte is counted internally only).

### 4. Projects

`p` / `C-a P` / `balamba project add <path>`: `git rev-parse --show-toplevel`
must equal the path; a linked worktree (git-dir ≠ git-common-dir) is **added
with a warning**; anything else is rejected (in the UI the prompt stays open
with the reason). `balamba project remove` / the tree menu / `d` on a project
row remove from balamba only — the folder is never touched (double-confirmed
in the UI).

### 5. New task flow

`n` / `C-a N` opens the spec's ordered prompts as Textual `PromptScreen`s:
name (free text, stored as-is) → slug (prefilled from `make_slug`: lowercase,
spaces→`-`, strip to `[a-z0-9._-]`, collapse dashes; validated with
`git check-ref-format --branch`) → `create from:` (prefilled literally
`origin/main`; validated with `git rev-parse --verify <ref>^{commit}`) →
`agent | shell` `ChoiceScreen`. Collisions (folder or branch exists) suffix
**both** slug and display name (`-2`, `-3`, …). Creation is exactly one
command: `git worktree add --no-track -b <slug> <path> <ref>`; the worktree
maps to `/path/to/balamba_worktrees/<project_folder>/<slug>`. The task stores
`base` for ahead/behind, and `--no-track` keeps the branch upstream-free
(verified by the test-suite: `rev-parse <branch>@{upstream}` fails).
Then balamba switches to the task, starts the terminal and focuses it.

### 6. Terminals as tabs

Each terminal tab = one hosted PTY session: agent tabs run the rendered
config template (default `opencode --session ses_<32 hex>`, id generated at
creation exactly as the spec: `ses_` + `uuid4().hex`), shell tabs run
`$SHELL` — always in the tab's cwd (set at spawn, updated from live `/proc`
polls). Agent definitions come from config (`BALAMBA_AGENTS`,
`BALAMBA_AGENT_<name>_COMMAND/_RESUME` with `{{session}}`/`{{dir}}`), so
adding a *second* agent is config-only — the stretch goal holds verbatim
(`tests/test_common.py` exercises it). `t` / `C-a T` shows the `agent | shell`
menu; with several agents configured, a second menu picks the agent.
**Deviation:** splits inside a tab (originally "native tmux") are not
re-implemented; the middle column hosts one PTY per tab, and multi-paning
remains available by running tmux yourself inside a shell tab.

### 7. Restore across restarts

There is no live server to reattach to (see 1), so **every start takes the
spec's "server gone" branch**: rebuild windows in saved order (projects →
tasks → tabs), relaunch agent tabs with their saved `ses_…` id via the RESUME
template, staggered 0.8 s apart; shells get a fresh `$SHELL` in the saved cwd
(`pane_current_path` → `os.readlink("/proc/<pid>/cwd")`, captured on a 2 s
poll and at quit; macOS fallback = last known cwd — documented gap); the
active project/task/tab and tree selection are stored in state (`balamba_ui`
key) and restored; sidebar widths reasserted at start.
**Deviations:** `window_layout` geometry restoration is not applicable
(one-PTY-per-tab, no pane trees), so the field is kept in the schema but
unused, and `active_pane` is likewise schema-compatible-but-unused.
Startup reconciliation (`git worktree list`) drops vanished worktrees, drops
non-repo project paths, and never adopts unknown `balamba_worktrees` dirs.

### 8. Git side panel

`GitPane` for the active context (task worktree or project checkout): branch
(`rev-parse --abbrev-ref HEAD`, with detached short-hash + ⚠), ahead/behind
as `↑a ↓b` computed with `git rev-list --left-right --count <ref>...HEAD`
against the **upstream when set, else the task's stored base**, changed files
from `git status --porcelain=v1 -z` (NUL parsing incl. rename original
paths) with the two-character `XY` markers colored by staged / unstaged /
untracked. Refresh: on context change, on git-pane focus, and every ~2 s —
all in an exclusive Textual thread worker (never blocks or steals focus).
Click (or `j/k` + Enter) opens the **diff popup** (`DiffScreen`, a Textual
modal): `git diff -- <file>` for unstaged, `git diff --cached -- <file>` for
staged-only, `git diff --no-index /dev/null <file>` for untracked.
**Deviation:** the popup's "piped to a pager" (`less` in a `display-popup`)
becomes an in-app read-only pager (j/k/↑/↓/PgUp/PgDn/g/G/q + wheel +
Textual drag-selection). Read-only; no staging UI; still inside the allowed
git surface.

### 9. Close task

`d` on a task row: `assess_close` checks `git status --porcelain` (dirty) and
detached HEAD, and `ConfirmScreen` step 1 lists the warnings with
Cancel/Continue (`Cancel`/Esc → nothing happens). Step 2 confirms that **the
worktree will be deleted** and carries the spec's `delete branch too` toggle
(space/x toggles; default **off** = keep the branch). On confirmation:
the task's tabs (windows) are killed, `git worktree remove` runs (`--force`
only when the tree was dirty — which the second confirmation already covered),
`git branch -d` runs only when the option is ticked (unmerged branches are
never silently dropped — refusal is reported and the branch kept), then the
task disappears from state. No commits, pushes, or merges, ever.
`d` on a terminal row closes that terminal (kills the PTY, removes the tab —
tmux's kill-pane semantics); `d` on a project removes it from balamba.

### 10. Open in editor

`e` / `C-a e`: a modal `EditorScreen` hosting a live `TerminalWidget` running
`$EDITOR` (config `BALAMBA_EDITOR`, `${EDITOR:-nvim}` semantics honored) with
the worktree as cwd. The three-column layout stays mounted underneath the
modal — exactly the `display-popup` goal ("preserving the three-column
layout"). When the editor process exits the screen closes; a missing editor
exits quickly with a warning toast instead of wedging.

### 11. State, config, locking

`~/.local/state/balamba/state.json` stays the single source of truth and the
sample skeleton's schema (`version`, `projects[].path/expanded/scratch`,
`tasks[].slug/name/path/base/windows/window_layout/active_window/active_pane`)
— written atomically (tmp + rename) under an exclusive `fcntl.flock` on
`state.json.lock` (`flock` in bash). Documented schema additions: `uid` per
terminal tab (session identity independent of index churn), `name` per task
terminal (tab label), per-task `expanded`, and a top-level `balamba_ui`
(active context) — all ignorable by external tools. Config is the same
sourced-bash file, **parsed not executed** (KEY=VALUE, arrays,
`${VAR:-default}` expansion, `BALAMBA_AGENT_<name>_{COMMAND,RESUME}`).
**Deviation:** mirroring into tmux `@balamba_*` options is dropped — one
process reads one config object, so drift is impossible by construction
(the spec's stretch "width round-trip" still works: edit config, restart,
`on_mount` reasserts; `C-a r` reasserts live).

### 12. Invocation & doctor

`balamba` (UI), `project add|remove`, `task list`, `save`, `doctor` — all in
`bin/balamba` → `cli.py`. `doctor` reports: the server reinterpretation +
live-instance lock state (+ tmux version "present, deliberately unused"),
state validity + missing worktrees per project, config values + agents, and
tool availability (git, **opencode**, shell, editor, pty, textual). It prints
the sign-off line. Exit code 1 when checks fail.

### 13. Bindings

`C-a` is a *Textual* prefix: `Binding("ctrl+a","prefix")` (configurable via
`BALAMBA_PREFIX`) sets a pending state that the app intercepts **before**
widget dispatch (an `App.on_event` override when pending — this reproduces
tmux's "prefix steals the next key" across every pane). Chords:
`N P T` new task/project/terminal, `e` editor, `d` detach, `r` redraw,
`o` cycle focus (tree → terminal → git), `g` git pane, `n/p` + `1..9` tabs,
`[` select mode, `?` help, `C-a C-a` forwards a literal `0x01` to the
terminal, `Esc` cancels; unknown keys are swallowed, tmux-style. The status
bar shows the `[C-a]` indicator while armed. When the terminal is focused,
every other keystroke goes to the PTY — that is the whole point of the
interface, and Textual's key dispatch provides it (widgets see keys first;
Textual's own priority `ctrl+q` quit was overridden to *forward* `^Q` when a
terminal has focus and only quit from chrome).
**Deviations:** `C-a d` cannot "detach and leave a live server" — sessions
are children of this process, so `C-a d` = save-and-quit, and next start
rebuilds + resumes (spec's restore path). Tree-level keys are prefix-free
while the tree is focused, as required. All bindings are editable in code
(`BINDINGS` / `_resolve_prefix` table); only the prefix key is
runtime-configurable (documented gap vs "all bindings configurable").

### 14/15 & Constraints

File layout: adapted above (the twist supersedes "bash + one ui.py"); the
git surface stays inside the allow-list (`rev-parse`, `check-ref-format`,
`worktree list/add/remove`, `branch -d`, `status`, `rev-list`, `diff`); no
network, no third-party servers; only Textual is added (mandated by the
twist); `pyte`-free: the VT emulator (`vt.py`) is stdlib-only.
Sign-off appears in `bin/balamba`, `balamba doctor`, and `C-a ?`.

---

## The embedded terminal (how content is hosted)

`vt.py` implements the working subset of xterm: UTF-8 text with east-asian
widths, deferred autowrap, C0 controls, tabs + `TBC`/`HTS`, CUU/CUD/CUF/CUB/
CNL/CPL/CHA/CUP/VPA, ED/EL (incl. `ED 3` clears scrollback), IL/DL/ICH/DCH/
SU/SD/ECH, SGR (16/256/24-bit + all intensity/attr resets), scroll regions,
DECSC/REST + ANSI `s`/`u`, `ESC 7/8`, Index/NEL/RI, `ESC c` hard reset,
alternate screen (47/1047/1049), hidden cursor, DECCKM, bracketed paste
(2004), focus reporting (1004), mouse reporting (9/1000/1002/1003/1006),
OSC 0/1/2 titles (others consumed), DSR/DA replies (cursor position, device
attributes), DCS/APC discarded, unknown sequences consumed silently.
`TerminalWidget` renders cell grids as styled `Text` per frame, translates
Textual `Key`/`Paste`/`Mouse*` events into terminal input (xterm-style
sequences incl. modified arrows, `CSI u` shift+enter, SGR mouse), honors the
child's mouse mode (wheel forwards when captured, scrolls scrollback
otherwise), and syncs size with `TIOCSWINSZ` on every layout change. Verified
against the real **opencode v2.3.2 TUI** (banner, prompt box, truecolor) in
an embedded session, plus zsh/vim-style full-screen apps in tests.

## Known gaps / honest deviations

1. No in-tab pane splits (one PTY per tab; run tmux inside a shell if needed).
2. No live re-attach to a running instance (single-instance lock instead).
3. `C-a d` quits-and-saves rather than detaching a persistent server.
4. `window_layout`/`active_pane` kept in state but unused (no pane geometry).
5. Only the prefix key is config-remappable; other bindings are code-level.
6. Shell cwd polling needs `/proc` (Linux); on macOS the saved cwd is the
   spawn/last-captured one.
7. Text selection uses Textual's screen selection (select mode `C-a [`) or
   the outer terminal's own copy semantics; there is no tmux copy-mode.
8. Clipboard "copy path" surfaces the path in a toast (no external clipboard
   dependency was allowed).
9. Colors use the xterm palette; untracked-file "diff" uses
   `git diff --no-index /dev/null <file>` (still inside the diff surface).

## Testing

```bash
python3 -m pytest tests/            # 65 tests
```

* `test_vt.py` — emulator: colors, addressing, regions, IL/DL/SU/SD, wrap,
  wide chars, alt screen, scrollback, DSR/DA replies, OSC titles, DCS skip.
* `test_common.py` — slug rules, `ses_` ids, sample-config parsing, second
  agent via config only, state locking/corruption, instance lock, mapping
  `/path/to/proj → /path/to/balamba_worktrees/proj/slug`.
* `test_gitops.py` — real repos: main-checkout validation (+ worktree
  warning), `--no-track` (no upstream), ahead/behind, porcelain `-z` incl.
  renames, `branch -d` refusing unmerged, dirty/detached detection.
* `test_task_flow.py` — collision `-2/-3` on folder+branch+display name,
  close-task semantics (branch kept by default; force only when dirty),
  reconcile (dropped worktrees, never-adopt strays).
* `test_app_ui.py` — Textual pilot: three-column boot, scratch shell created
  on first activation, typing into a live PTY (`echo hi`), full `C-a N`
  dialog chain producing a real worktree + agent session id + `ses_` resume
  template across an app restart, unread dots for background tabs, tab
  switching (`C-a 1`, status-bar clicks), git panel rows + diff popup +
  in-app pager scrolling, two-step close with branch toggle, right-click
  menu, focus cycling, wheel scrollback + select mode, editor popup lifecycle,
  width reassertion, quit-saves-state, and the CLI surfaces (doctor/task
  list/save/version).

## Run

```bash
bin/balamba
```
