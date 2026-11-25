"""twidget.py — Textual TerminalWidget: paints a VT screen and drives a PTY.

This is where the "plain terminal sessions host the content" twist lives:
the widget is a full Textual widget — it participates in focus, key bindings,
mouse events (clicks, wheel), and resize/layout like every other pane. No tmux
involvement at all (README: "Terminal content hosting").
"""

from __future__ import annotations

import os
import sys
import threading
from typing import Callable, Optional

from rich.style import Style
from rich.text import Text
from textual import events
from textual.widget import Widget

from . import vt as vt_mod
from .term import PtySession

CURSOR_STYLE = Style(reverse=True)

_KEYMAP = {
    "enter": b"\r",
    "escape": b"\x1b",
    "backspace": b"\x7f",
    "tab": b"\t",
    "shift+tab": b"\x1b[Z",
    "insert": b"\x1b[2~",
    "delete": b"\x1b[3~",
    "home": b"\x1b[H",
    "end": b"\x1b[F",
    "pageup": b"\x1b[5~",
    "pagedown": b"\x1b[6~",
    "f1": b"\x1bOP", "f2": b"\x1bOQ", "f3": b"\x1bOR", "f4": b"\x1bOS",
    "f5": b"\x1b[15~", "f6": b"\x1b[17~", "f7": b"\x1b[18~", "f8": b"\x1b[19~",
    "f9": b"\x1b[20~", "f10": b"\x1b[21~", "f11": b"\x1b[23~", "f12": b"\x1b[24~",
    "shift+enter": b"\x1b[13;2u",
    "ctrl+enter": b"\x1b[13;5u",
    "alt+enter": b"\x1b\r",
    "ctrl+backspace": b"\x08",
    "alt+backspace": b"\x1b\x7f",
    "shift+delete": b"\x1b[3;2~",
    "ctrl+delete": b"\x1b[3;5~",
    "shift+home": b"\x1b[1;2H",
    "ctrl+home": b"\x1b[1;5H",
    "shift+end": b"\x1b[1;2F",
    "ctrl+end": b"\x1b[1;5F",
    "shift+pageup": b"\x1b[5;2~",
    "ctrl+pageup": b"\x1b[5;5~",
    "shift+pagedown": b"\x1b[6;2~",
    "ctrl+pagedown": b"\x1b[6;5~",
    "ctrl+space": b"\x00",
    "ctrl+at": b"\x00",
    "ctrl+backslash": b"\x1c",
    "ctrl+right_square_bracket": b"\x1d",
    "ctrl+asciicircum": b"\x1e",
    "ctrl+underscore": b"\x1f",
}

_ARROW_FINAL = {"up": b"A", "down": b"B", "right": b"C", "left": b"D"}

_MOD_NUM = {}  # name -> numeric modifier (xterm: 1 + shift | alt<<1 | ctrl<<2)


def _mods(name: str) -> int:
    """Numeric xterm modifier for names like 'ctrl+shift+left'."""
    mods = name.split("+")[:-1]
    if not mods:
        return 0
    bits = 0
    if "shift" in mods:
        bits += 1
    if "alt" in mods:
        bits += 2
    if "ctrl" in mods:
        bits += 4
    return bits


def encode_key(event: events.Key, vt: vt_mod.VT) -> bytes | None:
    """Translate a Textual Key event into the bytes a child xterm expects."""
    name = event.key or ""
    parts = name.split("+")
    base = parts[-1]

    if base in _ARROW_FINAL and len(parts) <= 4 and name != base:
        mod = _mods(name)
        if mod and len(parts) > 1 and parts[0] in ("ctrl", "alt", "shift"):
            return b"\x1b[1;" + str(mod + 1).encode() + _ARROW_FINAL[base]
    if base in _ARROW_FINAL:
        if vt.app_cursor_keys:
            return b"\x1bO" + _ARROW_FINAL[base]
        return b"\x1b[" + _ARROW_FINAL[base]

    if name in _KEYMAP:
        return _KEYMAP[name]

    if len(parts) == 2 and parts[0] == "ctrl" and len(parts[1]) == 1 and parts[1].isalpha():
        return bytes([ord(parts[1].lower()) - 0x60])

    if name.startswith("alt+"):
        inner = name[4:]
        if len(inner) == 1:
            return b"\x1b" + inner.encode("utf-8")
        if inner in _KEYMAP:
            return b"\x1b" + _KEYMAP[inner]
        return None

    if event.character:
        return event.character.encode("utf-8", "replace")
    if len(name) == 1:
        return name.encode("utf-8")
    return None


