"""dialogs.py — Textual screens: prompts, menus, confirmations, diff pager,
editor popup. These replace the spec's `display-popup` flows entirely —
every dialog is a Textual ModalScreen with its own key and mouse handling
(README: "Popups & prompts")."""

from __future__ import annotations

from typing import Any, Callable, Iterable

from rich.style import Style
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, Static


class PromptScreen(ModalScreen[tuple[bool, str]]):
    """Single-line prompt with validation. Result: (ok, value)."""

    CSS = """
    PromptScreen { align: center middle; }
    #prompt-box {
        width: 68; height: auto;
        border: thick $accent;
        background: $panel;
        padding: 1 2;
    }
    #prompt-box Label { width: 1fr; }
    #prompt-msg { color: $text-error; height: auto; min-height: 0; }
    #prompt-hint { color: $text-muted; text-style: dim; }
    """

    def __init__(self, title: str, *, value: str = "", placeholder: str = "",
                 validate: Callable[[str], tuple[bool, str]] | None = None) -> None:
        super().__init__()
        self.title = title
        self.initial = value
        self.placeholder = placeholder
        self.validate = validate

    def compose(self) -> ComposeResult:
        with Vertical(id="prompt-box"):
            yield Label(self.title, id="prompt-title")
            yield Input(value=self.initial, placeholder=self.placeholder,
                        id="prompt-input")
            yield Static("", id="prompt-msg")
            yield Static("Enter to confirm · Esc to cancel", id="prompt-hint")

    def on_mount(self) -> None:
        inp = self.query_one(Input)
        inp.focus()
        inp.cursor_position = len(inp.value)

    async def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            event.stop()
            self.dismiss((False, ""))
        elif event.key == "enter":
            event.stop()
            value = self.query_one(Input).value
            ok, msg = True, ""
            if self.validate:
                ok, msg = self.validate(value)
            if ok:
                self.dismiss((True, value))
            else:
                self.query_one("#prompt-msg", Static).update(
                    Text(msg or "invalid", style="bold red"))


class ChoiceScreen(ModalScreen[tuple[bool, Any]]):
    """Vertical menu. Result: (ok, value). Supports right-click anchoring."""

    CSS = """
    ChoiceScreen { align: center middle; }
    #choice-box {
        width: auto; min-width: 26; height: auto;
        border: thick $primary;
        background: $panel;
        padding: 0 1;
    }
    """
    BOX_ID = "choice-box"

    def __init__(self, title: str, choices: Iterable[tuple[Any, str]],
                 *, anchor: tuple[int, int] | None = None) -> None:
        super().__init__()
        self.choices = list(choices)
        self.title = title
        self.anchor = anchor
        self.cursor = 0

    def compose(self) -> ComposeResult:
        box = Vertical(id=self.BOX_ID)
        yield box

    def on_mount(self) -> None:
        box = self.query_one("#choice-box")
        if self.anchor is not None:
            self.styles.background = "transparent"
            box.styles.position = "absolute"
            x, y = self.anchor
            box.styles.left = max(0, min(x, self.app.size.width - 32))
            box.styles.top = max(0, min(y, self.app.size.height - self._desired_height() - 1))
        box.mount(*self._rows())
        self._paint()

    def _desired_height(self) -> int:
        return len(self.choices) + (2 if self.title else 1)

    def _rows(self):
        widgets = []
        if self.title:
            widgets.append(Static(Text(self.title, style="bold"), classes="choice-title"))
        for i, (value, label) in enumerate(self.choices):
            s = Static("", classes="choice-row")
            s.data_value = value  # type: ignore[attr-defined]
            s.data_index = i      # type: ignore[attr-defined]
            widgets.append(s)
        return widgets

    def _paint(self) -> None:
        rows = self.query(".choice-row")
        for i, w in enumerate(rows):
            if i == self.cursor:
                w.update(Text(f"▸ {self.choices[i][1]}", style="reverse"))
            else:
                w.update(Text(f"  {self.choices[i][1]}"))

    async def on_key(self, event: events.Key) -> None:
        if event.key in ("down", "j"):
            self.cursor = min(len(self.choices) - 1, self.cursor + 1)
        elif event.key in ("up", "k"):
            self.cursor = max(0, self.cursor - 1)
        elif event.key == "enter":
            self._pick(self.cursor)
        elif event.key == "escape":
            self.dismiss((False, None))
            return
        elif event.key.isdigit() and 1 <= int(event.key) <= len(self.choices):
            self._pick(int(event.key) - 1)
        else:
            return
        event.stop()
        self._paint()

    def _pick(self, i: int) -> None:
        self.dismiss((True, self.choices[i][0]))

    async def on_mouse_up(self, event: events.MouseUp) -> None:
        widget = self.app.get_widget_at(event.x, event.y)[0]
        if isinstance(widget, Static) and "choice-row" in widget.classes:
            self.cursor = widget.data_index  # type: ignore[attr-defined]
            self._pick(self.cursor)
            event.stop()

    async def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        event.stop()
        self.cursor = max(0, self.cursor - 1)
        self._paint()

    async def on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        event.stop()
        self.cursor = min(len(self.choices) - 1, self.cursor + 1)
        self._paint()


