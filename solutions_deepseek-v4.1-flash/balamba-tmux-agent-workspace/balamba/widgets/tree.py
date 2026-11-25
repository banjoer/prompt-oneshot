"""Tree pane: projects → tasks → terminals, rendered as a Textual widget.

Everything is a normal Textual widget event: clicks, right-clicks, wheel
scrolling and configurable key bindings.  No tmux panes, no tmux mouse.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rich.console import Group, RenderableType
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Container
from textual.widget import Widget
from textual.widgets import Static

from ..state import Project, Task, TerminalTab


@dataclass
class Row:
    key: str
    kind: str  # project | task | scratch | terminal | hint
    project: Project
    task: Task | None = None
    tab: TerminalTab | None = None
    depth: int = 0
    selectable: bool = True


def build_rows(ws) -> list[Row]:
    state = ws.state
    rows: list[Row] = []
    for project in state.projects:
        rows.append(Row(f"p:{project.path}", "project", project, depth=0))
        if not project.expanded:
            continue
        for tab in project.scratch:
            rows.append(Row(f"s:{tab.id}", "scratch", project, tab=tab, depth=1))
        for task in project.tasks:
            rows.append(Row(f"t:{project.path}:{task.slug}", "task", project, task=task, depth=1))
            if task.expanded:
                for tab in task.windows:
                    rows.append(
                        Row(f"x:{tab.id}", "terminal", project, task=task, tab=tab, depth=2)
                    )
        if not project.scratch and not project.tasks:
            rows.append(
                Row(f"h:{project.path}", "hint", project, depth=1, selectable=False)
            )
    return rows


def _clip(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width <= 1:
        return text[:width]
    return text[: width - 1] + "…"


class TreeView(Widget, can_focus=True):
    """Scrollable, mouse-aware tree viewport."""

    DEFAULT_CSS = """
    TreeView {
        height: 1fr;
        padding: 0;
        background: #0f141b;
        color: #c9d1d9;
        scrollbar-size: 1 1;
    }
    TreeView:focus {
        background: #101720;
    }
    """

    BINDINGS = [("tab", "app.focus_next", "focus")]

    def __init__(self, ws, **kwargs):
        super().__init__(**kwargs)
        self.ws = ws
        self.rows: list[Row] = []
        self.view_offset = 0
        self.hover_key = ""
        self._regions: list[tuple[int, int, int, Row]] = []  # y, x0, x1, row

    # -- data ---------------------------------------------------------
    def rebuild(self, keep_key: str = "") -> None:
        previous = keep_key or self.selected_key
        self.rows = build_rows(self.ws)
        if previous and not any(row.key == previous for row in self.rows):
            self.selected_key = self._default_key()
        self.ensure_visible()
        self.refresh()

    @property
    def selected_key(self) -> str:
        return getattr(self.parent, "selected_key", "") if self.parent else ""

    @selected_key.setter
    def selected_key(self, value: str) -> None:
        if self.parent is not None and hasattr(self.parent, "selected_key"):
            self.parent.selected_key = value

    def _default_key(self) -> str:
        return self.rows[0].key if self.rows else ""

    def selected_row(self) -> Row | None:
        return next((r for r in self.rows if r.key == self.selected_key), None)

    def select_first(self) -> None:
        for row in self.rows:
            if row.selectable:
                self.selected_key = row.key
                return
        if self.rows:
            self.selected_key = self.rows[0].key

    def select_active(self) -> None:
        state = self.ws.state
        if state.active_tab:
            candidate = f"x:{state.active_tab}" if state.active_task else f"s:{state.active_tab}"
            if any(row.key == candidate for row in self.rows):
                self.selected_key = candidate
                self.ensure_visible()
                return
        if state.active_task:
            candidate = f"t:{state.active_project}:{state.active_task}"
            if any(row.key == candidate for row in self.rows):
                self.selected_key = candidate
                return
        if state.active_project:
            candidate = f"p:{state.active_project}"
            if any(row.key == candidate for row in self.rows):
                self.selected_key = candidate

    def move(self, delta: int) -> None:
        selectable = [i for i, row in enumerate(self.rows) if row.selectable]
        if not selectable:
            return
        current = next(
            (i for i, row in enumerate(self.rows) if row.key == self.selected_key), -1
        )
        if current in selectable:
            pos = selectable.index(current)
            new_pos = max(0, min(len(selectable) - 1, pos + delta))
        else:
            new_pos = 0 if delta >= 0 else len(selectable) - 1
        self.selected_key = self.rows[selectable[new_pos]].key
        self.ensure_visible()
        self.refresh()
        if hasattr(self.parent, "update_footer"):
            self.parent.update_footer()
        self.post_message(TreeSelectionChanged(self.selected_row()))

    def ensure_visible(self) -> None:
        height = max(1, self.content_size.height)
        try:
            index = next(i for i, r in enumerate(self.rows) if r.key == self.selected_key)
        except StopIteration:
            index = 0
        if index < self.view_offset:
            self.view_offset = index
        elif index >= self.view_offset + height:
            self.view_offset = index - height + 1
        self.view_offset = max(0, min(self.view_offset, max(0, len(self.rows) - height)))

    # -- render -------------------------------------------------------
    def _row_text(self, row: Row, width: int) -> Text:
        from rich.cells import cell_len

        state = self.ws.state
        active_project = state.active_project
        active_task = state.active_task
        active_tab = state.active_tab
        unread = self.ws.unread
        selected = row.key == self.selected_key
        hover = row.key == self.hover_key
        base_style = "on #172232" if selected else ("on #131b25" if hover else "")
        text = Text(style=base_style)
        indent = " " + "  " * row.depth

        def suffix_join(base: Text, suffix: Text, *, min_gap: int = 1) -> Text:
            gap = max(min_gap, width - base.cell_len - suffix.cell_len)
            base.append(" " * gap, style=base_style)
            base.append_text(suffix)
            if base.cell_len > width:
                base.truncate(width)
            elif base.cell_len < width:
                base.append(" " * (width - base.cell_len), style=base_style)
            return base

        if row.kind == "project":
            is_active = row.project.path == active_project
            expanded = row.project.expanded
            name_style = "bold #e6edf3" if is_active else "#c9d1d9"
            counts = f"{len(row.project.tasks)}T"
            if row.project.scratch:
                counts += f" {len(row.project.scratch)}S"
            suffix = Text()
            suffix.append(counts, style="#6e7681")
            if self.ws.unread_project(row.project):
                suffix.append(" ●", style="bold #f0883e")
            elif is_active:
                suffix.append(" ◂", style="#58a6ff")
            prefix_width = cell_len(indent) + 4
            name_width = max(4, width - prefix_width - suffix.cell_len - 1)
            text.append(indent)
            text.append("▾ " if expanded else "▸ ", style="#58a6ff" if expanded else "#6e7681")
            text.append("▣ ", style="#58a6ff" if is_active else "#6e7681")
            text.append(_clip(row.project.name, name_width), style=name_style)
            return suffix_join(text, suffix)

        if row.kind == "hint":
            text.append(indent)
            text.append("no tasks yet · press ", style="italic #6e7681")
            text.append("n", style="bold #58a6ff")
            text.append(" to create one", style="italic #6e7681")
            text.truncate(width)
            text.append(" " * max(0, width - text.cell_len), style=base_style)
            return text

        if row.kind == "scratch":
            tab = row.tab
            assert tab is not None
            is_active = tab.id == active_tab
            suffix = Text()
            if len(tab.panes) > 1:
                suffix.append(f"{len(tab.panes)}p ", style="#6e7681")
            if unread.get(tab.id):
                suffix.append("●", style="bold #f0883e")
            elif is_active:
                suffix.append("◂", style="#58a6ff")
            text.append(indent)
            text.append("  ", style="")
            text.append("⌁ ", style="#39c5cf")
            label_width = max(4, width - cell_len(indent) - 4 - suffix.cell_len - 1)
            text.append(_clip(tab.name, label_width), style="bold #e6edf3" if is_active else "#a9b1ba")
            return suffix_join(text, suffix)

        if row.kind == "task":
            task = row.task
            assert task is not None
            is_active = task.slug == active_task and row.project.path == active_project
            expanded = task.expanded
            suffix = Text()
            if self.ws.unread_task(task):
                suffix.append(" ●", style="bold #f0883e")
            elif is_active:
                suffix.append(" ◂", style="#58a6ff")
            prefix_width = cell_len(indent) + 4
            name_width = max(4, width - prefix_width - suffix.cell_len - 1)
            text.append(indent)
            text.append("▾ " if expanded else "▸ ", style="#bc8cff" if expanded else "#6e7681")
            text.append("◆ ", style="#bc8cff" if is_active else "#6e7681")
            text.append(
                _clip(task.name, name_width),
                style="bold #e6edf3" if is_active else "#c9d1d9",
            )
            return suffix_join(text, suffix)

        # terminal
        tab = row.tab
        assert tab is not None
        is_active = tab.id == active_tab
        kind_style = "#3fb950" if tab.kind == "agent" else "#39c5cf"
        suffix = Text()
        if len(tab.panes) > 1:
            suffix.append(f"{len(tab.panes)}p ", style="#6e7681")
        if unread.get(tab.id):
            suffix.append("●", style="bold #f0883e")
        elif is_active:
            suffix.append("◂", style="#58a6ff")
        text.append(indent)
        text.append("● " if is_active else "○ ", style=kind_style if is_active else "#484f58")
        label_width = max(4, width - cell_len(indent) - 2 - suffix.cell_len - 1)
        text.append(
            _clip(tab.label(), label_width),
            style="bold #e6edf3" if is_active else "#8b949e",
        )
        return suffix_join(text, suffix)

    def render(self) -> RenderableType:
        width = max(4, self.content_size.width)
        height = max(1, self.content_size.height)
        self._regions.clear()
        if not self.rows:
            return Text("no projects yet\npress p to add one", style="italic #6e7681")
        max_offset = max(0, len(self.rows) - height)
        self.view_offset = max(0, min(self.view_offset, max_offset))
        visible = self.rows[self.view_offset : self.view_offset + height]
        lines: list[Text] = []
        for index, row in enumerate(visible):
            y = index
            indent_width = 1 + row.depth * 2
            self._regions.append((self.view_offset + index, indent_width, indent_width + 2, row))
            lines.append(self._row_text(row, width))
        if len(self.rows) > height:
            # scroll position hint in the lower right, only when it fits
            pct = int(round((self.view_offset / max_offset) * 100)) if max_offset else 100
            hint = Text(f" {pct}% ", style="#6e7681")
            if len(lines) > 0 and width > len(hint):
                last = lines[-1]
                cut = width - len(hint)
                if last.cell_len > cut:
                    last.truncate(cut)
                pad = max(0, width - last.cell_len - len(hint))
                last.append(" " * pad)
                last.append_text(hint)
        return Group(*lines)

    # -- events -------------------------------------------------------
    def on_click(self, event: events.Click) -> None:
        event.stop()
        row = self._row_at(event.y + self.view_offset)
        if row is None:
            return
        self.focus()
        if event.button == 3:
            self.selected_key = row.key
            self.refresh()
            self.app.tree_context_menu(row, event.screen_x, event.screen_y)
            return
        if not row.selectable:
            return
        chevron = 1 + row.depth * 2
        if event.x <= chevron + 2 and row.kind in {"project", "task"}:
            self.app.toggle_row(row)
            return
        self.selected_key = row.key
        self.refresh()
        if hasattr(self.parent, "update_footer"):
            self.parent.update_footer()
        self.app.tree_activate(row)

    def on_mouse_move(self, event: events.MouseMove) -> None:
        row = self._row_at(event.y + self.view_offset)
        key = row.key if row else ""
        if key != self.hover_key:
            self.hover_key = key
            self.refresh()

    def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        event.stop()
        self.view_offset = max(0, self.view_offset - 3)
        self.refresh()

    def on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        event.stop()
        height = max(1, self.content_size.height)
        self.view_offset = min(max(0, len(self.rows) - height), self.view_offset + 3)
        self.refresh()

    def _row_at(self, y: int) -> Row | None:
        if 0 <= y < len(self.rows):
            return self.rows[y]
        return None

    def on_key(self, event: events.Key) -> None:
        mapping = self.app.cfg.tree_keys
        key = event.key
        action = ""
        if key in {"down", "j"} or key == mapping.get("down"):
            action = "down"
        elif key in {"up", "k"} or key == mapping.get("up"):
            action = "up"
        elif key in {"right", "l"} or key == mapping.get("expand"):
            action = "expand"
        elif key in {"left", "h"} or key == mapping.get("collapse"):
            action = "collapse"
        elif key in {"enter"} or key == mapping.get("activate"):
            action = "activate"
        elif key in {"home"}:
            action = "home"
        elif key in {"end"}:
            action = "end"
        elif key in {"pageup"}:
            action = "pageup"
        elif key in {"pagedown"}:
            action = "pagedown"
        else:
            # Configurable single-character actions.
            reverse = {v: k for k, v in mapping.items()}
            action = reverse.get(key, "")
        if not action:
            return
        event.stop()
        row = self.selected_row()
        if action == "down":
            self.move(1)
        elif action == "up":
            self.move(-1)
        elif action == "home":
            self.move(-10_000)
        elif action == "end":
            self.move(10_000)
        elif action == "pageup":
            self.move(-max(1, self.size.height - 2))
        elif action == "pagedown":
            self.move(max(1, self.size.height - 2))
        elif action in {"expand", "collapse"}:
            self.app.tree_fold(action == "expand")
        elif action == "activate":
            if row:
                self.app.tree_activate(row)
        elif action == "new-task":
            self.app.action_new_task()
        elif action == "new-terminal":
            self.app.action_new_terminal()
        elif action == "close-task":
            self.app.action_close_task()
        elif action == "editor":
            self.app.action_editor()
        elif action == "add-project":
            self.app.action_add_project()


class TreeSelectionChanged(events.Event):
    def __init__(self, row: Row | None) -> None:
        super().__init__()
        self.row = row


class TreePanel(Container):
    DEFAULT_CSS = """
    TreePanel {
        height: 1fr;
        background: #0f141b;
        border-right: solid #21262d;
    }
    TreePanel .panel-title {
        height: 1;
        padding: 0 1;
        background: #0b0f14;
        color: #8b949e;
    }
    TreePanel .panel-footer {
        height: 3;
        padding: 0 1;
        background: #0b0f14;
        color: #6e7681;
        border-top: solid #21262d;
    }
    TreePanel:focus-within .panel-title {
        color: #58a6ff;
        background: #0d1622;
    }
    """

    def __init__(self, ws, **kwargs):
        super().__init__(**kwargs)
        self.ws = ws
        self.selected_key = ""
        self.view = TreeView(ws)
        self.title = Static("", classes="panel-title", markup=False)
        self.footer = Static("", classes="panel-footer", markup=False)

    def compose(self) -> ComposeResult:
        yield self.title
        yield self.view
        yield self.footer

    def refresh_view(self) -> None:
        self.view.rebuild(self.selected_key)
        self.selected_key = self.view.selected_key
        self.title.update(self._title_text())
        self.footer.update(self._footer_text())

    def _title_text(self) -> str:
        stats = self.ws.stats()
        unread = sum(1 for v in self.ws.unread.values() if v)
        text = f" PROJECTS   {stats['projects']}P · {stats['tasks']}T"
        if unread:
            text += f"  ●{unread}"
        return text

    def _footer_text(self) -> str:
        row = self.view.selected_row()
        if row is None:
            return " p add project · ? help"
        if row.kind == "project":
            return " enter open · n task\n t shell · e editor"
        if row.kind == "task":
            return " enter open · t term · n task\n e edit · d close · menu"
        if row.kind in {"terminal", "scratch"}:
            prefix = self.app.cfg.prefix_key
            if prefix.startswith("ctrl+"):
                prefix = "c-" + prefix.split("+", 1)[1]
            return f" enter open · t term\n e edit · {prefix} x close"
        return " p add project · n new task"

    def update_footer(self) -> None:
        self.footer.update(self._footer_text())
