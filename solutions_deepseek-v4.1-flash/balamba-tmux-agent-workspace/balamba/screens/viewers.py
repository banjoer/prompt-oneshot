"""Full-screen Textual viewers: diff pager, editor host, about and help."""

from __future__ import annotations

import asyncio

from rich.console import Group, RenderableType
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, Static

from .. import AUTHOR, PRODUCED, SIGN_OFF, __version__
from ..widgets.terminal import TerminalArea


class DiffView(Widget, can_focus=True):
    DEFAULT_CSS = """
    DiffView {
        height: 1fr;
        background: #0a0e14;
        color: #c9d1d9;
        padding: 0 1;
        overflow: hidden;
    }
    """

    BINDINGS = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.lines: list[str] = []
        self.x_offset = 0
        self.y_offset = 0
        self.message = "loading diff…"

    def set_content(self, text: str) -> None:
        self.lines = text.replace("\r\n", "\n").replace("\r", "").split("\n")
        if self.lines and self.lines[-1] == "":
            self.lines.pop()
        self.message = "empty diff" if not self.lines else ""
        self.y_offset = 0
        self.x_offset = 0
        self.refresh()

    def set_error(self, text: str) -> None:
        self.lines = []
        self.message = text
        self.refresh()

    @property
    def total(self) -> int:
        return len(self.lines)

    def _line(self, raw: str, number: int, width: int) -> Text:
        gutter = f"{number:>5} "
        out = Text(gutter, style="#30363d")
        try:
            part = Text.from_ansi(raw)
        except Exception:
            part = Text(raw)
        part.expand_tabs(4)
        if self.x_offset:
            part = part[self.x_offset :]
        available = max(1, width - len(gutter))
        if part.cell_len > available:
            part.truncate(available)
        elif part.cell_len < available:
            part.pad_right(available - part.cell_len)
        if not part.spans:
            if raw.startswith("+++") or raw.startswith("---"):
                part.stylize("bold #8b949e")
            elif raw.startswith("+"):
                part.stylize("#3fb950")
            elif raw.startswith("-"):
                part.stylize("#f85149")
            elif raw.startswith("@@"):
                part.stylize("bold #58a6ff")
            elif raw.startswith("diff "):
                part.stylize("bold #bc8cff")
        out.append_text(part)
        return out

    def render(self) -> RenderableType:
        width = max(10, self.content_size.width)
        height = max(1, self.content_size.height)
        if not self.lines:
            return Text(self.message, style="italic #6e7681")
        max_offset = max(0, len(self.lines) - height)
        self.y_offset = max(0, min(self.y_offset, max_offset))
        visible = self.lines[self.y_offset : self.y_offset + height]
        lines = [self._line(raw, self.y_offset + i + 1, width) for i, raw in enumerate(visible)]
        return Group(*lines)

    def _move(self, delta: int) -> None:
        height = max(1, self.size.height)
        max_offset = max(0, len(self.lines) - height)
        self.y_offset = max(0, min(max_offset, self.y_offset + delta))
        self.refresh()
        try:
            self.screen.update_footer()
        except Exception:
            pass

    def on_key(self, event: events.Key) -> None:
        if event.key in {"j", "down"}:
            event.stop()
            self._move(1)
        elif event.key in {"k", "up"}:
            event.stop()
            self._move(-1)
        elif event.key == "pagedown":
            event.stop()
            self._move(max(1, self.size.height - 1))
        elif event.key == "pageup":
            event.stop()
            self._move(-max(1, self.size.height - 1))
        elif event.key in {"h", "left"}:
            event.stop()
            self.x_offset = max(0, self.x_offset - 4)
            self.refresh()
            try:
                self.screen.update_footer()
            except Exception:
                pass
        elif event.key in {"l", "right"}:
            event.stop()
            self.x_offset += 4
            self.refresh()
            try:
                self.screen.update_footer()
            except Exception:
                pass
        elif event.key == "home":
            event.stop()
            self.x_offset = 0
            self._move(-10_000)
        elif event.key == "end":
            event.stop()
            self._move(10_000)
        elif event.key == "g":
            event.stop()
            self._move(-10_000)
        elif event.key == "G":
            event.stop()
            self._move(10_000)

    def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        event.stop()
        self._move(-3)

    def on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        event.stop()
        self._move(3)


