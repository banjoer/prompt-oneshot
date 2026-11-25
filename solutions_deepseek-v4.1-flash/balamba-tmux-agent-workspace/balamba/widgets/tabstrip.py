"""Clickable tab strip above the terminal content (Textual chrome)."""

from __future__ import annotations

import os
from pathlib import Path

from rich.console import Group, RenderableType
from rich.text import Text
from textual import events
from textual.widget import Widget

from ..state import TerminalTab


def short_path(path: str, limit: int) -> str:
    if not path:
        return ""
    home = str(Path.home())
    text = path.replace(home, "~", 1) if path.startswith(home) else path
    if len(text) <= limit:
        return text
    parts = text.split(os.sep)
    if len(parts) >= 3:
        text = os.sep.join(["…", *parts[-2:]])
    if len(text) > limit:
        text = "…" + text[-(limit - 1) :]
    return text


class TabStrip(Widget):
    DEFAULT_CSS = """
    TabStrip {
        height: 3;
        background: #0b0f14;
        border-bottom: solid #21262d;
    }
    """

    def __init__(self, ws, **kwargs):
        super().__init__(**kwargs)
        self.ws = ws
        self.hover_action = ""
        self.regions: list[tuple[int, int, int, str, str]] = []

    def current_tabs(self) -> list[TerminalTab]:
        return self.ws.state.context_tabs()

    def render(self) -> RenderableType:
        width = max(10, self.content_size.width)
        tabs = self.current_tabs()
        self.regions.clear()
        line1 = Text()
        line1.append(" ")
        if not tabs:
            line1.append("no tabs", style="#6e7681")
            line1.append("  press ", style="#484f58")
            line1.append("t", style="bold #58a6ff")
            line1.append(" to create a terminal", style="#484f58")
            plus_start = len(line1.plain)
            line1.append("   ＋ ", style="bold #3fb950")
            self.regions.append((1, plus_start, plus_start + 5, "new-tab", ""))
        else:
            active_id = self.ws.state.active_tab
            try:
                active_index = next(i for i, t in enumerate(tabs) if t.id == active_id)
            except StopIteration:
                active_index = 0
            # horizontal chip layout; ensure the active chip is visible
            chips: list[tuple[TerminalTab, int, str, int]] = []
            for index, tab in enumerate(tabs, start=1):
                title = tab.name or tab.label()
                if len(title) > 14:
                    title = title[:13] + "…"
                prefix = f"{index} "
                dot = "● " if self.ws.unread.get(tab.id) else ""
                label = f"{prefix}{dot}{title}"
                chip = f" {label} × "
                chips.append((tab, index, chip, len(chip)))
            total = sum(c[3] for c in chips) + 6
            available = width - 2
            # If overflow, drop chips before the active one from the left.
            if total > available:
                keep_from = active_index
                while keep_from > 0 and sum(c[3] for c in chips[keep_from:]) + 42 < available:
                    keep_from -= 1
                if sum(c[3] for c in chips[keep_from:]) + 6 > available:
                    keep_from = active_index
                chips = chips[keep_from:]
            for tab, index, chip, chip_len in chips:
                active = tab.id == active_id
                start = len(line1.plain)
                style = "bold on #17324d #dbeafe" if active else "#8b949e"
                if tab.id == active_id:
                    line1.append(chip, style="bold #e6edf3 on #17324d")
                else:
                    line1.append(chip, style="#8b949e")
                # close hit area = the last 3 cells of the chip
                self.regions.append((1, start, start + chip_len - 3, f"tab:{tab.id}", ""))
                self.regions.append((1, start + chip_len - 3, start + chip_len, f"close:{tab.id}", ""))
            start = len(line1.plain)
            line1.append("  ＋ ", style="bold #3fb950")
            self.regions.append((1, start, start + 4, "new-tab", ""))

        # status/clock on the right
        clock = self.app.clock_text if hasattr(self.app, "clock_text") else ""
        right = f" {clock} "
        if len(line1.plain) + len(right) < width:
            line1.append(" " * max(0, width - len(line1.plain) - len(right)))
            line1.append(right, style="#484f58")
        else:
            line1.truncate(width)
        pad = max(0, width - line1.cell_len)
        line1.append(" " * pad)

        line2 = Text(style="on #0b0f14")
        active = self.ws.state.active_tab_obj()

        def add_piece(piece: str, style: str = "#8b949e", *, limit: int | None = None) -> None:
            budget = width - (limit or 0)
            if line2.cell_len + len(piece) <= budget:
                line2.append(piece, style=style)

        if active:
            missing = active.id in self.ws.missing_tabs
            tab_label = active.label()
            if missing:
                line2.append("  terminal not running", style="bold #f85149")
                line2.append("  · press ", style="#8b949e")
                line2.append("r", style="bold #58a6ff")
                line2.append(" to reattach", style="#8b949e")
            else:
                glyph = "◆" if active.kind == "agent" else "▸"
                line2.append(f"  {glyph} {tab_label}", style="#8b949e")
                if active.session:
                    add_piece(f"  {active.session[:10]}…", "#484f58", limit=0)
                cwd_width = max(8, min(34, width // 2))
                add_piece(f"  cwd {short_path(active.cwd, cwd_width)}", "#484f58", limit=0)
                panes = max(1, len(active.panes))
                pane_index = max(1, active.active_pane + 1)
                add_piece(f"  p{pane_index}/{panes}", "#6e7681", limit=0)
                if self.app.terminal is not None and self.app.terminal.scrollback_offset > 0:
                    add_piece(f"  scroll -{self.app.terminal.scrollback_offset}", "bold #d29922", limit=0)
                prefix = self.app.cfg.prefix_key
                if prefix.startswith("ctrl+"):
                    prefix = "c-" + prefix.split("+", 1)[1]
                add_piece(f"   {prefix} \\", "#484f58", limit=0)
                add_piece(" split", "#30363d", limit=0)
                add_piece(f" · {prefix} o", "#484f58", limit=0)
                add_piece(" pane", "#30363d", limit=0)
        else:
            line2.append("  select a project to begin", style="italic #484f58")
            add_piece("   p", "bold #58a6ff", limit=0)
            add_piece(" add project", "#484f58", limit=0)
            add_piece(" · F1", "bold #58a6ff", limit=0)
            add_piece(" about", "#484f58", limit=0)
        line2.truncate(width)
        line2.append(" " * max(0, width - line2.cell_len))
        return Group(line1, line2)

    # -- events --------------------------------------------------------
    def _action_at(self, y: int, x: int) -> tuple[str, str]:
        for line_y, x0, x1, action, payload in self.regions:
            if line_y == y and x0 <= x < x1:
                return action, payload
        return "", ""

    def on_click(self, event: events.Click) -> None:
        event.stop()
        action, payload = self._action_at(event.y, event.x)
        if event.button == 3:
            tab = None
            if action.startswith("tab:"):
                found = self.ws.state.find_tab(action.split(":", 1)[1])
                tab = found[1] if found else None
            self.app.tab_context_menu(tab or self.ws.state.active_tab_obj(), event.screen_x, event.screen_y)
            return
        if not action:
            return
        if action == "new-tab":
            self.app.action_new_terminal()
        elif action.startswith("tab:"):
            self.app.switch_tab(action.split(":", 1)[1])
        elif action.startswith("close:"):
            tab = self.ws.state.find_tab(action.split(":", 1)[1])
            if tab:
                self.app.confirm_close_tab(tab[1])

    def on_mouse_move(self, event: events.MouseMove) -> None:
        action, _ = self._action_at(event.y, event.x)
        if action != self.hover_action:
            self.hover_action = action
            # Only redraw on region changes; cheap enough at pointer rate.
            self.refresh(layout=False)

    def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        event.stop()
        self.app.action_prev_tab()

    def on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        event.stop()
        self.app.action_next_tab()
