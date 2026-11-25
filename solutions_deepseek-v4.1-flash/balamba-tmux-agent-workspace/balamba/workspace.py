"""Workspace service: state + git + tmux, with no UI concerns.

The Textual app talks to this object only.  Everything here is synchronous;
the app runs the slow paths (startup restore, git refresh) in workers.
"""

from __future__ import annotations

import os
import shlex
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator

from . import config as config_mod
from . import gitops
from .config import Config, load_config
from .state import (
    Project,
    State,
    StateError,
    Task,
    TerminalTab,
    load_state,
    new_session_id,
    save_state,
    slugify,
    state_stats,
)
from .tmuxctl import (
    IDLE_WINDOW,
    SESSION,
    WINDOW_PREFIX,
    PaneInfo,
    Tmux,
    TmuxError,
    editor_window_name,
    layout_leaf_count,
    shell_command,
)

Progress = Callable[[str], None]


class WorkspaceError(RuntimeError):
    pass


@dataclass
class Scope:
    project: Project
    task: Task | None = None

    @property
    def cwd(self) -> str:
        return self.task.path if self.task else self.project.path

    @property
    def label(self) -> str:
        return f"{self.project.name} / {self.task.name}" if self.task else self.project.name

    @property
    def tabs(self) -> list[TerminalTab]:
        return list(self.task.windows) if self.task else list(self.project.scratch)


@dataclass
class StartupReport:
    restored: bool = False
    attached: bool = False
    created_windows: int = 0
    adopted_windows: int = 0
    missing_windows: int = 0
    missing_tasks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str = ""
    duration: float = 0.0


@dataclass
class CloseResult:
    ok: bool
    message: str
    branch_deleted: bool = False
    branch_message: str = ""


