"""Right-click context menu as a Textual modal screen."""

from __future__ import annotations

from dataclasses import dataclass

from rich.console import Group, RenderableType
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Static


@dataclass
class MenuItem:
    action: str
    label: str
    hint: str = ""
    danger: bool = False
    disabled: bool = False


class MenuList(Widget, can_focus=True):
    DEFAULT_CSS = """
    MenuList {
        height: auto;
        max-height: 18;
        background: #0d1117;
    }
    """

    def __init__(self, items: list[MenuItem], **kwargs):
        super().__init__(**kwargs)
        self.items = items
        self.index = next((i for i, item in enumerate(items) if not item.disabled), 0)
        self.hover = -1

    def render(self) -> RenderableType:
        lines: list[Text] = []
        for i, item in enumerate(self.items):
            selected = i == self.index
            style = "on #17324d" if selected else ("on #131b25" if i == self.hover else "")
            text = Text(style=style)
            marker = "▸ " if selected else "  "
            text.append(marker, style="#58a6ff" if selected else "#30363d")
            label_style = "#6e7681" if item.disabled else ("#f85149" if item.danger else "#c9d1d9")
            text.append(item.label, style="bold " + label_style if selected else label_style)
            if item.hint:
                gap = max(1, 30 - text.cell_len - len(item.hint))
                text.append(" " * gap)
                text.append(item.hint, style="#484f58")
            text.pad_right(max(0, 38 - text.cell_len))
            lines.append(text)
        return Group(*lines)

    def _choose(self, index: int) -> None:
        if 0 <= index < len(self.items) and not self.items[index].disabled:
            self.screen.dismiss(self.items[index].action)

    def on_click(self, event: events.Click) -> None:
        event.stop()
        if 0 <= event.y < len(self.items):
            self.index = event.y
            self._choose(event.y)

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if event.y != self.hover:
            self.hover = event.y
            self.refresh()

    def on_key(self, event: events.Key) -> None:
        if event.key in {"down", "j"}:
            event.stop()
            for delta in range(1, len(self.items) + 1):
                idx = (self.index + delta) % len(self.items)
                if not self.items[idx].disabled:
                    self.index = idx
                    break
            self.refresh()
        elif event.key in {"up", "k"}:
            event.stop()
            for delta in range(1, len(self.items) + 1):
                idx = (self.index - delta) % len(self.items)
                if not self.items[idx].disabled:
                    self.index = idx
                    break
            self.refresh()
        elif event.key == "enter":
            event.stop()
            self._choose(self.index)
        elif event.key == "escape":
            event.stop()
            self.screen.dismiss(None)


class ContextMenuScreen(ModalScreen):
    DEFAULT_CSS = """
    ContextMenuScreen {
        background: #05070a;
        align: left top;
    }
    #ctx {
        position: absolute;
        width: 44;
        height: auto;
        background: #0d1117;
        border: round #30363d;
        padding: 0;
    }
    #ctx-title {
        height: 1;
        padding: 0 1;
        background: #161b22;
        color: #58a6ff;
        text-style: bold;
    }
    """

    def __init__(self, title: str, items: list[MenuItem], x: int, y: int, **kwargs):
        super().__init__(**kwargs)
        self.menu_title = title
        self.items = items
        self.x = x
        self.y = y

    def compose(self) -> ComposeResult:
        with Vertical(id="ctx"):
            yield Static(self.menu_title, id="ctx-title", markup=False)
            yield MenuList(self.items)

    def on_mount(self) -> None:
        height = len(self.items) + 3
        max_x = max(0, self.app.size.width - 46)
        max_y = max(0, self.app.size.height - height - 2)
        self.query_one("#ctx", Vertical).styles.offset = (
            min(max(0, self.x), max_x),
            min(max(0, self.y), max_y),
        )
        self.query_one(MenuList).focus()

    def on_click(self, event: events.Click) -> None:
        # Clicks inside the menu are stopped by MenuList; anything here is outside.
        event.stop()
        self.dismiss(None)
