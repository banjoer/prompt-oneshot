# balamba — original specification

> Copied verbatim from the challenge appendix for reference. This build implements the UI with Python + Textual; see README.md for every reinterpretation.

# balamba — spec

A tmux-based, keyboard-first recreation of the parts of Orca I actually use:
projects → tasks (git worktrees) → terminals, with resume across restarts.

## Non-goals

- No GUI, no web UI, no browser panes, no annotations, no PR/merge automation.
- No custom model or agent protocol; balamba only launches agents you already have.
- No git operations beyond worktree add/remove and creating the task branch.
- Not a tmux replacement or a general workspace manager; it owns its own tmux server.

## Architecture

- Dedicated tmux server: `tmux -L balamba -f ~/.config/balamba/tmux.conf`, prefix `C-a`.
- Shell scripts do all tmux driving, state, git and worktree work.
- One stdlib-only Python file renders the two interactive panes (tree, git). No pip,
  no packages, no fzf. It reads state and talks to tmux; it never owns state.
- State lives in `~/.local/state/balamba/state.json` (+ `flock` for writers).
  `state.json` is the source of truth, reconciled against `git worktree list` at startup.
- Config lives in `~/.config/balamba/config` (sourced bash) and is mirrored into tmux
  options (`@balamba_*`) so the Python panes read the same values.

## Layout

One tmux session `balamba`; each terminal tab is a tmux window; splits are tmux panes.

```
┌──────────────┬────────────────────────────┬─────────────────┐
│ tree   (~30) │ tab content (splits)       │ git      (~34)  │
│ projects     │                            │ branch, ahead   │
│  └ tasks     │                            │ changed files   │
│     └ terms  │                            │                 │
└──────────────┴────────────────────────────┴─────────────────┘
  status bar (bottom): balamba · <context>            [tab] [tab]
```

- Chrome (tree + git) is replicated per window; the app treats it as one logical sidebar.
  Panes in the active window refresh at full rate; the others only check activation at ~0.2 Hz
  (a non-focused pane receives no focus event when its window becomes active).
- Sidebar width is a config value reasserted after attach and on activation; tmux has no
  cross-window layout sync, so widths drift otherwise.
- Empty context (project with no scratch terminals yet) gets one shell tab on first activation.
- Tabs are native windows: clickable in the status bar, `C-a 1..9`, `C-a n/p`.

## Tree

- Hierarchy: project (main checkout) → tasks (worktrees) → terminals (tabs).
- Projects can also host scratch terminals in the main checkout, alongside tasks.
- Active project expanded, others collapsed to one line; manual expand/collapse is remembered.
- Keyboard: `j/k`/arrows move, `h/l` collapse/expand, `Enter` activate, `n` new task,
  `t` new terminal, `d` close task, `e` open in editor, `p` add project.
- Mouse: click a row to select/activate, click the chevron to toggle, right-click for a menu.
  With `mouse on` the first click on a non-focused pane both focuses it and is delivered.
  Text selection needs `prefix+[` while a pane reports the mouse; wheel scrolling is in-app.
- Unread marker: a dot on a terminal/task row when its window produced output since last visit
  (`window_activity_flag`, requires `monitor-activity on`; the flag clears when a client views
  the window). No bells, no desktop notifications, no agent-status plugin.

## Project

- Add via `p` or `balamba project add <path>`: path must resolve to a git main checkout
  (`rev-parse --show-toplevel` equals the path; warn if it is itself a worktree).
- Remove from balamba only. Never touches the folder.

## New task

1. `task name:` (free text; stored as-is for display).
2. Slug from the name: lowercase, spaces → `-`, strip everything but `[a-z0-9._-]`,
   collapse dashes. Slug is the worktree folder name and the branch name.
   Validated with `git check-ref-format --branch`. Collision (folder exists, or local branch
   `<slug>` exists) → suffix both slug and display name: `<slug>-2`, `<slug>-3`, …
3. `create from:` free text, prefilled literally `origin/main`. Any ref that
   `git rev-parse --verify <ref>^{commit}` accepts works (local or remote).
4. Terminal: `agent` or `shell`.
5. Create worktree + branch in one command (see below), switch to the task, start the
   terminal, focus it.

Worktree path: `/path/to/project_folder` →
`/path/to/balamba_worktrees/<project_folder>/<slug>`.

```
git worktree add --no-track -b <slug> <path> <ref>
```

