"""Welcome / empty state for the center column."""

from __future__ import annotations

from rich.console import Group, RenderableType
from rich.text import Text
from textual import events
from textual.widget import Widget

from .. import SIGN_OFF, __version__


LOGO = [
    "  ██████                            ",
    "  ██   ██  ▄▄▄   ██      ▄▄▄   ██▄██ ▄▄▄",
    "  ██████  █▄▄█   ██      █▄▄█   ██▀██ █▄▄█",
    "  ██   ██ █▄▄█   ██▄▄▄   █▄▄█   ██  █ █▄▄█",
]


class WelcomePane(Widget):
    DEFAULT_CSS = """
    WelcomePane {
        height: 1fr;
        width: 1fr;
        background: #0b1016;
        color: #c9d1d9;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.regions: list[tuple[int, int, int, str]] = []
        self.hover = ""

    def _card(self) -> tuple[list[Text], list[tuple[int, str]]]:
        app = self.app
        ws = app.ws
        state = ws.state
        lines: list[Text] = []
        actions: list[tuple[int, str]] = []

        def add(text: str, style: str = "") -> None:
            lines.append(Text(text, style=style))

        def blank() -> None:
            lines.append(Text(""))

        def button(label: str, action: str, style: str = "") -> None:
            line = Text()
            line.append("  ")
            line.append(f" {label} ", style=style or "bold #58a6ff")
            actions.append((len(lines), action))
            lines.append(line)

        if getattr(app, "booting", False):
            add("balamba", style="bold #58a6ff")
            blank()
            add("restoring workspace…", style="bold #e6edf3")
            add(getattr(app, "boot_message", "connecting to tmux…"), style="#8b949e")
            blank()
            add("chrome  Textual", style="#484f58")
            add("content  tmux (dedicated -L balamba server)", style="#484f58")
            return lines, actions

        error = ws.startup_error or getattr(app, "fatal_error", "")
        if error:
            add("balamba", style="bold #f85149")
            blank()
            add("state could not be loaded", style="bold #e6edf3")
            add(error, style="#8b949e")
            blank()
            add(f"state file: {ws.config.state_file}", style="#6e7681")
            button("open doctor", "doctor", "bold #0d1117 on #d29922")
            return lines, actions

        for i, row in enumerate(LOGO):
            add(row, style="bold #58a6ff" if i == 0 else "#58a6ff")
        blank()
        add("agent workspaces  ·  projects → tasks → terminals", style="#8b949e")
        add("keyboard-first, mouse-friendly, restores everything", style="#6e7681")
        blank()

        project = state.active_project_obj()
        if not state.projects:
            add("Start with a git main checkout", style="bold #e6edf3")
            add("Worktrees, branches and terminals are created for you.", style="#8b949e")
            blank()
            button("p  add project", "add-project", "bold #0d1117 on #58a6ff")
            button("F1  about & shortcuts", "about", "bold #8b949e on #161b22")
            blank()
            add("Nothing is downloaded and no network is used.", style="#484f58")
            add(SIGN_OFF + f" · v{__version__}", style="#30363d")
            return lines, actions

        tabs = state.context_tabs()
        if not tabs:
            add(f"{project.name}", style="bold #e6edf3")
            add(f"{project.path}", style="#6e7681")
            blank()
            add("No terminals in this project yet.", style="#8b949e")
            add("Create a task (worktree) or a scratch shell in the checkout.", style="#6e7681")
            blank()
            button("n  new task", "new-task", "bold #0d1117 on #3fb950")
            button("t  scratch shell", "new-terminal", "bold #0d1117 on #58a6ff")
            blank()
            add("Tasks appear under the project on the left.", style="#484f58")
            add(SIGN_OFF, style="#30363d")
            return lines, actions

        tab = state.active_tab_obj()
        if tab and tab.id in ws.missing_tabs:
            add("Terminal is not running", style="bold #f85149")
            add(f"{tab.label()} · {tab.cwd}", style="#8b949e")
            blank()
            add("The tmux content window vanished, but the saved tab remains.", style="#6e7681")
            add("Reattaching uses the same agent session id.", style="#6e7681")
            blank()
            button("r  reattach terminal", "revive", "bold #0d1117 on #d29922")
            button("c-a x  close tab", "close-tab", "bold #8b949e on #161b22")
            return lines, actions

        stats = ws.stats()
        add(f"{stats['projects']} projects · {stats['tasks']} tasks · {stats['tabs']} terminals", style="#8b949e")
        blank()
        add("Select a row in the tree, or press t to open another terminal.", style="#6e7681")
        add("The git panel is read-only and refreshes every two seconds.", style="#484f58")
        blank()
        add(SIGN_OFF, style="#30363d")
        return lines, actions

    def render(self) -> RenderableType:
        lines, actions = self._card()
        self.regions.clear()
        width = max(30, self.content_size.width)
        height = max(8, self.content_size.height)
        top = max(0, (height - len(lines)) // 2)
        rendered: list[Text] = [Text("") for _ in range(top)]
        for i, line in enumerate(lines):
            y = top + i
            for action_y, action in actions:
                if action_y == i:
                    x0 = 2
                    x1 = max(2, len(line.plain))
                    self.regions.append((y, x0, x1, action))
                    if action == self.hover:
                        line.stylize("underline", 1, len(line.plain))
            rendered.append(line)
        return Group(*rendered)

    def _action_at(self, x: int, y: int) -> str:
        for ry, x0, x1, action in self.regions:
            if ry == y and x0 <= x < x1:
                return action
        return ""

    def on_click(self, event: events.Click) -> None:
        action = self._action_at(event.x, event.y)
        if action:
            event.stop()
            self.app.welcome_action(action)
        else:
            event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        action = self._action_at(event.x, event.y)
        if action != self.hover:
            self.hover = action
            self.refresh()
