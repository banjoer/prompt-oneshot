#!/usr/bin/env bash
# lib/task.sh — task and terminal helpers.
#
# New-task and close-task are interactive Textual flows in this build (the
# spec's modal prompts are Textual screens).  These shims expose the parts that
# make sense from a non-interactive shell and keep the documented file layout.

if [ -n "${BASH_SOURCE[0]:-}" ]; then
  BALAMBA_LIB_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
else
  BALAMBA_LIB_DIR="$(pwd)/lib"
fi
BALAMBA_ROOT="${BALAMBA_ROOT:-$(cd -- "$BALAMBA_LIB_DIR/.." && pwd)}"
# shellcheck source=lib/common.sh
. "$BALAMBA_LIB_DIR/common.sh"

balamba_task_list() {
  "$BALAMBA_ROOT/bin/balamba" task list
}

balamba_save() {
  "$BALAMBA_ROOT/bin/balamba" save
}

balamba_open() {
  "$BALAMBA_ROOT/bin/balamba" "$@"
}

# Print the worktree path for a project/slug (does not create it).
balamba_worktree_path() {
  balamba_py -c '
import sys
from balamba.gitops import worktree_path_for
print(worktree_path_for(sys.argv[1], sys.argv[2]))
' "$1" "$2"
}

# Print the launch command for an agent tab (template already rendered).
balamba_agent_command() {
  balamba_py -c '
import sys
from balamba.config import load_config
cfg = load_config()
agent = cfg.agent(sys.argv[3] if len(sys.argv) > 3 else None)
print(agent.render(sys.argv[1], sys.argv[2], resume=False))
' "$1" "$2" "${3:-}"
}

# Note for scripts: create tasks from the UI (`n`) or call
# balamba.workspace.Workspace.create_task(...) from Python.  Deliberately no
# shell prompt is provided here so there is exactly one task workflow.
balamba_new_task_note() {
  printf 'new task is a Textual wizard: run balamba and press the configured new-task key\n'
}