class ConfirmScreen(ModalScreen[dict]):
    """Warning/confirmation with Cancel/Continue and an optional toggle row.

    Result dict: {"confirmed": bool, "toggle": bool}
    """

    CSS = """
    ConfirmScreen { align: center middle; }
    #confirm-box {
        width: 72; height: auto;
        border: thick $primary;
        background: $panel;
        padding: 1 2;
    }
    #confirm-lines Label, #confirm-lines Static { width: 1fr; }
    #confirm-hint { color: $text-muted; }
    """

    def __init__(self, title: str, lines: list[str | Text], *,
                 continue_label: str = "Continue", cancel_label: str = "Cancel",
                 toggle_label: str | None = None, toggle_on: bool = False,
                 warnings: bool = False) -> None:
        super().__init__()
        self.title = title
        self.lines = lines
        self.continue_label = continue_label
        self.cancel_label = cancel_label
        self.toggle_label = toggle_label
        self.toggle_on = toggle_on
        self.warnings = warnings

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Label(Text(self.title, style="bold"))
            for ln in self.lines:
                yield Static(ln if isinstance(ln, Text) else Text(ln))
            if self.toggle_label:
                yield Static("", id="confirm-toggle")
            yield Static(
                f"[ {self.cancel_label} ]   [ {self.continue_label} ]   ·   "
                "n/Esc cancels · y/Enter continues"
                + ("   ·   space toggles option" if self.toggle_label else ""),
                id="confirm-hint")

    def on_mount(self) -> None:
        self._paint_toggle()

    def _paint_toggle(self) -> None:
        if not self.toggle_label:
            return
        box = "[x]" if self.toggle_on else "[ ]"
        style = "bold green" if self.toggle_on else ""
        self.query_one("#confirm-toggle", Static).update(
            Text(f"{box} {self.toggle_label}", style=style))

    async def on_key(self, event: events.Key) -> None:
        if event.key in ("y", "enter"):
            event.stop()
            self.dismiss({"confirmed": True, "toggle": self.toggle_on})
        elif event.key in ("n", "escape", "c"):
            event.stop()
            self.dismiss({"confirmed": False, "toggle": self.toggle_on})
        elif event.key in ("space", "x", "b", "t") and self.toggle_label:
            event.stop()
            self.toggle_on = not self.toggle_on
            self._paint_toggle()


