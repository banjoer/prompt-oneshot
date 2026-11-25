"""gitops.py — project validation, worktree add/remove, status & diff helpers.

Spec file mapping: re-implements `lib/git.sh` (see README.md).

Only the git surface allowed by the spec is used:
    rev-parse, check-ref-format, worktree list|add|remove, branch -d,
    status, rev-list, diff
plus `symbolic-ref`/`config`-free plumbing done through `rev-parse` where
possible.  No commits, pushes, merges or rebases, ever.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

GIT_TIMEOUT = 20  # seconds per git call


def _git(cwd: str, *args: str) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
            errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired) as exc:  # pragma: no cover
        return 127, "", str(exc)
    return proc.returncode, proc.stdout, proc.stderr


# ---------------------------------------------------------------------------
# Project validation
# ---------------------------------------------------------------------------

def is_git_repo(path: str) -> bool:
    rc, _, _ = _git(path, "rev-parse", "--git-dir")
    return rc == 0


@dataclass
class CheckoutInfo:
    ok: bool
    toplevel: str | None
    is_main_checkout: bool
    warning: str

    @property
    def error(self) -> str | None:
        return None if self.ok else self.warning


def validate_main_checkout(path: str) -> CheckoutInfo:
    """The spec's rule: `rev-parse --show-toplevel` must equal the path.

    A path that is itself a linked worktree also satisfies the equality check,
    so we additionally compare --git-dir vs --git-common-dir and warn.
    """
    if not os.path.isdir(path):
        return CheckoutInfo(False, None, False, f"not a directory: {path}")
    rc, toplevel, err = _git(path, "rev-parse", "--show-toplevel")
    if rc != 0:
        return CheckoutInfo(False, None, False, f"not a git repository: {path}")
    toplevel = toplevel.strip()
    if os.path.realpath(path) != os.path.realpath(toplevel):
        return CheckoutInfo(
            False, toplevel, False,
            f"{path} is not the repository root (toplevel is {toplevel})",
        )
    # Linked worktrees report a private git-dir but a shared common-dir.
    rc1, gdir, _ = _git(path, "rev-parse", "--absolute-git-dir")
    rc2, gcommon, _ = _git(path, "rev-parse", "--git-common-dir")
    if rc1 == 0 and rc2 == 0:
        gdir = os.path.abspath(gdir.strip())
        gc = gcommon.strip()
        if not os.path.isabs(gc):
            gc = os.path.join(os.path.abspath(toplevel), gc)
        gcommon_abs = os.path.normpath(gc)
        gdir_abs = os.path.normpath(gdir)
        if gdir_abs != gcommon_abs:
            return CheckoutInfo(
                True, toplevel, False,
                "warning: this path is itself a git worktree, not the main checkout",
            )
    return CheckoutInfo(True, toplevel, True, "")


# ---------------------------------------------------------------------------
# Refs / slugs
# ---------------------------------------------------------------------------

def check_branch_name(cwd: str, name: str) -> bool:
    rc, _, _ = _git(cwd, "check-ref-format", "--branch", name)
    return rc == 0


def ref_exists(cwd: str, ref: str) -> bool:
    rc, _, _ = _git(cwd, "rev-parse", "--verify", f"{ref}^{{commit}}")
    return rc == 0


def local_branch_exists(cwd: str, name: str) -> bool:
    rc, _, _ = _git(cwd, "rev-parse", "--verify", f"refs/heads/{name}")
    return rc == 0


# ---------------------------------------------------------------------------
# Worktrees
# ---------------------------------------------------------------------------

def worktree_list(cwd: str) -> list[dict]:
    """Return [{"path", "branch"}] via `git worktree list --porcelain`."""
    rc, out, _ = _git(cwd, "worktree", "list", "--porcelain")
    if rc != 0:
        return []
    result, cur = [], {}
    for line in out.splitlines():
        if line.startswith("worktree "):
            if cur:
                result.append(cur)
            cur = {"path": line[len("worktree "):], "branch": ""}
        elif line.startswith("branch ") and cur:
            cur["branch"] = line[len("branch "):].removeprefix("refs/heads/")
    if cur:
        result.append(cur)
    return result


def worktree_add(main_path: str, branch: str, path: str, ref: str) -> tuple[bool, str]:
    """Exactly the spec's command: git worktree add --no-track -b <slug> <path> <ref>."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rc, _, err = _git(main_path, "worktree", "add", "--no-track", "-b", branch, path, ref)
    return rc == 0, err.strip()


