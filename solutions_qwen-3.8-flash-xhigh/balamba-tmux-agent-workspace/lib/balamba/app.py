"""app.py — the BalambaApp: layout, bindings, mouse, timers, reconciliation,
restore, status bar, and every dialog flow.

100% Textual: the chrome never touches tmux, and mouse behaviour (clicks,
wheel) is pure Textual events. Terminal content is hosted by plain PTY
sessions rendered through the embedded VT emulator (README.md).
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

from rich.style import Style
from rich.text import Text
from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Static

from . import SIGNOFF_LINE, common, dialogs, gitops, task as task_mod
from .panes import GitPane, StatusBar, TreePane
from .term import PtySession
from .twidget import TerminalWidget
from .vt import VT

QUICK_EXIT_SECONDS = 3.0

SELECTED_STYLE = Style(reverse=True)
DIM_STYLE = Style(dim=True)
BOLD_STYLE = Style(bold=True)
DOT_STYLE = Style(color="#ffb000")
DEAD_STYLE = Style(color="#ff5555", bold=True)
OK_STYLE = Style(color="#5fd75f")
WARN_STYLE = Style(color="#ffb000")

GLYPH_PROJECT_OPEN, GLYPH_PROJECT_SHUT = "▾", "▸"
GLYPH_AGENT, GLYPH_SHELL = "◈", "◇"


@dataclass
class TabRun:
    """Runtime state for one terminal tab (the spec's window/terminal)."""
    uid: str
    term: dict                       # state.json record for this tab
    vt: VT
    widget: Optional[TerminalWidget] = None
    session: Optional[PtySession] = None
    unread: bool = False
    dead: Optional[int] = None       # exit code of a *quick* (unexpected) death
    spawned_at: float = 0.0
    context: tuple = ()
    index_in_ctx: int = 0


@dataclass
class TreeRow:
    kind: str                        # project|task|terminal|scratchterm
    pi: int
    ti: Optional[int]
    wi: Optional[int]
    label: str
    has_chevron: bool = False
    expanded: bool = False
    dot: bool = False
    dead: bool = False
    active_ctx: bool = False
    icon: str = GLYPH_SHELL
    uid: Optional[str] = None
    path: str = ""


@dataclass
class GitInfo:
    path: str = ""
    ok: bool = False
    branch: str = ""
    detached: bool = False
    files: list = field(default_factory=list)
    ab: Optional[tuple] = None
    ab_ref: str = ""
    error: str = ""


class ContentStack(Container):
    """Middle column: hosts all terminal widgets; only the active tab is
    visible, but every session keeps running (like non-focused tmux panes)."""

    DEFAULT_CSS = """
    ContentStack {
        width: 1fr;
        height: 1fr;
    }
    ContentStack > TerminalWidget {
        position: absolute;
        width: 100%;
        height: 100%;
    }
    #placeholder {
        width: 1fr;
        height: 1fr;
        content-align: center middle;
        color: #8888aa;
        background: #101014;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("no terminals in this context — press t to start one",
                     id="placeholder")


class BalambaApp(App[None]):
    TITLE = "balamba"
    ENABLE_COMMAND_PALETTE = False
    CSS = """
    Screen { background: #0c0c12; }
    #cols { width: 1fr; height: 1fr; }
    """

    BINDINGS = [
        # prefix — like tmux's C-a; see config BALAMBA_PREFIX (README)
        Binding("ctrl+a", "prefix", "Prefix", show=False),
        # override Textual's own priority ctrl+q: forward it to the hosted
        # terminal when the terminal has focus, otherwise quit-and-save.
        Binding("ctrl+q", "ctrl_q", "Quit", show=False),
    ]

    def __init__(self, cfg: common.Config, state: dict, *,
                 hold_lock: Optional[int] = None) -> None:
        super().__init__()
        self.cfg = cfg
        self.state = state
        self._hold_lock = hold_lock
        self.prefix_key = cfg.prefix
        self.runs: dict[str, TabRun] = {}
        self.rows: list[TreeRow] = []
        self.cursor = 0
        self.ctx_pi = 0
        self.ctx_ti: Optional[int] = None      # None == project/scratch context
        self._prefix_pending = False
        self.select_mode = False
        self.git = GitInfo()
        self.git_cursor = 0
        self._tab_rects: list[tuple[int, int, int]] = []

    # ------------------------------------------------------------------ layout
    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal(id="cols"):
                yield TreePane(id="tree")
                yield ContentStack(id="content")
                yield GitPane(id="git")
            yield StatusBar(id="status")

    async def on_mount(self) -> None:
        if self.prefix_key != "ctrl+a":
            self.bind(self.prefix_key, "prefix", show=False)
        self._apply_widths()
        self._restore_ctx()
        self._build_runs()
        self.rebuild_rows()
        self._sync_content_visibility(focus=True)
        self._start_git_refresh()
        self.refresh_chrome()
        self.set_interval(2.0, self._tick)
        self.set_interval(0.5, self._pump)
        if self._projects():
            # spec: empty context gets one shell tab on first activation —
            # booting into a context counts as activating it
            self.set_ctx(self.ctx_pi, self.ctx_ti, create_if_empty=True)
        self.restore_work()
        self.notify(SIGNOFF_LINE,
                    title=f"balamba · tree {self.cfg.tree_width} · git {self.cfg.git_width}",
                    timeout=6)

    @work(exclusive=True)
    async def restore_work(self) -> None:
        """Rebuild all sessions from state — the spec's restore path.

        Agents are relaunched `opencode --session ses_…` in the saved cwd,
        staggered ~0.8 s apart (spec: 0.5–1 s; each TUI costs seconds)."""
        active = self._active_uid()
        ordered = sorted(self.runs.values(),
                         key=lambda r: (0 if r.uid == active else 1,))
        for i, run in enumerate(ordered):
            if run.session is not None or run.dead is not None:
                continue
            if i:
                await asyncio.sleep(0.8)
            self._launch(run, resume=True)
        self.refresh_chrome()

    # ------------------------------------------------------------------ widths
    def _apply_widths(self) -> None:
        try:
            self.query_one("#tree", TreePane).styles.width = self.cfg.tree_width
            self.query_one("#git", GitPane).styles.width = self.cfg.git_width
        except Exception:
            pass

    # ------------------------------------------------------------------ context helpers
    def _projects(self) -> list[dict]:
        return self.state.get("projects", [])

    def project(self, pi: int) -> dict:
        return self._projects()[pi]

    def ctx_task(self) -> Optional[dict]:
        projects = self._projects()
        if not projects or self.ctx_pi >= len(projects):
            return None
        proj = projects[self.ctx_pi]
        if self.ctx_ti is None:
            return None
        if self.ctx_ti >= len(proj["tasks"]):
            return None
        return proj["tasks"][self.ctx_ti]

    def ctx_terms(self) -> list[dict]:
        t = self.ctx_task()
        if t is not None:
            return t["windows"]
        projects = self._projects()
        if projects and self.ctx_pi < len(projects):
            return projects[self.ctx_pi].get("scratch", [])
        return []

    def ctx_path(self) -> str:
        t = self.ctx_task()
        if t is not None:
            return t["path"]
        projects = self._projects()
        if projects and self.ctx_pi < len(projects):
            return projects[self.ctx_pi]["path"]
        return ""

    def ctx_label(self) -> str:
        projects = self._projects()
        if not projects or self.ctx_pi >= len(projects):
            return "no projects — p to add"
        proj = projects[self.ctx_pi]
        base = os.path.basename(proj["path"].rstrip("/"))
        t = self.ctx_task()
        return f"{base}/{t['slug']}" if t else base

    def ctx_active_index(self) -> int:
        terms = self.ctx_terms()
        if not terms:
            return 0
        holder = self.ctx_task()
        if holder is None:
            projects = self._projects()
            holder = projects[self.ctx_pi] if projects else {}
        key = "active_window" if self.ctx_task() else "active_scratch"
        idx = int(holder.get(key, 0) or 0)
        return max(0, min(idx, len(terms) - 1))

    def _active_uid(self) -> Optional[str]:
        terms = self.ctx_terms()
        idx = self.ctx_active_index()
        if 0 <= idx < len(terms):
            return terms[idx].get("uid")
        return None

    def _restore_ctx(self) -> None:
        ui = self.state.get("balamba_ui", {})
        self.ctx_pi = min(int(ui.get("ctx_project", 0) or 0),
                          max(0, len(self._projects()) - 1))
        ti = ui.get("ctx_task")
        self.ctx_ti = int(ti) if ti is not None else None
        projects = self._projects()
        if projects and self.ctx_ti is not None:
            if self.ctx_ti >= len(projects[self.ctx_pi]["tasks"]):
                self.ctx_ti = None

    def _save(self) -> None:
        self.state["balamba_ui"] = {"ctx_project": self.ctx_pi,
                                    "ctx_task": self.ctx_ti}
        self._capture_cwds()
        common.save_state(self.state)

    def _capture_cwds(self) -> None:
        for run in self.runs.values():
            s = run.session
            if s and s.alive():
                cwd = s.live_cwd()
                if cwd:
                    run.term["cwd"] = cwd

    # ------------------------------------------------------------------ runs
    def _build_runs(self) -> None:
        content = self.query_one("#content", ContentStack)
        widgets = []
        for pi, proj in enumerate(self._projects()):
            groups: list[tuple[Optional[int], list[dict]]] = [
                (None, proj.get("scratch", []))]
            for ti, t in enumerate(proj["tasks"]):
                groups.append((ti, t["windows"]))
            for context, terms in groups:
                for wi, term in enumerate(terms):
                    term.setdefault("uid", common.new_uid())
                    run = self._make_run(term, context, wi)
                    widgets.append(run.widget)
        if widgets:
            content.mount(*widgets)

    def _make_run(self, term: dict, context: tuple, wi: int) -> TabRun:
        uid = term["uid"]
        if uid in self.runs:
            run = self.runs[uid]
            run.term, run.context, run.index_in_ctx = term, context, wi
            return run
        vt = VT(24, 80)
        run = TabRun(uid=uid, term=term, vt=vt, context=context, index_in_ctx=wi)
        run.widget = TerminalWidget(
            vt=vt,
            title=common.tab_label(term),
            on_activity=lambda: self._mark_unread(run),
            is_viewed=lambda: self._run_viewed(run),
            allow_mouse_capture=lambda: not self.select_mode,
            on_exit=lambda code: self._handle_exit(run, code),
        )
        self.runs[uid] = run
        return run

    def _run_viewed(self, run: TabRun) -> bool:
        on_main = not isinstance(self.screen, ModalScreen)
        return (on_main
                and self._active_uid() == run.uid
                and run.context == (self.ctx_pi, self.ctx_ti)
                and self.focused is run.widget)

    def _mark_unread(self, run: TabRun) -> None:
        if not run.unread:
            run.unread = True
            self.refresh_chrome()

    def _launch(self, run: TabRun, *, resume: bool = False) -> None:
        term = run.term
        if run.session is not None and run.session.alive():
            return
        cmd = task_mod.terminal_spec(self.cfg, term, resume=resume)
        if cmd is None:
            agent = term.get("agent", "?")
            run.widget.feed_note(f"balamba: unknown agent '{agent}' — "
                                 f"check BALAMBA_AGENT_{agent}_COMMAND in config")
            run.dead = 127
            self.notify(f"unknown agent '{agent}'", severity="error")
            return
        cwd = term.get("cwd") or self._context_path(run.context) or os.getcwd()
        cols = max(20, run.widget.size.width or 80)
        rows = max(6, run.widget.size.height or 24)
        session = PtySession(cmd, cwd=cwd, cols=cols, rows=rows)
        run.dead = None
        run.spawned_at = time.time()
        run.session = session
        # wire callbacks BEFORE spawn: the reader thread can deliver the
        # first chunk the instant Popen returns, and unwired output is lost.
        run.widget.wire_session(session)
        try:
            session.spawn()
        except OSError as exc:
            run.dead = 127
            run.widget.feed_note(f"balamba: spawn failed: {exc}")
            run.session = None
            return
        if os.environ.get("BALAMBA_DEBUG"):
            print(f"[launch] uid={run.uid} cmd={cmd[:80]} cwd={cwd} "
                  f"resume={resume} alive={session.alive()}", file=sys.stderr)

    def _context_path(self, context: tuple) -> str:
        pi, ti = context
        projects = self._projects()
        if pi >= len(projects):
            return os.getcwd()
        if ti is None:
            return projects[pi]["path"]
        if ti < len(projects[pi]["tasks"]):
            return projects[pi]["tasks"][ti]["path"]
        return projects[pi]["path"]

    def _handle_exit(self, run: TabRun, code: int) -> None:
        elapsed = time.time() - run.spawned_at
        if elapsed < QUICK_EXIT_SECONDS:
            run.dead = code
            self.notify(f"{common.tab_label(run.term)} exited quickly "
                        f"(code {code}) — right-click → restart",
                        severity="warning", timeout=8)
        else:
            self._remove_tab(run)
            return
        self.refresh_chrome()

    # ------------------------------------------------------------------ content sync
    def _sync_content_visibility(self, *, focus: bool = False) -> None:
        active = self._active_uid()
        for run in self.runs.values():
            if run.widget is None:
                continue
            run.widget.visible = (run.uid == active)
            if run.uid == active:
                run.unread = False
        try:
            ph = self.query_one("#placeholder", Static)
            ph.visible = active is None
        except Exception:
            pass
        if focus:
            w = self.runs[active].widget if (active and active in self.runs) else None
            if w is not None and w.visible:
                w.focus()
            else:
                try:
                    self.query_one("#tree", TreePane).focus()
                except Exception:
                    pass
        self.query_one("#status", StatusBar).refresh()

    def refresh_chrome(self) -> None:
        self.rebuild_rows()
        try:
            self.query_one("#tree", TreePane).refresh()
            self.query_one("#git", GitPane).refresh()
            self.query_one("#status", StatusBar).refresh()
        except Exception:
            pass

    # ------------------------------------------------------------------ tree rows
    def rebuild_rows(self) -> None:
        rows: list[TreeRow] = []
        for pi, proj in enumerate(self._projects()):
            name = os.path.basename(proj["path"].rstrip("/")) or proj["path"]
            missing = not os.path.isdir(proj["path"])
            is_ctx = (pi == self.ctx_pi and self.ctx_ti is None)
            child_dot = self._group_has_unread(proj.get("scratch", [])) or \
                any(self._group_has_unread(t["windows"]) for t in proj["tasks"])
            rows.append(TreeRow(
                kind="project", pi=pi, ti=None, wi=None,
                label=name + ("  ✗missing" if missing else ""),
                has_chevron=bool(proj["tasks"] or proj.get("scratch")),
                expanded=bool(proj.get("expanded")),
                dot=child_dot and not is_ctx, active_ctx=is_ctx,
                path=proj["path"]))
            if not proj.get("expanded"):
                continue
            for ti, t in enumerate(proj["tasks"]):
                t_ctx = (pi == self.ctx_pi and ti == self.ctx_ti)
                tabs = t["windows"]
                expanded = bool(t.get("expanded", t_ctx))
                rows.append(TreeRow(
                    kind="task", pi=pi, ti=ti, wi=None, label=t["name"],
                    has_chevron=bool(tabs), expanded=expanded,
                    dot=self._group_has_unread(tabs) and not t_ctx,
                    dead=self._group_has_dead(tabs) and not t_ctx,
                    active_ctx=t_ctx, path=t["path"]))
                if expanded:
                    for wi, w in enumerate(tabs):
                        rows.append(self._term_row("terminal", pi, ti, wi, w, 4))
            for wi, w in enumerate(proj.get("scratch", [])):
                rows.append(self._term_row("scratchterm", pi, None, wi, w, 2))
        self.rows = rows
        self.cursor = max(0, min(self.cursor, max(0, len(rows) - 1)))

    def _group_has_unread(self, terms: list[dict]) -> bool:
        return any(r.unread for w in terms if (r := self.runs.get(w.get("uid", ""))))

    def _group_has_dead(self, terms: list[dict]) -> bool:
        return any(r.dead is not None for w in terms
                   if (r := self.runs.get(w.get("uid", ""))))

    def _term_row(self, kind: str, pi: int, ti: Optional[int], wi: int,
                  w: dict, indent: int) -> TreeRow:
        run = self.runs.get(w.get("uid", ""))
        is_agent = w.get("kind") == "agent"
        active = (pi == self.ctx_pi and ti == self.ctx_ti
                  and wi == self.ctx_active_index())
        return TreeRow(
            kind=kind, pi=pi, ti=ti, wi=wi,
            label=common.tab_label(w),
            dot=bool(run and run.unread and not active),
            dead=bool(run and run.dead is not None),
            active_ctx=active,
            icon=GLYPH_AGENT if is_agent else GLYPH_SHELL,
            uid=w.get("uid"),
            path=w.get("cwd", ""),
        )

    def tree_lines(self) -> list[Text]:
        lines: list[Text] = []
        for i, row in enumerate(self.rows):
            txt = Text(justify="left", end="")
            if row.kind == "project":
                txt.append((GLYPH_PROJECT_OPEN if row.expanded
                            else GLYPH_PROJECT_SHUT) + " ")
            elif row.kind == "task":
                txt.append("  " + (GLYPH_PROJECT_OPEN if row.expanded
                                   else GLYPH_PROJECT_SHUT) + " ")
            elif row.kind == "terminal":
                txt.append("    " + row.icon + " ")
            else:
                txt.append("  " + row.icon + " ")
            base = BOLD_STYLE if row.active_ctx else Style()
            txt.append(row.label, DEAD_STYLE if row.dead else base)
            if row.dot:
                txt.append(" ●", DOT_STYLE)
            if i == self.cursor:
                txt.stylize(SELECTED_STYLE, 0, len(txt.plain))
            lines.append(txt)
        return lines

    def _ensure_cursor_visible(self) -> None:
        pane = self.query_one("#tree", TreePane)
        rows = pane.visible_rows()
        if self.cursor < pane.view_top:
            pane.view_top = self.cursor
        elif self.cursor >= pane.view_top + rows:
            pane.view_top = self.cursor - rows + 1
        pane.refresh()

    # ------------------------------------------------------------------ tree keys
    def tree_key(self, name: str) -> bool:
        if not self.rows:
            return name in ("n", "p") or self._empty_tree_key(name)
        last = len(self.rows) - 1
        if name in ("j", "down"):
            self.cursor = min(last, self.cursor + 1)
        elif name in ("k", "up"):
            self.cursor = max(0, self.cursor - 1)
        elif name in ("g", "home"):
            self.cursor = 0
        elif name in ("G", "end"):
            self.cursor = last
        elif name == "pageup":
            self.cursor = max(0, self.cursor - self._pane_height())
        elif name == "pagedown":
            self.cursor = min(last, self.cursor + self._pane_height())
        elif name == "h":
            self._collapse_or_parent()
        elif name == "l":
            self._expand_or_child()
        elif name == "enter":
            self.activate_row(self.rows[self.cursor])
        elif name == "n":
            self.flow_new_task()
        elif name == "t":
            self.flow_new_terminal()
        elif name == "d":
            self.flow_delete_under_cursor()
        elif name == "e":
            self.flow_editor()
        elif name == "p":
            self.flow_add_project()
        else:
            return False
        self._ensure_cursor_visible()
        self.refresh_chrome()
        return True

    def _empty_tree_key(self, name: str) -> bool:
        if name == "p":
            self.flow_add_project()
            return True
        if name == "n":
            self.flow_new_task()
            return True
        return False

    def _pane_height(self) -> int:
        try:
            return self.query_one("#tree", TreePane).visible_rows()
        except Exception:
            return 10

    def _collapse_or_parent(self) -> None:
        row = self.rows[self.cursor]
        if row.has_chevron and row.expanded:
            row.expanded = False
            self._store_expand(row, False)
        elif row.kind in ("terminal", "scratchterm"):
            idx = self._parent_row_index(self.cursor)
            if idx is not None:
                self.cursor = idx
        elif row.kind == "task":
            self.cursor = self._project_row_index(row.pi)

    def _expand_or_child(self) -> None:
        row = self.rows[self.cursor]
        if row.has_chevron and not row.expanded:
            row.expanded = True
            self._store_expand(row, True)

    def _store_expand(self, row: TreeRow, expanded: bool) -> None:
        proj = self.project(row.pi)
        if row.kind == "project":
            proj["expanded"] = expanded
        elif row.kind == "task":
            proj["tasks"][row.ti]["expanded"] = expanded
        self._save()

    def _parent_row_index(self, idx: int) -> Optional[int]:
        r = self.rows[idx]
        for i in range(idx - 1, -1, -1):
            c = self.rows[i]
            if r.kind == "terminal" and c.kind == "task" and c.pi == r.pi \
                    and c.ti == r.ti:
                return i
            if r.kind == "scratchterm" and c.kind == "project" and c.pi == r.pi:
                return i
        return None

    def _project_row_index(self, pi: int) -> int:
        for i, r in enumerate(self.rows):
            if r.kind == "project" and r.pi == pi:
                return i
        return 0

    # ------------------------------------------------------------------ tree mouse
    def tree_click_select(self, idx: int, *, activate: bool) -> None:
        if idx >= len(self.rows):
            return
        self.cursor = idx
        if activate:
            self.activate_row(self.rows[idx])
        self.refresh_chrome()

    def tree_click_chevron(self, idx: int) -> None:
        if idx >= len(self.rows):
            return
        row = self.rows[idx]
        self.cursor = idx
        if row.has_chevron:
            row.expanded = not row.expanded
            self._store_expand(row, row.expanded)
        self.refresh_chrome()

    def tree_right_click(self, idx: int, x: int, y: int) -> None:
        if idx >= len(self.rows):
            return
        self.cursor = idx
        self.refresh_chrome()
        row = self.rows[idx]
        if row.kind == "project":
            choices = [
                ("activate", "activate"),
                ("new-task", "new task (n)"),
                ("new-scratch", "new scratch terminal (t)"),
                ("editor", "open in editor (e)"),
                ("remove-project", "remove from balamba (d)"),
                ("copy-path", "copy path"),
            ]
        elif row.kind == "task":
            choices = [
                ("activate", "activate"),
                ("new-terminal", "new terminal (t)"),
                ("close-task", "close task (d)"),
                ("editor", "open in editor (e)"),
                ("copy-path", "copy path"),
            ]
        else:
            choices = [
                ("activate", "activate tab"),
                ("restart", "restart terminal"),
                ("close-terminal", "close terminal"),
                ("copy-path", "copy path"),
            ]

        def done(result):
            if result and result[0]:
                self.menu_action(result[1], row)

        self.push_screen(dialogs.ChoiceScreen(row.label, choices,
                                              anchor=(x, y)), done)

    def menu_action(self, action: str, row: TreeRow) -> None:
        if action == "activate":
            self.activate_row(row)
        elif action == "new-task":
            self.flow_new_task(prefer_pi=row.pi)
        elif action == "new-scratch":
            self.flow_new_terminal(scratch=True, pi=row.pi)
        elif action == "new-terminal":
            self.flow_new_terminal(prefer=(row.pi, row.ti))
        elif action == "close-task":
            self.flow_close_task(row.pi, row.ti)
        elif action == "remove-project":
            self.flow_remove_project(row.pi)
        elif action == "editor":
            path = row.path or self.ctx_path()
            self.flow_editor(path=path)
        elif action == "restart":
            self.restart_terminal(row.uid)
        elif action == "close-terminal":
            self.close_terminal(row.uid)
        elif action == "copy-path":
            path = row.path or ""
            self.notify(path, title="path — enable select mode (C-a [) or "
                        "use your terminal's Shift+drag to copy", timeout=8)

    # ------------------------------------------------------------------ activation
    def activate_row(self, row: TreeRow) -> None:
        if row.kind == "project":
            self.set_ctx(row.pi, None)
        elif row.kind == "task":
            self.set_ctx(row.pi, row.ti)
        elif row.kind in ("terminal", "scratchterm"):
            self.set_ctx(row.pi, row.ti, tab=row.wi)

    def set_ctx(self, pi: int, ti: Optional[int], *, tab: Optional[int] = None,
                create_if_empty: bool = True) -> None:
        if pi >= len(self._projects()):
            return
        self._apply_widths()        # spec: sidebar widths reasserted on activation
        self.ctx_pi, self.ctx_ti = pi, ti
        proj = self.project(pi)
        proj["expanded"] = True            # spec: active project is expanded
        if ti is not None and ti < len(proj["tasks"]):
            proj["tasks"][ti]["expanded"] = True
        terms = self.ctx_terms()
        if create_if_empty and ti is None and not terms:
            # spec: empty context (project with no scratch terminals yet)
            # gets one shell tab on first activation
            self.add_terminal(pi, None,
                              task_mod.make_shell_terminal(proj["path"]),
                              activate=True, launch_now=True)
            return
        if tab is not None and terms:
            holder = self.ctx_task() or proj
            key = "active_window" if self.ctx_task() else "active_scratch"
            holder[key] = max(0, min(tab, len(terms) - 1))
            self._save()
        uid = self._active_uid()
        if uid and uid in self.runs:
            run = self.runs[uid]
            if run.session is None and run.dead is None:
                self._launch(run, resume=True)
        self._repoint_run_contexts()
        self._sync_content_visibility(focus=True)
        self._start_git_refresh()
        self.refresh_chrome()

    def _repoint_run_contexts(self) -> None:
        for pi, proj in enumerate(self._projects()):
            for wi, w in enumerate(proj.get("scratch", [])):
                run = self.runs.get(w.get("uid", ""))
                if run:
                    run.context, run.index_in_ctx = (pi, None), wi
            for ti, t in enumerate(proj["tasks"]):
                for wi, w in enumerate(t["windows"]):
                    run = self.runs.get(w.get("uid", ""))
                    if run:
                        run.context, run.index_in_ctx = (pi, ti), wi

    def activate_tab_index(self, idx: int) -> None:
        terms = self.ctx_terms()
        if 0 <= idx < len(terms):
            self.set_ctx(self.ctx_pi, self.ctx_ti, tab=idx)

    def cycle_tab(self, direction: int) -> None:
        terms = self.ctx_terms()
        if not terms:
            return
        idx = (self.ctx_active_index() + direction) % len(terms)
        self.activate_tab_index(idx)

    # ------------------------------------------------------------------ tabs
    def add_terminal(self, pi: int, ti: Optional[int], term: dict, *,
                     activate: bool, launch_now: bool) -> TabRun:
        proj = self.project(pi)
        lst = proj["tasks"][ti]["windows"] if ti is not None \
            else proj.setdefault("scratch", [])
        term.setdefault("uid", common.new_uid())
        lst.append(term)
        run = self._make_run(term, (pi, ti), len(lst) - 1)
        self._build_runs_missing()
        if activate:
            self.set_ctx(pi, ti, tab=len(lst) - 1)
        if launch_now:
            self._launch(run)
        self._save()
        self.refresh_chrome()
        return run

    def close_terminal(self, uid: Optional[str]) -> None:
        if uid:
            self._remove_tab(self.runs.get(uid))

    def _remove_tab(self, run: Optional[TabRun]) -> None:
        if run is None:
            return
        pi, ti = run.context
        if pi >= len(self._projects()):
            return
        proj = self.project(pi)
        lst = proj["tasks"][ti]["windows"] if ti is not None \
            else proj.get("scratch", [])
        for i, w in enumerate(lst):
            if w.get("uid") == run.uid:
                lst.pop(i)
                break
        if run.session:
            run.session.kill(grace=0.1)
        if run.widget:
            run.widget.remove()
        self.runs.pop(run.uid, None)
        terms = self.ctx_terms()
        if terms:
            holder = self.ctx_task() or proj
            key = "active_window" if self.ctx_task() else "active_scratch"
            holder[key] = max(0, min(run.index_in_ctx, len(terms) - 1))
        self._repoint_run_contexts()
        self._sync_content_visibility(focus=True)
        self._save()
        self.refresh_chrome()

    def restart_terminal(self, uid: Optional[str]) -> None:
        if not uid or uid not in self.runs:
            return
        run = self.runs[uid]
        if run.session:
            run.session.kill(grace=0.1)
            run.session = None
        if run.widget:
            run.widget.session = None
            run.widget.history_back = 0
        run.vt = VT(run.vt.rows, run.vt.cols)
        run.widget.vt = run.vt
        run.dead = None
        resume = run.term.get("kind") == "agent"
        self._launch(run, resume=resume)
        self._sync_content_visibility()
        self.refresh_chrome()

    # ------------------------------------------------------------------ new task
    def flow_new_task(self, prefer_pi: Optional[int] = None) -> None:
        projects = self._projects()
        if not projects:
            self.flow_add_project()
            return
        pi = (prefer_pi if prefer_pi is not None and prefer_pi < len(projects)
              else self.ctx_pi)
        proj = projects[pi]
        # spec order: (a) task name → (b) slug → (c) create from → (d) kind
        self.push_screen(
            dialogs.PromptScreen("task name:",
                                 placeholder="free text; stored as-is for display",
                                 validate=lambda v: (bool(v.strip()),
                                                     "name is required")),
            lambda r: self._after_name(r, proj))

    def _after_name(self, result, proj: dict) -> None:
        if not result or not result[0]:
            return
        name = result[1]
        slug_default = common.make_slug(name)
        screen = dialogs.PromptScreen(
            "slug:", value=slug_default,
            placeholder="folder + branch name",
            validate=lambda v: self._validate_slug(proj, v))
        self.push_screen(screen, lambda r: self._after_slug(r, name, proj))

    def _after_slug(self, result, name: str, proj: dict) -> None:
        if not result or not result[0]:
            return
        slug = result[1]

        def on_base(r):
            if not r or not r[0]:
                return
            base = r[1]
            self.push_screen(
                dialogs.ChoiceScreen("terminal:", self._kind_choices()),
                lambda k: self._task_kind_chosen(k, name, slug, base, proj))

        self.push_screen(
            dialogs.PromptScreen(
                "create from:", value=task_mod.DEFAULT_BASE,
                placeholder="any ref git rev-parse --verify accepts",
                validate=lambda v: (True, "")
                if gitops.ref_exists(proj["path"], v)
                else (False, f"not a valid ref: {v}")),
            on_base)

    def _default_agent(self) -> str:
        agents = self.cfg.agents or []
        if self.cfg.agent_default in agents:
            return self.cfg.agent_default
        return agents[0] if agents else self.cfg.agent_default

    def _task_kind_chosen(self, result, name, slug, base, proj) -> None:
        if not result or not result[0]:
            return
        kind = result[1]
        agents = self.cfg.agents or []
        if kind == "agent" and len(agents) > 1:
            self.push_screen(
                dialogs.ChoiceScreen("agent:", [(a, a) for a in agents]),
                lambda r: self._task_finish(r, name, slug, base, proj, "agent"))
        else:
            self._task_finish((True, self._default_agent()), name, slug, base,
                              proj, kind)

    def _task_finish(self, result, name, slug, base, proj, kind) -> None:
        if not result or not result[0]:
            return
        if kind == "agent":
            agent = result[1] if isinstance(result[1], str) and result[1] \
                in self.cfg.agents else self._default_agent()
            term = {"kind": "agent", "agent": agent,
                    "session": common.new_agent_session_id()}
        else:
            term = {"kind": "shell"}
        try:
            created = task_mod.create_task(self.state, proj["path"], name,
                                           slug, base, term)
        except RuntimeError as exc:
            self.notify(f"task failed: {exc}", severity="error", timeout=12)
            return
        self._build_runs_missing()
        self._repoint_run_contexts()
        run = self.runs[created.task["windows"][0]["uid"]]
        self._launch(run)
        self.set_ctx(created.project_index, created.task_index, tab=0)
        self.refresh_chrome()
        self.notify(f"created task {created.task['slug']} from {base} "
                    "(branch has no upstream — --no-track)")

    def _build_runs_missing(self) -> None:
        content = self.query_one("#content", ContentStack)
        mounted = set(content.query(TerminalWidget))
        for pi, proj in enumerate(self._projects()):
            groups: list[tuple[Optional[int], list[dict]]] = [
                (None, proj.get("scratch", []))]
            for ti, t in enumerate(proj["tasks"]):
                groups.append((ti, t["windows"]))
            for context, terms in groups:
                for wi, w in enumerate(terms):
                    w.setdefault("uid", common.new_uid())
                    run = self._make_run(w, context, wi)
                    if run.widget is not None and run.widget not in mounted:
                        content.mount(run.widget)

    def _validate_slug(self, proj: dict, v: str) -> tuple[bool, str]:
        if not v:
            return False, "empty slug"
        if not gitops.check_branch_name(proj["path"], v):
            return False, "invalid branch name (git check-ref-format --branch)"
        return True, ""

    def _kind_choices(self) -> list[tuple[str, str]]:
        return [("agent", "agent — configured CLI (opencode)"),
                ("shell", "shell — fresh $SHELL in the worktree")]

    # ------------------------------------------------------------------ new terminal
    def flow_new_terminal(self, *, scratch: bool = False,
                          pi: Optional[int] = None,
                          prefer: Optional[tuple] = None) -> None:
        if not self._projects():
            self.notify("add a project first (p)", severity="warning")
            return
        if prefer is not None:
            pi, ti = prefer
        else:
            ti = None if scratch else self.ctx_ti
            pi = pi if pi is not None else self.ctx_pi
        cwd = self._context_path((pi, ti))
        self.push_screen(dialogs.ChoiceScreen("new terminal:",
                                              self._kind_choices()),
                         lambda r: self._new_term_kind(r, pi, ti, cwd))

    def _new_term_kind(self, result, pi: int, ti: Optional[int], cwd: str) -> None:
        if not result or not result[0]:
            return
        kind = result[1]
        if kind == "shell":
            self.add_terminal(pi, ti, task_mod.make_shell_terminal(cwd),
                              activate=True, launch_now=True)
            return
        agents = self.cfg.agents or []
        if len(agents) > 1:
            self.push_screen(dialogs.ChoiceScreen("agent:", [(a, a) for a in agents]),
                             lambda r: self._new_agent(r, pi, ti, cwd))
        else:
            self._new_agent((True, self._default_agent()), pi, ti, cwd)

    def _new_agent(self, result, pi: int, ti: Optional[int], cwd: str) -> None:
        if not result or not result[0]:
            return
        term = task_mod.make_agent_terminal(cwd, result[1],
                                            common.new_agent_session_id())
        self.add_terminal(pi, ti, term, activate=True, launch_now=True)

    # ------------------------------------------------------------------ projects
    def flow_add_project(self) -> None:
        def validate(v: str) -> tuple[bool, str]:
            path = os.path.realpath(os.path.expanduser(v))
            info = gitops.validate_main_checkout(path)
            if not info.ok:
                return False, info.warning
            for p in self._projects():
                if os.path.realpath(p["path"]) == path:
                    return False, "already added"
            if not info.is_main_checkout:
                self._pending_project_warning = info.warning
            return True, ""

        def done(result):
            if not result or not result[0]:
                return
            path = os.path.realpath(os.path.expanduser(result[1]))
            warn = getattr(self, "_pending_project_warning", "")
            self._pending_project_warning = ""
            self.state["projects"].append(
                {"path": path, "expanded": True, "scratch": [], "tasks": []})
            if warn:
                self.notify(warn, severity="warning", timeout=12)
            self._save()
            self._repoint_run_contexts()
            self.set_ctx(len(self._projects()) - 1, None)
            self.refresh_chrome()

        self._pending_project_warning = ""
        self.push_screen(dialogs.PromptScreen(
            "project path:", value="~/",
            placeholder="absolute path to a git main checkout",
            validate=validate), done)

    def flow_remove_project(self, pi: int) -> None:
        proj = self.project(pi)
        screen = dialogs.ConfirmScreen(
            "remove project from balamba",
            [Text(proj["path"]),
             Text("the folder on disk is NEVER touched", style=OK_STYLE),
             Text(f"{len(proj['tasks'])} task(s) and "
                  f"{len(proj.get('scratch', []))} scratch tab(s) will be "
                  "dropped from the tree; their sessions are killed")],
            continue_label="Remove")

        def done(result):
            if not result or not result.get("confirmed"):
                return
            for t in proj["tasks"]:
                self._kill_task_windows(t)
            for w in list(proj.get("scratch", [])):
                run = self.runs.get(w.get("uid"))
                if run:
                    if run.session:
                        run.session.kill(grace=0.1)
                    if run.widget:
                        run.widget.remove()
                    self.runs.pop(run.uid, None)
            self.state["projects"].pop(pi)
            self._clamp_ctx()
            self._repoint_run_contexts()
            self._save()
            self.refresh_chrome()
            if self._projects():
                self.set_ctx(self.ctx_pi, self.ctx_ti, create_if_empty=True)
            else:
                self._sync_content_visibility(focus=True)
            self.notify("project removed from balamba only")

        self.push_screen(screen, done)

    def _clamp_ctx(self) -> None:
        projects = self._projects()
        self.ctx_pi = max(0, min(self.ctx_pi, len(projects) - 1))
        if not projects:
            self.ctx_ti = None
            return
        tasks = projects[self.ctx_pi]["tasks"]
        if self.ctx_ti is not None and self.ctx_ti >= len(tasks):
            self.ctx_ti = len(tasks) - 1 if tasks else None

    # ------------------------------------------------------------------ close task
    def flow_delete_under_cursor(self) -> None:
        if not self.rows:
            return
        row = self.rows[self.cursor]
        if row.kind == "task":
            self.flow_close_task(row.pi, row.ti)
        elif row.kind in ("terminal", "scratchterm"):
            self.close_terminal(row.uid)
        elif row.kind == "project":
            self.flow_remove_project(row.pi)

    def flow_close_task(self, pi: int, ti: int) -> None:
        proj = self.project(pi)
        t = proj["tasks"][ti]
        assess = task_mod.assess_close(self.state, pi, ti)
        lines: list = [Text(f"task: {t['name']} · branch: {assess.branch}"),
                       Text(f"worktree: {t['path']}")]
        for w in assess.warnings:
            lines.append(Text(f"⚠ {w}", style=WARN_STYLE))
        if not assess.warnings:
            lines.append(Text("worktree is clean", style=OK_STYLE))
        first = dialogs.ConfirmScreen("close task — step 1 of 2", lines,
                                      continue_label="Continue")

        def step2(r):
            if not r or not r.get("confirmed"):
                return
            second = dialogs.ConfirmScreen(
                "close task — step 2 of 2: THE WORKTREE WILL BE DELETED",
                [Text(f"git worktree remove "
                      f"{'--force ' if assess.dirty else ''}{t['path']}"),
                 Text("branches are kept unless you tick the option; "
                      "git branch -d refuses unmerged branches",
                      style=DIM_STYLE),
                 Text("no commits, pushes, or merges are performed",
                      style=DIM_STYLE)],
                continue_label="Delete",
                toggle_label="delete branch too (git branch -d)",
                toggle_on=False)
            self.push_screen(second, step3)

        def step3(r):
            if not r or not r.get("confirmed"):
                return
            res = task_mod.close_task(
                self.state, pi, ti, delete_branch=bool(r.get("toggle")),
                kill_windows=self._kill_task_windows)
            for n in res.notes:
                self.notify(n, timeout=12)
            if not res.ok:
                self.notify("close aborted: " + "; ".join(res.notes),
                            severity="error", timeout=12)
            self._clamp_ctx()
            self._repoint_run_contexts()
            self._save()
            self.refresh_chrome()
            self.set_ctx(self.ctx_pi, self.ctx_ti, create_if_empty=False)

        self.push_screen(first, step2)

    def _kill_task_windows(self, task: dict) -> None:
        for w in task.get("windows", []):
            run = self.runs.get(w.get("uid"))
            if run:
                if run.session:
                    run.session.kill(grace=0.1)
                if run.widget:
                    run.widget.remove()
                self.runs.pop(run.uid, None)

    # ------------------------------------------------------------------ editor
    def flow_editor(self, *, path: Optional[str] = None,
                    pi: Optional[int] = None, ti: Optional[int] = -1) -> None:
        if path is None:
            path = self.ctx_path()
        if not path or not os.path.isdir(path):
            self.notify("no valid context folder to edit", severity="warning")
            return
        editor = self.cfg.editor or "echo balamba: no editor configured"
        vt = VT(30, 100)
        widget = TerminalWidget(
            vt=vt,
            is_viewed=lambda: True,
            allow_mouse_capture=lambda: False,
        )
        session = PtySession(editor, cwd=path, cols=100, rows=30)
        widget.session = session
        widget.wire_session(session)
        screen = dialogs.EditorScreen(widget)
        widget.on_exit_cb = lambda code: self._editor_exit(screen, session, code)
        try:
            session.spawn()
        except OSError as exc:
            self.notify(f"editor spawn failed: {exc}", severity="error")
            return
        self.push_screen(screen)

    def _editor_exit(self, screen, session, code: int) -> None:
        if session.alive():
            session.kill(grace=0.1)
        if self.screen is screen:
            self.pop_screen()
        else:
            # not (yet) topmost: EditorScreen.on_mount will close it
            screen._pending_close = True
        if code not in (0, None):
            self.notify(f"editor exited with code {code}", severity="warning")

    # ------------------------------------------------------------------ diff
    def flow_diff(self, entry: gitops.FileEntry) -> None:
        self._flow_diff(self.git.path, entry)

    @work(exclusive=False, group="diff")
    async def _flow_diff(self, path: str, entry: gitops.FileEntry) -> None:
        import asyncio
        text, how = await asyncio.to_thread(gitops.file_diff, path, entry)
        self.push_screen(dialogs.DiffScreen(f"diff · {how}", text))

    # ------------------------------------------------------------------ git pane
    def _start_git_refresh(self) -> None:
        try:
            self._refresh_git_worker()
        except Exception:
            pass

    def git_focus_refresh(self) -> None:
        self._start_git_refresh()

    @work(thread=True, exclusive=True, group="git")
    def _refresh_git_worker(self) -> None:
        path = self.ctx_path()
        info = GitInfo(path=path)
        if path and os.path.isdir(path) and gitops.is_git_repo(path):
            branch, detached = gitops.current_branch(path)
            info.branch, info.detached, info.ok = branch, detached, True
            info.files = gitops.status_files(path)
            up = gitops.upstream_of(path)
            if up:
                info.ab, info.ab_ref = gitops.ahead_behind(path, up), up
            else:
                base = (self.ctx_task() or {}).get("base")
                if base and gitops.ref_exists(path, base):
                    info.ab, info.ab_ref = gitops.ahead_behind(path, base), base
            # snapshot reads are fine; marshal UI update to the UI thread
            self.git = info
            self.call_from_thread(self._on_git_ready)

    def _on_git_ready(self) -> None:
        try:
            self.query_one("#git", GitPane).refresh()
            self.query_one("#status", StatusBar).refresh()
        except Exception:
            pass

    def git_lines(self) -> list[Text]:
        out: list[Text] = []
        head = Text(justify="left", end="")
        head.append("── git ", style=DIM_STYLE)
        head.append(self.git.branch or "(none)", style=BOLD_STYLE)
        if self.git.detached:
            head.append(" ⚠detached", style=WARN_STYLE)
        out.append(head)
        if self.git.ok:
            if self.git.ab is not None:
                line = Text(justify="left", end="")
                line.append(f"↑{self.git.ab[0]} ↓{self.git.ab[1]} ", style=OK_STYLE)
                line.append(f"vs {self.git.ab_ref}", style=DIM_STYLE)
                out.append(line)
            else:
                out.append(Text("no upstream / base ref", style=DIM_STYLE))
            out.append(Text(f"files: {len(self.git.files)}", style=DIM_STYLE))
            out.append(Text(""))
            for i, f in enumerate(self.git.files):
                line = Text(justify="left", end="")
                ms = (Style(color="#5fd75f") if f.staged
                      else Style(color="#ff5555") if f.untracked else WARN_STYLE)
                line.append(f"[{f.x}{f.y}] ", style=ms)
                shown = f.path
                if f.orig_path:
                    shown = (os.path.basename(f.orig_path) + "→"
                             + os.path.basename(f.path))
                line.append(shown if len(shown) <= 26 else shown[:25] + "…")
                if i == self.git_cursor:
                    line.stylize(SELECTED_STYLE, 0, len(line.plain))
                out.append(line)
            if not self.git.files:
                out.append(Text("(clean)", style=OK_STYLE))
        else:
            out.append(Text(self.git.error or "(no git context)", style=WARN_STYLE))
        return out

    def git_key(self, name: str) -> bool:
        n = len(self.git.files)
        if name in ("j", "down"):
            self.git_cursor = min(max(0, n - 1), self.git_cursor + 1)
        elif name in ("k", "up"):
            self.git_cursor = max(0, self.git_cursor - 1)
        elif name == "enter" and n:
            self.flow_diff(self.git.files[self.git_cursor])
            return True
        elif name in ("r",):
            self._start_git_refresh()
        else:
            return False
        return True

    def git_click_row(self, idx: int) -> None:
        files_start = 4 if self.git.ok else 2
        pos = idx - files_start
        if 0 <= pos < len(self.git.files):
            self.git_cursor = pos
            self.flow_diff(self.git.files[pos])

    # ------------------------------------------------------------------ status
    def status_text(self, width: int) -> Text:
        t = Text(justify="left", end="")
        t.append("balamba", style=BOLD_STYLE)
        t.append(" · " + self.ctx_label())
        if self._prefix_pending:
            t.append("  [C-a] ", style=SELECTED_STYLE)
        if self.select_mode:
            t.append("  [SEL] ", style=WARN_STYLE)
        terms = self.ctx_terms()
        self._tab_rects = []
        if terms:
            t.append("  ")
            for i, w in enumerate(terms):
                run = self.runs.get(w.get("uid", ""))
                mark = ""
                if run is not None and run.dead is not None:
                    mark = " ✗"
                elif run is not None and run.unread:
                    mark = " ●"
                seg = f"[{i + 1}:{common.tab_label(w)}{mark}]"
                x0 = len(t.plain)
                style = SELECTED_STYLE if i == self.ctx_active_index() else DIM_STYLE
                t.append(" " + seg, style=style)
                self._tab_rects.append((x0, x0 + len(seg) + 1, i))
        hint = "C-a? help"
        fill = max(1, width - len(t.plain) - len(hint) - 1)
        t.append(" " * fill)
        t.append(hint, style=DIM_STYLE)
        return t

    def status_tab_at(self, x: int) -> Optional[int]:
        for x0, x1, i in self._tab_rects:
            if x0 <= x <= x1:
                return i
        return None

    # ------------------------------------------------------------------ prefix
    def begin_prefix(self) -> None:
        if isinstance(self.screen, (dialogs.PromptScreen, dialogs.ChoiceScreen,
                                    dialogs.ConfirmScreen,
                                    dialogs.KeyHelpScreen)):
            return
        self._prefix_pending = True
        self.refresh_chrome()

    def action_prefix(self) -> None:
        self.begin_prefix()

    async def on_event(self, event: events.Event) -> None:
        if isinstance(event, events.Key) and self._prefix_pending:
            await self._resolve_prefix(event)
            return
        await super().on_event(event)

    async def _resolve_prefix(self, event: events.Key) -> None:
        self._prefix_pending = False
        key = event.key
        self.refresh_chrome()
        if key in ("N", "upper_n"):
            self.flow_new_task()
        elif key in ("P", "upper_p"):
            self.flow_add_project()
        elif key in ("T", "upper_t"):
            self.flow_new_terminal()
        elif key == "e":
            self.flow_editor()
        elif key == "d":
            self.action_quit_save()
        elif key == "r":
            self.action_redraw()
        elif key == "o":
            self.action_cycle_focus()
        elif key == "g":
            self._focus_git()
        elif key == "n":
            self.cycle_tab(1)
        elif key == "p":
            self.cycle_tab(-1)
        elif key in ("[", "left_square_bracket"):
            self.toggle_select_mode()
        elif key in ("?", "question_mark"):
            self.flow_keys()
        elif key == "escape":
            pass
        elif key.isdigit() and len(key) == 1:
            self.activate_tab_index((int(key) - 1) % 10)
        elif key == self.prefix_key:
            w = self.focused
            if isinstance(w, TerminalWidget) and w.session:
                w.session.write(b"\x01")   # C-a C-a → literal C-a to terminal
        # unknown: swallowed (like tmux)

    def action_ctrl_q(self) -> None:
        w = self.focused
        if isinstance(w, TerminalWidget) and w.session:
            w.session.write(b"\x11")
        else:
            self.action_quit_save()

    def toggle_select_mode(self) -> None:
        self.select_mode = not self.select_mode
        self.notify("select mode ON — clicks/wheel no longer reach the "
                    "terminal; drag to select text" if self.select_mode
                    else "select mode OFF")
        self.refresh_chrome()

    def action_cycle_focus(self) -> None:
        order: list[Widget] = [self.query_one("#tree", TreePane)]
        uid = self._active_uid()
        if uid and uid in self.runs and self.runs[uid].widget:
            order.append(self.runs[uid].widget)
        order.append(self.query_one("#git", GitPane))
        cur = self.focused
        idx = 0
        for i, w in enumerate(order):
            if w is cur:
                idx = (i + 1) % len(order)
                break
        order[idx].focus()

    def _focus_git(self) -> None:
        self.query_one("#git", GitPane).focus()

    def flow_keys(self) -> None:
        sections = [
            ("prefix (C-a — configurable via BALAMBA_PREFIX)", [
                ("C-a N / P / T", "new task / add project / new terminal"),
                ("C-a 1..9", "jump to tab N"),
                ("C-a n / p", "next / previous tab"),
                ("C-a e", f"editor in context ($EDITOR={self.cfg.editor})"),
                ("C-a d", "detach = save & quit (README note)"),
                ("C-a r", "redraw; reassert sidebar widths"),
                ("C-a o", "cycle focus tree → content → git"),
                ("C-a g", "focus the git pane"),
                ("C-a [", "toggle terminal text-select mode"),
                ("C-a C-a", "send a literal C-a to the terminal"),
                ("C-a ?", "this screen"),
            ]),
            ("tree pane (when focused, keys act without prefix)", [
                ("j / k / ↑ / ↓", "move selection"),
                ("h / l", "collapse / expand"),
                ("Enter", "activate row"),
                ("n / t / d / e / p", "task / terminal / close / editor / project"),
                ("click / chevron / right-click", "select / toggle / menu"),
                ("wheel", "in-app scroll"),
            ]),
            ("git pane (when focused)", [
                ("j / k", "choose file"),
                ("Enter / click file", "open diff popup (in-app pager)"),
                ("r", "refresh now (also every ~2 s)"),
            ]),
            ("terminal (content column)", [
                ("typing", "goes to the hosted PTY session"),
                ("wheel", "scrollback, or forwarded when the app captures mouse"),
                ("C-a [", "select mode: drag to select rendered text"),
            ]),
            ("about", [("", SIGNOFF_LINE)]),
        ]
        self.push_screen(dialogs.KeyHelpScreen(sections))

    def action_redraw(self) -> None:
        self._apply_widths()
        self._repoint_run_contexts()
        self.refresh_chrome()
        self.notify("redrawn; sidebar widths reasserted from config")

    # ------------------------------------------------------------------ timers
    def _pump(self) -> None:
        """Flush reader-thread handoffs the app was not ready for.

        (Lost data would otherwise wedge a terminal; this is the belt to the
        call_from_thread suspenders — README, "Activity & timing".)"""
        for run in list(self.runs.values()):
            if run.widget is not None:
                try:
                    run.widget._flush_pending()
                    run.widget._drain_exit()
                except Exception:
                    if os.environ.get("BALAMBA_DEBUG"):
                        import traceback
                        traceback.print_exc()

    def _tick(self) -> None:
        self._pump()
        changed = False
        for run in list(self.runs.values()):
            s = run.session
            if s and s.alive() and run.term.get("kind") == "shell":
                cwd = s.live_cwd()
                if cwd and cwd != run.term.get("cwd"):
                    run.term["cwd"] = cwd
                    changed = True
        if changed:
            self._save()
        self._start_git_refresh()
        self.refresh_chrome()

    # ------------------------------------------------------------------ quit
    def action_quit_save(self) -> None:
        self._save()
        self.exit()

    def on_unmount(self) -> None:
        try:
            self._save()
        except Exception:
            pass
        for run in list(self.runs.values()):
            if run.session:
                run.session.kill(grace=0.1)
        if self._hold_lock is not None:
            common.release_instance_lock(self._hold_lock)
            self._hold_lock = None
