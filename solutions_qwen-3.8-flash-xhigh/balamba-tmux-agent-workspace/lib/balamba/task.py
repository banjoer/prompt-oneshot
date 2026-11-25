"""task.py — new-task flow, close-task flow, terminal tab policies.

Spec file mapping: re-implements `lib/task.sh` (see README.md).

All functions here are UI-free: dialogs in `dialogs.py` collect the answers,
then call into this module, which touches git and the state file only.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from . import common, gitops

DEFAULT_BASE = "origin/main"  # spec: `create from:` is prefilled literally


# ---------------------------------------------------------------------------
# New task
# ---------------------------------------------------------------------------

@dataclass
class SlugResolution:
    slug: str
    name: str
    path: str
    attempts: list[str] = field(default_factory=list)


def resolve_slug(project_path: str, base_slug: str, base_name: str) -> SlugResolution:
    """Suffix slug *and* display name `<x>-2`, `<x>-3`… on folder/branch collision."""
    n = 1
    attempts: list[str] = []
    while True:
        slug = base_slug if n == 1 else f"{base_slug}-{n}"
        name = base_name if n == 1 else f"{base_name}-{n}"
        path = common.worktree_path_for(project_path, slug)
        branch_exists = gitops.local_branch_exists(project_path, slug)
        folder_exists = os.path.exists(path)
        attempts.append(slug)
        if not branch_exists and not folder_exists:
            return SlugResolution(slug=slug, name=name, path=path, attempts=attempts)
        n += 1
        if n > 100:  # practical guard
            raise RuntimeError("could not resolve a free slug after 100 attempts")


@dataclass
class TaskCreated:
    task: dict
    project_index: int
    task_index: int


def create_task(state: dict, project_path: str, name: str, slug: str,
                base: str, terminal: dict) -> TaskCreated:
    """Create worktree+branch in one command, add to state, return indices."""
    res = resolve_slug(project_path, slug, name)
    ok, err = gitops.worktree_add(project_path, res.slug, res.path, base)
    if not ok:
        raise RuntimeError(err or "git worktree add failed")
    term = dict(terminal)
    term.setdefault("kind", "shell")
    term.setdefault("cwd", res.path)
    term.setdefault("uid", common.new_uid())
    term["name"] = res.name
    task = {
        "slug": res.slug,
        "name": res.name,
        "path": res.path,
        "base": base,
        "windows": [term],
        "window_layout": "",
        "active_window": 0,
        "active_pane": 0,
    }
    for i, p in enumerate(state["projects"]):
        if os.path.realpath(p["path"]) == os.path.realpath(project_path):
            p["tasks"].append(task)
            p["expanded"] = True
            return TaskCreated(task=task, project_index=i,
                               task_index=len(p["tasks"]) - 1)
    raise KeyError(f"project not in state: {project_path}")


# ---------------------------------------------------------------------------
# Terminals
# ---------------------------------------------------------------------------

def make_shell_terminal(cwd: str) -> dict:
    return {"kind": "shell", "cwd": os.path.abspath(cwd), "uid": common.new_uid()}


def make_agent_terminal(cwd: str, agent: str, session: str) -> dict:
    return {
        "kind": "agent",
        "agent": agent,
        "session": session,
        "cwd": os.path.abspath(cwd),
        "uid": common.new_uid(),
    }


def terminal_spec(cfg: common.Config, term: dict, *, resume: bool = False) -> str | None:
    """Render the shell command line a terminal tab should run."""
    if term.get("kind") == "agent":
        agent = term.get("agent") or cfg.agent_default
        cmd = cfg.agent_command(agent, term.get("session", ""), term.get("cwd", ""),
                                resume=resume)
        return cmd
    shell = os.environ.get("SHELL") or "/bin/sh"
    return shell  # plain shell; cwd is set by the pty session itself


# ---------------------------------------------------------------------------
# Close task
# ---------------------------------------------------------------------------

@dataclass
class CloseAssessment:
    dirty: bool
    detached: bool
    branch: str
    warnings: list[str]


def assess_close(state: dict, project_index: int, task_index: int) -> CloseAssessment:
    project = state["projects"][project_index]
    task = project["tasks"][task_index]
    dirty = gitops.worktree_is_dirty(task["path"])
    detached = gitops.is_detached(task["path"])
    branch, _ = gitops.current_branch(task["path"])
    warnings = []
    if dirty:
        warnings.append("worktree has uncommitted changes")
    if detached:
        warnings.append("HEAD is detached (branch not checked out)")
    return CloseAssessment(dirty=dirty, detached=detached, branch=branch,
                           warnings=warnings)


@dataclass
class CloseResult:
    ok: bool
    notes: list[str]


def close_task(state: dict, project_index: int, task_index: int, *,
               delete_branch: bool, kill_windows) -> CloseResult:
    """Kill the task's terminal tabs, remove the worktree, optionally delete branch.

    `kill_windows(task)` is provided by the UI layer and must stop the running
    PTY sessions for the task's tabs.  Removal uses `git worktree remove`, with
    `--force` only because we already got the spec's second confirmation.
    """
    project = state["projects"][project_index]
    task = project["tasks"][task_index]
    notes: list[str] = []
    kill_windows(task)

    dirty = gitops.worktree_is_dirty(task["path"])
    ok, err = gitops.worktree_remove(project["path"], task["path"], force=dirty)
    if not ok:
        return CloseResult(ok=False, notes=notes + [f"worktree remove failed: {err or '?'}"])
    notes.append(f"removed worktree {task['path']}")

    if delete_branch:
        bok, berr = gitops.branch_delete(project["path"], task["slug"])
        if bok:
            notes.append(f"deleted branch {task['slug']}")
        else:
            notes.append(f"kept branch {task['slug']} (git branch -d refused: {berr})")

    project["tasks"].pop(task_index)
    return CloseResult(ok=True, notes=notes)


# ---------------------------------------------------------------------------
# Startup reconciliation (spec: hand-removed worktrees disappear; unknown dirs
# are ignored, never adopted silently)
# ---------------------------------------------------------------------------

def reconcile(state: dict) -> list[str]:
    notes = []
    for project in list(state["projects"]):
        path = project["path"]
        if not os.path.isdir(path) or not gitops.is_git_repo(path):
            notes.append(f"project missing or not a repo, hidden: {path}")
            state["projects"].remove(project)
            continue
        known = {os.path.realpath(w["path"]) for w in gitops.worktree_list(path)}
        for task in list(project["tasks"]):
            if os.path.realpath(task["path"]) not in known:
                notes.append(f"worktree gone, dropped from tree: {task['slug']}")
                project["tasks"].remove(task)
    return notes
