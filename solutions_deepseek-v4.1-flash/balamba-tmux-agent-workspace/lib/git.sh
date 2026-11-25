#!/usr/bin/env bash
# lib/git.sh — project validation, worktrees and status.
#
# Thin bash surface over balamba/gitops.py.  The git vocabulary stays inside
# the allowed set: rev-parse, check-ref-format, worktree list/add/remove,
# branch -d, status, rev-list and diff.  No commits, pushes or merges.

if [ -n "${BASH_SOURCE[0]:-}" ]; then
  BALAMBA_LIB_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
else
  BALAMBA_LIB_DIR="$(pwd)/lib"
fi
BALAMBA_ROOT="${BALAMBA_ROOT:-$(cd -- "$BALAMBA_LIB_DIR/.." && pwd)}"
# shellcheck source=lib/common.sh
. "$BALAMBA_LIB_DIR/common.sh"

# balamba_project_validate <path>
# Prints "ok|main checkout", "ok|linked worktree", or "error|message".
balamba_project_validate() {
  balamba_py -c '
import sys
from balamba.gitops import validate_project
check = validate_project(sys.argv[1])
if check.is_worktree:
    print("error|" + (check.warning or "linked worktree"))
elif check.ok:
    print("ok|" + check.message)
else:
    print("error|" + (check.message or "invalid project"))
' "$1"
}

# balamba_worktree_add <project> <slug> <ref>
balamba_worktree_add() {
  balamba_py -c '
import sys
from balamba.gitops import add_worktree
result = add_worktree(sys.argv[1], sys.argv[2], sys.argv[3])
print(("ok|" if result.ok else "error|") + result.output)
print(result.path)
sys.exit(0 if result.ok else 1)
' "$1" "$2" "$3"
}

# balamba_worktree_remove <project> <worktree-path> [--force]
balamba_worktree_remove() {
  local force=""
  [ "${3:-}" = "--force" ] && force="True"
  balamba_py -c '
import sys
from balamba.gitops import remove_worktree
result = remove_worktree(sys.argv[1], sys.argv[2], force=bool(sys.argv[3]))
print(result.text or ("removed" if result.ok else "failed"))
sys.exit(0 if result.ok else 1)
' "$1" "$2" "${force:-}"
}

# balamba_git_status <path> [base]
balamba_git_status() {
  balamba_py -c '
import sys
from balamba.gitops import repo_status
status = repo_status(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "")
if not status.ok:
    print("error:", status.error); raise SystemExit(1)
print(f"branch {status.branch}" + (" (detached)" if status.detached else ""))
label = "upstream" if status.upstream else "base"
print(f"{label} {status.comparison or "-"}  ahead {status.ahead.ahead}  behind {status.ahead.behind}")
for f in status.files:
    print(f"{f.code:>2} {f.path}  [{f.markers}]")
' "$1" "$2"
}
