# Tests

The suite uses only the Python standard library's `unittest`, plus the Textual dependency
the application itself needs. It never touches the real `~/.config/balamba`,
`~/.local/state/balamba`, the default tmux server, or `-L balamba`; each test creates a
temporary state/config directory and a unique tmux socket.

```bash
cd ..
python3 -m unittest discover -s tests -v
```

Coverage:

* `test_core.py`
  * slugging and `-2`/`-3` collision suffixing for both slug and display name
  * bash config parsing (arrays, multiple agents, custom prefix/tree keys)
  * spec-format state loading, stable ids, layout/active-pane migration, `.bak` recovery
  * layout leaf counting
  * project validation, linked-worktree rejection, `worktree add --no-track` and no upstream
  * porcelain staged/unstaged/untracked parsing
  * task creation paths, close-task branch semantics (`-d`, unmerged refused), force removal
  * project removal without touching disk
  * worktree reconciliation
  * split/layout/cwd/active-tab restoration after killing the content server
  * `bin/balamba doctor`, invalid project CLI exit codes
* `test_textual.py`
  * three-column Textual layout and terminal capture
  * tree keyboard/mouse chevron behaviour
  * prefix `N`/`T` dialogs, custom prefix/tree keys, About sign-off
  * clickable status-bar tabs, git diff overlay, wheel scrollback
