"""Git operations, deliberately limited to the surface allowed by the spec.

Only: rev-parse, check-ref-format, worktree list/add/remove, branch -d,
status, rev-list and diff.  No commits, pushes, merges or rebases.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

GIT_ENV = {
    "LC_ALL": "C",
    "GIT_OPTIONAL_LOCKS": "0",
    "GIT_TERMINAL_PROMPT": "0",
}


@dataclass
class GitResult:
    ok: bool
    out: str
    err: str
    code: int

    @property
    def text(self) -> str:
        return (self.out + (("\n" + self.err) if self.err else "")).strip()


def git(
    args: Sequence[str],
    cwd: str | Path,
    *,
    timeout: float = 8.0,
    env_extra: dict[str, str] | None = None,
) -> GitResult:
    env = os.environ.copy()
    env.update(GIT_ENV)
    if env_extra:
        env.update(env_extra)
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        return GitResult(proc.returncode == 0, proc.stdout, proc.stderr, proc.returncode)
    except FileNotFoundError:
        return GitResult(False, "", "git not found on PATH", 127)
    except subprocess.TimeoutExpired:
        return GitResult(False, "", f"git {' '.join(args)} timed out", 124)
    except OSError as exc:
        return GitResult(False, "", str(exc), 1)


@dataclass
class ProjectCheck:
    ok: bool
    path: str = ""
    toplevel: str = ""
    message: str = ""
    warning: str = ""
    is_worktree: bool = False

    @property
    def display(self) -> str:
        return self.warning or self.message


def validate_project(path: str | Path) -> ProjectCheck:
    """A project must be the top level of a git *main* checkout."""
    raw = Path(path).expanduser()
    try:
        resolved = raw.resolve(strict=True)
    except OSError as exc:
        return ProjectCheck(False, str(raw), message=f"path does not exist: {exc}")
    if not resolved.is_dir():
        return ProjectCheck(False, str(resolved), message="path is not a directory")
    top = git(["rev-parse", "--show-toplevel"], resolved)
    if not top.ok:
        return ProjectCheck(False, str(resolved), message="not inside a git repository")
    toplevel = os.path.realpath(top.out.strip())
    if toplevel != str(resolved):
        return ProjectCheck(
            False,
            str(resolved),
            toplevel,
            message=f"not a main checkout root (repo root is {toplevel})",
        )
    abs_git = git(["rev-parse", "--absolute-git-dir"], resolved)
    common = git(["rev-parse", "--git-common-dir"], resolved)
    is_worktree = False
    if abs_git.ok and common.ok:
        common_path = Path(common.out.strip())
        if not common_path.is_absolute():
            common_path = (resolved / common_path).resolve()
        is_worktree = os.path.realpath(common_path) != os.path.realpath(abs_git.out.strip())
    if is_worktree:
        return ProjectCheck(
            True,
            str(resolved),
            toplevel,
            message="linked git worktree",
            warning=(
                "this path is itself a linked worktree, not a main checkout; "
                "balamba projects must be main checkouts"
            ),
            is_worktree=True,
        )
    return ProjectCheck(True, str(resolved), toplevel, message="main checkout")


def list_worktrees(project_path: str) -> list[dict[str, str]]:
    result = git(["worktree", "list", "--porcelain"], project_path)
    if not result.ok:
        return []
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in result.out.splitlines():
        if not line.strip():
            if current:
                entries.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    if current:
        entries.append(current)
    return entries


def worktree_present(project_path: str, worktree_path: str) -> bool:
    if not Path(worktree_path).is_dir():
        return False
    wanted = os.path.realpath(worktree_path)
    return any(
        os.path.realpath(entry.get("worktree", "")) == wanted for entry in list_worktrees(project_path)
    )


def branch_exists(project_path: str, branch: str) -> bool:
    # rev-parse verifies the exact local branch ref without consulting upstream.
    check = git(["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], project_path)
    return check.ok


def valid_branch_name(project_path: str, slug: str) -> tuple[bool, str]:
    result = git(["check-ref-format", "--branch", slug], project_path)
    return (result.ok, result.text if not result.ok else "")


def valid_ref(project_path: str, ref: str) -> bool:
    if not ref.strip():
        return False
    result = git(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], project_path, timeout=5)
    return result.ok


def worktree_root_for(project_path: str, configured: Path | None = None) -> Path:
    if configured:
        return Path(configured).expanduser()
    return Path(project_path).expanduser().resolve().parent / "balamba_worktrees"


def worktree_path_for(project_path: str, slug: str, configured: Path | None = None) -> Path:
    return worktree_root_for(project_path, configured) / Path(project_path).name / slug


@dataclass
class UniqueName:
    slug: str
    display: str
    attempts: int = 1


def unique_slug(
    project_path: str,
    name: str,
    base_slug: str,
    configured_root: Path | None = None,
) -> UniqueName:
    """Find a slug whose folder and local branch do not exist.

    Both the slug and the display name get the ``-2`` / ``-3`` suffix.
    """
    from .state import slugify

    base_slug = slugify(base_slug or name)
    for attempt in range(1, 500):
        slug = base_slug if attempt == 1 else f"{base_slug}-{attempt}"
        path = worktree_path_for(project_path, slug, configured_root)
        if path.exists() or branch_exists(project_path, slug):
            continue
        display = name.strip() or slug
        if attempt > 1:
            display = f"{display}-{attempt}"
        return UniqueName(slug, display, attempt)
    raise RuntimeError("could not find a free task slug after 499 attempts")


@dataclass
class WorktreeAddResult:
    ok: bool
    path: str
    output: str
    command: list[str] = field(default_factory=list)


def add_worktree(
    project_path: str,
    slug: str,
    ref: str,
    configured_root: Path | None = None,
) -> WorktreeAddResult:
    path = worktree_path_for(project_path, slug, configured_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    args = ["worktree", "add", "--no-track", "-b", slug, str(path), ref]
    result = git(args, project_path, timeout=120)
    return WorktreeAddResult(result.ok, str(path), result.text, ["git", *args])


def remove_worktree(project_path: str, worktree_path: str, force: bool = False) -> GitResult:
    args = ["worktree", "remove"]
    if force:
        args.append("--force")
    args.append(worktree_path)
    return git(args, project_path, timeout=120)


def delete_branch(project_path: str, branch: str) -> GitResult:
    return git(["branch", "-d", branch], project_path, timeout=30)


@dataclass
class FileStatus:
    path: str
    orig: str = ""
    x: str = " "
    y: str = " "
    untracked: bool = False

    @property
    def staged(self) -> bool:
        return self.x not in {" ", "?", "!"}

    @property
    def unstaged(self) -> bool:
        return self.y not in {" ", "?", "!"}

    @property
    def markers(self) -> str:
        if self.untracked:
            return "?"
        marks = ""
        marks += "S" if self.staged else "·"
        marks += "U" if self.unstaged else "·"
        return marks

    @property
    def code(self) -> str:
        return (self.x + self.y).strip() or "??"


def _parse_porcelain_z(payload: str) -> list[FileStatus]:
    tokens = payload.split("\0")
    files: list[FileStatus] = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        i += 1
        if not token:
            continue
        if len(token) < 4:
            continue
        x, y = token[0], token[1]
        path = token[3:]
        orig = ""
        if x in "RC" or y in "RC":
            if i < len(tokens):
                orig = tokens[i]
                i += 1
        files.append(FileStatus(path=path, orig=orig, x=x, y=y, untracked=(x == "?" or y == "?")))
    return files


@dataclass
class AheadBehind:
    ahead: int = 0
    behind: int = 0
    label: str = ""
    ok: bool = False


def ahead_behind(path: str, ref: str) -> AheadBehind:
    if not ref:
        return AheadBehind()
    result = git(["rev-list", "--left-right", "--count", f"{ref}...HEAD"], path, timeout=10)
    if not result.ok:
        return AheadBehind(label=ref)
    parts = result.out.strip().split()
    if len(parts) != 2:
        return AheadBehind(label=ref)
    behind, ahead = parts
    try:
        return AheadBehind(int(ahead), int(behind), ref, True)
    except ValueError:
        return AheadBehind(label=ref)


@dataclass
class RepoStatus:
    path: str
    ok: bool = False
    branch: str = ""
    detached: bool = False
    head: str = ""
    upstream: str = ""
    base: str = ""
    comparison: str = ""
    ahead: AheadBehind = field(default_factory=AheadBehind)
    files: list[FileStatus] = field(default_factory=list)
    error: str = ""
    dirty: bool = False
    worktree: bool = False

    @property
    def changed_count(self) -> int:
        return len(self.files)


def has_upstream(path: str) -> str:
    result = git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"], path)
    return result.out.strip() if result.ok else ""


def repo_status(path: str, base: str = "", *, main_checkout: bool = False) -> RepoStatus:
    status = RepoStatus(path=path, base=base)
    if not path or not Path(path).is_dir():
        status.error = "worktree directory is missing"
        return status
    head = git(["rev-parse", "--short", "HEAD"], path)
    if not head.ok:
        status.error = head.text or "not a git worktree"
        return status
    status.head = head.out.strip()
    branch = git(["rev-parse", "--abbrev-ref", "HEAD"], path)
    if not branch.ok:
        status.error = branch.text or "cannot read HEAD"
        return status
    status.branch = branch.out.strip()
    status.detached = status.branch == "HEAD"
    porcelain = git(["status", "--porcelain=v1", "-z"], path, timeout=10)
    if not porcelain.ok:
        status.error = porcelain.text or "git status failed"
        return status
    status.files = _parse_porcelain_z(porcelain.out)
    status.dirty = bool(status.files)
    status.upstream = has_upstream(path)
    status.worktree = bool(Path(path).parent.name == "balamba_worktrees")
    comparison = status.upstream or ("" if main_checkout else base)
    status.comparison = comparison
    if comparison:
        status.ahead = ahead_behind(path, comparison)
    status.ok = True
    return status


def diff_for_file(path: str, file_path: str) -> tuple[bool, str, str]:
    """Return (ok, text, label).  Text contains ANSI colours for the viewer."""
    result = git(
        ["diff", "--color=always", "--no-ext-diff", "HEAD", "--", file_path],
        path,
        timeout=15,
    )
    if result.ok and result.out.strip():
        return True, result.out, f"git diff HEAD -- {file_path}"
    result = git(
        ["diff", "--color=always", "--no-ext-diff", "--", file_path],
        path,
        timeout=15,
    )
    if result.ok and result.out.strip():
        return True, result.out, f"git diff -- {file_path}"
    target = Path(path) / file_path
    try:
        if target.is_file() and target.stat().st_size < 512_000:
            data = target.read_text(encoding="utf-8", errors="replace")
            return True, data, f"untracked file · {file_path}"
    except OSError as exc:
        return False, f"could not read {file_path}: {exc}", file_path
    return True, f"No diff for {file_path} (clean, empty, or binary file).", file_path


def is_detached(path: str) -> bool:
    result = git(["rev-parse", "--abbrev-ref", "HEAD"], path)
    return result.ok and result.out.strip() == "HEAD"


def count_dirty(path: str) -> int:
    result = git(["status", "--porcelain=v1"], path)
    if not result.ok:
        return 0
    return len([line for line in result.out.splitlines() if line.strip()])