class TerminalWidget(Widget, can_focus=True):
    """A live terminal: VT screen + PTY child + Textual key/mouse plumbing."""

    DEFAULT_CSS = """
    TerminalWidget {
        width: 100%;
        height: 100%;
        background: #14141a;
        color: #d6d6de;
        padding: 0 0;
    }
    """

    def __init__(self,
                 session: Optional[PtySession] = None,
                 vt: Optional[vt_mod.VT] = None,
                 *,
                 title: str = "",
                 id: str | None = None,
                 on_exit: Optional[Callable[[int], None]] = None,
                 on_activity: Optional[Callable[[], None]] = None,
                 is_viewed: Optional[Callable[[], bool]] = None,
                 allow_mouse_capture: Optional[Callable[[], bool]] = None) -> None:
        super().__init__(id=id)
        self.vt = vt or vt_mod.VT(24, 80)
        self.session = session
        self.title = title
        self.on_exit_cb = on_exit
        self.on_activity = on_activity
        self.is_viewed = is_viewed or (lambda: True)
        self.allow_mouse_capture = allow_mouse_capture or (lambda: True)
        self.history_back = 0
        self._motion_button = -1
        self._dead: int | None = None
        self._pending = bytearray()      # bytes awaiting the UI thread
        self._pending_exit: int | None = None
        self._pending_lock = threading.Lock()

    # -- wiring ---------------------------------------------------------------
    def wire_session(self, session: PtySession) -> None:
        self.session = session
        session.on_data = self._child_data
        session.on_exit = self._child_exit

    def _child_data(self, data: bytes) -> None:
        # invoked on the reader thread: buffer, then hand off to the UI thread
        with self._pending_lock:
            self._pending.extend(data)
        try:
            self.app.call_from_thread(self._flush_pending)
        except Exception:
            # app not ready: bytes stay buffered and are flushed by the
            # periodic pump — nothing is ever lost.
            pass

    def _flush_pending(self) -> None:
        with self._pending_lock:
            if not self._pending:
                return
            data = bytes(self._pending)
            consumed = len(data)
        try:
            self._feed_on_ui_thread(data)
        except BaseException:
            if os.environ.get("BALAMBA_DEBUG"):
                import traceback
                traceback.print_exc()
            with self._pending_lock:
                if len(self._pending) > 1024 * 1024:
                    # poison and unbounded: drop to stay alive
                    self._pending.clear()
            raise
        with self._pending_lock:
            del self._pending[:consumed]

    def _feed_on_ui_thread(self, data: bytes) -> None:
        if os.environ.get("BALAMBA_DEBUG"):
            print(f"[feed] {self.title!r} {data[:40]!r}", file=sys.stderr)
        if not self.is_viewed():
            if self.on_activity:
                self.on_activity()
        self.vt.feed(data)
        self._drain_replies()
        if self.history_back:
            self.history_back = 0
        self.refresh()

    def _child_exit(self, code: int) -> None:
        with self._pending_lock:
            if self._pending_exit is None:
                self._pending_exit = code
        try:
            self.app.call_from_thread(self._drain_exit)
        except Exception:
            pass

    def _drain_exit(self) -> None:
        with self._pending_lock:
            code, self._pending_exit = self._pending_exit, None
        if code is not None:
            self._on_exit_on_ui(code)

    def _on_exit_on_ui(self, code: int) -> None:
        self.refresh()
        if self.on_exit_cb:
            self.on_exit_cb(code)

    def feed_note(self, note: str) -> None:
        """Print a balamba-side message into the terminal screen."""
        self.vt.feed(note.encode("utf-8", "replace") + b"\r\n")
        self.refresh()

    def _drain_replies(self) -> None:
        if self.vt.replies and self.session:
            data = bytes(self.vt.replies)
            self.vt.replies.clear()
            self.session.write(data)

    # -- layout ---------------------------------------------------------------
    def on_mount(self) -> None:
        self._apply_size()

    def on_resize(self, event: events.Resize) -> None:
        self._apply_size()

    def _apply_size(self) -> None:
        cols = self.size.width
        rows = self.size.height
        # widgets that are hidden/unlaid report size 0 — resizing the VT then
        # would destroy the live screen; keep the current geometry instead.
        if cols < 2 or rows < 2:
            return
        if (cols, rows) != (self.vt.cols, self.vt.rows):
            self.vt.resize(rows, cols)
            if self.session:
                self.session.resize(cols, rows)
        self.refresh()

    # -- rendering --------------------------------------------------------------
    def render(self) -> Text:
        text = Text(no_wrap=True, end="", justify="left")
        rows = max(1, self.size.height)
        screen = self.vt.buf.grid
        if self.vt.on_alt or self.history_back == 0:
            lines = list(screen)
            cursor_row = self.vt.row if self.show_cursor() else None
        else:
            combined = list(self.vt.scrollback) + list(screen)
            total = len(combined)
            end = total - self.history_back
            start = max(0, end - rows)
            lines = combined[start:end]
            cursor_row = None
        for i, line in enumerate(lines):
            self._append_styled_row(text, line,
                                    cursor_col=self.vt.col if i == cursor_row else None)
            if i < rows - 1:
                text.append("\n")
        for _ in range(max(0, rows - len(lines))):
            text.append("\n" + " " * self.vt.cols)
        return text

    def show_cursor(self) -> bool:
        return (self.has_focus and self.vt.cursor_visible
                and self.is_viewed())

    def _append_styled_row(self, text: Text, line: list[tuple], cursor_col: int | None) -> None:
        col = 0
        run: list[str] = []
        run_style: Style | None = None

        def flush() -> None:
            if run:
                text.append("".join(run), run_style)
                run.clear()

        for ch, style in line:
            if ch is None:                      # wide-char spare column
                col += 1
                continue
            eff = CURSOR_STYLE if cursor_col == col else style
            run.append(" " if ch == "" else ch)
            if run_style is None or run_style == eff:
                run_style = eff if run_style is None else run_style
            if run_style != eff:
                # style changed on this cell: flush previous cells
                last = run.pop()
                flush()
                run.append(last)
                run_style = eff
            col += 1
        if col < self.vt.cols:
            run.append(" " * (self.vt.cols - col))
            if run_style is None:
                run_style = Style()
        flush()

    # -- keys --------------------------------------------------------------------
    async def on_key(self, event: events.Key) -> None:
        event.stop()
        event.prevent_default()
        prefix = getattr(self.app, "prefix_key", None)
        if prefix is not None and event.key == prefix and \
                hasattr(self.app, "begin_prefix"):
            self.app.begin_prefix()          # C-a while the terminal is focused
            return
        data = encode_key(event, self.vt)
        if data is not None and self.session:
            self.session.write(data)

    # -- paste --------------------------------------------------------------------
    async def on_paste(self, event: events.Paste) -> None:
        event.stop()
        text = event.text
        if self.vt.bracketed_paste:
            payload = (b"\x1b[200~" + text.encode("utf-8", "replace")
                       + b"\x1b[201~")
        else:
            payload = text.replace("\r\n", "\r").replace("\n", "\r") \
                .encode("utf-8", "replace")
        if self.session:
            self.session.write(payload)

    # -- focus -----------------------------------------------------------------------
    def on_focus(self) -> None:
        if self.vt.focus_tracking and self.session:
            self.session.write(b"\x1b[I")

    def on_blur(self) -> None:
        if self.vt.focus_tracking and self.session:
            self.session.write(b"\x1b[O")

    # -- mouse --------------------------------------------------------------------------
    def _mouse_allowed(self) -> bool:
        return bool(self.allow_mouse_capture()) and self.vt.mouse_mode > 0

    async def on_mouse_down(self, event: events.MouseDown) -> None:
        self.focus()                     # first click focuses *and* is delivered
        if self._mouse_allowed():
            self._motion_button = max(0, event.button - 1)
            self._send_mouse(event, press=True)
            event.stop()

    async def on_mouse_up(self, event: events.MouseUp) -> None:
        if self._mouse_allowed():
            self._send_mouse(event, press=False)
            event.stop()
        self._motion_button = -1

    async def on_mouse_move(self, event: events.MouseMove) -> None:
        if self._mouse_allowed():
            if self.vt.mouse_mode >= 3 or (self.vt.mouse_mode >= 2
                                           and self._motion_button >= 0):
                self._send_mouse(event, press=True, motion=True)

    async def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        event.stop()
        if self._mouse_allowed():
            self._send_wheel(up=True)
        else:
            self._scroll_lines(3)

    async def on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        event.stop()
        if self._mouse_allowed():
            self._send_wheel(up=False)
        else:
            self._scroll_lines(-3)

    def _scroll_lines(self, n: int) -> None:
        if self.vt.on_alt:
            return
        limit = len(self.vt.scrollback)
        self.history_back = max(0, min(limit, self.history_back + n))
        self.refresh()

    def _send_wheel(self, up: bool) -> None:
        code = 64 if up else 65
        self._emit_raw(code, press=True)
        self._emit_raw(code, press=False)

    def _send_mouse(self, event, press: bool, motion: bool = False) -> None:
        btn = max(0, min(2, event.button - 1))
        code = btn | (32 if motion else 0)
        x = event.x - self.region.x
        y = event.y - self.region.y
        self._emit(event, code, press, x, y)

    def _emit_raw(self, code: int, press: bool) -> None:
        # wheel events: report the last pointer position
        x = self.app.mouse_position.x - self.region.x
        y = self.app.mouse_position.y - self.region.y
        self._emit(None, code, press, x, y)

    def _emit(self, event, code: int, press: bool, x: int, y: int) -> None:
        if not self.session:
            return
        if self.vt.mouse_sgr:
            seq = f"\x1b[<{code};{x + 1};{y + 1}{'M' if press else 'm'}"
            data = seq.encode("latin1", "replace")
        else:
            data = (b"\x1b[M" + bytes([32 + code,
                                       32 + min(254, y + 1),
                                       32 + min(254, x + 1)]))
        self.session.write(data)
