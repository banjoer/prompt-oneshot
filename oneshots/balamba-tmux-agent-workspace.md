# Balamba — tmux Projects → Worktrees → Terminals Workspace

**Difficulty:** Extreme  |  **Stack:** Bash + tmux + Python (stdlib)  |  **Estimated time:** 8–14 hours

## The Problem

Agentic coding has outgrown the single-terminal workflow. Once you run several agents in
parallel, each in its own git worktree, the coordination cost explodes: scattered tmux
panes, forgotten worktrees, lost sessions after a reboot, and branches you can no longer
tell apart. Balamba fixes this by being a keyboard-first, tmux-based workspace manager —
a terminal re-creation of the parts of Orca that actually matter: projects → tasks (git
worktrees) → terminals, with full resume across restarts. It owns its own tmux server,
keeps all state in one JSON file reconciled against `git worktree list`, and deliberately
does almost nothing else: no PR automation, no merge tooling, no agent protocol of its
own. Build the whole thing from the specification embedded below.

## Requirements

1. **Dedicated tmux server.** All work runs inside `tmux -L balamba -f
   ~/.config/balamba/tmux.conf` with prefix `C-a`. Balamba owns this server and never
   attaches to or modifies the user's default server. Running `balamba` either attaches
   to a live `balamba` server (nothing to restore) or rebuilds the workspace from saved
   state and attaches.
2. **Three-column chrome.** One tmux session named `balamba`. Every window shows the tree
   pane (~30 columns) on the left, tab content (native splits) in the middle, the git pane
   (~34 columns) on the right, and a status bar at the bottom (`balamba · <context>` plus
   the clickable tab list). Chrome is replicated per window but treated as one logical
   sidebar: panes in the active window refresh at full rate, while panes in inactive
   windows only poll activation at ~0.2 Hz (a non-focused pane gets no focus event when
   its window becomes active). Sidebar widths are config values reasserted after attach
   and on activation.
3. **Tree hierarchy and navigation.** project (main checkout) → tasks (worktrees) →
   terminals (tabs); projects may also host scratch terminals in the main checkout
   alongside tasks. The active project is expanded and others collapse to one line;
   manual expand/collapse is remembered. Keyboard: `j/k` and arrows move, `h/l`
   collapse/expand, `Enter` activates, `n` new task, `t` new terminal, `d` close task,
   `e` open in editor, `p` add project. Mouse: click a row to select/activate, click the
   chevron to toggle, right-click for a menu; with `mouse on` the first click on a
   non-focused pane both focuses it and is delivered; wheel scrolling is in-app and text
   selection stays available via `prefix+[`. Show an unread dot on a terminal/task row
   whose window produced output since the last visit (`window_activity_flag`, requires
   `monitor-activity on`, cleared when a client views the window). No bells, no desktop
   notifications, no agent-status plugins.
4. **Projects.** Add via `p` or `balamba project add <path>`. The path must resolve to a
   git main checkout: `git rev-parse --show-toplevel` must equal the path, and a path
   that is itself a worktree gets a warning. Removal is from balamba only and must never
   touch the folder on disk.
5. **New task flow.** Prompt in order: (a) `task name:` — free text, stored as-is for
   display; (b) slug — lowercase, spaces → `-`, strip everything but `[a-z0-9._-]`,
   collapse dashes, validated with `git check-ref-format --branch`; on collision (folder
   exists or local branch `<slug>` exists) suffix both slug and display name as
   `<slug>-2`, `<slug>-3`, …; (c) `create from:` — free text prefilled literally
   `origin/main`, accepting any ref that `git rev-parse --verify <ref>^{commit}` takes;
   (d) terminal kind — `agent` or `shell`. Then create the worktree and branch in one
   command, switch to the task, start the terminal, and focus it. Worktree path maps
   `/path/to/project_folder` → `/path/to/balamba_worktrees/<project_folder>/<slug>`, and
   creation is exactly:
   `git worktree add --no-track -b <slug> <path> <ref>`.
   `--no-track` is deliberate: without it git auto-sets the new branch's upstream to the
   start point (e.g. `origin/main`), so a stray `git push` would target main.
