"""balamba — Textual application.

All chrome and interaction live here (or in the widgets/screens it mounts):
three-column layout, tree, tabs, git panel, status bar, dialogs, context menus,
keyboard and mouse.  tmux is used only as a terminal-content host.
"""

from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime
from pathlib import Path

from rich.text import Text
from textual import events, work
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from . import SIGN_OFF, __version__
from . import gitops
from .config import Config, config_summary, load_config
from .gitops import repo_status
from .screens.context_menu import ContextMenuScreen, MenuItem
from .screens.dialogs import (
    AddProjectScreen,
    CloseTaskScreen,
    ConfirmScreen,
    NewTaskScreen,
    TerminalMenuScreen,
)
from .screens.viewers import (
    DiffScreen,
    EditorScreen,
    InfoScreen,
    about_body,
    help_body,
)
from .state import Project, Task, TerminalTab
from .widgets.git import GitPanel
from .widgets.status import StatusBar
from .widgets.tabstrip import TabStrip, short_path
from .widgets.terminal import TerminalArea
from .widgets.tree import Row, TreePanel
from .widgets.welcome import WelcomePane
from .workspace import Scope, Workspace, WorkspaceError


class BalambaApp(App):
    CSS_PATH = "styles.tcss"
    TITLE = "balamba"
    SUB_TITLE = "textual agent workspace"
    ENABLE_COMMAND_PALETTE = False

    def __init__(self, ws: Workspace, **kwargs):
        super().__init__(**kwargs)
        self.ws = ws
        self.cfg: Config = ws.config
        self.git_status = None
        self.booting = True
        self.boot_message = "starting…"
        self.fatal_error = ""
        self.prefix_armed = False
        self._prefix_timer = None
        self.clock_text = datetime.now().strftime("%H:%M")
        self.terminal: TerminalArea | None = None
        self.tree_panel: TreePanel | None = None
        self.tab_strip: TabStrip | None = None
        self.git_panel: GitPanel | None = None
        self.status_bar: StatusBar | None = None
        self.welcome: WelcomePane | None = None
        self._auto_shell_done: set[str] = set()
        self._last_git_context = ""
        self._busy_label = ""
        self._started = time.time()

    # -- composition ---------------------------------------------------
    def compose(self) -> ComposeResult:
        with Horizontal(id="main"):
            yield TreePanel(self.ws, id="tree-panel")
            with Vertical(id="center"):
                yield TabStrip(self.ws, id="tabstrip")
                with Container(id="content"):
                    self.terminal = TerminalArea(self.ws, id="terminal")
                    yield self.terminal
                    yield WelcomePane(id="welcome")
            yield GitPanel(self.ws, id="git-panel")
        yield StatusBar(self.ws, id="statusbar")

    def on_mount(self) -> None:
        self.tree_panel = self.query_one(TreePanel)
        self.tab_strip = self.query_one(TabStrip)
        self.git_panel = self.query_one(GitPanel)
        self.status_bar = self.query_one(StatusBar)
        self.welcome = self.query_one(WelcomePane)
        self.terminal = self.query_one(TerminalArea)
        self.welcome.display = True
        self.apply_widths()
        self.tree_panel.refresh_view()
        self.tree_panel.view.focus()
        self.set_interval(1.0, self._clock_tick)
        self.set_interval(0.9, self._activity_tick)
        self.set_interval(2.0, self._git_tick)
        self.set_interval(4.0, self._metadata_tick)
        self.set_interval(12.0, self._save_tick)
        self.git_panel.set_status(None)
        self._startup()

    @work(thread=True, exclusive=True, group="startup")
    def _startup(self) -> None:
        def progress(message: str) -> None:
            try:
                self.call_from_thread(self._boot_progress, message)
            except Exception:
                pass

        try:
            report = self.ws.startup(progress=progress)
        except Exception as exc:  # keep the app alive and show the problem
            from .workspace import StartupReport

            report = StartupReport(error=str(exc), warnings=[str(exc)])
        try:
            self.call_from_thread(self._startup_done, report)
        except Exception:
            pass

    def _boot_progress(self, message: str) -> None:
        self.boot_message = message
        if self.welcome:
            self.welcome.refresh()
        if self.status_bar:
            self.status_bar.refresh()

    def _startup_done(self, report) -> None:
        self.booting = False
        if report.error:
            self.fatal_error = report.error
            self.notify(f"startup failed: {report.error}", severity="error", timeout=12)
        else:
            pieces = []
            if report.restored:
                pieces.append(f"restored {report.created_windows} terminals")
            elif report.attached:
                pieces.append(f"attached · adopted {report.adopted_windows} terminals")
            if report.missing_windows:
                pieces.append(f"{report.missing_windows} lost")
            pieces.append(f"{report.duration:.1f}s")
            self.notify(" · ".join(pieces) or "workspace ready", timeout=4)
            if report.warnings:
                self.notify(report.warnings[-1][:180], severity="warning", timeout=10)
        self.tree_panel.refresh_view()
        self.tree_panel.view.select_active()
        self.tree_panel.selected_key = self.tree_panel.view.selected_key
        self.refresh_all()
        self.tree_panel.view.focus()
        self._git_tick()

    # -- widths / layout ----------------------------------------------
    def apply_widths(self) -> None:
        if not self.tree_panel or not self.git_panel:
            return
        width = max(60, self.size.width)
        tree = self.cfg.tree_width
        git = self.cfg.git_width
        min_center = 36
        if tree + git + min_center > width:
            excess = tree + git + min_center - width
            tree = max(20, tree - excess // 2)
            git = max(22, git - (excess - excess // 2))
        if width < 90:
            tree = min(tree, 24)
            git = min(git, 26)
        self.tree_panel.styles.width = tree
        self.git_panel.styles.width = git

    def on_resize(self, event: events.Resize) -> None:
        self.apply_widths()
        if self.terminal and self.terminal.tab:
            self.terminal._apply_size()

    # -- global refresh ------------------------------------------------
    def refresh_all(self) -> None:
        if not self.tree_panel:
            return
        self.apply_widths()
        selected = self.tree_panel.selected_key
        self.tree_panel.selected_key = selected
        self.tree_panel.refresh_view()
        self.tree_panel.view.select_active() if not self.tree_panel.view.selected_row() else None
        self.tree_panel.selected_key = self.tree_panel.view.selected_key
        if self.tab_strip:
            self.tab_strip.refresh()
        if self.status_bar:
            self.status_bar.refresh()
        if self.welcome:
            self.welcome.refresh()
        active = self.ws.active_tab()
        if self.terminal:
            if active:
                self.terminal.attach_tab(active[2])
            else:
                self.terminal.attach_tab(None)
        if self.welcome:
            self.welcome.display = active is None
        if self.git_panel and self.git_status is not None:
            self.git_panel.set_status(self.git_status)

    def refresh_tabstrip(self) -> None:
        if self.tab_strip:
            self.tab_strip.refresh()
        if self.status_bar:
            self.status_bar.refresh()

    # -- timers --------------------------------------------------------
    def _clock_tick(self) -> None:
        now = datetime.now().strftime("%H:%M")
        if now != self.clock_text:
            self.clock_text = now
            self.refresh_tabstrip()

    def _activity_tick(self) -> None:
        if self.booting or not self.tree_panel:
            return
        # Deliberately synchronous: it is one cheap tmux query and it avoids
        # mutating shared state from a worker while the UI thread is active.
        try:
            changed = self.ws.refresh_activity()
        except Exception:
            return
        if changed:
            self.tree_panel.refresh_view()
            self.refresh_tabstrip()
            if self.welcome:
                self.welcome.refresh()
        active = self.ws.active_tab()
        if active and active[2].id in self.ws.missing_tabs:
            self.refresh_tabstrip()

    def _git_tick(self) -> None:
        if self.booting:
            return
        self.run_worker(self._git_async(), group="git", exclusive=True)

    async def _git_async(self) -> None:
        try:
            status = await asyncio.to_thread(self.ws.git_status)
        except Exception as exc:
            status = None
            self.notify(f"git refresh failed: {exc}", severity="warning")
        self.git_status = status
        if self.git_panel:
            self.git_panel.set_status(status)
        self.refresh_tabstrip()
        scope = self.ws.active_scope()
        self._last_git_context = f"{scope.project.path}:{scope.task.slug if scope.task else ''}" if scope else ""
        if self.welcome:
            self.welcome.refresh()

    def _metadata_tick(self) -> None:
        if self.booting or self.ws.startup_error:
            return
        try:
            self.ws.capture_metadata(save=False)
            if self.ws.dirty:
                self.ws.save()
        except Exception:
            pass
        self.refresh_tabstrip()

    def _save_tick(self) -> None:
        if self.booting or self.ws.startup_error:
            return
        try:
            self.ws.capture_metadata(save=False)
            if self.ws.dirty:
                self.ws.save()
        except Exception:
            pass

    # -- global keys ---------------------------------------------------
    async def on_event(self, event: events.Event) -> None:
        """Intercept the app prefix before the focused widget sees the key.

        Textual forwards keys straight to the focused widget and only bubbles
        unhandled keys to the App.  A tmux-style prefix must win over the tree's
        normal keys, so we handle it here, before that forwarding happens.
        """
        if (
            isinstance(event, events.Key)
            and not event.is_forwarded
            and isinstance(self.screen, EditorScreen)
            and event.key in {"ctrl+c", "ctrl+q"}
        ):
            # The editor overlay hosts a real terminal; do not let Textual's
            # copy/quit shortcuts steal these keys from vim/emacs.
            try:
                if self.screen.terminal:
                    self.screen.terminal._send_key(
                        "C-c" if event.key == "ctrl+c" else "C-q"
                    )
            except Exception:
                pass
            event.stop()
            return
        if (
            isinstance(event, events.Key)
            and not event.is_forwarded
            and not isinstance(self.screen, ModalScreen)
            and not self.booting
        ):
            if self._handle_global(event):
                event.stop()
                try:
                    event.prevent_default()
                except Exception:
                    pass
                return
        await super().on_event(event)

    def _match_prefix(self, key: str) -> bool:
        return key == self.cfg.prefix_key

    def _handle_global(self, event: events.Key) -> bool:
        key = event.key
        if key in {"f1"}:
            self.action_about()
            return True
        if key == "f2":
            self.action_help()
            return True
        if key == "f3":
            self.action_doctor()
            return True
        if key == "f5":
            self._git_tick()
            self.notify("git panel refreshed", timeout=2)
            return True
        if key == "r":
            found = self.ws.active_tab()
            if found and found[2].id in self.ws.missing_tabs:
                self.revive_active_tab()
                return True
        if key == "ctrl+shift+q":
            self.action_detach()
            return True
        if self._match_prefix(key):
            if self.prefix_armed:
                self._disarm_prefix()
                if self.focused is self.terminal and self.terminal:
                    self.terminal._send_key(self._literal_prefix_key())
                return True
            self._arm_prefix()
            return True
        if self.prefix_armed:
            self._prefix_command(event)
            return True
        if key in {"ctrl+c", "ctrl+q"}:
            if self.focused is self.terminal and self.terminal and self.terminal.tab:
                self.terminal._send_key("C-c" if key == "ctrl+c" else "C-q")
            else:
                self.action_detach()
            return True
        return False

    def _literal_prefix_key(self) -> str:
        key = self.cfg.prefix_key
        if key.startswith("ctrl+") and len(key) > 5:
            return "C-" + key[-1]
        if key.startswith("alt+") and len(key) > 4:
            return "M-" + key[-1]
        return key

    def _arm_prefix(self) -> None:
        self.prefix_armed = True
        if self._prefix_timer:
            self._prefix_timer.stop()
        self._prefix_timer = self.set_timer(2.5, self._disarm_prefix)
        self.refresh_tabstrip()
        if self.status_bar:
            self.status_bar.refresh()

    def _disarm_prefix(self) -> None:
        self.prefix_armed = False
        if self._prefix_timer:
            self._prefix_timer.stop()
            self._prefix_timer = None
        self.refresh_tabstrip()

    def _prefix_command(self, event: events.Key) -> None:
        key = event.key
        char = event.character or ""
        # Textual reports shift+letter as the uppercase character.
        command = char if len(char) == 1 else (key if len(key) == 1 else "")
        self._disarm_prefix()
        if key == "escape":
            return
        if key.isdigit():
            self.action_tab(int(key))
            return
        action = self.cfg.command_for(command)
        if not action and command == "t":
            action = "new-terminal"  # friendly alias; spec's default is T
        if action == "new-task":
            self.action_new_task()
        elif action == "add-project":
            self.action_add_project()
        elif action == "new-terminal":
            self.action_new_terminal()
        elif action == "next-tab":
            self.action_next_tab()
        elif action == "prev-tab":
            self.action_prev_tab()
        elif action == "editor":
            self.action_editor(scope=self.ws.active_scope())
        elif action in {"detach", "quit"}:
            self.action_detach()
        elif action == "redraw":
            self.action_redraw()
        elif action == "close-tab":
            self.action_close_tab()
        elif action == "split-v":
            self.action_split(True)
        elif action == "split-h":
            self.action_split(False)
        elif action == "cycle-pane":
            self.action_cycle_pane()
        elif action == "focus-cycle":
            self.cycle_focus()
        elif action == "about":
            self.action_about()
        elif action == "help":
            self.action_help()
        elif command == "[":
            self.notify("Textual text selection is native; drag to select, then copy.")
        else:
            self.notify(f"unknown prefix command: {command or key}", severity="warning")

    # -- focus ---------------------------------------------------------
    def focus_tree(self) -> None:
        if self.tree_panel:
            self.tree_panel.view.focus()

    def focus_git(self) -> None:
        if self.git_panel:
            self.git_panel.body.focus()

    def focus_terminal(self) -> None:
        if self.terminal and self.ws.active_tab():
            self.terminal.focus()

    def cycle_focus(self) -> None:
        focused = self.focused
        if focused is self.tree_panel.view:
            if self.ws.active_tab():
                self.focus_terminal()
            else:
                self.focus_git()
        elif focused is self.terminal:
            self.focus_git()
        else:
            self.focus_tree()

    # -- tree model ----------------------------------------------------
    def selected_row(self) -> Row | None:
        return self.tree_panel.view.selected_row() if self.tree_panel else None

    def current_scope(self) -> Scope | None:
        row = self.selected_row()
        if row:
            if row.kind == "project":
                return Scope(row.project, None)
            if row.kind in {"task", "terminal", "scratch"} and row.task:
                return Scope(row.project, row.task)
            if row.kind == "scratch":
                return Scope(row.project, None)
        return self.ws.active_scope()

    def current_project(self) -> Project | None:
        row = self.selected_row()
        if row and row.kind in {"project", "task", "terminal", "scratch", "hint"}:
            return row.project
        scope = self.ws.active_scope()
        return scope.project if scope else None

    def current_task(self) -> Task | None:
        row = self.selected_row()
        if row:
            if row.kind == "project":
                return None
            if row.kind in {"scratch"}:
                return None
            if row.task:
                return row.task
        return self.ws.active_task_obj()

    def toggle_row(self, row: Row) -> None:
        if row.kind == "project":
            row.project.expanded = not row.project.expanded
        elif row.kind == "task" and row.task:
            row.task.expanded = not row.task.expanded
            if row.task.expanded:
                self.ws.state.active_project = row.project.path
                self.ws.state.active_task = row.task.slug
        self.ws.dirty = True
        self.ws.save()
        self.tree_panel.refresh_view()

    def tree_fold(self, expand: bool) -> None:
        row = self.selected_row()
        if not row:
            return
        if row.kind == "project":
            row.project.expanded = expand
        elif row.kind == "task" and row.task:
            row.task.expanded = expand
        elif row.tab and row.task:
            row.task.expanded = expand
        elif row.tab:
            row.project.expanded = expand
        self.ws.dirty = True
        self.ws.save()
        self.tree_panel.refresh_view()

    def tree_activate(self, row: Row) -> None:
        if self.booting:
            self.notify("still restoring…", timeout=2)
            return
        if row.kind == "hint":
            self.action_add_project() if not row.project.tasks else self.action_new_task()
            return
        if row.kind == "project":
            self.ws.ensure_project_expanded(row.project)
            tab = row.project.scratch[0] if row.project.scratch else None
            self.ws.set_active(row.project, None, tab)
            self.ws.save()
            needs_shell = not row.project.scratch
            self.refresh_all()
            self.focus_tree()
            self._git_tick()
            if needs_shell and row.project.path not in self._auto_shell_done:
                self._auto_shell_done.add(row.project.path)
                self._create_scratch_shell(row.project)
            return
        if row.kind == "task" and row.task:
            self.ws.ensure_project_expanded(row.project)
            row.task.expanded = True
            tab = None
            if row.task.windows:
                index = min(max(row.task.active_window, 0), len(row.task.windows) - 1)
                tab = row.task.windows[index]
            self.ws.set_active(row.project, row.task, tab)
            self.ws.save()
            self.refresh_all()
            self._git_tick()
            if not tab:
                self._create_scope_shell(row.project, row.task)
            else:
                self.focus_terminal()
            return
        if row.tab:
            self.switch_tab(row.tab.id)

    def _create_scratch_shell(self, project: Project) -> None:
        try:
            tab = self.ws.create_tab(project, None, "shell")
        except WorkspaceError as exc:
            self.notify(str(exc), severity="error")
            return
        self.refresh_all()
        self.focus_terminal()
        self.notify(f"started scratch shell in {project.name}")

    def _create_scope_shell(self, project: Project, task: Task) -> None:
        try:
            tab = self.ws.create_tab(project, task, "shell")
        except WorkspaceError as exc:
            self.notify(str(exc), severity="error")
            return
        self.refresh_all()
        self.focus_terminal()

    # -- tabs ----------------------------------------------------------
    def switch_tab(self, tab_id: str) -> None:
        found = self.ws.state.find_tab(tab_id)
        if not found:
            return
        project, tab, task = found
        self.ws.ensure_project_expanded(project)
        if task:
            task.expanded = True
        self.ws.activate_tab(project, task, tab)
        self.ws.save()
        # Keep the tree selection in sync when the tab is reached from the status bar.
        self.tree_panel.view.selected_key = f"x:{tab.id}" if task else f"s:{tab.id}"
        self.tree_panel.selected_key = self.tree_panel.view.selected_key
        self.refresh_all()
        self.focus_terminal()
        self._git_tick()

    def action_next_tab(self) -> None:
        tabs = self.ws.state.context_tabs()
        if not tabs:
            self.notify("no tabs in this context")
            return
        try:
            index = next(i for i, t in enumerate(tabs) if t.id == self.ws.state.active_tab)
        except StopIteration:
            index = -1
        self.switch_tab(tabs[(index + 1) % len(tabs)].id)

    def action_prev_tab(self) -> None:
        tabs = self.ws.state.context_tabs()
        if not tabs:
            return
        try:
            index = next(i for i, t in enumerate(tabs) if t.id == self.ws.state.active_tab)
        except StopIteration:
            index = 0
        self.switch_tab(tabs[(index - 1) % len(tabs)].id)

    def action_tab(self, number: int) -> None:
        tabs = self.ws.state.context_tabs()
        if 1 <= number <= len(tabs):
            self.switch_tab(tabs[number - 1].id)

    def action_close_tab(self) -> None:
        tab = self.ws.state.active_tab_obj()
        if not tab:
            return
        self.confirm_close_tab(tab)

    def confirm_close_tab(self, tab: TerminalTab) -> None:
        found = self.ws.state.find_tab(tab.id)
        if not found:
            return
        project, _, task = found
        warning = ""
        if tab.kind == "agent":
            warning = f"\n\nThis kills the agent terminal. Its session id is: {tab.session[:16]}…"
        self.push_screen(
            ConfirmScreen(
                "Close terminal",
                f"Close “{tab.name}” in {project.name}"
                + (f" › {task.name}" if task else " (scratch)")
                + warning
                + "\n\nThe worktree and branch are not touched.",
                confirm_label="Close terminal",
                danger=True,
            ),
            callback=lambda result: self._close_tab_done(tab, project, task, result),
        )

    def _close_tab_done(self, tab, project, task, result) -> None:
        if not result or not result.get("confirmed"):
            return
        try:
            self.ws.close_tab(project, task, tab)
        except Exception as exc:
            self.notify(f"could not close tab: {exc}", severity="error")
            return
        self.refresh_all()
        self.tree_panel.view.select_active()
        self.tree_panel.selected_key = self.tree_panel.view.selected_key
        self.tree_panel.refresh_view()
        self.focus_tree()

    # -- new task / terminal / project ---------------------------------
    def _editable(self) -> bool:
        if self.ws.startup_error:
            self.notify("state file is invalid; fix it (F3 doctor)", severity="error")
            return False
        return True

    def action_new_task(self) -> None:
        if not self._editable():
            return
        if self.booting:
            self.notify("still restoring…")
            return
        project = self.current_project()
        if not project:
            self.notify("add a project first (p)", severity="warning")
            self.action_add_project()
            return
        self.push_screen(
            NewTaskScreen(self.ws, project),
            callback=lambda result: self._new_task_result(project, result),
        )

    def _new_task_result(self, project: Project, result) -> None:
        if not result:
            return
        self.notify(f"creating worktree {result['slug']}…", timeout=3)
        self.run_worker(self._create_task_async(project, result), group="task-create", exclusive=True)

    async def _create_task_async(self, project: Project, result: dict) -> None:
        try:
            task, tab = await asyncio.to_thread(
                self.ws.create_task,
                project,
                result["name"],
                result["slug"],
                result["base"],
                result["kind"],
                agent=result.get("agent") or None,
            )
        except Exception as exc:
            self.notify(f"task creation failed: {exc}", severity="error", timeout=12)
            self.refresh_all()
            return
        self.tree_panel.view.selected_key = f"x:{tab.id}"
        self.tree_panel.selected_key = self.tree_panel.view.selected_key
        self.refresh_all()
        self.focus_terminal()
        self._git_tick()
        self.notify(f"task {task.name} · branch {task.slug} · from {task.base}", timeout=5)

    def action_add_project(self) -> None:
        if not self._editable():
            return
        if self.booting:
            self.notify("still restoring…")
            return
        self.push_screen(AddProjectScreen(self.ws), callback=self._add_project_result)

    def _add_project_result(self, path) -> None:
        if not path:
            return
        try:
            project = self.ws.add_project(path)
        except WorkspaceError as exc:
            self.notify(str(exc), severity="error", timeout=8)
            return
        self.tree_panel.view.selected_key = f"p:{project.path}"
        self.tree_panel.selected_key = self.tree_panel.view.selected_key
        self._auto_shell_done.discard(project.path)
        self.refresh_all()
        self.focus_tree()
        self.notify(f"project added: {project.name}")

    def action_new_terminal(self) -> None:
        if not self._editable():
            return
        if self.booting:
            self.notify("still restoring…")
            return
        project = self.current_project()
        if not project:
            self.notify("add a project first (p)", severity="warning")
            return
        row = self.selected_row()
        task: Task | None = None
        if row and row.task:
            task = row.task
        elif row and row.kind == "project":
            task = None
        else:
            task = self.ws.state.active_task_obj()
        self.push_screen(
            TerminalMenuScreen(self.ws, project, task),
            callback=lambda result: self._new_terminal_result(project, task, result),
        )

    def _new_terminal_result(self, project: Project, task: Task | None, result) -> None:
        if not result:
            return
        self.run_worker(
            self._create_terminal_async(project, task, result),
            group="terminal-create",
            exclusive=True,
        )

    async def _create_terminal_async(self, project: Project, task: Task | None, result: dict) -> None:
        try:
            tab = await asyncio.to_thread(
                self.ws.create_tab, project, task, result.get("kind", "shell"), agent=result.get("agent")
            )
        except Exception as exc:
            self.notify(f"terminal creation failed: {exc}", severity="error", timeout=10)
            return
        self.tree_panel.view.selected_key = f"x:{tab.id}" if task else f"s:{tab.id}"
        self.tree_panel.selected_key = self.tree_panel.view.selected_key
        self.refresh_all()
        self.focus_terminal()
        self._git_tick()
        self.notify(f"opened {tab.label()}", timeout=3)

    # -- editor --------------------------------------------------------
    def action_editor(self, scope: Scope | None = None) -> None:
        scope = scope or self.current_scope()
        if not scope:
            self.notify("select a project or task first", severity="warning")
            return
        try:
            token, win_id = self.ws.open_editor(scope.project, scope.task)
        except WorkspaceError as exc:
            self.notify(str(exc), severity="error")
            return
        label = self.cfg.editor
        screen = EditorScreen(self.ws, win_id, label, scope.cwd)
        self.push_screen(screen, callback=self._editor_closed)

    def _editor_closed(self, win_id) -> None:
        if win_id:
            self.ws.close_editor(win_id)
        self.refresh_all()
        self.focus_tree()

    # -- close task ----------------------------------------------------
    def action_close_task(self) -> None:
        row = self.selected_row()
        if row and row.kind == "project":
            self.notify("select a task row to close a task", severity="warning")
            return
        task = self.current_task()
        if not task:
            self.notify("select a task to close", severity="warning")
            return
        project = None
        for candidate in self.ws.state.projects:
            if any(t is task for t in candidate.tasks):
                project = candidate
                break
        if not project:
            self.notify("task is not in the workspace", severity="error")
            return
        self.push_screen(
            CloseTaskScreen(self.ws, project, task),
            callback=lambda result: self._close_task_result(project, task, result),
        )

    def _close_task_result(self, project: Project, task: Task, result) -> None:
        if not result:
            return
        force = bool(self.ws.task_warnings(project, task))
        self.notify(f"closing {task.name}…", timeout=3)
        self.run_worker(
            self._close_task_async(project, task, force, result.get("delete_branch", False)),
            group="task-close",
            exclusive=True,
        )

    async def _close_task_async(self, project, task, force: bool, delete_branch: bool) -> None:
        try:
            result = await asyncio.to_thread(
                self.ws.close_task,
                project,
                task,
                force=force,
                delete_branch=delete_branch,
            )
        except Exception as exc:
            self.notify(f"close failed: {exc}", severity="error", timeout=10)
            return
        if not result.ok:
            self.notify(result.message, severity="error", timeout=10)
            self.refresh_all()
            return
        self.tree_panel.view.select_active()
        self.tree_panel.selected_key = self.tree_panel.view.selected_key
        self.refresh_all()
        self.focus_tree()
        self._git_tick()
        message = result.message
        if delete_branch:
            message += f" · branch: {result.branch_message or ('deleted' if result.branch_deleted else 'kept')}"
        self.notify(message, timeout=6)

    # -- splits / panes ------------------------------------------------
    def action_split(self, vertical: bool) -> None:
        tab = self.ws.state.active_tab_obj()
        if not tab:
            self.notify("no active terminal")
            return
        try:
            self.ws.split_tab(tab, vertical=vertical)
        except Exception as exc:
            self.notify(str(exc), severity="error")
            return
        self.refresh_all()
        self.focus_terminal()
        self.notify("pane split")

    def action_close_pane(self) -> None:
        tab = self.ws.state.active_tab_obj()
        if not tab:
            return
        try:
            self.ws.close_pane(tab)
        except Exception as exc:
            self.notify(str(exc), severity="warning")
            return
        self.refresh_all()

    def action_cycle_pane(self) -> None:
        tab = self.ws.state.active_tab_obj()
        if not tab:
            return
        try:
            self.ws.cycle_pane(tab, 1)
        except Exception as exc:
            self.notify(f"could not select pane: {exc}", severity="warning")
            return
        if self.terminal:
            self.terminal._tick_now()
        self.refresh_tabstrip()

    def action_revive_tab(self) -> None:
        tab = self.ws.state.active_tab_obj()
        if not tab:
            return
        self.revive_active_tab()

    def revive_active_tab(self) -> None:
        tab = self.ws.state.active_tab_obj()
        if not tab:
            return
        if self.ws.revive_tab(tab):
            self.notify(f"reattached {tab.label()}")
            self.refresh_all()
            self.focus_terminal()
        else:
            self.notify("could not reattach terminal", severity="error")

    # -- diff ----------------------------------------------------------
    def show_diff(self, path: str) -> None:
        scope = self.ws.active_scope()
        if not scope:
            return
        title = f" DIFF   {scope.label} · {path}"
        screen = DiffScreen(title)
        self.push_screen(screen)
        self.run_worker(self._load_diff(scope.cwd, path, screen), group="diff", exclusive=False)

    async def _load_diff(self, cwd: str, path: str, screen: DiffScreen) -> None:
        try:
            ok, text, label = await asyncio.to_thread(gitops.diff_for_file, cwd, path)
        except Exception as exc:
            try:
                screen.set_error(str(exc))
            except Exception:
                pass
            return
        if not ok:
            try:
                screen.set_error(text)
            except Exception:
                pass
            return
        lines = text.splitlines()
        if len(lines) > 20000:
            text = "\n".join(lines[:20000]) + f"\n… truncated ({len(lines) - 20000} more lines)"
        try:
            screen.set_content(text, label)
        except Exception:
            pass

    # -- menus ---------------------------------------------------------
    def _open_menu(self, row: Row | None, title: str, items: list[MenuItem], x: int, y: int) -> None:
        if not items:
            return
        self.push_screen(
            ContextMenuScreen(title, items, x, y),
            callback=lambda action: self._menu_action(row, action),
        )

    def _menu_action(self, row: Row | None, action: str | None) -> None:
        if not action:
            return
        if row is None:
            return
        tab = row.tab
        project = row.project
        task = row.task
        if action == "activate":
            self.tree_activate(row)
        elif action == "new-task":
            self.ws.ensure_project_expanded(project)
            self.ws.state.active_project = project.path
            self.ws.state.active_task = ""
            self.push_screen(
                NewTaskScreen(self.ws, project),
                callback=lambda result: self._new_task_result(project, result),
            )
        elif action == "new-terminal":
            self.push_screen(
                TerminalMenuScreen(self.ws, project, task),
                callback=lambda result: self._new_terminal_result(project, task, result),
            )
        elif action == "editor":
            self.ws.state.active_project = project.path
            self.ws.state.active_task = task.slug if task else ""
            if row and self.tree_panel and any(r.key == row.key for r in self.tree_panel.view.rows):
                self.tree_panel.view.selected_key = row.key
                self.tree_panel.selected_key = row.key
            self.action_editor(Scope(project, task))
        elif action == "copy-path":
            self._copy(task.path if task else project.path)
        elif action == "copy-cwd":
            self._copy(tab.cwd if tab else (task.path if task else project.path))
        elif action == "toggle":
            self.toggle_row(row)
        elif action == "close-task" and task:
            self.push_screen(
                CloseTaskScreen(self.ws, project, task),
                callback=lambda result: self._close_task_result(project, task, result),
            )
        elif action == "remove-project":
            self._confirm_remove_project(project)
        elif action == "restart-agents" and task:
            self.run_worker(self._restart_agents(project, task), group="restart", exclusive=True)
        elif action == "restart-tab" and tab:
            self._restart_tab(project, task, tab)
        elif action == "close-tab" and tab:
            self.confirm_close_tab(tab)
        elif action == "split-right" and tab:
            self.ws.state.active_tab = tab.id
            self.ws.state.active_task = task.slug if task else ""
            self.action_split(True)
        elif action == "split-down" and tab:
            self.ws.state.active_tab = tab.id
            self.ws.state.active_task = task.slug if task else ""
            self.action_split(False)
        elif action == "close-pane" and tab:
            self.ws.state.active_tab = tab.id
            self.action_close_pane()
        elif action == "diff" and tab:
            pass
        elif action == "about":
            self.action_about()

    def tree_context_menu(self, row: Row, x: int, y: int) -> None:
        project = row.project
        task = row.task
        tab = row.tab
        items: list[MenuItem] = []
        if row.kind == "project":
            items = [
                MenuItem("new-task", "New task", "n"),
                MenuItem("new-terminal", "New scratch shell", "t"),
                MenuItem("editor", "Open editor here", "e"),
                MenuItem("copy-path", "Copy project path", ""),
                MenuItem("toggle", "Expand / collapse", ""),
                MenuItem("remove-project", "Remove project from balamba", "danger", danger=True),
            ]
        elif row.kind == "task":
            items = [
                MenuItem("activate", "Open task", "enter"),
                MenuItem("new-terminal", "New terminal", "t"),
                MenuItem("editor", "Open editor in worktree", "e"),
                MenuItem("copy-path", "Copy worktree path", ""),
                MenuItem("restart-agents", "Restart agent terminals", ""),
                MenuItem("toggle", "Expand / collapse terminals", ""),
                MenuItem("close-task", "Close task…", "d", danger=True),
            ]
        elif row.tab:
            items = [
                MenuItem("activate", "Open terminal", "enter"),
                MenuItem("new-terminal", "New terminal", "t"),
                MenuItem("split-right", "Split right", "c-a \\"),
                MenuItem("split-down", "Split down", "c-a -"),
                MenuItem("copy-cwd", "Copy working directory", ""),
                MenuItem("restart-tab", "Restart terminal", "r"),
                MenuItem("close-tab", "Close terminal", "c-a x", danger=True),
            ]
        else:
            items = [
                MenuItem("new-task", "New task", "n"),
                MenuItem("new-terminal", "New terminal", "t"),
            ]
        title = project.name
        if task:
            title += f" › {task.name}"
        if tab:
            title += f" › {tab.label()}"
        self._open_menu(row, title, items, x, y)

    def tab_context_menu(self, tab: TerminalTab | None, x: int, y: int) -> None:
        if not tab:
            project = self.current_project()
            if project:
                self._open_menu(
                    Row(f"p:{project.path}", "project", project),
                    project.name,
                    [MenuItem("new-terminal", "New terminal", "t")],
                    x,
                    y,
                )
            return
        found = self.ws.state.find_tab(tab.id)
        if not found:
            return
        project, _, task = found
        row = Row(f"x:{tab.id}", "terminal", project, task=task, tab=tab, depth=2)
        items = [
            MenuItem("activate", "Switch to tab", "enter"),
            MenuItem("split-right", "Split right", "c-a \\"),
            MenuItem("split-down", "Split down", "c-a -"),
            MenuItem("copy-cwd", "Copy working directory", ""),
            MenuItem("restart-tab", "Restart terminal", ""),
            MenuItem("close-tab", "Close terminal", "c-a x", danger=True),
        ]
        self._open_menu(row, tab.label(), items, x, y)

    def terminal_context_menu(self, pane, x: int, y: int) -> None:
        tab = self.ws.state.active_tab_obj()
        if not tab:
            return
        found = self.ws.state.find_tab(tab.id)
        if not found:
            return
        project, _, task = found
        row = Row(f"x:{tab.id}", "terminal", project, task=task, tab=tab, depth=2)
        items = [
            MenuItem("split-right", "Split right", "c-a \\"),
            MenuItem("split-down", "Split down", "c-a -"),
            MenuItem("copy-cwd", "Copy pane cwd", ""),
            MenuItem("close-pane", "Close this pane", "", danger=True),
            MenuItem("new-terminal", "New terminal", "t"),
        ]
        self._open_menu(row, f"{tab.label()} · {pane.command}", items, x, y)

    def git_file_context_menu(self, index: int, x: int, y: int) -> None:
        status = self.git_status
        if not status or not status.files or index >= len(status.files):
            return
        file = status.files[index]
        scope = self.ws.active_scope()
        if not scope:
            return
        project = scope.project
        task = scope.task
        row = Row(f"git:{file.path}", "gitfile", project, task=task)
        items = [
            MenuItem("diff", "Open diff overlay", "enter"),
            MenuItem("copy-relative", "Copy relative path", ""),
            MenuItem("copy-absolute", "Copy absolute path", ""),
        ]
        self.push_screen(
            ContextMenuScreen(file.path, items, x, y),
            callback=lambda action: self._git_file_action(action, file.path, scope.cwd),
        )

    def _git_file_action(self, action: str | None, path: str, cwd: str) -> None:
        if action == "diff":
            self.show_diff(path)
        elif action == "copy-relative":
            self._copy(path)
        elif action == "copy-absolute":
            self._copy(str(Path(cwd) / path))

    def git_context_menu(self, x: int, y: int) -> None:
        status = self.git_status
        if not status:
            return
        project = self.current_project()
        task = self.current_task()
        row = Row("git", "git", project, task=task) if project else None
        items = [
            MenuItem("git-refresh", "Refresh git panel", "F5"),
            MenuItem("copy-branch", "Copy branch name", ""),
            MenuItem("editor", "Open editor", "e"),
        ]
        self.push_screen(
            ContextMenuScreen("Git", items, x, y),
            callback=lambda action: self._git_action(action, status),
        )

    def _git_action(self, action: str | None, status) -> None:
        if action == "git-refresh":
            self._git_tick()
        elif action == "copy-branch":
            self._copy(status.branch if status and status.ok else "")
        elif action == "editor":
            self.action_editor(scope=self.ws.active_scope())

    def _copy(self, text: str) -> None:
        if not text:
            return
        try:
            self.copy_to_clipboard(text)
            self.notify(f"copied {text}", timeout=3)
        except Exception:
            self.notify(f"clipboard unavailable · {text}", severity="warning")

    # -- project removal ----------------------------------------------
    def _confirm_remove_project(self, project: Project) -> None:
        self.push_screen(
            ConfirmScreen(
                "Remove project",
                f"Remove “{project.name}” from balamba?\n\n"
                f"{project.path}\n\n"
                "The folder, its worktrees and every branch stay on disk. "
                "Only balamba's state and the terminal windows are removed.",
                confirm_label="Remove from balamba",
                danger=True,
            ),
            callback=lambda result: self._remove_project_done(project, result),
        )

    def _remove_project_done(self, project: Project, result) -> None:
        if not result or not result.get("confirmed"):
            return
        try:
            self.ws.remove_project(project)
        except Exception as exc:
            self.notify(f"removal failed: {exc}", severity="error")
            return
        self._auto_shell_done.discard(project.path)
        self.tree_panel.selected_key = ""
        self.tree_panel.refresh_view()
        self.refresh_all()
        self.focus_tree()
        self.notify("project removed from balamba · files untouched")

    # -- restart terminals --------------------------------------------
    def _restart_tab(self, project: Project, task: Task | None, tab: TerminalTab) -> None:
        self.ws.state.active_project = project.path
        self.ws.state.active_tab = tab.id
        self.ws.state.active_task = task.slug if task else ""
        try:
            self.ws.kill_tab(tab, remove_state=False)
        except Exception:
            pass
        self.ws.missing_tabs.add(tab.id)
        self.revive_active_tab()

    async def _restart_agents(self, project: Project, task: Task) -> None:
        for tab in list(task.windows):
            if tab.kind != "agent":
                continue
            try:
                win = self.ws.window_ids.get(tab.id)
                if win:
                    await asyncio.to_thread(self.ws.tmux.kill_window, win)
                self.ws.missing_tabs.add(tab.id)
                await asyncio.to_thread(self.ws.revive_tab, tab)
            except Exception:
                continue
        self.refresh_all()
        self.notify("agent terminals restarted")

    # -- misc actions --------------------------------------------------
    def action_redraw(self) -> None:
        try:
            cfg = load_config(self.cfg.config_file)
        except Exception as exc:
            self.notify(f"config reload failed: {exc}", severity="error")
            return
        if cfg.tmux_socket != self.ws.tmux.socket:
            self.notify("socket changed in config; restart balamba to use it", severity="warning")
        self.cfg = cfg
        self.ws.config = cfg
        self.ws.tmux.config = cfg
        if self.ws.tmux.server_running():
            self.ws.tmux.mirror_options()
        self.apply_widths()
        self.refresh_all()
        if self.terminal:
            self.terminal._apply_size()
        self.notify(f"redrawn · {config_summary(cfg)}")

    def action_about(self) -> None:
        try:
            body = about_body(self.ws)
        except Exception as exc:
            body = Text(f"could not build about screen: {exc}")
        self.push_screen(InfoScreen(f" ABOUT   balamba {__version__}", body))

    def action_help(self) -> None:
        self.push_screen(InfoScreen(" HELP   keys, mouse and focus", help_body(self.ws)))

    def action_doctor(self) -> None:
        lines = [Text(SIGN_OFF, style="bold #e6edf3"), Text("")]
        try:
            for label, ok, detail in self.ws.doctor_lines():
                line = Text()
                line.append("✓ " if ok else "✗ ", style="#3fb950" if ok else "#f85149")
                line.append(f"{label:<10}", style="#58a6ff")
                line.append(str(detail), style="#8b949e")
                lines.append(line)
        except Exception as exc:
            lines.append(Text(str(exc), style="#f85149"))
        lines.append(Text(""))
        lines.append(Text(f"state   {self.cfg.state_file}", style="#6e7681"))
        lines.append(Text(f"config  {self.cfg.config_file}", style="#6e7681"))
        try:
            socket_text = self.ws.tmux.socket_path()
        except Exception as exc:
            socket_text = f"unavailable: {exc}"
        lines.append(Text(f"tmp     {socket_text}", style="#6e7681"))
        body = Text()
        for i, line in enumerate(lines):
            if i:
                body.append("\n")
            body.append_text(line)
        self.push_screen(InfoScreen(" DOCTOR   workspace health", body))

    def welcome_action(self, action: str) -> None:
        if action == "add-project":
            self.action_add_project()
        elif action == "new-task":
            self.action_new_task()
        elif action == "new-terminal":
            self.action_new_terminal()
        elif action == "about":
            self.action_about()
        elif action == "help":
            self.action_help()
        elif action == "doctor":
            self.action_doctor()
        elif action == "revive":
            self.revive_active_tab()
        elif action == "close-tab":
            self.action_close_tab()

    def action_detach(self) -> None:
        if not self.ws.startup_error:
            try:
                if self.ws.tmux.server_running():
                    self.ws.capture_metadata(save=False)
                self.ws.save()
            except Exception:
                pass
        self.exit(message=f"{SIGN_OFF}\ntmux server -L {self.cfg.tmux_socket} left running")

    def action_quit(self) -> None:
        self.action_detach()

    def on_unmount(self) -> None:
        if self.ws.startup_error:
            return
        try:
            self.ws.capture_metadata(save=False)
            self.ws.save()
        except Exception:
            pass


def run_app() -> None:
    from .workspace import make_workspace

    ws = make_workspace()
    BalambaApp(ws).run()
