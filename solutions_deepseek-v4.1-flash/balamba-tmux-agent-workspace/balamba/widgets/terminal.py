"""Terminal content area.

tmux hosts the processes (one window per tab, panes for splits) but every cell
on screen is laid out and painted by Textual.  Keys and mouse gestures are
forwarded to the active tmux pane with ``send-keys``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from rich.console import Group, RenderableType
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.css.query import NoMatches
from textual.widget import Widget
from textual.widgets import Static

from ..state import TerminalTab
from ..tmuxctl import PaneInfo, TmuxError

KEY_MAP = {
    "enter": "Enter",
    "tab": "Tab",
    "shift+tab": "BTab",
    "backspace": "BSpace",
    "escape": "Escape",
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
    "home": "Home",
    "end": "End",
    "pageup": "PPage",
    "pagedown": "NPage",
    "insert": "IC",
    "delete": "DC",
    "f1": "F1",
    "f2": "F2",
    "f3": "F3",
    "f4": "F4",
    "f5": "F5",
    "f6": "F6",
    "f7": "F7",
    "f8": "F8",
    "f9": "F9",
    "f10": "F10",
    "f11": "F11",
    "f12": "F12",
}


def _safe_text(ansi: str, width: int) -> Text:
    ansi = ansi.replace("\t", "    ")
    try:
        text = Text.from_ansi(ansi)
    except Exception:
        text = Text(ansi)
    if width > 0:
        if text.cell_len > width:
            text.truncate(width)
        elif text.cell_len < width:
            text.pad_right(width - text.cell_len)
    return text


class PaneView(Static):
    DEFAULT_CSS = """
    PaneView {
        padding: 0;
        margin: 0;
        background: #0b1016;
    }
    PaneView.active-pane {
        background: #0d1520;
    }
    """

    def __init__(self, area: "TerminalArea", pane: PaneInfo, **kwargs):
        super().__init__("", markup=False, **kwargs)
        self.area = area
        self.pane = pane
        self.lines: list[str] = []
        self.styles.position = "absolute"
        self.styles.offset = (pane.left, pane.top)
        self.styles.width = pane.width
        self.styles.height = pane.height

    def set_pane(self, pane: PaneInfo) -> None:
        self.pane = pane
        self.styles.offset = (pane.left, pane.top)
        self.styles.width = pane.width
        self.styles.height = pane.height
        self.set_class(pane.active, "active-pane")

    def set_lines(self, lines: list[str]) -> None:
        if lines == self.lines:
            return
        self.lines = lines
        self.update(Group(*[_safe_text(line, self.pane.width) for line in lines]))

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self.area.select_pane(self.pane)
        if event.button == 3:
            self.area.app.terminal_context_menu(self.pane, event.screen_x, event.screen_y)
        self.area.focus()

    def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        event.stop()
        self.area.scroll_pane(self.pane, 3)

    def on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        event.stop()
        self.area.scroll_pane(self.pane, -3)


class TerminalArea(Widget, can_focus=True):
    DEFAULT_CSS = """
    TerminalArea {
        height: 1fr;
        width: 1fr;
        padding: 0;
        margin: 0;
        background: #30363d;
        color: #c9d1d9;
        overflow: hidden;
    }
    TerminalArea:focus {
        background: #0d1219;
    }
    #terminal-message {
        position: absolute;
        width: 100%;
        height: 100%;
        content-align: center middle;
        text-align: center;
        background: #0d1117;
        color: #8b949e;
        padding: 2 4;
    }
    """

    BINDINGS = [
        ("tab", "send_tab", "tab"),
        ("shift+tab", "send_btab", "backtab"),
    ]

    def __init__(self, ws, *, window_id: str = "", tab: TerminalTab | None = None, **kwargs):
        super().__init__(**kwargs)
        self.ws = ws
        self.tab = tab
        self.window_id = window_id
        self.message = Static("", id="terminal-message", markup=True)
        self.views: dict[str, PaneView] = {}
        self.panes: list[PaneInfo] = []
        self.offsets: dict[str, int] = {}
        self.history_available: dict[str, int] = {}
        self._busy = False
        self._poll_timer = None
        self._resize_timer = None
        self._last_size = (0, 0)
        self._message_visible = True
        self.passthrough_keys: set[str] = set()
        self._dividers: list[Static] = []
        self._divider_signature: tuple = ()

    def compose(self) -> ComposeResult:
        yield self.message

    def on_mount(self) -> None:
        self._poll_timer = self.set_interval(0.13, self._tick)
        if self.tab is None and not self.window_id:
            self.show_message("no terminal selected")
        elif self.tab:
            self._apply_size()
            self._tick()

    def on_unmount(self) -> None:
        if self._poll_timer:
            self._poll_timer.stop()
        if self._resize_timer:
            self._resize_timer.stop()

    # -- session -------------------------------------------------------
    def attach_tab(self, tab: TerminalTab | None) -> None:
        if tab is not None and self.tab is not None and tab.id == self.tab.id:
            self.tab = tab
            return
        self.tab = tab
        self.window_id = ""
        self.offsets.clear()
        self.history_available.clear()
        self._last_size = (0, 0)
        if tab is None:
            self.show_message("no terminal selected\n\npress [b]t[/b] to open one", markup=True)
        else:
            self.hide_message()
            self._apply_size()
        self._tick()

    def attach_window(self, window_id: str) -> None:
        self.window_id = window_id
        self.tab = None
        self.offsets.clear()
        self.history_available.clear()
        self._last_size = (0, 0)
        self.hide_message()
        self._apply_size()
        self._tick()

    def detach_window(self) -> None:
        self.window_id = ""

    @property
    def target_window(self) -> str:
        if self.window_id:
            return self.window_id
        if not self.tab:
            return ""
        win = self.ws.window_ids.get(self.tab.id, "")
        if not win:
            info = self.ws.tmux.window_for_tab(self.tab.id)
            win = info.id if info else ""
            if win:
                self.ws.window_ids[self.tab.id] = win
        return win

    # -- rendering helpers --------------------------------------------
    def show_message(self, text: str, *, markup: bool = False) -> None:
        self.message.update(Text.from_markup(text) if markup else Text(text))
        self.message.styles.display = "block"
        self._message_visible = True
        for view in self.views.values():
            view.styles.display = "none"
        for divider in self._dividers:
            divider.styles.display = "none"

    def hide_message(self) -> None:
        if self._message_visible:
            self.message.styles.display = "none"
            self._message_visible = False
        for view in self.views.values():
            view.styles.display = "block"
        for divider in self._dividers:
            divider.styles.display = "block"

    @property
    def scrollback_offset(self) -> int:
        return max(self.offsets.values(), default=0)

    def _active_pane(self) -> PaneInfo | None:
        return next((p for p in self.panes if p.active), self.panes[0] if self.panes else None)

    def select_pane(self, pane: PaneInfo) -> None:
        if not self.tab:
            return
        try:
            self.ws.tmux.select_pane(pane.id)
            self.ws.select_pane_index(self.tab, pane.index)
        except TmuxError:
            pass
        self.offsets.pop(pane.id, None)
        self._tick_now()

    def scroll_pane(self, pane: PaneInfo, delta: int) -> None:
        current = self.offsets.get(pane.id, 0)
        limit = max(0, self.history_available.get(pane.id, 600) - pane.height)
        new = max(0, min(limit, current + delta))
        if new == current:
            return
        self.offsets[pane.id] = new
        self.app.refresh_tabstrip()
        self._tick_now()

    def _tick_now(self) -> None:
        if self._busy:
            return
        self._busy = True
        self.run_worker(self._poll_async(), group="terminal-pane", exclusive=True)

    def _tick(self) -> None:
        self._tick_now()

    async def _poll_async(self) -> None:
        try:
            await self._poll_once()
        finally:
            self._busy = False

    async def _poll_once(self) -> None:
        if self.tab is None and not self.window_id:
            return
        # Never poll a hidden main terminal while a modal (editor, diff, …) is up.
        if self.screen is not self.app.screen:
            return
        if getattr(self.app, "booting", False):
            self.show_message("restoring workspace…")
            return
        if self.tab is not None and self.tab.id in self.ws.missing_tabs:
            self.show_message(
                "terminal is no longer running\npress [b]r[/b] to reattach · [b]c-a x[/b] to close",
                markup=True,
            )
            return
        win = self.target_window
        if not win:
            self.show_message("terminal is no longer running" if self.tab else "no terminal")
            return
        size = self.size
        if size.width > 0 and size.height > 0 and (size.width, size.height) != self._last_size:
            self._last_size = (size.width, size.height)
            try:
                await asyncio.to_thread(self.ws.tmux.resize_window, win, size.width, size.height)
            except (TmuxError, Exception):
                pass
        max_h = max((p.height for p in self.panes), default=size.height)
        history = max(0, max(self.offsets.values(), default=0) + max_h + 4) if any(
            self.offsets.values()
        ) else 0
        history = min(700, history)
        target_tab = self.tab
        try:
            if target_tab is not None:
                panes, captures = await asyncio.to_thread(self.ws.capture_panes, target_tab, history)
            else:
                panes = await asyncio.to_thread(self.ws.tmux.list_panes, win)
                captures = {}
                for pane in panes:
                    captures[pane.id] = await asyncio.to_thread(
                        self.ws.tmux.capture, pane.id, history
                    )
        except Exception as exc:  # tmux vanished mid-poll
            self.show_message(f"terminal unavailable\n{exc}")
            return
        # The user may have switched tabs while the capture was in flight.
        if self.tab is not target_tab or (self.window_id and not self.window_id == win):
            return
        if not panes:
            self.show_message("terminal exited")
            return
        self.hide_message()
        await self._sync_views(panes, captures)
        self.panes = panes

    async def _sync_views(self, panes: list[PaneInfo], captures: dict[str, list[str]]) -> None:
        ids = [p.id for p in panes]
        stale = [pid for pid in self.views if pid not in ids]
        if stale:
            for pid in stale:
                view = self.views.pop(pid)
                try:
                    await view.remove()
                except Exception:
                    pass
        for pane in panes:
            view = self.views.get(pane.id)
            if view is None:
                view = PaneView(self, pane)
                self.views[pane.id] = view
                await self.mount(view)
            view.set_pane(pane)
            lines = self._visible_lines(pane, captures.get(pane.id, []))
            view.set_lines(lines)
            self.history_available[pane.id] = max(len(captures.get(pane.id, [])), 700)
        self.panes = panes
        await self._sync_dividers(panes)
        if self.views:
            self.hide_message()

    async def _sync_dividers(self, panes: list[PaneInfo]) -> None:
        signature = tuple((p.id, p.left, p.top, p.width, p.height) for p in panes)
        if signature == self._divider_signature:
            return
        self._divider_signature = signature
        for divider in self._dividers:
            try:
                await divider.remove()
            except Exception:
                pass
        self._dividers.clear()
        if len(panes) < 2:
            return
        for pane in panes:
            if pane.left > 0:
                divider = Static("│" * max(1, pane.height), markup=False)
                divider.styles.position = "absolute"
                divider.styles.offset = (pane.left - 1, pane.top)
                divider.styles.width = 1
                divider.styles.height = pane.height
                divider.styles.background = "#0b1016"
                divider.styles.color = "#3d444d"
                self._dividers.append(divider)
                await self.mount(divider)
            if pane.top > 0:
                divider = Static("─" * max(1, pane.width), markup=False)
                divider.styles.position = "absolute"
                divider.styles.offset = (pane.left, pane.top - 1)
                divider.styles.width = pane.width
                divider.styles.height = 1
                divider.styles.background = "#0b1016"
                divider.styles.color = "#3d444d"
                self._dividers.append(divider)
                await self.mount(divider)

    def _visible_lines(self, pane: PaneInfo, captured: list[str]) -> list[str]:
        lines = list(captured)
        if lines and lines[-1] == "":
            lines.pop()
        height = max(1, pane.height)
        offset = min(self.offsets.get(pane.id, 0), max(0, len(lines) - height))
        if offset:
            visible = lines[-(height + offset) : len(lines) - offset]
        else:
            visible = lines[-height:]
        if len(visible) < height:
            visible = [""] * (height - len(visible)) + visible
        width = max(1, pane.width)
        out: list[str] = []
        for line in visible:
            if len(line) > width * 4:
                line = line[: width * 8]
            out.append(line)
        if pane.dead:
            out[-1] = " [process exited] "
        return out

    # -- size / focus --------------------------------------------------
    def on_resize(self, event: events.Resize) -> None:
        if self._resize_timer:
            self._resize_timer.stop()
        self._resize_timer = self.set_timer(0.12, self._apply_size)

    def _apply_size(self) -> None:
        win = self.target_window
        if not win or self.size.width < 5 or self.size.height < 3:
            return
        try:
            self.ws.tmux.resize_window(win, self.size.width, self.size.height)
        except TmuxError:
            pass
        self._last_size = (self.size.width, self.size.height)
        self._tick_now()

    def on_focus(self, event: events.Focus) -> None:
        self._tick_now()

    # -- input ---------------------------------------------------------
    def action_send_tab(self) -> None:
        self._send_key("Tab")

    def action_send_btab(self) -> None:
        self._send_key("BTab")

    def _send_key(self, key: str, *, reset_scroll: bool = True) -> None:
        if reset_scroll and self.offsets:
            self.offsets.clear()
            self.app.refresh_tabstrip()
        try:
            if self.tab is not None:
                self.ws.send_key(self.tab, key)
            elif self.window_id:
                pane = self._active_pane()
                if pane:
                    self.ws.tmux.send_key(pane.id, key)
        except TmuxError:
            pass

    def _send_text(self, text: str) -> None:
        if self.offsets:
            self.offsets.clear()
            self.app.refresh_tabstrip()
        try:
            if self.tab is not None:
                self.ws.send_text(self.tab, text)
            elif self.window_id:
                pane = self._active_pane()
                if pane:
                    self.ws.tmux.send_literal(pane.id, text)
        except TmuxError:
            pass

    def on_key(self, event: events.Key) -> None:
        if self.tab is not None and self.tab.id in self.ws.missing_tabs:
            if event.key in {"r", "enter"}:
                event.stop()
                self.app.revive_active_tab()
            return
        if event.key in self.passthrough_keys:
            return
        if self.tab is None and not self.window_id:
            return
        key = event.key
        if key in KEY_MAP:
            event.stop()
            event.prevent_default()
            self._send_key(KEY_MAP[key])
            return
        if key in {"space"}:
            event.stop()
            event.prevent_default()
            self._send_text(" ")
            return
        if key.startswith("ctrl+") and len(key) == 6:
            event.stop()
            event.prevent_default()
            self._send_key("C-" + key[-1])
            return
        if key.startswith("alt+") and len(key) >= 5:
            suffix = key[4:]
            if len(suffix) == 1:
                event.stop()
                event.prevent_default()
                self._send_key("M-" + suffix)
            return
        if event.is_printable and event.character:
            event.stop()
            event.prevent_default()
            self._send_text(event.character)
            return
        # Unknown special key: swallow rather than leak into focus navigation.
        event.stop()
        event.prevent_default()

    def on_paste(self, event: events.Paste) -> None:
        event.stop()
        self._send_text(event.text.replace("\r\n", "\r"))