6. **Terminals as tabs.** Each terminal is a tab with kind (`agent`|`shell`), agent name,
   session uuid (agents), and cwd. Agent launch is `opencode --session ses_<32 hex>` in
   the tab's cwd; generate `ses_` + uuid4 hex at creation (opencode rejects ids that do
   not start with `ses_`). The session materialises on the first message, and the same id
   resumes it after a restart. Shell launch is `$SHELL` in the tab's cwd. New terminals
   via `t` / `C-a T` show an `agent | shell` menu; splits inside a tab are native tmux.
   Agents are defined in config (`command`, `resume` template with `{{session}}` and
   `{{dir}}`), with opencode the only one shipped for now.
7. **Restore across restarts.** If the server is running, attach and restore nothing. If
   the server is gone (quit, crash, reboot), rebuild from saved state: recreate
   windows/panes in saved order; restore split geometry from the saved `window_layout`
   only when the live pane count equals the saved leaf count (a lower count would be
   silently truncated), else fall back to equal splits; store and restore the active pane
   and active window separately (the layout string carries neither); reassert sidebar
   widths after attach; relaunch agents staggered ~0.5–1 s apart; give shells a fresh
   `$SHELL` in the saved cwd (`pane_current_path` captured on detach and every poll); run
   anything else (vim, a dev server) as a plain shell in the saved cwd. At startup,
   reconcile: worktrees removed by hand disappear from the tree, unknown dirs are ignored
   and never adopted silently.
8. **Git side panel.** For the active context (task worktree or project main checkout)
   show: the branch name; ahead/behind computed against the task's stored base ref
   (`git rev-list --left-right --count <base>...HEAD`) so it works without an upstream,
   or against the upstream if one is set; changed files with staged / unstaged /
   untracked markers (`status --porcelain=v1 -z`); a click on a file opens a
   `display-popup` with `git diff` piped to a pager. Auto-refresh on focus and every ~2 s,
   never steal focus, stay read-only (no staging UI).
9. **Close task.** `d` on a task: warn if the worktree is dirty or HEAD is detached;
   `Cancel` does nothing, `Continue` leads to a second confirmation that the worktree
   will be deleted. On confirmation kill the task's windows, run
   `git worktree remove <path>` (`--force` only after the second confirmation), and
   remove the task from state. The dialog offers `delete branch too`, default off — the
   default keeps the branch because it may still need pushing or review. When chosen, the
   delete uses `git branch -d`, so an unmerged branch is never silently dropped. No
   commits, pushes, or merges, ever.
10. **Open in editor.** `e` opens a `display-popup` running `$EDITOR` (configurable) in
    the worktree, preserving the three-column layout.
11. **State, config, and locking.** State lives in `~/.local/state/balamba/state.json`
    (with `flock` for writers) and is the source of truth, reconciled against
    `git worktree list` at startup. Config lives in `~/.config/balamba/config` (sourced
    bash) and is mirrored into tmux options (`@balamba_*`) so the Python panes read the
    same values.
12. **Invocation and doctor.** `balamba` attaches or builds-and-attaches. Subcommands:
    `balamba project add|remove <path>`, `balamba task list`, `balamba save`,
    `balamba doctor` (reports server/socket, state validity, missing worktrees, opencode
    availability).
13. **Bindings.** Prefix `C-a`. App-level: `C-a N` new task, `C-a P` add project,
    `C-a T` new terminal, `C-a e` editor, `C-a d` detach, `C-a r` redraw. Tree-level keys
    work without the prefix while the tree pane is focused. All bindings are configurable.
14. **File layout.** Deliver exactly this structure, all created from scratch:
    `bin/balamba` (entry point: attach / subcommands), `lib/common.sh` (config, state
    read/write, locking), `lib/tmux.sh` (server, windows, panes, chrome, restore),
    `lib/git.sh` (project validation, worktree add/remove, status), `lib/task.sh` (new
    task, close task, terminals), `pane/ui.py` (tree + git pane renderer, stdlib only),
    `tmux.conf` (server config, bindings, formats).
15. **Sign-off:** the finished solution must display, somewhere easy to spot, the date and
    time it was produced and the model/author that produced it — e.g. a header comment in
    `bin/balamba` plus an about/version line printed by `balamba doctor`.

## Constraints

- Unix-like OS (Linux or macOS) with `tmux` (≥ 3.x) and `git` installed; `opencode` on
  `PATH` for agent tabs. These are the only prerequisites — no other downloads.
- Shell scripts do all tmux driving, state, git, and worktree work. Exactly one Python
  file renders the two interactive panes: stdlib only, no pip, no packages, no fzf. It
  reads state and talks to tmux; it never owns state.
