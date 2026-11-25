# balamba — Textual workspace (projects → worktrees → terminals)

Produced: 2026-11-25 by Muse Spark 1.3 Contributor (opencode-go).

Keyboard-first manager for parallel coding agents: each task is a git
worktree, each terminal is a tab, all state in one JSON file, full resume
across restarts.

## Run

```sh
pip install -r requirements.txt   # needs textual>=8
bin/balamba                       # build-and-attach (first run), or attach
bin/balamba doctor                # server/socket, state, worktrees, opencode
bin/balamba project add|remove <path>
bin/balamba task list
bin/balamba save
```

Prerequisites: Linux/macOS, `tmux` ≥ 3.x, `git`, `opencode` on `PATH`
for agent tabs, Python 3.10+ with `textual`.

## Architecture (TWIST: Textual owns all chrome)

```
┌──────────────┬────────────────────────────┬─────────────────┐
│ Tree  (~30)  │ Tabs + terminal content    │ Git      (~34) │
│ Textual Tree │ capture-pane views + Input │ Textual Static  │
└──────────────┴────────────────────────────┴─────────────────┘
  status bar (Textual): balamble · <context>   [clickable tabs]
```

- `app/main.py` — the entire interface as Textual widgets/screens/events:
  three-column layout, `Tree` pane, terminal tab views, git pane, status
  bar with clickable tab buttons, wizard/modal dialogs, key bindings,
  mouse (click/wheel/right-click). This is the only UI.
- `app/backend.py` — stdlib-only bridge: state, config, tmux-backend and
  git helpers used by the UI.
- `bin/balamba` — entry point: launches the Textual UI, plus
  `project add|remove`, `task list`, `save`, `doctor` subcommands.
- `lib/common.sh` — config/state paths, locking helpers.
- `lib/tmux.sh` — **backend-only** tmux helpers (windows/panes,
  capture-pane, send-keys, activity, restore). Creates no chrome.
- `lib/git.sh` — project validation, worktree add/remove, status
  (restricted git surface: `rev-parse`, `check-ref-format`, `worktree`,
  `branch -d`, `status`, `rev-list`, `diff` only).
- `lib/task.sh` — slug/ID helpers, worktree paths, agent command templates.
- `pane/ui.py` — compatibility shim: preserves the deliverable path and
  simply launches the Textual UI (`app/main.py`).
- `tmux.conf` — **backend-only** server config (see deviations).
- State: `~/.local/state/balamba/state.json` (flock for writers, atomic
  replace), reconciled against `git worktree list` at startup.
- Config: `~/.config/balamba/config` (sourced bash); the UI reads it
  directly and mirrors widths/editor/agent into tmux `@balamba_*` options.

## Keys

Prefix `C-a`, then: `N` new task · `P` add project · `T` new terminal ·
`e` editor · `d` quit UI (backend server keeps running) · `r` redraw ·
`1..9` tabs · `n/p` next/prev tab. `?` help.
Tree focused (no prefix): `j/k`/arrows move · `h/l` collapse/expand ·
`Enter` activate · `n/t/d/e/p` as above.
Mouse: click row select/activate, click chevron toggle, right-click menu,
wheel scrolls in-app. While typing in an input, keys are never hijacked
(press `Esc`/focus elsewhere first, then the prefix).

## Reinterpretations and tmux-specific deviations (TWIST)

The original design renders chrome *inside tmux* (tree/git panes per
window, tmux status bar, tmux mouse bindings). Per the twist, **all**
chrome is Textual and **tmux hosts terminal content only**. Concretely:

1. **No tmux-driven chrome.** `lib/tmux.sh` and `tmux.conf` create no
   sidebar panes, no status-bar content, no key tables for the UI, and no
   mouse bindings (`mouse off`). Chrome replication-per-window, 0.2 Hz
   inactive-pane refresh, and cross-window width reassertion are obsolete:
   there is exactly one logical sidebar (Textual widgets), so widths
   cannot drift. The 0.2 Hz poll is kept in equivalent form: inactive
   backend windows are polled for activity flags only, never captured.
2. **Terminal content via capture, not attach.** The middle pane renders
   `tmux capture-pane` polls (0.5 s) per backend pane and forwards typing
   via `send-keys`. Trade-off: full-screen TUIs such as opencode remain
   fully functional in tmux, but the chrome view shows plain-text polls
   with latency instead of pixel-perfect cursor addressing. Mitigations:
   agent sessions persist under the same ids, so `tmux -L balamba attach`
   shows them perfectly; `$EDITOR` opens via UI suspend (full terminal).
3. **Unread dots.** Computed from content-hash change while a window is
   not viewed, OR-ed with `window_activity_flag` (`monitor-activity on`
   is kept). Rationale: with no tmux client attached, nothing clears the
   tmux flag on view, so the UI clears unread state itself when you visit
   a window. No bells, no desktop notifications (unchanged).
4. **Text selection.** tmux copy-mode (`prefix+[`) does not exist here
   because tmux owns no input. In-app equivalents: wheel/keyboard
   scrollback in every pane, `copy path` in the right-click menu, and the
   diff popup for file contents.
5. **Splits.** Native tmux splits are still the mechanism (`split-window`,
   layout strings), but they are rendered stacked in the middle pane with
   click-to-focus; layout restore keeps the original heuristic (reapply
   `window_layout` only when the live pane count equals the saved leaf
   count, else equal splits). Active pane/window are stored separately
   from the layout string, as specified.
6. **`pane/ui.py` is a shim.** The stdlib-only in-tmux renderer from the
   original file layout cannot exist without tmux-driven chrome; the path
   is preserved as a launcher so the deliverable structure still resolves.
7. **Bindings live in code, not `tmux.conf`.** Prefix handling is a
   Textual `on_key` state machine (`app/main.py`); all app/tree actions
   funnel through `app_action`. They are changeable in one place rather
   than through tmux `bind-key`. Widths/editor/agents stay in
   `~/.config/balamba/config`.
8. **Detach = quit UI.** `C-a d` exits the Textual client; the dedicated
   `balamba` tmux server keeps running, so relaunching reattaches to live
   content (or rebuilds from state if the server is gone) — the same
   observable contract as tmux detach.
9. **Single client view.** tmux multi-client per-window chrome consistency
   ("replicated chrome staying consistent") is vacuous: every client runs
   its own Textual chrome over the same state file + backend server.

Everything else follows the embedded spec verbatim: dedicated `balamba`
server/session, project validation (`rev-parse --show-toplevel`, worktree
warning), slug rules + `-2`/`-3` collision suffixes,
`git worktree add --no-track -b <slug> <path> <ref>`,
`ses_` + 32-hex agent sessions, `$SHELL` shells, agent templates with
`{{session}}`/`{{dir}}`, staggered relaunch (~0.6 s), fresh shells in
saved cwds, git panel (branch, ahead/behind vs base or upstream,
staged/unstaged/untracked via `porcelain=v1 -z`, click → diff popup,
~2 s refresh, read-only), two-confirmation close with `--force` only
after confirmation and `git branch -d` (never silent on unmerged),
editor popup preserving layout, `flock` writers, JSON state as source of
truth with hand-removed worktrees dropped and unknown dirs never adopted.
