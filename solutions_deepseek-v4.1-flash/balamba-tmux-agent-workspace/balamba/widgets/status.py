"""Bottom status bar: context, clickable tab list, prefix state, clock."""

from __future__ import annotations

from datetime import datetime

from rich.console import Group, RenderableType
from rich.text import Text
from textual import events
from textual.widget import Widget

from .. import SIGN_OFF, __version__
from .tabstrip import short_path


class StatusBar(Widget):
    DEFAULT_CSS = """
    StatusBar {
        height: 3;
        background: #070b10;
        border-top: solid #21262d;
    }
    """

    def __init__(self, ws, **kwargs):
        super().__init__(**kwargs)
        self.ws = ws
        self.regions: list[tuple[int, int, int, str, str]] = []
        self.hover_action = ""

    def render(self) -> RenderableType:
        width = max(20, self.content_size.width)
        state = self.ws.state
        app = self.app
        raw_prefix = app.cfg.prefix_key
        if raw_prefix.startswith("ctrl+") and len(raw_prefix) > 5:
            prefix = "c-" + raw_prefix.split("+", 1)[1]
        elif raw_prefix.startswith("alt+") and len(raw_prefix) > 4:
            prefix = "m-" + raw_prefix.split("+", 1)[1]
        else:
            prefix = raw_prefix
        self.regions.clear()

        line = Text(style="on #070b10")
        # brand block
        start = len(line.plain)
        line.append(" balamba ", style="bold #0d1117 on #58a6ff")
        self.regions.append((0, start, start + 9, "about", ""))
        line.append(" ")
        project = state.active_project_obj()
        task = state.active_task_obj()
        context = "no project"
        if project:
            context = project.name
            if task:
                context += f" › {task.name}"
        start = len(line.plain)
        line.append(context, style="bold #e6edf3")
        self.regions.append((0, start, start + len(context), "focus-tree", ""))
        line.append("  ")

        status = app.git_status
        if status and status.ok:
            branch_text = status.branch if not status.detached else f"detached@{status.head}"
            chip_start = len(line.plain)
            line.append(" ⎇ ", style="#3fb950")
            line.append(branch_text, style="#8b949e")
            line.append(" ")
            self.regions.append((0, chip_start, len(line.plain), "focus-git", ""))
            if status.ahead.ok:
                line.append(f"↑{status.ahead.ahead}", style="#3fb950" if status.ahead.ahead else "#30363d")
                line.append(" ")
                line.append(f"↓{status.ahead.behind}", style="#f85149" if status.ahead.behind else "#30363d")
                line.append(" ")

        # prefix mode indicator
        if getattr(app, "prefix_armed", False):
            chip_start = len(line.plain)
            line.append(" PREFIX ", style="bold #0d1117 on #d29922")
            line.append(" waiting for command…  ", style="#d29922")
            self.regions.append((0, chip_start, len(line.plain), "help", ""))
        elif getattr(app, "booting", False):
            line.append(" connecting… ", style="italic #58a6ff")

        # clickable tab list
        tabs = state.context_tabs()
        if tabs:
            line.append(" ")
            for index, tab in enumerate(tabs[:9], start=1):
                active = tab.id == state.active_tab
                unread = self.ws.unread.get(tab.id)
                start = len(line.plain)
                text = f" {index} "
                style = "bold #0d1117 on #58a6ff" if active else "#8b949e"
                line.append(text, style=style)
                if unread:
                    line.append("●", style="bold #f0883e")
                else:
                    line.append(" ", style="")
                short = (tab.name if tab.name else ("agent" if tab.kind == "agent" else "shell"))[:8]
                line.append(short, style="#8b949e" if not active else "#0d1117 on #58a6ff")
                line.append(" ", style="")
                self.regions.append((0, start, len(line.plain), f"tab:{tab.id}", ""))
            start = len(line.plain)
            line.append("＋", style="#3fb950")
            self.regions.append((0, start, len(line.plain), "new-tab", ""))

        clock = app.clock_text if hasattr(app, "clock_text") else datetime.now().strftime("%H:%M")
        right = f" {clock}  "
        help_start = None
        if line.cell_len + len(right) + 4 < width:
            line.append(" " * max(0, width - line.cell_len - len(right) - 3))
            help_start = len(line.plain)
            line.append(" ? ", style="bold #58a6ff")
            self.regions.append((0, help_start, help_start + 3, "help", ""))
            line.append(right, style="#484f58")
        else:
            line.truncate(width)
        pad = max(0, width - line.cell_len)
        line.append(" " * pad, style="on #070b10")

        # hints line
        hints = Text(style="on #070b10")
        p = prefix or "c-a"
        hints.append(" ", style="")
        pairs = [
            (f"{p} {app.cfg.command_key('new-task')}", "new task"),
            (f"{p} {app.cfg.command_key('add-project')}", "project"),
            (f"{p} {app.cfg.command_key('new-terminal')}", "terminal"),
            (f"{p} {app.cfg.command_key('editor')}", "editor"),
            (f"{p} {app.cfg.command_key('detach')}", "detach"),
        ]
        for i, (key, label) in enumerate(pairs):
            hints.append(key, style="bold #58a6ff")
            hints.append(" ", style="")
            hints.append(label, style="#6e7681")
            hints.append("  ·  ", style="#30363d")
        hints.append(
            f"{app.cfg.key_for('down', 'j')}/{app.cfg.key_for('up', 'k')}",
            style="#8b949e",
        )
        hints.append(" move  ·  ", style="#30363d")
        hints.append("F1", style="#8b949e")
        hints.append(" help", style="#30363d")
        if width >= 150:
            hints.append("  ·  ", style="#30363d")
            hints.append("chrome Textual · content tmux", style="#484f58")
        hints.truncate(width)
        hints.append(" " * max(0, width - hints.cell_len), style="on #070b10")
        return Group(line, hints)

    def _action_at(self, event: events.Click) -> tuple[str, str]:
        for line_y, x0, x1, action, payload in self.regions:
            if event.y == line_y and x0 <= event.x < x1:
                return action, payload
        return "", ""

    def on_click(self, event: events.Click) -> None:
        event.stop()
        action, _ = self._action_at(event)
        if action == "about":
            self.app.action_about()
        elif action == "help":
            self.app.action_help()
        elif action == "focus-tree":
            self.app.focus_tree()
        elif action == "focus-git":
            self.app.focus_git()
        elif action == "new-tab":
            self.app.action_new_terminal()
        elif action.startswith("tab:"):
            self.app.switch_tab(action.split(":", 1)[1])

    def on_mouse_move(self, event: events.MouseMove) -> None:
        action = ""
        for line_y, x0, x1, act, payload in self.regions:
            if event.y == line_y and x0 <= event.x < x1:
                action = act
                break
        if action != self.hover_action:
            self.hover_action = action
            self.refresh(layout=False)

    def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        event.stop()
        self.app.action_prev_tab()

    def on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        event.stop()
        self.app.action_next_tab()