class DiffScreen(ModalScreen[None]):
    """Read-only pager for `git diff` output (in-app scroll, no `less`)."""

    CSS = """
    DiffScreen { align: center middle; }
    #diff-box {
        width: 96%; height: 90%;
        border: thick $primary;
        background: #0d0d12;
        padding: 0 1;
    }
    #diff-body { width: 1fr; height: 1fr; }
    """

    def __init__(self, title: str, text: str) -> None:
        super().__init__()
        self.title = title
        self.lines = text.splitlines() or ["(empty diff)"]
        self.view_top = 0
        self.view_rows = 20

    def compose(self) -> ComposeResult:
        with Vertical(id="diff-box"):
            yield Static(self._body, id="diff-body")

    @property
    def _body(self) -> Text:
        rows = self.view_rows
        out = Text(justify="left", end="")
        out.append(Text(self.title + " · j/k/↑/↓ PgUp/PgDn scroll · g/G jump · q close",
                        style="bold"))
        out.append("\n")
        view = self.lines[self.view_top:self.view_top + max(1, rows - 1)]
        for i, ln in enumerate(view):
            out.append(self._colorize(ln))
            if i < len(view) - 1:
                out.append("\n")
        return out

    @staticmethod
    def _colorize(line: str) -> Text:
        if line.startswith("+++") or line.startswith("---"):
            return Text(line, style="bold cyan")
        if line.startswith("@@"):
            return Text(line, style="bold yellow")
        if line.startswith("+"):
            return Text(line, style="green")
        if line.startswith("-"):
            return Text(line, style="red")
        if line.startswith(("diff ", "index ", "deleted ", "new file",
                            "old mode", "new mode")):
            return Text(line, style=Style(dim=True))
        return Text(line)

    def on_mount(self) -> None:
        self.call_after_refresh(self._measure)

    def _measure(self) -> None:
        body = self.query_one("#diff-body", Static)
        self.view_rows = max(3, body.size.height)
        self._repaint()

    def _repaint(self) -> None:
        self.query_one("#diff-body", Static).update(self._body)

    async def on_resize(self, event: events.Resize) -> None:
        self.call_after_refresh(self._measure)

    async def on_key(self, event: events.Key) -> None:
        rows = max(3, self.view_rows - 1)
        step = {
            "up": -1, "k": -1, "down": 1, "j": 1,
            "pageup": -rows, "b": -rows, "pagedown": rows, "f": rows,
            "space": rows,
        }.get(event.key)
        if event.key in ("g", "home"):
            self.view_top = 0
        elif event.key in ("G", "end"):
            self.view_top = max(0, len(self.lines) - rows)
        elif event.key in ("q", "escape"):
            self.dismiss(None)
            return
        elif step is not None:
            self.view_top = max(0, min(max(0, len(self.lines) - rows),
                                      self.view_top + step))
        else:
            return
        event.stop()
        self._repaint()

    async def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        event.stop()
        self.view_top = max(0, self.view_top - 3)
        self._repaint()

    async def on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        event.stop()
        self.view_top = min(max(0, len(self.lines) - 3), self.view_top + 3)
        self._repaint()


class EditorScreen(ModalScreen[int]):
    """`e` — $EDITOR in the worktree, hosted in a TerminalWidget.

    Replaces the spec's `display-popup`: the three-column layout stays behind
    the modal, exactly as the popup preserved it under tmux."""

    CSS = """
    EditorScreen { align: center middle; }
    #editor-box {
        width: 92%; height: 88%;
        border: double $success;
        background: #000000;
    }
    """

    def __init__(self, terminal_widget) -> None:
        super().__init__()
        self.terminal_widget = terminal_widget

    def compose(self) -> ComposeResult:
        from textual.containers import Container
        with Container(id="editor-box"):
            yield self.terminal_widget

    def on_mount(self) -> None:
        self.terminal_widget.focus()
        self.call_after_refresh(self._settle)

    def _settle(self) -> None:
        w = self.terminal_widget
        # the child may already have produced output (or exited) while the
        # widget was not mounted yet — drain the buffers now
        w._flush_pending()
        if getattr(self, "_pending_close", False):
            self.dismiss(0)
            return
        w._drain_exit()


class KeyHelpScreen(ModalScreen[None]):
    """C-a ? — bindings reference, includes the sign-off line (req. 15)."""

    CSS = """
    KeyHelpScreen { align: center middle; }
    #help-box {
        width: 78; height: auto; max-height: 90%;
        border: thick $primary;
        background: $panel;
        padding: 1 2;
    }
    """

    def __init__(self, sections: list[tuple[str, list[tuple[str, str]]]],
                 footer: str = "") -> None:
        super().__init__()
        self.sections = sections
        self.footer = footer

    def compose(self) -> ComposeResult:
        body = Text()
        for title, rows in self.sections:
            body.append(Text(title + "\n", style="bold underline"))
            for key, desc in rows:
                body.append(f"  {key:<18}", style="cyan")
                body.append(desc + "\n")
        if self.footer:
            body.append("\n" + self.footer + "\n", style="italic")
        body.append("Esc / q to close", style="dim")
        with Vertical(id="help-box"):
            yield Static(body)

    async def on_key(self, event: events.Key) -> None:
        if event.key in ("escape", "q"):
            event.stop()
            self.dismiss(None)
