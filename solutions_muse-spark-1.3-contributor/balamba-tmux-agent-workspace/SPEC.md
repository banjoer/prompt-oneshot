# balamba — spec (Textual reinterpretation)

This solution implements the `balamba-tmux-agent-workspace` challenge with
the TWIST: the entire interface is Python + Textual; tmux (or plain
terminal sessions) hosts terminal content only.

Source of truth for behavior: `README.md` (runbook + every
reinterpretation and tmux-specific deviation) and the code:

- UI contract: `app/main.py` (layout, tree, tabs, git pane, status bar,
  dialogs, keys, mouse)
- Backend contract: `app/backend.py`, `lib/*.sh` (state, config, tmux
  content hosting, restricted git surface)
- Entry: `bin/balamba` (`attach | project add|remove | task list |
  save | doctor`)

Key invariants (kept from the original spec):

- Dedicated tmux server `tmux -L balamba`, session `balamba`; the app
  never touches the user's default server.
- State `~/.local/state/balamba/state.json` is authoritative, `flock`
  for writers, reconciled against `git worktree list` at startup.
- Worktree path `/path/to/<folder>` →
  `/path/to/balamba_worktrees/<folder>/<slug>`; creation exactly
  `git worktree add --no-track -b <slug> <path> <ref>`.
- Agent ids `ses_` + 32 hex; resume reuses the id.
- Close task: two confirmations, `worktree remove --force` only after
  the second, optional `git branch -d`, never silent on unmerged.
- No commits, pushes, merges, rebases, PR automation, notifications.
