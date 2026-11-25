"""Git side panel — Textual rendering of branch, ahead/behind and files."""

from __future__ import annotations

from rich.console import Group, RenderableType
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Container
from textual.widget import Widget
from textual.widgets import Static

from ..gitops import FileStatus, RepoStatus


STATUS_COLORS = {
    "M": "#d29922",
    "A": "#3fb950",
    "D": "#f85149",
    "R": "#bc8cff",
    "C": "#39c5cf",
    "U": "#f85149",
    "?": "#d2a8ff",
    "!": "#6e7681",
}


class GitBody(Widget, can_focus=True):
    DEFAULT_CSS = """
    GitBody {
        height: 1fr;
        padding: 0 1;
        background: #0f141b;
        color: #c9d1d9;
    }
    GitBody:focus {
        background: #101720;
    }
    """

    def __init__(self, ws, **kwargs):
        super().__init__(**kwargs)
        self.ws = ws
        self.status: RepoStatus | None = None
        self.view_offset = 0
        self.selected_file = 0
        self.hover_file = -1
        self.loading = False
        self._file_rows: list[tuple[int, int]] = []  # (line index, file index)
        self._header_height = 0

    def set_status(self, status: RepoStatus | None, *, loading: bool = False) -> None:
        self.status = status
        self.loading = loading
        if status and self.selected_file >= len(status.files):
            self.selected_file = max(0, len(status.files) - 1)
        self.refresh()

    def _header_lines(self, width: int) -> list[Text]:
        status = self.status
        lines: list[Text] = []
        if status is None:
            lines.append(Text("no active context", style="italic #6e7681"))
            return lines
        if not status.ok:
            lines.append(Text("git unavailable", style="bold #f85149"))
            lines.append(Text(status.error or "unknown error", style="#8b949e"))
            return lines

        line = Text()
        line.append("⎇ ", style="#3fb950")
        branch = status.branch if not status.detached else f"detached @ {status.head}"
        line.append(branch, style="bold #e6edf3" if not status.detached else "bold #d29922")
        if status.detached:
            line.append("  detached", style="bold #d29922")
        lines.append(line)

        meta = Text()
        comparison = status.comparison or ("upstream" if status.upstream else "")
        label = "upstream" if status.upstream else "base"
        if comparison:
            meta.append(f"{label} ", style="#6e7681")
            meta.append(comparison, style="#8b949e")
            if status.ahead.ok:
                meta.append("  ")
                meta.append(f"↑{status.ahead.ahead}", style="#3fb950" if status.ahead.ahead else "#484f58")
                meta.append(" ")
                meta.append(f"↓{status.ahead.behind}", style="#f85149" if status.ahead.behind else "#484f58")
            else:
                meta.append("  ?", style="#6e7681")
        else:
            meta.append("no upstream / base ref", style="#6e7681")
        if status.upstream and status.base and status.base != status.upstream:
            pass
        lines.append(meta)
        if status.upstream and not status.detached:
            extra = Text("upstream ", style="#6e7681")
            extra.append(status.upstream, style="#8b949e")
            lines.append(extra)
        if status.files:
            count = Text()
            count.append("changed ", style="#6e7681")
            count.append(str(len(status.files)), style="bold #d29922")
            if width >= 30:
                count.append("   S/U/?", style="#484f58")
            lines.append(count)
        else:
            lines.append(Text("clean working tree", style="#3fb950"))
        lines.append(Text("─" * max(4, width), style="#21262d"))
        self._header_height = len(lines)
        return lines

    def _file_line(self, file: FileStatus, index: int, width: int) -> Text:
        selected = index == self.selected_file and self.has_focus
        hover = index == self.hover_file
        style = "on #172232" if selected else ("on #131b25" if hover else "")
        text = Text(style=style)
        code = file.code
        color = STATUS_COLORS.get(code[0], "#8b949e")
        marker = "▸ " if index == self.selected_file else "  "
        text.append(marker, style="#58a6ff" if index == self.selected_file else "#484f58")
        text.append(f"{code:<2}", style=f"bold {color}")
        text.append(" ")
        badges = ""
        if file.untracked:
            badges = " ?"
        else:
            badges = ("S" if file.staged else "·") + ("U" if file.unstaged else "·")
        name_space = max(3, width - 5 - len(badges))
        name = file.path
        if len(name) > name_space:
            name = "…" + name[-(name_space - 1) :]
        text.append(name, style="#c9d1d9")
        gap = max(1, width - text.cell_len - len(badges))
        text.append(" " * gap)
        for char in badges:
            if char == "S":
                text.append(char, style="bold #3fb950")
            elif char == "U":
                text.append(char, style="bold #d29922")
            elif char == "?":
                text.append(char, style="bold #d2a8ff")
            else:
                text.append(char, style="#30363d")
        if text.cell_len > width:
            text.truncate(width)
        visible = max(0, width - text.cell_len)
        text.append(" " * visible, style=style)
        return text

    def render(self) -> RenderableType:
        width = max(8, self.content_size.width)
        height = max(1, self.content_size.height)
        header = self._header_lines(width)
        lines = list(header)
        self._file_rows.clear()
        status = self.status
        if status and status.ok:
            files = status.files
            if files:
                viewport = max(1, height - len(header))
                max_offset = max(0, len(files) - viewport)
                self.view_offset = max(0, min(self.view_offset, max_offset))
                for i in range(self.view_offset, min(len(files), self.view_offset + viewport)):
                    self._file_rows.append((len(lines), i))
                    lines.append(self._file_line(files[i], i, width))
            elif self.loading:
                lines.append(Text("refreshing…", style="italic #6e7681"))
        if self.loading and status and status.ok:
            lines.append(Text("refreshing…", style="italic #484f58"))
        for line in lines:
            if line.cell_len > width:
                line.truncate(width)
        if len(lines) > height:
            lines = lines[:height]
        return Group(*lines)

    # -- navigation ----------------------------------------------------
    def _move(self, delta: int) -> None:
        status = self.status
        if not status or not status.files:
            return
        viewport = max(1, self.size.height - self._header_height)
        self.selected_file = max(0, min(len(status.files) - 1, self.selected_file + delta))
        if self.selected_file < self.view_offset:
            self.view_offset = self.selected_file
        elif self.selected_file >= self.view_offset + viewport:
            self.view_offset = self.selected_file - viewport + 1
        self.refresh()

    def on_focus(self, event: events.Focus) -> None:
        try:
            self.app._git_tick()
        except Exception:
            pass

    def on_key(self, event: events.Key) -> None:
        if event.key in {"j", "down"}:
            event.stop()
            self._move(1)
        elif event.key in {"k", "up"}:
            event.stop()
            self._move(-1)
        elif event.key in {"enter"}:
            event.stop()
            self.open_selected()
        elif event.key in {"pagedown"}:
            event.stop()
            self._move(max(1, self.size.height - self._header_height - 1))
        elif event.key in {"pageup"}:
            event.stop()
            self._move(-max(1, self.size.height - self._header_height - 1))

    def open_selected(self) -> None:
        status = self.status
        if not status or not status.files:
            return
        file = status.files[self.selected_file]
        self.app.show_diff(file.path)

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self.focus()
        for line_index, file_index in self._file_rows:
            if event.y == line_index:
                self.selected_file = file_index
                if event.button == 3:
                    self.app.git_file_context_menu(file_index, event.screen_x, event.screen_y)
                else:
                    self.open_selected()
                self.refresh()
                return
        if event.button == 3:
            self.app.git_context_menu(event.screen_x, event.screen_y)

    def on_mouse_move(self, event: events.MouseMove) -> None:
        hover = -1
        for line_index, file_index in self._file_rows:
            if event.y == line_index:
                hover = file_index
                break
        if hover != self.hover_file:
            self.hover_file = hover
            self.refresh()

    def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        event.stop()
        self.view_offset = max(0, self.view_offset - 3)
        self.refresh()

    def on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        event.stop()
        status = self.status
        if not status:
            return
        viewport = max(1, self.size.height - self._header_height)
        self.view_offset = min(max(0, len(status.files) - viewport), self.view_offset + 3)
        self.refresh()