- No network calls, no third-party APIs, no external servers, no auth. The only storage is
  the JSON state file (plus the tmux server itself).
- Git surface is limited to: `rev-parse`, `check-ref-format`, `worktree list`,
  `worktree add`, `worktree remove`, `branch -d`, `status`, `rev-list`, `diff`. No
  commits, pushes, merges, or rebases.
- `mouse on` is enabled; the first click on a non-focused pane is both focus and click.
  Text selection remains available via `prefix+[`; wheel scrolling is in-app.
- The complete specification is embedded below and is the only source of truth needed.

## Sample Data / Inputs

Example `~/.config/balamba/config` (sourced bash):

```bash
# balamba config
BALAMBA_TREE_WIDTH=30
BALAMBA_GIT_WIDTH=34
BALAMBA_EDITOR="${EDITOR:-nvim}"
BALAMBA_AGENT_DEFAULT=opencode
BALAMBA_AGENTS=("opencode")
BALAMBA_AGENT_opencode_COMMAND="opencode --session {{session}}"
BALAMBA_AGENT_opencode_RESUME="opencode --session {{session}}"
```

Example `~/.local/state/balamba/state.json` skeleton:

```json
{
  "version": 1,
  "projects": [
    {
      "path": "/home/me/src/widget",
      "expanded": true,
      "scratch": [],
      "tasks": [
        {
          "slug": "fix-login",
          "name": "Fix login",
          "path": "/home/me/balamba_worktrees/widget/fix-login",
          "base": "origin/main",
          "windows": [
            {
              "kind": "agent",
              "agent": "opencode",
              "session": "ses_0123456789abcdef0123456789abcdef",
              "cwd": "/home/me/balamba_worktrees/widget/fix-login"
            }
          ],
          "window_layout": "<tmux layout string>",
          "active_window": 0,
          "active_pane": 0
        }
      ]
    }
  ]
}
```

Example worktree creation:

```
$ git worktree add --no-track -b fix-login /home/me/balamba_worktrees/widget/fix-login origin/main
```

## Deliverable

- `bin/balamba` — entry point (attach / subcommands)
- `lib/common.sh` — config, state read/write, locking
- `lib/tmux.sh` — server, windows, panes, chrome, restore
- `lib/git.sh` — project validation, worktree add/remove, status
- `lib/task.sh` — new task, close task, terminals
- `pane/ui.py` — tree + git pane renderer (stdlib only)
- `tmux.conf` — server config, bindings, formats
- Run: `bin/balamba` (build-and-attach on first run; `bin/balamba doctor` for a health
  check). Ensure `bin/balamba` is executable.

## Done When

- [ ] First run creates the dedicated `balamba` tmux server/session and shows
      tree | content | git with the status bar.
- [ ] `p` adds a git main checkout as a project; a path that is not a main checkout is
      rejected with a warning.
- [ ] `n` creates a task with a worktree at `.../balamba_worktrees/<project>/<slug>`,
      branch `<slug>`, and no upstream (`git rev-parse --abbrev-ref <branch>@{upstream}`
      fails).
- [ ] Colliding names produce `-2`/`-3` suffixes on folder, branch, and display name.
- [ ] An agent tab runs `opencode --session ses_<32 hex>`; a shell tab runs `$SHELL`;
      both land in the correct cwd.
- [ ] Killing the tmux server and re-running `bin/balamba` restores windows, splits (or
      equal splits when the leaf count mismatches), the active window/pane, agent
      sessions, and shell cwds.
- [ ] The git panel shows branch, ahead/behind vs base (and vs upstream when set), and
      changed files with staged/unstaged/untracked markers; clicking a file opens the
      diff popup.
- [ ] `d` on a dirty task warns and requires two confirmations; branch deletion uses
      `git branch -d`.
- [ ] `e` opens `$EDITOR` in a popup without breaking the three-column layout.
- [ ] `bin/balamba doctor` reports server/socket, state validity, missing worktrees, and
      opencode availability.

## Stretch Goals (optional)

- A right-click context menu with extra actions (copy path, reveal in editor, restart
  agent).
- A second agent definition added purely via config (e.g. a different CLI or a wrapper
  script), with zero code changes.
- Width round-trip: change a sidebar width in config, reattach, and confirm it reasserts
  across every window.

## Appendix: Full Specification (SPEC.md)

The verbatim specification follows. It is part of this challenge; everything above is a
distillation of it and the spec wins on any detail.

````markdown
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
````