class DiffScreen(ModalScreen):
    DEFAULT_CSS = """
    DiffScreen {
        align: center middle;
        background: #05070a;
    }
    #diff-box {
        width: 94%;
        height: 92%;
        background: #0d1117;
        border: round #58a6ff;
    }
    #diff-title {
        height: 1;
        padding: 0 1;
        background: #161b22;
        color: #e6edf3;
        text-style: bold;
    }
    #diff-footer {
        height: 1;
        padding: 0 1;
        background: #0b0f14;
        color: #6e7681;
    }
    """

    BINDINGS = [("escape", "close_diff", "close"), ("q", "close_diff", "close")]

    def __init__(self, title: str, **kwargs):
        super().__init__(**kwargs)
        self.title_text = title

    def compose(self) -> ComposeResult:
        with Vertical(id="diff-box"):
            yield Static(self.title_text, id="diff-title", markup=False)
            yield DiffView()
            yield Static(
                "j/k scroll · h/l pan · PgUp/PgDn · q / esc close",
                id="diff-footer",
                markup=False,
            )

    def on_mount(self) -> None:
        self.query_one(DiffView).focus()

    def set_content(self, text: str, label: str = "") -> None:
        self.query_one(DiffView).set_content(text)
        if label:
            self.query_one("#diff-title", Static).update(f" DIFF   {label}")
        self.update_footer()

    def set_error(self, text: str) -> None:
        self.query_one(DiffView).set_error(text)

    def action_close_diff(self) -> None:
        self.dismiss(None)

    def update_footer(self) -> None:
        view = self.query_one(DiffView)
        self.query_one("#diff-footer", Static).update(
            f" {view.total} lines · y {view.y_offset + 1} · x {view.x_offset}  "
            "   j/k scroll · h/l pan · q / esc close"
        )


