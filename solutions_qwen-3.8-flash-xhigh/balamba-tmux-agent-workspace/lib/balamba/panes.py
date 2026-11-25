"""panes.py — chrome widgets: TreePane, GitPane, StatusBar.

Everything here is Textual: rows are painted with `Text` spans, keys are
widget bindings, mouse clicks/wheel are Textual events routed to the app.
The app owns state; these widgets render + hit-test + forward (the spec's
"one logical sidebar, replicated per window" becomes "one sidebar, always
present" — README: "Chrome replication").
"""

from __future__ import annotations

from rich.text import Text
from textual import events
from textual.widget import Widget


class _LinePane(Widget):
    """Common machinery: one-line-per-row renderer with in-app wheel scroll."""

    def __init__(self, *, id: str | None = None, classes: str = "") -> None:
        super().__init__(id=id, classes=classes)
        self.view_top = 0

    # implemented by subclasses / app
    def pane_lines(self) -> list[Text]:  # pragma: no cover - abstract
        return []

    def visible_rows(self) -> int:
        return max(1, self.size.height)

    def render(self) -> Text:
        lines = self.pane_lines()
        rows = self.visible_rows()
        self.view_top = max(0, min(self.view_top, max(0, len(lines) - rows)))
        window = lines[self.view_top:self.view_top + rows]
        out = Text(justify="left", end="")
        for i, ln in enumerate(window):
            if i:
                out.append("\n")
            out.append(ln)
        for _ in range(rows - len(window)):
            out.append("\n")
        return out

    def row_at(self, event) -> int | None:
        """Screen y -> absolute row index (accounting for borders), or None."""
        y = event.y - self.content_region.y
        if y < 0 or y >= self.visible_rows():
            return None
        idx = self.view_top + y
        lines = self.pane_lines()
        return idx if idx < len(lines) else None

    def scroll_by(self, n: int) -> None:
        self.view_top += n
        self.refresh()


class TreePane(_LinePane, can_focus=True):
    """Left column: projects → tasks → terminals."""

    DEFAULT_CSS = """
    TreePane {
        width: 30;
        height: 1fr;
        background: #101018;
        color: #cdd3e1;
        border: round #33395b;
    }
    TreePane:focus {
        border: round #7f9fff;
    }
    """

    def pane_lines(self) -> list[Text]:
        return self.app.tree_lines()

    # -- keys ------------------------------------------------------------------
    async def on_key(self, event: events.Key) -> None:
        handled = self.app.tree_key(event.key)
        if handled:
            event.stop()
            event.prevent_default()
            self.refresh()

    # -- mouse -----------------------------------------------------------------
    async def on_mouse_up(self, event: events.MouseUp) -> None:
        idx = self.row_at(event)
        if idx is None:
            return
        x = event.x - self.content_region.x
        if event.button == 3:                     # right button
            self.app.tree_right_click(idx, event.screen_x, event.screen_y)
        elif event.button == 1:                   # left
            if x < 3:
                self.app.tree_click_chevron(idx)
            else:
                self.app.tree_click_select(idx, activate=True)
        self.refresh()
        event.stop()

    async def on_mouse_down(self, event: events.MouseDown) -> None:
        # first click on an unfocused pane both focuses and is delivered:
        # MouseUp does the work, so we only focus here.
        self.focus()

    async def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        event.stop()
        self.scroll_by(-3)

    async def on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        event.stop()
        self.scroll_by(3)


class GitPane(_LinePane, can_focus=True):
    """Right column: read-only git status for the active context."""

    DEFAULT_CSS = """
    GitPane {
        width: 34;
        height: 1fr;
        background: #101018;
        color: #cdd3e1;
        border: round #33395b;
    }
    GitPane:focus {
        border: round #7f9fff;
    }
    """

    def pane_lines(self) -> list[Text]:
        return self.app.git_lines()

    async def on_key(self, event: events.Key) -> None:
        handled = self.app.git_key(event.key)
        if handled:
            event.stop()
            event.prevent_default()
            self.refresh()

    async def on_mouse_up(self, event: events.MouseUp) -> None:
        idx = self.row_at(event)
        if idx is not None and event.button == 1:
            self.app.git_click_row(idx)
        self.refresh()
        event.stop()

    async def on_mouse_down(self, event: events.MouseDown) -> None:
        self.focus()

    def on_focus(self) -> None:
        self.app.git_focus_refresh()      # spec: git panel auto-refresh on focus

    async def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        event.stop()
        self.scroll_by(-3)

    async def on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        event.stop()
        self.scroll_by(3)


class StatusBar(Widget):
    """Bottom bar: `balamba · <context>` + the clickable tab list."""

    DEFAULT_CSS = """
    StatusBar {
        width: 100%;
        height: 1;
        background: #262636;
        color: #dfe1f2;
    }
    """

    def render(self) -> Text:
        return self.app.status_text(self.size.width)

    async def on_mouse_up(self, event: events.MouseUp) -> None:
        if event.button != 1:
            return
        hit = self.app.status_tab_at(event.x - self.region.x)
        if hit is not None:
            self.app.activate_tab_index(hit)
        event.stop()
        self.app.refresh_chrome()

    async def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        event.stop()
        self.app.cycle_tab(1)

    async def on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        event.stop()
        self.app.cycle_tab(-1)