`--no-track` is deliberate: without it git auto-sets the new branch's upstream to the start
point (e.g. `origin/main`), which makes a stray `git push` target main.

## Terminals

- Each terminal is a tab: `kind` (`agent`|`shell`), agent name, session uuid (agents), cwd.
- Agent launch: `opencode --session ses_<32 hex>` in the tab's cwd. opencode rejects ids that do
  not start with `ses_`, so generate `ses_` + uuid4 hex at creation. The session materialises on
  the first message; the same id resumes it after a restart.
  Session titles are not set in opencode; readable names live in balamba's tree and tab title.
- Shell launch: `$SHELL` in the tab's cwd.
- New terminals: `t` / `C-a T` → menu `agent | shell`. Splits inside a tab are native tmux.
- Agents are defined in config (`command`, `resume` template with `{{session}}` and `{{dir}}`),
  opencode the only one shipped for now.

## Restore

Trigger: `balamba` attaches to a running server (nothing to restore), or rebuilds from
`state.json` when the server is gone (quit, crash, reboot).

- Recreate windows/panes in saved order; restore split geometry from `window_layout` only when
  the live pane count equals the saved leaf count (a lower count is silently truncated otherwise),
  else fall back to equal splits.
- `window_layout` carries no active pane or active window: store and restore both separately.
- Reassert sidebar widths after attach; tmux rescales each window's layout to the client size.
- Agents: relaunch `opencode --session ses_<32 hex>` in the saved cwd, staggered ~0.5–1s apart
  (each TUI costs 3–7s startup and ~160MB).
- Shells: fresh `$SHELL` in the saved cwd (`pane_current_path` captured on detach + every poll).
- Anything else (vim, dev server): a plain shell in the saved cwd.
- Dying server-side cwd capture happens on detach and on the tree's periodic poll.
- Startup reconciles: worktrees removed by hand disappear from the tree; unknown dirs are ignored,
  never adopted silently.

## Git side panel

For the active context (task worktree or project main checkout):
- Branch name; and ahead/behind computed against the task's stored base ref
  (`git rev-list --left-right --count <base>...HEAD`), so it works without an upstream.
  If an upstream is set, show that instead.
- Changed files with staged / unstaged / untracked markers (`status --porcelain=v1 -z`).
- Click a file → `display-popup` with `git diff` piped to a pager.
- Auto-refresh on focus and every ~2s; never steals focus; read-only (no staging UI).

## Close task

`d` on a task:
1. Warn if the worktree is dirty. Warn if HEAD is detached (e.g. you detached by hand).
2. `Cancel` → nothing happens. `Continue` → second confirmation that the worktree will be deleted.
3. On confirmation: kill the task's windows, `git worktree remove <path>` (with `--force` only
   after the second confirmation), remove from state.
4. Branch handling: the close dialog offers `delete branch too`, default off. The default keeps
   the branch — it is the thing you may still want to push or review. When chosen, the delete uses
   `git branch -d`, so an unmerged branch is never silently dropped. No commits, no pushes,
   no merges.

## Open in editor

`e` → `display-popup` running `$EDITOR` (configurable) in the worktree, so the 3-column
layout is preserved.

## Invocation

- `balamba` — attach or build-and-attach.
- `balamba project add|remove <path>`, `balamba task list`, `balamba save`, `balamba doctor`.
- `balamba doctor`: server/socket, state validity, missing worktrees, opencode availability.

## Proposed bindings

Prefix `C-a`. App-level: `C-a N` new task, `C-a P` add project, `C-a T` new terminal,
`C-a e` editor, `C-a d` detach, `C-a r` redraw. Tree-level keys work without the prefix
when the tree pane is focused. All configurable.

## Files

```
balamba/
  bin/balamba            entry point (attach / subcommands)
  lib/common.sh          config, state read/write, locking
  lib/tmux.sh            server, windows, panes, chrome, restore
  lib/git.sh             project validation, worktree add/remove, status
  lib/task.sh            new task, close task, terminals
  pane/ui.py             tree + git pane renderer (stdlib only)
  tmux.conf              server config, bindings, formats
  SPEC.md
```

## Risks to validate first

1. `opencode --session <uuid>` creating vs continuing a session reliably in a fresh cwd.
2. Click routing inside the tree/git panes (apps enable mouse reporting; tmux must forward).
3. `window_layout` restoration surviving a full rebuild; fall back to equal splits if not.
4. Replicated chrome staying consistent (width, tree state) across several tab windows.
