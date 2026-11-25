"""State model, locking, slug helpers and worktree reconciliation.

`state.json` is the source of truth.  Writers take a flock on a sibling lock
file and replace the state atomically, so a killed process never leaves a
half-written file behind.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import re
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterator

SCHEMA_VERSION = 1

SLUG_RE = re.compile(r"[^a-z0-9._-]+")
DASH_RE = re.compile(r"-{2,}")


def new_tab_id() -> str:
    return "tab_" + uuid.uuid4().hex[:10]


def new_session_id() -> str:
    return "ses_" + uuid.uuid4().hex


def slugify(name: str) -> str:
    text = name.strip().lower()
    text = text.replace(" ", "-")
    text = SLUG_RE.sub("", text)
    text = DASH_RE.sub("-", text).strip("-_.")
    if not text:
        text = "task"
    if text.startswith("-"):
        text = "task" + text
    return text


@dataclass
class TerminalTab:
    """One terminal tab.  Each tab owns one tmux window (content only)."""

    id: str = field(default_factory=new_tab_id)
    name: str = "shell"
    kind: str = "shell"  # agent | shell | other
    cwd: str = ""
    agent: str = ""
    session: str = ""
    layout: str = ""
    panes: list[str] = field(default_factory=list)
    active_pane: int = 0

    @property
    def is_agent(self) -> bool:
        return self.kind == "agent"

    def label(self) -> str:
        if self.kind == "agent":
            return f"agent · {self.agent or 'agent'}"
        if self.kind == "shell":
            return "shell"
        return self.name or "terminal"

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "cwd": self.cwd,
        }
        if self.agent:
            data["agent"] = self.agent
        if self.session:
            data["session"] = self.session
        if self.layout:
            data["layout"] = self.layout
        if self.panes:
            data["panes"] = list(self.panes)
        data["active_pane"] = self.active_pane
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any], fallback_id: str = "") -> "TerminalTab":
        kind = str(data.get("kind") or "shell")
        if kind not in {"agent", "shell", "other"}:
            kind = "shell"
        tab_id = str(data.get("id") or "")
        if not tab_id:
            if fallback_id:
                digest = hashlib.sha1(fallback_id.encode("utf-8")).hexdigest()[:10]
                tab_id = "tab_" + digest
            else:
                tab_id = new_tab_id()
        return cls(
            id=tab_id,
            name=str(data.get("name") or ("agent" if kind == "agent" else "shell")),
            kind=kind,
            cwd=str(data.get("cwd") or ""),
            agent=str(data.get("agent") or ""),
            session=str(data.get("session") or ""),
            layout=str(data.get("layout") or ""),
            panes=[str(p) for p in data.get("panes") or [] if p],
            active_pane=int(data.get("active_pane") or 0),
        )


@dataclass
class Task:
    slug: str
    name: str
    path: str
    base: str = "origin/main"
    windows: list[TerminalTab] = field(default_factory=list)
    window_layout: str = ""
    active_window: int = 0
    active_pane: int = 0
    expanded: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "name": self.name,
            "path": self.path,
            "base": self.base,
            "windows": [w.to_dict() for w in self.windows],
            "window_layout": self.window_layout,
            "active_window": self.active_window,
            "active_pane": self.active_pane,
            "expanded": self.expanded,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], scope: str = "") -> "Task":
        slug = str(data.get("slug") or "")
        windows = [
            TerminalTab.from_dict(w, fallback_id=f"task:{scope}:{slug}:{i}")
            for i, w in enumerate(data.get("windows") or [])
            if isinstance(w, dict)
        ]
        task = cls(
            slug=slug,
            name=str(data.get("name") or slug or ""),
            path=str(data.get("path") or ""),
            base=str(data.get("base") or "origin/main"),
            windows=windows,
            window_layout=str(data.get("window_layout") or ""),
            active_window=int(data.get("active_window") or 0),
            active_pane=int(data.get("active_pane") or 0),
            expanded=bool(data.get("expanded") or False),
        )
        # Spec-compatible state stored split geometry and the selected pane on
        # the task.  Our extension keeps them per tab; migrate on load.
        if windows:
            index = min(max(task.active_window, 0), len(windows) - 1)
            task.active_window = index
            active = windows[index]
            if task.window_layout and not active.layout:
                active.layout = task.window_layout
            raw_active = (data.get("windows") or [])[index] if (data.get("windows") or []) else {}
            if isinstance(raw_active, dict) and "active_pane" not in raw_active and task.active_pane:
                active.active_pane = task.active_pane
        return task


@dataclass
class Project:
    path: str
    expanded: bool = True
    scratch: list[TerminalTab] = field(default_factory=list)
    tasks: list[Task] = field(default_factory=list)

    @property
    def name(self) -> str:
        return Path(self.path).name or self.path

    def task_by_slug(self, slug: str) -> Task | None:
        return next((t for t in self.tasks if t.slug == slug), None)

    def tab_by_id(self, tab_id: str) -> tuple[TerminalTab, Task | None] | None:
        for tab in self.scratch:
            if tab.id == tab_id:
                return tab, None
        for task in self.tasks:
            for tab in task.windows:
                if tab.id == tab_id:
                    return tab, task
        return None

    def all_tabs(self) -> Iterator[tuple[TerminalTab, Task | None]]:
        for tab in self.scratch:
            yield tab, None
        for task in self.tasks:
            for tab in task.windows:
                yield tab, task

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "expanded": self.expanded,
            "scratch": [t.to_dict() for t in self.scratch],
            "tasks": [t.to_dict() for t in self.tasks],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Project":
        path = str(data.get("path") or "")
        return cls(
            path=path,
            expanded=bool(data.get("expanded") if "expanded" in data else True),
            scratch=[
                TerminalTab.from_dict(t, fallback_id=f"scratch:{path}:{i}")
                for i, t in enumerate(data.get("scratch") or [])
                if isinstance(t, dict)
            ],
            tasks=[
                Task.from_dict(t, scope=path)
                for t in data.get("tasks") or []
                if isinstance(t, dict)
            ],
        )


@dataclass
class State:
    version: int = SCHEMA_VERSION
    projects: list[Project] = field(default_factory=list)
    active_project: str = ""
    active_task: str = ""
    active_tab: str = ""

    def project_by_path(self, path: str) -> Project | None:
        resolved = os.path.realpath(os.path.expanduser(path))
        return next((p for p in self.projects if os.path.realpath(p.path) == resolved), None)

    def project_for_tab(self, tab_id: str) -> tuple[Project, TerminalTab, Task | None] | None:
        for project in self.projects:
            found = project.tab_by_id(tab_id)
            if found:
                return project, found[0], found[1]
        return None

    def active_project_obj(self) -> Project | None:
        return self.project_by_path(self.active_project) if self.active_project else None

    def active_task_obj(self) -> Task | None:
        project = self.active_project_obj()
        if not project or not self.active_task:
            return None
        return project.task_by_slug(self.active_task)

    def active_tab_obj(self) -> TerminalTab | None:
        found = self.project_for_tab(self.active_tab) if self.active_tab else None
        return found[1] if found else None

    def context_tabs(self) -> list[TerminalTab]:
        project = self.active_project_obj()
        if not project:
            return []
        task = self.active_task_obj()
        return list(task.windows) if task else list(project.scratch)

    def find_tab(self, tab_id: str) -> tuple[Project, TerminalTab, Task | None] | None:
        return self.project_for_tab(tab_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "projects": [p.to_dict() for p in self.projects],
            "active_project": self.active_project,
            "active_task": self.active_task,
            "active_tab": self.active_tab,
            "ui": {
                "active_project": self.active_project,
                "active_task": self.active_task,
                "active_tab": self.active_tab,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "State":
        projects = [Project.from_dict(p) for p in data.get("projects") or [] if isinstance(p, dict)]
        ui = data.get("ui") if isinstance(data.get("ui"), dict) else {}
        return cls(
            version=int(data.get("version") or SCHEMA_VERSION),
            projects=projects,
            active_project=str(data.get("active_project") or ui.get("active_project") or ""),
            active_task=str(data.get("active_task") or ui.get("active_task") or ""),
            active_tab=str(data.get("active_tab") or ui.get("active_tab") or ""),
        )


class StateError(Exception):
    pass


def load_state(path: Path | None = None) -> tuple[State, list[str]]:
    if path is None:
        override = os.environ.get("BALAMBA_STATE_FILE")
        if override:
            path = Path(override)
        else:
            from .config import state_path

            path = state_path()
    path = Path(path)
    warnings: list[str] = []
    if not path.exists():
        return State(), warnings

    def read(candidate: Path):
        raw = json.loads(candidate.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("top-level JSON must be an object")
        return State.from_dict(raw)

    try:
        state = read(path)
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
        backup = path.with_suffix(path.suffix + ".bak")
        if backup.exists():
            try:
                state = read(backup)
                warnings.append(f"{path} was unreadable ({exc}); recovered {backup.name}")
            except Exception as backup_exc:
                raise StateError(f"cannot read {path} or {backup.name}: {exc} / {backup_exc}") from exc
        else:
            raise StateError(f"cannot read {path}: {exc}") from exc
    if state.version > SCHEMA_VERSION:
        warnings.append(f"state schema v{state.version} is newer than v{SCHEMA_VERSION}")
    return state, warnings


@contextlib.contextmanager
def state_lock(state_file: Path | None = None) -> Iterator[None]:
    """Exclusive inter-process lock for state writers."""
    from .config import state_path

    target = Path(state_file) if state_file else state_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_path = target.with_suffix(target.suffix + ".lock")
    with open(lock_path, "a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def save_state(state: State, state_file: Path | None = None) -> Path:
    """Atomically write state while holding the writer lock."""
    from .config import state_path

    target = Path(state_file) if state_file else state_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state.to_dict(), indent=2, sort_keys=False) + "\n"
    with state_lock(target):
        if target.exists():
            try:
                target.with_suffix(target.suffix + ".bak").write_text(
                    target.read_text(encoding="utf-8"), encoding="utf-8"
                )
            except OSError:
                pass
        fd, tmp_name = tempfile.mkstemp(prefix=".state-", suffix=".tmp", dir=str(target.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, target)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
    return target


def state_stats(state: State) -> dict[str, int]:
    tasks = sum(len(p.tasks) for p in state.projects)
    tabs = sum(1 for p in state.projects for _ in p.all_tabs())
    agents = sum(
        1
        for p in state.projects
        for tab, _ in p.all_tabs()
        if tab.kind == "agent"
    )
    return {"projects": len(state.projects), "tasks": tasks, "tabs": tabs, "agents": agents}
