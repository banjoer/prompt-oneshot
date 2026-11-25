# balamba git helpers: validation, worktree add/remove, status
# Sign-off: produced 2026-11-25 by Muse Spark 1.3 Contributor (opencode-go).
set -u

git_toplevel() {
  git -C "$1" rev-parse --show-toplevel 2>/dev/null
}

# Validate project path: must be a git main checkout (toplevel == resolved path).
# Echoes toplevel on success. Returns 1 otherwise. Warns if path is itself a worktree.
git_validate_project() {
  local raw="$1" resolved top is_wt
  resolved="$(realpath -m "$raw" 2>/dev/null || readlink -f "$raw" 2>/dev/null || echo "$raw")"
  top="$(git -C "$resolved" rev-parse --show-toplevel 2>/dev/null)" || {
    echo "balamba: not a git repository: $raw" >&2
    return 1
  }
  if [ "$top" != "$resolved" ]; then
    echo "balamba: path is not the main checkout (toplevel: $top, given: $resolved)" >&2
    return 1
  fi
  is_wt="$(git -C "$resolved" rev-parse --is-inside-work-tree 2>/dev/null || true)"
  # Warn if this toplevel is itself registered as a linked worktree elsewhere
  if git -C "$resolved" rev-parse --git-common-dir >/dev/null 2>&1; then
    local common gitdir
    gitdir="$(git -C "$resolved" rev-parse --git-dir 2>/dev/null)"
    common="$(git -C "$resolved" rev-parse --git-common-dir 2>/dev/null)"
    if [ "$gitdir" != "$common" ] && [ "$gitdir" != ".git" ]; then
      echo "balamba: warning: path looks like a linked worktree ($resolved)" >&2
    fi
  fi
  echo "$top"
}

git_is_worktree_path() {
  # true if $1 is inside the worktree list of repo $2
  local path="$1" repo="$2"
  git -C "$repo" worktree list --porcelain 2>/dev/null | grep -q "^worktree $path$"
}

git_worktree_add() {
  # $1=repo $2=slug(branch) $3=path $4=ref
  git -C "$1" worktree add --no-track -b "$2" "$3" "$4"
}

git_worktree_remove() {
  # $1=repo $2=path [--force]
  local repo="$1" path="$2" force="${3:-}"
  if [ "$force" = "--force" ]; then
    git -C "$repo" worktree remove --force "$path"
  else
    git -C "$repo" worktree remove "$path"
  fi
}

git_branch_delete() {
  # $1=repo $2=branch (uses -d so unmerged is never silently dropped)
  git -C "$1" branch -d "$2"
}

git_worktree_dirty() {
  # true (0) if dirty; prints porcelain
  local out
  out="$(git -C "$1" status --porcelain=v1 -z 2>/dev/null | tr '\0' '\n')"
  if [ -n "$out" ]; then
    echo "$out"
    return 0
  fi
  return 1
}

git_head_detached() {
  git -C "$1" symbolic-ref -q HEAD >/dev/null 2>&1 && return 1 || return 0
}

git_branch_name() {
  git -C "$1" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "(detached)"
}

git_ahead_behind_base() {
  # $1=repo $2=base -> "ahead behind"
  git -C "$1" rev-list --left-right --count "$2...HEAD" 2>/dev/null || echo "0 0"
}

git_upstream() {
  git -C "$1" rev-parse --abbrev-ref "@{upstream}" 2>/dev/null
}

git_ahead_behind_upstream() {
  git -C "$1" rev-list --left-right --count "@{upstream}...HEAD" 2>/dev/null || echo "0 0"
}

git_changed_files() {
  # NUL-separated porcelain
  git -C "$1" status --porcelain=v1 -z 2>/dev/null
}

git_diff_file() {
  # $1=repo $2=file (plus pager handled by caller)
  local repo="$1" file="$2"
  if git -C "$repo" diff --quiet -- "$file" 2>/dev/null; then
    git -C "$repo" diff --cached -- "$file" 2>/dev/null
  else
    git -C "$repo" diff -- "$file" 2>/dev/null
  fi
}

slugify() {
  # stdin/stdout: lowercase, spaces->-, strip [^a-z0-9._-], collapse dashes, trim
  python3 -c '
import sys, re
s = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
s = s.strip().lower().replace(" ", "-").replace("\t", "-").replace("_", "_")
s = re.sub(r"[^a-z0-9._-]", "-", s)
s = re.sub(r"-+", "-", s).strip("-._")
print(s[:80] if s else "task")
' "$1"
}