class EditorScreen(ModalScreen):
    DEFAULT_CSS = """
    EditorScreen {
        background: #05070a;
        align: center middle;
    }
    #editor-box {
        width: 96%;
        height: 94%;
        background: #0d1117;
        border: round #bc8cff;
    }
    #editor-head {
        height: 1;
        background: #161b22;
        padding: 0 1;
    }
    #editor-head Static {
        width: 1fr;
        height: 1;
        color: #e6edf3;
    }
    #close-editor {
        height: 1;
        min-width: 14;
        border: none;
        background: #21262d;
        color: #e6edf3;
        padding: 0 1;
    }
    #editor-foot {
        height: 1;
        background: #0b0f14;
        color: #6e7681;
        padding: 0 1;
    }
    """

    BINDINGS = [("f10", "close_editor", "close editor")]

    def __init__(self, ws, window_id: str, label: str, cwd: str, **kwargs):
        super().__init__(**kwargs)
        self.ws = ws
        self.window_id = window_id
        self.label = label
        self.cwd = cwd
        self.terminal: TerminalArea | None = None
        self._closed = False

    def compose(self) -> ComposeResult:
        with Vertical(id="editor-box"):
            with Horizontal(id="editor-head"):
                yield Static(f" EDITOR   {self.label}   {self.cwd}", markup=False)
                yield Button("Close · F10", id="close-editor")
            self.terminal = TerminalArea(self.ws, window_id=self.window_id)
            yield self.terminal
            yield Static(
                " F10 close · editor keys go straight to the terminal · mouse wheel scrolls",
                id="editor-foot",
                markup=False,
            )

    def on_mount(self) -> None:
        self.terminal.passthrough_keys = {"f10"}
        self.terminal.focus()
        self.set_interval(0.8, self._check_alive)

    def _check_alive(self) -> None:
        try:
            panes = self.ws.tmux.list_panes(self.window_id)
        except Exception:
            panes = []
        if not panes or all(p.dead for p in panes):
            try:
                self.query_one("#editor-foot", Static).update(
                    " editor exited · press F10 to close this overlay"
                )
            except Exception:
                pass

    def action_close_editor(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.dismiss(self.window_id)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-editor":
            self.action_close_editor()


class InfoScreen(ModalScreen):
    DEFAULT_CSS = """
    InfoScreen {
        align: center middle;
        background: #05070a;
    }
    #info-box {
        width: 88%;
        height: 88%;
        background: #0d1117;
        border: round #58a6ff;
    }
    #info-head {
        height: 1;
        padding: 0 1;
        background: #161b22;
        color: #e6edf3;
        text-style: bold;
    }
    #info-scroll {
        height: 1fr;
        padding: 1 2;
        background: #0d1117;
    }
    #info-foot {
        height: 1;
        padding: 0 1;
        background: #0b0f14;
        color: #6e7681;
    }
    """

    BINDINGS = [("escape", "close_info", "close"), ("q", "close_info", "close")]

    def __init__(self, title: str, body: Text, **kwargs):
        super().__init__(**kwargs)
        self.title_text = title
        self.body = body

    def compose(self) -> ComposeResult:
        with Vertical(id="info-box"):
            yield Static(self.title_text, id="info-head", markup=False)
            with VerticalScroll(id="info-scroll"):
                yield Static(self.body, id="info-body", markup=False)
            yield Static(" esc / q close", id="info-foot", markup=False)

    def on_mount(self) -> None:
        self.query_one("#info-scroll", VerticalScroll).focus()

    def action_close_info(self) -> None:
        self.dismiss(None)


def _kv(lines: list[Text], key: str, value: str, *, key_style: str = "#58a6ff") -> None:
    line = Text()
    line.append(f"{key:<12}", style=key_style)
    line.append(value, style="#c9d1d9")
    lines.append(line)


def about_body(ws) -> Text:
    cfg = ws.config
    stats = ws.stats()
    lines: list[Text] = []
    logo = [
        "  ██████                            ",
        "  ██   ██  ▄▄▄   ██      ▄▄▄   ██▄██ ▄▄▄",
        "  ██████  █▄▄█   ██      █▄▄█   ██▀██ █▄▄█",
        "  ██   ██ █▄▄█   ██▄▄▄   █▄▄█   ██  █ █▄▄█",
    ]
    for i, row in enumerate(logo):
        lines.append(Text(row, style="#58a6ff" if i else "bold #58a6ff"))
    lines.append(Text(""))
    lines.append(Text("  agent workspaces · projects → tasks → terminals", style="#8b949e"))
    lines.append(Text("  chrome and interaction: Python + Textual (textualize)", style="#8b949e"))
    lines.append(Text("  terminal content: dedicated tmux server (content only)", style="#8b949e"))
    lines.append(Text(""))
    lines.append(Text(f"  {SIGN_OFF}", style="bold #e6edf3"))
    lines.append(Text(f"  version {__version__} · built {PRODUCED} · by {AUTHOR}", style="#8b949e"))
    lines.append(Text(f"  state   {ws.config.state_file}", style="#6e7681"))
    lines.append(Text(f"  config  {cfg.config_file}", style="#6e7681"))
    lines.append(Text(f"  tmux    socket -L {cfg.tmux_socket} · mouse off · status off", style="#6e7681"))
    lines.append(Text(""))
    lines.append(Text("  workspace", style="bold #3fb950"))
    _kv(lines, "projects", str(stats["projects"]), key_style="#3fb950")
    _kv(lines, "tasks", str(stats["tasks"]), key_style="#3fb950")
    _kv(lines, "terminals", str(stats["tabs"]), key_style="#3fb950")
    _kv(lines, "agents", str(stats["agents"]), key_style="#3fb950")
    _kv(
        lines,
        "widths",
        f"tree {cfg.tree_width} · git {cfg.git_width} · prefix {cfg.prefix_key}",
        key_style="#3fb950",
    )
    _kv(lines, "agents", ", ".join(cfg.agents), key_style="#3fb950")
    lines.append(Text(""))
    lines.append(Text("  a Textual reinterpretation", style="bold #bc8cff"))
    lines.append(
        Text(
            "  The original challenge builds chrome from tmux panes, formats and\n"
            "  mouse bindings.  Here every sidebar, tab, dialog, key and click is a\n"
            "  Textual widget/screen/event; tmux hosts only terminal content.\n"
            "  See README.md for every deviation.",
            style="#8b949e",
        )
    )
    lines.append(Text(""))
    lines.append(Text("  health", style="bold #d29922"))
    try:
        for label, ok, detail in ws.doctor_lines():
            marker = "✓" if ok else "✗"
            branch = Text()
            branch.append(f"  {marker} ", style="#3fb950" if ok else "#f85149")
            branch.append(f"{label:<10}", style="#8b949e")
            branch.append(str(detail), style="#6e7681")
            lines.append(branch)
    except Exception as exc:
        lines.append(Text(f"  could not inspect: {exc}", style="#f85149"))
    return _join(lines)


def _join(lines: list[Text]) -> Text:
    out = Text()
    for i, line in enumerate(lines):
        if i:
            out.append("\n")
        out.append_text(line)
    return out


def help_body(ws) -> Text:
    cfg = ws.config
    p = cfg.prefix_key
    if p.startswith("ctrl+"):
        p = "c-" + p.split("+", 1)[1]
    lines: list[Text] = []
    lines.append(Text("KEYBOARD", style="bold #58a6ff"))
    key = lambda action: ws.config.command_key(action)
    pairs = [
        (f"{p} {key('new-task')}", "new task (wizard)"),
        (f"{p} {key('add-project')}", "add project"),
        (f"{p} {key('new-terminal')}", "new terminal (agent | shell)"),
        (f"{p} {key('editor')}", "open editor overlay"),
        (f"{p} {key('detach')}", "detach (leave tmux server running)"),
        (f"{p} {key('redraw')}", "redraw / reload config widths"),
        (f"{p} 1..9", "switch tab"),
        (f"{p} {key('next-tab')} / {p} {key('prev-tab')}", "next / previous tab"),
        (f"{p} {key('close-tab')}", "close active tab"),
        (f"{p} {key('split-v')} / {p} {key('split-h')}", "split tab right / down"),
        (f"{p} {key('cycle-pane')}", "cycle split panes"),
        (f"{p} {key('focus-cycle')}", "cycle focus tree → terminal → git"),
        (f"{p} {key('about')}", "about / sign-off"),
    ]
    for key, label in pairs:
        _kv(lines, key, label)
    lines.append(Text(""))
    lines.append(Text("GLOBAL", style="bold #d29922"))
    _kv(lines, "F1", "about / sign-off", key_style="#d29922")
    _kv(lines, "F2", "this help", key_style="#d29922")
    _kv(lines, "F3", "doctor (server, state, worktrees, opencode)", key_style="#d29922")
    _kv(lines, "F5", "refresh git panel", key_style="#d29922")
    lines.append(Text(""))
    lines.append(Text("TREE (when the tree pane is focused)", style="bold #bc8cff"))
    tree = [
        (f"{cfg.key_for('down', 'j')} / ↓", "move down"),
        (f"{cfg.key_for('up', 'k')} / ↑", "move up"),
        (f"{cfg.key_for('expand', 'l')} / →", "expand project/task"),
        (f"{cfg.key_for('collapse', 'h')} / ←", "collapse"),
        (cfg.key_for("activate", "enter"), "activate row"),
        (cfg.key_for("new-task", "n"), "new task in selected/active project"),
        (cfg.key_for("new-terminal", "t"), "new terminal"),
        (cfg.key_for("close-task", "d"), "close selected task"),
        (cfg.key_for("editor", "e"), "open editor"),
        (cfg.key_for("add-project", "p"), "add project"),
    ]
    for key, label in tree:
        _kv(lines, key, label, key_style="#bc8cff")
    lines.append(Text(""))
    lines.append(Text("MOUSE", style="bold #3fb950"))
    mouse = [
        ("click row", "select and activate"),
        ("click chevron", "expand / collapse"),
        ("right-click", "context menu"),
        ("wheel", "scroll tree, git, terminal scrollback"),
        ("click file", "git diff overlay"),
        ("click tab", "switch tab · × closes"),
        ("drag", "Textual text selection (tmux mouse stays off)"),
    ]
    for key, label in mouse:
        _kv(lines, key, label, key_style="#3fb950")
    lines.append(Text(""))
    lines.append(Text("TERMINAL FOCUS", style="bold #d29922"))
    lines.append(Text("  Typing goes to the active tmux pane. Tab, arrows and ctrl keys are forwarded.", style="#8b949e"))
    lines.append(Text("  F10 closes the editor overlay. c-a is the app prefix (press twice for literal).", style="#8b949e"))
    lines.append(Text(""))
    lines.append(Text(f"{SIGN_OFF}", style="#6e7681"))
    return _join(lines)