class GitPanel(Container):
    DEFAULT_CSS = """
    GitPanel {
        height: 1fr;
        background: #0f141b;
        border-left: solid #21262d;
    }
    GitPanel .panel-title {
        height: 1;
        padding: 0 1;
        background: #0b0f14;
        color: #8b949e;
    }
    GitPanel .panel-footer {
        height: 3;
        padding: 0 1;
        background: #0b0f14;
        color: #6e7681;
        border-top: solid #21262d;
    }
    GitPanel:focus-within .panel-title {
        color: #3fb950;
        background: #0d1a13;
    }
    """

    def __init__(self, ws, **kwargs):
        super().__init__(**kwargs)
        self.ws = ws
        self.title = Static("", classes="panel-title", markup=False)
        self.body = GitBody(ws)
        self.footer = Static("", classes="panel-footer", markup=False)

    def compose(self) -> ComposeResult:
        yield self.title
        yield self.body
        yield self.footer

    def set_status(self, status: RepoStatus | None, *, loading: bool = False) -> None:
        self.body.set_status(status, loading=loading)
        self.title.update(self._title_text(status))
        self.footer.update(" click file → diff\n S/U/? · read-only")

    def _title_text(self, status: RepoStatus | None) -> str:
        if status is None:
            return " GIT"
        if not status.ok:
            return " GIT   unavailable"
        if status.detached:
            return f" GIT   detached · {status.head}"
        return f" GIT   {status.branch}"