class Workspace:
    def __init__(self, cfg: Config | None = None):
        self.config = cfg or load_config()
        self.tmux = Tmux(self.config)
        self.warnings: list[str] = []
        self.startup_error: str = ""
        try:
            self.state, warnings = load_state(self.config.state_file)
            self.warnings.extend(warnings)
        except StateError as exc:
            self.state = State()
            self.startup_error = str(exc)
            self.warnings.append(str(self.startup_error))
        self.window_ids: dict[str, str] = {}
        self.unread: dict[str, bool] = {}
        self.seen_activity: dict[str, int] = {}
        self.missing_tabs: set[str] = set()
        self.dirty = True
        self._pane_cache: dict[str, list[PaneInfo]] = {}

    # -- lookups -------------------------------------------------------
    def all_tabs(self) -> Iterator[tuple[Project, Task | None, TerminalTab]]:
        for project in self.state.projects:
            for tab in project.scratch:
                yield project, None, tab
            for task in project.tasks:
                for tab in task.windows:
                    yield project, task, tab

    def tab_count(self) -> int:
        return sum(1 for _ in self.all_tabs())

    def scope_for(self, tab: TerminalTab) -> Scope | None:
        found = self.state.find_tab(tab.id)
        if not found:
            return None
        project, _, task = found
        return Scope(project, task)

    def active_scope(self) -> Scope | None:
        project = self.state.active_project_obj()
        if not project:
            return None
        task = self.state.active_task_obj()
        return Scope(project, task)

    def active_tab(self) -> tuple[Project, Task | None, TerminalTab] | None:
        if not self.state.active_tab:
            return None
        found = self.state.find_tab(self.state.active_tab)
        if not found:
            return None
        project, tab, task = found
        return project, task, tab

    def project_by_path(self, path: str) -> Project | None:
        return self.state.project_by_path(path)

    def ensure_project_expanded(self, project: Project) -> None:
        project.expanded = True
        for other in self.state.projects:
            if other is not project and other.path != project.path:
                other.expanded = False

    def set_active(
        self,
        project: Project,
        task: Task | None,
        tab: TerminalTab | None,
    ) -> None:
        self.state.active_project = project.path
        self.state.active_task = task.slug if task else ""
        self.state.active_tab = tab.id if tab else ""
        project.expanded = True
        if task:
            task.expanded = True
            if tab:
                try:
                    index = task.windows.index(tab)
                except ValueError:
                    index = task.active_window
                task.active_window = index
                task.active_pane = tab.active_pane
                if tab.layout:
                    task.window_layout = tab.layout
        if tab:
            self.mark_seen(tab.id)
        self.dirty = True

    def activate_tab(self, project: Project, task: Task | None, tab: TerminalTab) -> bool:
        self.set_active(project, task, tab)
        win = self.window_ids.get(tab.id)
        if not win:
            info = self.tmux.window_for_tab(tab.id)
            win = info.id if info else ""
        if win:
            try:
                panes = self.tmux.list_panes(win)
                if tab.active_pane < len(panes):
                    self.tmux.select_pane(panes[tab.active_pane].id)
            except TmuxError:
                pass
        return True

    # -- configuration ------------------------------------------------
    @property
    def _fallback_size(self) -> tuple[int, int]:
        return (100, 30)

    def agent_command(self, tab: TerminalTab, *, resume: bool) -> str:
        if tab.kind != "agent":
            shell = shell_command()
            return f'"{shell}"'
        agent = self.config.agent(tab.agent)
        if not agent.command:
            shell = shell_command()
            return f'"{shell}"'
        return agent.render(tab.session, tab.cwd, resume=resume)

    # -- startup / restore --------------------------------------------
    def startup(self, progress: Progress | None = None) -> StartupReport:
        started = time.time()
        report = StartupReport(warnings=list(self.warnings))
        if self.startup_error:
            report.error = self.startup_error
            report.duration = time.time() - started
            return report

        def note(message: str) -> None:
            if progress:
                try:
                    progress(message)
                except Exception:
                    pass

        note("reconciling state against git worktrees…")
        self.reconcile(report)

        running = self.tmux.server_running()
        if running:
            report.attached = True
            self._cleanup_transient_windows()
            self._cleanup_orphan_content_windows()
            note("attached to the running balamba tmux server")
            self._adopt_existing(report, note)
        else:
            report.restored = True
            note("starting dedicated tmux server…")
            self.tmux.start_server()
            self._restore_windows(report, note)
        self.tmux.mirror_options()

        self._ensure_active(report)
        self.restore_active_pane()
        self.refresh_activity(force=True)
        self.capture_metadata(save=False)
        self.save()
        self.dirty = True
        report.duration = time.time() - started
        return report

    def reconcile(self, report: StartupReport | None = None) -> None:
        missing: list[str] = []
        for project in list(self.state.projects):
            if not Path(project.path).is_dir():
                self.warnings.append(f"project folder is missing: {project.path}")
                continue
            if not gitops.git(["rev-parse", "--show-toplevel"], project.path).ok:
                self.warnings.append(f"not a git repository: {project.path}")
                continue
            present = {
                os.path.realpath(entry.get("worktree", ""))
                for entry in gitops.list_worktrees(project.path)
            }
            for task in list(project.tasks):
                if not Path(task.path).is_dir() or os.path.realpath(task.path) not in present:
                    missing.append(f"{project.name}/{task.name} ({task.path})")
                    project.tasks.remove(task)
                    if self.state.active_task == task.slug:
                        self.state.active_task = ""
                        self.state.active_tab = ""
        if missing:
            self.warnings.append("removed tasks whose worktrees disappeared: " + ", ".join(missing))
        if report is not None:
            report.missing_tasks.extend(missing)
            report.warnings = list(self.warnings)
        self.dirty = True

    def _cleanup_transient_windows(self) -> None:
        for win in self.tmux.list_windows():
            if win.name.startswith("ed_"):
                try:
                    self.tmux.kill_window(win.id)
                except TmuxError:
                    pass

    def _cleanup_orphan_content_windows(self) -> None:
        expected = {WINDOW_PREFIX + tab.id for _, _, tab in self.all_tabs()}
        for win in self.tmux.list_windows():
            if win.name.startswith(WINDOW_PREFIX) and win.name not in expected:
                try:
                    self.tmux.kill_window(win.id)
                except TmuxError:
                    pass

    def _restore_windows(self, report: StartupReport, note: Progress) -> None:
        total = self.tab_count()
        index = 0
        for project, task, tab in self.all_tabs():
            index += 1
            scope = Scope(project, task)
            tab.cwd = tab.cwd or scope.cwd
            note(f"restoring terminal {index}/{total} — {tab.label()}")
            try:
                self.window_ids[tab.id] = self._create_tab_window(tab, scope, resume=True)
                report.created_windows += 1
            except TmuxError as exc:
                self.warnings.append(f"could not restore {tab.label()}: {exc}")
                self.missing_tabs.add(tab.id)
            if tab.kind == "agent" and index < total:
                # Each TUI costs seconds of startup and ~160 MB: space them out.
                time.sleep(0.65)

    def _create_tab_window(self, tab: TerminalTab, scope: Scope, *, resume: bool) -> str:
        command = self.agent_command(tab, resume=resume)
        width, height = self._fallback_size
        win_id = self.tmux.new_window(
            WINDOW_PREFIX + tab.id,
            tab.cwd or scope.cwd,
            command,
            width=width,
            height=height,
        )
        if not win_id:
            info = self.tmux.window_for_tab(tab.id)
            win_id = info.id if info else ""
        if not win_id:
            raise TmuxError("window was not created")
        desired = max(1, len(tab.panes) or layout_leaf_count(tab.layout) or 1)
        desired = min(desired, 8)
        if desired > 1:
            for pane_index in range(1, desired):
                pane_cwd = (
                    tab.panes[pane_index]
                    if pane_index < len(tab.panes)
                    else (tab.cwd or scope.cwd)
                )
                try:
                    self.tmux.split_window(
                        win_id,
                        pane_cwd,
                        vertical=(pane_index % 2 == 1),
                        width=width,
                        height=height,
                    )
                except TmuxError:
                    break
        panes = self.tmux.list_panes(win_id)
        applied = False
        if tab.layout and layout_leaf_count(tab.layout) == len(panes) and len(panes) > 1:
            applied = self.tmux.apply_layout(win_id, tab.layout)
        if not applied and len(panes) > 1:
            # Fall back to equal splits when the saved layout cannot be applied.
            self.tmux.run(["select-layout", "-t", win_id, "tiled"], timeout=5)
        if tab.active_pane < len(panes):
            self.tmux.select_pane(panes[tab.active_pane].id)
        return win_id

    def _adopt_existing(self, report: StartupReport, note: Progress) -> None:
        windows = self.tmux.window_map()
        for project, task, tab in self.all_tabs():
            win = windows.get(WINDOW_PREFIX + tab.id)
            if win:
                self.window_ids[tab.id] = win.id
                self.seen_activity[tab.id] = win.activity
                report.adopted_windows += 1
            else:
                self.missing_tabs.add(tab.id)
                report.missing_windows += 1
        (project, task, tab) = self.active_tab() or (None, None, None)  # type: ignore[misc]
        if tab:
            note(f"attached · {tab.label()}")
        self.capture_metadata(save=False)

    def _ensure_active(self, report: StartupReport) -> None:
        state = self.state
        if not state.projects:
            state.active_project = state.active_task = state.active_tab = ""
            return
        project = state.active_project_obj() or state.projects[0]
        task = state.active_task_obj() if project is state.active_project_obj() else None
        tabs = task.windows if task else project.scratch
        if not tabs:
            # Prefer any task, then any tab, before giving up.
            for candidate_task in project.tasks:
                if candidate_task.windows:
                    task = candidate_task
                    tabs = task.windows
                    break
            else:
                if project.scratch:
                    tabs = project.scratch
        tab = None
        if state.active_tab:
            found = state.find_tab(state.active_tab)
            if found and found[0] is project:
                tab = found[1]
                task = found[2]
        if not tab and tabs:
            index = 0
            if task and 0 <= task.active_window < len(tabs):
                index = task.active_window
            tab = tabs[index]
        self.set_active(project, task, tab)

    def restore_active_pane(self) -> None:
        found = self.active_tab()
        if not found:
            return
        _, _, tab = found
        win = self.window_ids.get(tab.id, "")
        if not win:
            info = self.tmux.window_for_tab(tab.id)
            win = info.id if info else ""
            if win:
                self.window_ids[tab.id] = win
        if not win:
            return
        panes = self.tmux.list_panes(win)
        if panes and 0 <= tab.active_pane < len(panes):
            try:
                self.tmux.select_pane(panes[tab.active_pane].id)
            except TmuxError:
                pass

    def refresh_activity(self, force: bool = False) -> bool:
        windows = self.tmux.list_windows()
        by_name = {w.name: w for w in windows}
        changed = False
        active_id = self.state.active_tab
        for project, task, tab in self.all_tabs():
            win = by_name.get(WINDOW_PREFIX + tab.id)
            if not win:
                if self.window_ids.pop(tab.id, None):
                    self.missing_tabs.add(tab.id)
                    changed = True
                continue
            self.window_ids[tab.id] = win.id
            previous = self.seen_activity.get(tab.id, 0)
            if not previous or force:
                self.seen_activity[tab.id] = win.activity
                previous = win.activity
            if tab.id == active_id:
                self.seen_activity[tab.id] = win.activity
                if self.unread.get(tab.id):
                    self.unread[tab.id] = False
                    changed = True
                continue
            became_unread = (win.activity > previous or win.activity_flag) and not self.unread.get(
                tab.id
            )
            if became_unread:
                self.unread[tab.id] = True
                changed = True
        self.missing_tabs.intersection_update({tab.id for _, _, tab in self.all_tabs()})
        return changed

    def mark_seen(self, tab_id: str) -> None:
        self.unread[tab_id] = False
        win = self.tmux.window_for_tab(tab_id)
        if win:
            self.seen_activity[tab_id] = win.activity

    def unread_task(self, task: Task) -> bool:
        return any(self.unread.get(tab.id) for tab in task.windows)

    def unread_project(self, project: Project) -> bool:
        for tab in project.scratch:
            if self.unread.get(tab.id):
                return True
        return any(self.unread_task(task) for task in project.tasks)

    # -- metadata / state ---------------------------------------------
    def capture_metadata(self, *, save: bool = True) -> bool:
        """Capture pane cwds, layouts and active panes from tmux."""
        changed = False
        for project, task, tab in self.all_tabs():
            win = self.window_ids.get(tab.id) or (self.tmux.window_for_tab(tab.id) or None)
            win_id = win if isinstance(win, str) else (win.id if win else "")
            if not win_id:
                continue
            panes = self.tmux.list_panes(win_id)
            if not panes:
                continue
            self._pane_cache[tab.id] = panes
            cwds = [p.cwd for p in panes]
            layout = self.tmux.window_layout(win_id)
            active_pane = next((p for p in panes if p.active), panes[0])
            if tab.cwd != active_pane.cwd:
                tab.cwd = active_pane.cwd
                changed = True
            if tab.panes != cwds:
                tab.panes = cwds
                changed = True
            if layout and tab.layout != layout:
                tab.layout = layout
                changed = True
            if tab.active_pane != active_pane.index:
                tab.active_pane = active_pane.index
                changed = True
        # Mirror the active tab into the spec-level task fields.  Doing this in
        # a separate pass avoids the last-iterated tab winning.
        for project in self.state.projects:
            for task in project.tasks:
                if not task.windows:
                    continue
                index = next(
                    (i for i, tab in enumerate(task.windows) if tab.id == self.state.active_tab),
                    None,
                )
                if index is None:
                    index = min(max(task.active_window, 0), len(task.windows) - 1)
                active = task.windows[index]
                if task.window_layout != active.layout:
                    task.window_layout = active.layout
                    changed = True
                if task.active_window != index:
                    task.active_window = index
                    changed = True
                if task.active_pane != active.active_pane:
                    task.active_pane = active.active_pane
                    changed = True
        if changed:
            self.dirty = True
            if save:
                self.save()
        return changed

    def save(self) -> Path:
        self.mark_task_metadata()
        path = save_state(self.state, self.config.state_file)
        self.dirty = False
        return path

    def mark_task_metadata(self) -> None:
        for project in self.state.projects:
            for task in project.tasks:
                if not task.windows:
                    continue
                index = min(max(task.active_window, 0), len(task.windows) - 1)
                active = task.windows[index]
                if active.layout:
                    task.window_layout = active.layout
                task.active_pane = active.active_pane

    # -- projects ------------------------------------------------------
    def add_project(self, path: str) -> Project:
        check = gitops.validate_project(path)
        if check.is_worktree:
            raise WorkspaceError(check.warning or "this path is a linked worktree, not a main checkout")
        if not check.ok:
            raise WorkspaceError(check.message or "not a git project")
        existing = self.state.project_by_path(check.path)
        if existing:
            raise WorkspaceError(f"project already added: {check.path}")
        project = Project(path=check.path, expanded=True)
        for other in self.state.projects:
            other.expanded = False
        self.state.projects.append(project)
        self.state.active_project = project.path
        self.state.active_task = ""
        self.state.active_tab = ""
        self.dirty = True
        self.save()
        return project

    def remove_project(self, project: Project) -> None:
        for tab in list(project.scratch):
            self.kill_tab(tab, remove_state=True)
        for task in list(project.tasks):
            for tab in list(task.windows):
                self.kill_tab(tab, remove_state=True)
        self.state.projects = [p for p in self.state.projects if p is not project]
        if self.state.active_project == project.path:
            self.state.active_project = self.state.projects[0].path if self.state.projects else ""
            self.state.active_task = ""
            self.state.active_tab = ""
        self.dirty = True
        self.save()

    # -- tasks ---------------------------------------------------------
    def prepare_task_names(
        self, project: Project, name: str, slug_input: str
    ) -> gitops.UniqueName:
        base_slug = slugify(slug_input or name)
        valid, error = gitops.valid_branch_name(project.path, base_slug)
        if not valid:
            raise WorkspaceError(f"invalid branch name: {error}")
        return gitops.unique_slug(
            project.path, name, base_slug, self.config.worktrees_root
        )

    def create_task(
        self,
        project: Project,
        name: str,
        slug: str,
        base: str,
        kind: str,
        *,
        agent: str | None = None,
    ) -> tuple[Task, TerminalTab]:
        name = name.strip()
        slug = slug.strip()
        if not name:
            raise WorkspaceError("task name is required")
        if not gitops.valid_ref(project.path, base):
            raise WorkspaceError(f"create from ref does not resolve to a commit: {base}")
        if not gitops.valid_branch_name(project.path, slug)[0]:
            raise WorkspaceError(f"invalid branch name: {slug}")
        path = gitops.worktree_path_for(project.path, slug, self.config.worktrees_root)
        if path.exists() or gitops.branch_exists(project.path, slug):
            raise WorkspaceError(f"slug is already taken: {slug}")
        result = gitops.add_worktree(project.path, slug, base, self.config.worktrees_root)
        if not result.ok:
            raise WorkspaceError(result.output or "git worktree add failed")
        task = Task(
            slug=slug,
            name=name,
            path=str(path),
            base=base,
            expanded=True,
        )
        project.tasks.append(task)
        self.ensure_project_expanded(project)
        self.state.active_project = project.path
        self.state.active_task = task.slug
        self.state.active_tab = ""
        self.dirty = True
        try:
            tab = self.create_tab(project, task, kind, agent=agent)
        except WorkspaceError:
            self.save()
            raise
        self.save()
        return task, tab

    def close_task(
        self,
        project: Project,
        task: Task,
        *,
        force: bool = False,
        delete_branch: bool = False,
    ) -> CloseResult:
        for tab in list(task.windows):
            try:
                self.kill_tab(tab, remove_state=False)
            except Exception:
                pass
        task.windows = []
        if Path(task.path).exists():
            removed = gitops.remove_worktree(project.path, task.path, force=force)
        else:
            from .gitops import GitResult

            removed = GitResult(True, "", "worktree directory was already missing", 0)
        if not removed.ok:
            self.warnings.append(removed.err or removed.out)
            self.dirty = True
            self.save()
            return CloseResult(False, f"git worktree remove failed: {removed.text}")
        project.tasks = [t for t in project.tasks if t is not task]
        branch_deleted = False
        branch_message = ""
        if delete_branch:
            branch = gitops.delete_branch(project.path, task.slug)
            branch_deleted = branch.ok
            branch_message = branch.text or (
                "branch deleted" if branch.ok else "branch was not deleted"
            )
        if self.state.active_task == task.slug:
            replacement = project.tasks[0] if project.tasks else None
            self.state.active_task = replacement.slug if replacement else ""
            self.state.active_tab = (
                replacement.windows[0].id
                if replacement and replacement.windows
                else (project.scratch[0].id if project.scratch else "")
            )
        self.dirty = True
        self.save()
        return CloseResult(
            True,
            f"task {task.name} removed",
            branch_deleted=branch_deleted,
            branch_message=branch_message,
        )

    def task_warnings(self, project: Project, task: Task) -> list[str]:
        warnings: list[str] = []
        if not Path(task.path).is_dir():
            warnings.append("worktree directory is missing")
            return warnings
        if gitops.is_detached(task.path):
            warnings.append("HEAD is detached")
        count = gitops.count_dirty(task.path)
        if count:
            warnings.append(f"worktree is dirty ({count} changed file{'s' if count != 1 else ''})")
        if not gitops.worktree_present(project.path, task.path):
            warnings.append("git no longer lists this worktree")
        return warnings

    # -- terminals -----------------------------------------------------
    def create_tab(
        self,
        project: Project,
        task: Task | None,
        kind: str,
        *,
        agent: str | None = None,
        name: str = "",
    ) -> TerminalTab:
        scope = Scope(project, task)
        cwd = scope.cwd
        tab_id = "tab_" + uuid.uuid4().hex[:10]
        agent_name = ""
        session = ""
        if kind == "agent":
            definition = self.config.agent(agent or self.config.agent_default)
            agent_name = definition.name
            session = new_session_id()
            default_name = definition.name
        elif kind == "shell":
            default_name = "shell"
        else:
            kind = "shell"
            default_name = "shell"
        tab = TerminalTab(
            id=tab_id,
            name=name or default_name,
            kind=kind,
            cwd=cwd,
            agent=agent_name,
            session=session,
            active_pane=0,
        )
        try:
            if not self.tmux.server_running():
                self.tmux.start_server()
            self.window_ids[tab.id] = self._create_tab_window(
                tab, scope, resume=False
            )
        except TmuxError as exc:
            raise WorkspaceError(f"could not start terminal: {exc}") from exc
        if task is None:
            project.scratch.append(tab)
        else:
            task.windows.append(tab)
            task.expanded = True
        self.set_active(project, task, tab)
        self.seen_activity[tab.id] = 0
        self.dirty = True
        self.save()
        return tab

    def revive_tab(self, tab: TerminalTab) -> bool:
        scope = self.scope_for(tab)
        if not scope:
            return False
        try:
            self.window_ids[tab.id] = self._create_tab_window(tab, scope, resume=tab.kind == "agent")
            self.missing_tabs.discard(tab.id)
            self.seen_activity[tab.id] = 0
            self.dirty = True
            self.save()
            return True
        except TmuxError:
            return False

    def kill_tab(self, tab: TerminalTab, *, remove_state: bool) -> None:
        win = self.window_ids.pop(tab.id, "")
        if not win:
            info = self.tmux.window_for_tab(tab.id)
            win = info.id if info else ""
        if win:
            try:
                self.tmux.kill_window(win)
            except TmuxError:
                pass
        self.missing_tabs.discard(tab.id)
        self.unread.pop(tab.id, None)
        self.seen_activity.pop(tab.id, None)
        if remove_state:
            found = self.state.find_tab(tab.id)
            if not found:
                return
            project, _, task = found
            if task:
                task.windows = [t for t in task.windows if t.id != tab.id]
                if self.state.active_tab == tab.id:
                    task.active_window = max(0, min(task.active_window, len(task.windows) - 1))
                    self.state.active_tab = task.windows[0].id if task.windows else ""
            else:
                project.scratch = [t for t in project.scratch if t.id != tab.id]
                if self.state.active_tab == tab.id:
                    self.state.active_tab = project.scratch[0].id if project.scratch else ""
            self.dirty = True
            self.save()

    def close_tab(self, project: Project, task: Task | None, tab: TerminalTab) -> None:
        self.kill_tab(tab, remove_state=True)
        remaining = task.windows if task else project.scratch
        current = None
        if self.state.active_tab:
            current = next((t for t in remaining if t.id == self.state.active_tab), None)
        if current:
            self.set_active(project, task, current)
        elif remaining:
            self.set_active(project, task, remaining[0])
        else:
            self.set_active(project, task, None)
        self.save()

    def rename_tab(self, tab: TerminalTab, name: str) -> None:
        tab.name = name.strip() or tab.label()
        self.dirty = True
        self.save()

    def split_tab(self, tab: TerminalTab, *, vertical: bool) -> str:
        win = self.window_ids.get(tab.id)
        if not win:
            raise WorkspaceError("terminal window is not running")
        panes = self.tmux.list_panes(win)
        cwd = panes[-1].cwd if panes else tab.cwd
        try:
            pane_id = self.tmux.split_window(
                win, cwd, vertical=vertical, width=100, height=30
            )
        except TmuxError as exc:
            raise WorkspaceError(str(exc)) from exc
        self.capture_metadata(save=True)
        return pane_id

    def close_pane(self, tab: TerminalTab) -> None:
        win = self.window_ids.get(tab.id)
        if not win:
            return
        panes = self.tmux.list_panes(win)
        if len(panes) <= 1:
            raise WorkspaceError("cannot close the last pane; close the tab instead")
        active = next((p for p in panes if p.active), panes[-1])
        self.tmux.kill_pane(active.id)
        self.capture_metadata(save=True)

    def capture_panes(self, tab: TerminalTab, history: int = 0) -> tuple[list[PaneInfo], dict[str, list[str]]]:
        win = self.window_ids.get(tab.id) or ""
        if not win:
            info = self.tmux.window_for_tab(tab.id)
            win = info.id if info else ""
        if not win:
            return [], {}
        panes = self.tmux.list_panes(win)
        captures: dict[str, list[str]] = {}
        for pane in panes:
            captures[pane.id] = self.tmux.capture(pane.id, history=history)
        return panes, captures

    def send_text(self, tab: TerminalTab, text: str) -> None:
        pane = self.active_pane(tab)
        if pane:
            self.tmux.send_literal(pane.id, text)

    def send_key(self, tab: TerminalTab, key: str) -> None:
        pane = self.active_pane(tab)
        if pane:
            self.tmux.send_key(pane.id, key)

    def active_pane(self, tab: TerminalTab) -> PaneInfo | None:
        win = self.window_ids.get(tab.id)
        if not win:
            info = self.tmux.window_for_tab(tab.id)
            win = info.id if info else ""
            if win:
                self.window_ids[tab.id] = win
        if not win:
            return None
        panes = self.tmux.list_panes(win)
        if not panes:
            return None
        return next((p for p in panes if p.active), panes[0])

    def select_pane_index(self, tab: TerminalTab, index: int) -> None:
        win = self.window_ids.get(tab.id)
        if not win:
            return
        panes = self.tmux.list_panes(win)
        if 0 <= index < len(panes):
            self.tmux.select_pane(panes[index].id)
            tab.active_pane = index
            self.dirty = True

    def cycle_pane(self, tab: TerminalTab, delta: int = 1) -> int:
        win = self.window_ids.get(tab.id)
        if not win:
            return 0
        panes = self.tmux.list_panes(win)
        if not panes:
            return 0
        current = next((i for i, p in enumerate(panes) if p.active), 0)
        new_index = (current + delta) % len(panes)
        self.tmux.select_pane(panes[new_index].id)
        tab.active_pane = new_index
        self.dirty = True
        return new_index

    def resize_tab_window(self, tab: TerminalTab, width: int, height: int) -> None:
        win = self.window_ids.get(tab.id)
        if not win:
            return
        if width < 20 or height < 5:
            return
        try:
            self.tmux.resize_window(win, width, height)
        except TmuxError:
            pass

    # -- editor --------------------------------------------------------
    def open_editor(self, project: Project, task: Task | None) -> tuple[str, str]:
        scope = Scope(project, task)
        token = uuid.uuid4().hex[:8]
        name = editor_window_name(token)
        editor = self.config.editor or os.environ.get("EDITOR") or "vi"
        try:
            if not self.tmux.server_running():
                self.tmux.start_server()
            win_id = self.tmux.new_window(
                name,
                scope.cwd,
                editor,
                width=self._fallback_size[0],
                height=self._fallback_size[1],
            )
        except TmuxError as exc:
            raise WorkspaceError(f"could not launch editor: {exc}") from exc
        if not win_id:
            raise WorkspaceError(f"could not launch editor: {editor}")
        return token, win_id

    def close_editor(self, win_id: str) -> None:
        try:
            self.tmux.kill_window(win_id)
        except TmuxError:
            pass

    # -- git -----------------------------------------------------------
    def git_status(self):
        scope = self.active_scope()
        if not scope:
            return None
        if scope.task:
            return gitops.repo_status(scope.task.path, scope.task.base)
        return gitops.repo_status(scope.project.path, main_checkout=True)

    def stats(self) -> dict[str, int]:
        return state_stats(self.state)

    def doctor_lines(self) -> list[tuple[str, bool, str]]:
        """(label, ok, detail) rows shared by the CLI and the About screen."""
        rows: list[tuple[str, bool, str]] = []
        try:
            running = self.tmux.server_running()
            socket = self.tmux.socket_path()
        except Exception as exc:
            running = False
            socket = f"unavailable: {exc}"
        rows.append(
            (
                "server",
                True,
                f"{'running' if running else 'stopped (starts on launch)'} · {socket}",
            )
        )
        rows.append(
            (
                "state",
                not self.startup_error,
                f"{self.config.state_file} · {self.stats()}"
                if not self.startup_error
                else self.startup_error,
            )
        )
        missing = []
        for project in self.state.projects:
            if not Path(project.path).is_dir():
                missing.append(project.path)
                continue
            for task in project.tasks:
                if not gitops.worktree_present(project.path, task.path):
                    missing.append(task.path)
        rows.append(("worktrees", not missing, ", ".join(missing) if missing else "all present"))
        import shutil

        opencode = shutil.which("opencode")
        rows.append(("opencode", bool(opencode), opencode or "not on PATH"))
        return rows


def make_workspace() -> Workspace:
    config_mod.ensure_layout_files()
    cfg = load_config()
    return Workspace(cfg)