def worktree_remove(main_path: str, path: str, force: bool = False) -> tuple[bool, str]:
    args = ["worktree", "remove"] + (["--force"] if force else []) + [path]
    rc, _, err = _git(main_path, *args)
    return rc == 0, err.strip()


# ---------------------------------------------------------------------------
# Status / branch info for the git side panel
# ---------------------------------------------------------------------------

def current_branch(cwd: str) -> tuple[str, bool]:
    """Return (display_name, detached)."""
    rc, out, _ = _git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    if rc != 0:
        return "", True
    name = out.strip()
    if name == "HEAD":  # detached
        rc2, short, _ = _git(cwd, "rev-parse", "--short", "HEAD")
        return (short.strip() if rc2 == 0 else "?"), True
    return name, False


def upstream_of(cwd: str) -> str | None:
    rc, out, _ = _git(cwd, "rev-parse", "--abbrev-ref", "@{upstream}")
    if rc != 0:
        return None
    name = out.strip()
    return None if name in ("", "@{upstream}") else name


def ahead_behind(cwd: str, base: str) -> tuple[int, int] | None:
    """(ahead, behind) vs `base` using rev-list --left-right --count base...HEAD.

    Works without an upstream, exactly as the spec requires.
    """
    if not ref_exists(cwd, base):
        return None
    rc, out, _ = _git(cwd, "rev-list", "--left-right", "--count", f"{base}...HEAD")
    if rc != 0:
        return None
    behind, ahead = out.strip().split("\t")[:2]
    return int(ahead), int(behind)


@dataclass
class FileEntry:
    path: str
    orig_path: str | None  # for renames
    x: str                 # index (staged) marker
    y: str                 # worktree (unstaged) marker

    @property
    def staged(self) -> bool:
        return self.x not in (" ", "?")

    @property
    def unstaged(self) -> bool:
        return self.y not in (" ", "?")

    @property
    def untracked(self) -> bool:
        return self.x == "?" and self.y == "?"

    @property
    def marker(self) -> str:
        return f"{self.x}{self.y}"


def status_files(cwd: str) -> list[FileEntry]:
    """Parse `git status --porcelain=v1 -z` (NUL records; renames carry orig path)."""
    rc, out, _ = _git(cwd, "status", "--porcelain=v1", "-z")
    if rc != 0:
        return []
    records = out.split("\0")
    entries: list[FileEntry] = []
    i = 0
    while i < len(records):
        rec = records[i]
        if not rec:
            break
        xy, path = rec[:2], rec[3:]
        orig = None
        if xy[0] in ("R", "C") or xy[1] in ("R", "C"):
            i += 1
            orig = records[i] if i < len(records) else None
        entries.append(FileEntry(path=path, orig_path=orig, x=xy[0], y=xy[1]))
        i += 1
    return entries


def file_diff(cwd: str, entry: FileEntry) -> tuple[str, str]:
    """Return (diff_text, how) for the diff popup — plain `git diff` family only."""
    if entry.untracked:
        rc, out, err = _git(cwd, "diff", "--no-index", "/dev/null", entry.path)
        return out or (err or "no diff"), "git diff --no-index /dev/null " + entry.path
    if entry.staged and not entry.unstaged:
        rc, out, err = _git(cwd, "diff", "--cached", "--", entry.path)
        return out or "(no text diff — binary or mode change?)", "git diff --cached -- " + entry.path
    rc, out, err = _git(cwd, "diff", "--", entry.path)
    if rc == 0 and out:
        return out, "git diff -- " + entry.path
    # staged-and-modified, or file deleted in worktree
    rc2, out2, _ = _git(cwd, "diff", "--cached", "--", entry.path)
    text = out2 or out
    return (text or "(no textual diff)"), "git diff -- " + entry.path


def is_detached(cwd: str) -> bool:
    # `rev-parse --abbrev-ref HEAD` prints the literal "HEAD" when detached —
    # keeps us inside the allowed git surface (no symbolic-ref).
    rc, out, _ = _git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    return rc != 0 or out.strip() == "HEAD"


def worktree_is_dirty(cwd: str) -> bool:
    rc, out, _ = _git(cwd, "status", "--porcelain")
    return rc == 0 and bool(out.strip())


def branch_delete(main_path: str, name: str) -> tuple[bool, str]:
    """`git branch -d` — unmerged branches are never silently dropped."""
    rc, _, err = _git(main_path, "branch", "-d", name)
    return rc == 0, err.strip()
