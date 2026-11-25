"""Modal dialogs — all ordinary Textual screens and widgets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, OptionList, Static
from textual.widgets.option_list import Option

from ..gitops import validate_project
from ..state import Project, Task, slugify
from ..workspace import Workspace, WorkspaceError


DIALOG_CSS = """
DialogScreen {
    align: center middle;
    background: #05070a;
}
#dialog {
    width: 78;
    max-width: 94%;
    height: auto;
    max-height: 96%;
    background: #0d1117;
    border: round #58a6ff;
    padding: 0 2;
}
#dialog-title {
    height: 1;
    text-style: bold;
    color: #e6edf3;
}
#dialog-subtitle {
    height: auto;
    color: #6e7681;
    margin-bottom: 1;
}
.dialog-label {
    height: 1;
    color: #58a6ff;
    text-style: bold;
    margin-top: 1;
}
.dialog-hint {
    height: auto;
    color: #6e7681;
}
.dialog-error {
    height: auto;
    color: #f85149;
    text-style: bold;
}
.dialog-warn {
    height: auto;
    color: #d29922;
}
.dialog-ok {
    height: auto;
    color: #3fb950;
}
.dialog-body {
    height: auto;
}
Input {
    background: #0a0e14;
    color: #e6edf3;
    border: solid #30363d;
    margin-top: 1;
}
Input:focus {
    border: solid #58a6ff;
}
OptionList {
    background: #0a0e14;
    border: solid #30363d;
    height: auto;
    max-height: 10;
    margin-top: 1;
}
OptionList > .option-list--option-highlighted {
    background: #17324d;
    color: #e6edf3;
}
Button {
    min-width: 12;
    width: auto;
    margin-right: 1;
    padding: 0 1;
}
.dialog-buttons {
    height: auto;
    margin-top: 1;
    align-horizontal: right;
}
.step-dots {
    height: 1;
    color: #30363d;
    margin-bottom: 0;
}
.details {
    height: auto;
    background: #0a0e14;
    border: solid #21262d;
    padding: 0 1;
    margin-top: 0;
}
"""


class DialogScreen(ModalScreen):
    DEFAULT_CSS = DIALOG_CSS
    BINDINGS = [("escape", "cancel", "cancel")]

    def __init__(self, title: str, subtitle: str = "", **kwargs):
        super().__init__(**kwargs)
        self.title_text = title
        self.subtitle_text = subtitle

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static(self.title_text, id="dialog-title", markup=False)
            if self.subtitle_text:
                yield Static(self.subtitle_text, id="dialog-subtitle", markup=False)
            yield from self.compose_body()

    def compose_body(self) -> ComposeResult:
        yield Static("")

    def action_cancel(self) -> None:
        self.dismiss(None)


class NewTaskScreen(DialogScreen):
    """Four-step flow: name → slug → create-from → terminal kind."""

    BINDINGS = [("escape", "cancel", "cancel")]

    def __init__(self, ws: Workspace, project: Project, **kwargs):
        from ..gitops import worktree_root_for

        super().__init__(
            "New task",
            f"{project.name} · worktrees in {worktree_root_for(project.path, ws.config.worktrees_root)}",
            **kwargs,
        )
        self.ws = ws
        self.project = project
        self.step = 0
        self.task_name = ""
        self.task_slug = ""
        self.base = "origin/main"
        self.kind = "agent"
        self.agent = ws.config.agent_default
        self._options: list[tuple[str, str]] = []
        self._error = ""

    def compose_body(self) -> ComposeResult:
        yield Static("", id="step-dots", classes="step-dots", markup=False)
        yield Static("", id="task-summary", classes="details", markup=False)
        yield Static("Task name", id="task-label", classes="dialog-label", markup=False)
        yield Input(placeholder="Fix the login redirect", id="task-input")
        yield Static("", id="task-hint", classes="dialog-hint", markup=False)
        yield Static("", id="task-error", classes="dialog-error", markup=False)
        yield OptionList(id="task-kind")
        with Horizontal(classes="dialog-buttons"):
            yield Button("Back", id="back")
            yield Button("Cancel", id="cancel")
            yield Button("Next", id="next", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#task-kind", OptionList).display = False
        self.query_one("#task-summary", Static).display = False
        self._refresh_step()
        self.query_one("#task-input", Input).focus()

    # -- step helpers --------------------------------------------------
    def _set_error(self, message: str) -> None:
        self._error = message
        self.query_one("#task-error", Static).update(message)

    def _refresh_step(self) -> None:
        dots = Text()
        labels = ["name", "slug", "create from", "terminal"]
        for i, label in enumerate(labels):
            if i < self.step:
                dots.append(f"✓ {label}", style="#3fb950")
            elif i == self.step:
                dots.append(f"● {label}", style="bold #58a6ff")
            else:
                dots.append(f"○ {label}", style="#484f58")
            if i < len(labels) - 1:
                dots.append("  ──  ", style="#30363d")
        self.query_one("#step-dots", Static).update(dots)
        inp = self.query_one("#task-input", Input)
        kind_list = self.query_one("#task-kind", OptionList)
        label = self.query_one("#task-label", Static)
        hint = self.query_one("#task-hint", Static)
        summary = self.query_one("#task-summary", Static)
        next_button = self.query_one("#next", Button)
        back_button = self.query_one("#back", Button)
        back_button.disabled = self.step == 0
        self._set_error("")

        if self.step == 0:
            inp.display = True
            kind_list.display = False
            summary.display = False
            label.update("Task name")
            inp.value = self.task_name
            inp.placeholder = "Fix the login redirect"
            hint.update("Free text, kept exactly as typed for display.")
            next_button.label = "Next"
        elif self.step == 1:
            inp.display = True
            kind_list.display = False
            summary.display = False
            label.update("Slug (folder + branch)")
            inp.value = self.task_slug or slugify(self.task_name)
            inp.placeholder = "fix-the-login-redirect"
            hint.update(
                f"Path: {self._task_path(inp.value)}\n"
                "Lowercase; spaces become '-'; colliding names get -2, -3, …"
            )
            next_button.label = "Next"
        elif self.step == 2:
            inp.display = True
            kind_list.display = False
            summary.display = False
            label.update("Create from")
            inp.value = self.base
            inp.placeholder = "origin/main"
            hint.update("Any ref accepted by git rev-parse --verify <ref>^{commit}.")
            next_button.label = "Next"
        else:
            inp.display = False
            kind_list.display = True
            summary.display = True
            label.update("Terminal kind")
            hint.update("Splits inside a tab are native tmux panes.")
            summary.update(self._summary_text())
            next_button.label = "Create task"
            self._fill_kinds()
        if self.step < 3:
            self.call_after_refresh(inp.focus)

    def _task_path(self, slug: str) -> str:
        from ..gitops import worktree_path_for

        return str(worktree_path_for(self.project.path, slug or "…", self.ws.config.worktrees_root))

    def _summary_text(self) -> str:
        from ..widgets.tabstrip import short_path

        return (
            f"name    {self.task_name}\n"
            f"slug    {self.task_slug or slugify(self.task_name)}\n"
            f"base    {self.base}\n"
            f"path    {short_path(self._task_path(self.task_slug or slugify(self.task_name)), 54)}\n"
            f"kind    {self.kind}" + (f" · {self.agent}" if self.kind == "agent" else "")
        )

    def _fill_kinds(self) -> None:
        options = self.query_one("#task-kind", OptionList)
        options.clear_options()
        self._options = []
        for name, definition in self.ws.config.agents.items():
            self._options.append(("agent", name))
            options.add_option(
                Option(
                    Text.assemble(
                        ("◆  agent · ", "#3fb950"),
                        (name, "bold #e6edf3"),
                        ("     opencode-style TUI", "#484f58"),
                    ),
                    id=f"agent:{name}",
                )
            )
        self._options.append(("shell", ""))
        shell = __import__("os").environ.get("SHELL", "/bin/sh")
        options.add_option(
            Option(Text.assemble(("▸  shell · ", "#39c5cf"), (shell, "bold #e6edf3")), id="shell:")
        )
        index = next(
            (i for i, (kind, agent) in enumerate(self._options) if kind == self.kind and agent == self.agent),
            0,
        )
        options.highlighted = index
        options.focus()

    # -- validation ----------------------------------------------------
    def _advance(self) -> None:
        if self.step == 0:
            value = self.query_one("#task-input", Input).value.strip()
            if not value:
                self._set_error("A task name is required.")
                return
            self.task_name = value
            self.task_slug = ""
            self.step = 1
            # Prefill with a best-effort unique slug.
            try:
                unique = self.ws.prepare_task_names(self.project, self.task_name, slugify(self.task_name))
                self.task_slug = unique.slug
                self._preview_suffix = unique
            except WorkspaceError as exc:
                self._set_error(str(exc))
                return
            self.query_one("#task-input", Input).value = self.task_slug
            self._refresh_step()
        elif self.step == 1:
            raw = self.query_one("#task-input", Input).value.strip() or slugify(self.task_name)
            try:
                unique = self.ws.prepare_task_names(self.project, self.task_name, raw)
            except WorkspaceError as exc:
                self._set_error(str(exc))
                return
            self.task_slug = unique.slug
            self.task_name = unique.display
            self.query_one("#task-input", Input).value = self.task_slug
            if unique.attempts > 1:
                self.notify(
                    f"Name collided; using {unique.slug} (display: {unique.display})",
                    severity="warning",
                )
            self.step = 2
            self.query_one("#task-input", Input).value = self.base
            self._refresh_step()
        elif self.step == 2:
            base = self.query_one("#task-input", Input).value.strip()
            if not base:
                self._set_error("A start ref is required.")
                return
            from ..gitops import valid_ref

            if not valid_ref(self.project.path, base):
                self._set_error(f"'{base}' does not resolve to a commit.")
                return
            self.base = base
            self.step = 3
            self._refresh_step()
        else:
            self._finish()

    def _finish(self) -> None:
        if self.step != 3:
            return
        self.dismiss(
            {
                "name": self.task_name,
                "slug": self.task_slug,
                "base": self.base,
                "kind": self.kind,
                "agent": self.agent if self.kind == "agent" else "",
            }
        )

    def _back(self) -> None:
        if self.step == 0:
            return
        if self.step == 3:
            self.step = 2
        else:
            self.step -= 1
        self._refresh_step()

    # -- events --------------------------------------------------------
    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self._advance()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        option_id = event.option.id or ""
        kind, _, agent = option_id.partition(":")
        self.kind = kind
        self.agent = agent
        self.query_one("#task-summary", Static).update(self._summary_text())
        self._finish()

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        option_id = event.option.id or ""
        kind, _, agent = option_id.partition(":")
        self.kind = kind if kind in {"agent", "shell"} else "agent"
        self.agent = agent
        if self.step == 3:
            self.query_one("#task-summary", Static).update(self._summary_text())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "next":
            self._advance()
        elif event.button.id == "back":
            self._back()
        elif event.button.id == "cancel":
            self.dismiss(None)


class AddProjectScreen(DialogScreen):
    def __init__(self, ws: Workspace, **kwargs):
        super().__init__(
            "Add project",
            "A project must be the root of a git main checkout.",
            **kwargs,
        )
        self.ws = ws

    def compose_body(self) -> ComposeResult:
        yield Static("Project path", classes="dialog-label", markup=False)
        yield Input(placeholder="~/src/my-project", id="project-path")
        yield Static(
            "git rev-parse --show-toplevel must equal this path.\n"
            "Linked worktrees are rejected with a warning.",
            classes="dialog-hint",
            markup=False,
        )
        yield Static("", id="project-status", classes="dialog-hint", markup=False)
        with Horizontal(classes="dialog-buttons"):
            yield Button("Cancel", id="cancel")
            yield Button("Add project", id="add", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#project-path", Input).focus()

    def _add(self) -> None:
        value = self.query_one("#project-path", Input).value.strip()
        status = self.query_one("#project-status", Static)
        if not value:
            status.update("Enter a path.")
            status.classes = "dialog-error"
            return
        check = validate_project(value)
        if check.is_worktree:
            status.update(f"Warning: {check.warning}. Choose the main checkout instead.")
            status.classes = "dialog-error"
            return
        if not check.ok:
            status.update(f"Not a valid project: {check.message}")
            status.classes = "dialog-error"
            return
        if self.ws.state.project_by_path(check.path):
            status.update("This project is already in balamba.")
            status.classes = "dialog-error"
            return
        self.dismiss(check.path)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self._add()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add":
            self._add()
        else:
            self.dismiss(None)


class CloseTaskScreen(DialogScreen):
    """Two-step, explicit confirmation with an opt-in branch delete."""

    def __init__(self, ws: Workspace, project: Project, task: Task, **kwargs):
        self.ws = ws
        self.project = project
        self.target_task = task
        self.warnings = ws.task_warnings(project, task)
        super().__init__("Close task", f"{project.name} › {task.name}", **kwargs)
        self.stage = 1
        self.delete_branch = False

    def compose_body(self) -> ComposeResult:
        yield Static("", id="close-stage", classes="step-dots", markup=False)
        yield Static("", id="close-warnings", classes="dialog-warn", markup=False)
        yield Static("", id="close-details", classes="details", markup=False)
        yield Checkbox("delete branch too (git branch -d)", id="delete-branch", value=False)
        yield Static("", id="close-note", classes="dialog-hint", markup=False)
        with Horizontal(classes="dialog-buttons"):
            yield Button("Cancel", id="cancel")
            yield Button("Continue", id="continue", variant="warning")

    def on_mount(self) -> None:
        self._refresh()
        self.query_one("#continue", Button).focus()

    def _refresh(self) -> None:
        stage = self.query_one("#close-stage", Static)
        warnings = self.query_one("#close-warnings", Static)
        details = self.query_one("#close-details", Static)
        note = self.query_one("#close-note", Static)
        cont = self.query_one("#continue", Button)
        if self.stage == 1:
            stage.update("● warning     ○ confirm deletion")
            if self.warnings:
                warnings.update("Warning:\n" + "\n".join(f"  ! {w}" for w in self.warnings))
            else:
                warnings.update("No dirty files or detached HEAD detected.")
            from ..widgets.tabstrip import short_path

            details.update(
                f"task      {self.target_task.name}\n"
                f"branch    {self.target_task.slug}\n"
                f"worktree  {short_path(self.target_task.path, 52)}\n"
                f"base      {self.target_task.base}"
            )
            note.update(
                "Continue leads to a second confirmation. Cancel changes nothing."
            )
            cont.label = "Continue"
        else:
            stage.update("✓ warning     ● confirm deletion")
            warnings.update(
                "Second confirmation: the worktree directory will be deleted from disk."
            )
            from ..widgets.tabstrip import short_path

            details.update(
                f"delete    {short_path(self.target_task.path, 52)}\n"
                f"branch    {'delete ' + self.target_task.slug if self.query_one('#delete-branch', Checkbox).value else 'keep (recommended)'}\n"
                f"force     {'yes — dirty worktree' if self.warnings else 'no'}"
            )
            note.update("No commits, pushes or merges. Removed from balamba state afterwards.")
            cont.label = "Delete now"
            cont.variant = "error"

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        self.delete_branch = event.value
        if self.stage == 2:
            self._refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        if event.button.id == "continue":
            if self.stage == 1:
                self.stage = 2
                self._refresh()
                self.query_one("#continue", Button).focus()
            else:
                self.dismiss({"delete_branch": self.delete_branch})


class TerminalMenuScreen(DialogScreen):
    def __init__(self, ws: Workspace, project: Project, task: Task | None, **kwargs):
        scope = f"{project.name} › {task.name}" if task else f"{project.name} · scratch"
        super().__init__("New terminal", f"{scope} · cwd {task.path if task else project.path}", **kwargs)
        self.ws = ws
        self.project = project
        self.target_task = task
        self.cwd = task.path if task else project.path
        self.kind = "agent"
        self.agent = ws.config.agent_default
        self.options: list[tuple[str, str]] = []

    def compose_body(self) -> ComposeResult:
        yield Static("Choose a terminal kind", classes="dialog-label", markup=False)
        yield OptionList(id="terminal-kind")
        yield Static("", id="terminal-hint", classes="dialog-hint", markup=False)
        with Horizontal(classes="dialog-buttons"):
            yield Button("Cancel", id="cancel")
            yield Button("Create", id="create", variant="primary")

    def on_mount(self) -> None:
        option_list = self.query_one("#terminal-kind", OptionList)
        self.options = []
        for name, definition in self.ws.config.agents.items():
            self.options.append(("agent", name))
            option_list.add_option(
                Option(
                    Text.assemble(
                        ("◆ agent · ", "#3fb950"),
                        (name, "bold #e6edf3"),
                        ("     session-backed TUI", "#484f58"),
                    ),
                    id=f"agent:{name}",
                )
            )
        self.options.append(("shell", ""))
        import os

        shell = os.environ.get("SHELL", "/bin/sh")
        option_list.add_option(
            Option(Text.assemble(("▸ shell · ", "#39c5cf"), (shell, "bold #e6edf3")), id="shell:")
        )
        option_list.highlighted = 0
        option_list.focus()
        self._update_hint("agent", self.ws.config.agent_default)

    def _update_hint(self, kind: str, agent: str) -> None:
        hint = self.query_one("#terminal-hint", Static)
        if kind == "agent":
            definition = self.ws.config.agent(agent)
            hint.update(f"Launch: {definition.render('ses_<32 hex>', self.cwd, resume=False)}")
        else:
            import os

            hint.update(f"Launch: {os.environ.get('SHELL', '/bin/sh')} in {self.cwd}")

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        kind, _, agent = (event.option.id or "").partition(":")
        self.kind = kind if kind in {"agent", "shell"} else "agent"
        self.agent = agent
        self._update_hint(self.kind, self.agent)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        kind, _, agent = (event.option.id or "").partition(":")
        self.kind = kind if kind in {"agent", "shell"} else "agent"
        self.agent = agent
        self.dismiss({"kind": self.kind, "agent": self.agent})

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create":
            self.dismiss({"kind": self.kind, "agent": self.agent})
        else:
            self.dismiss(None)


class ConfirmScreen(DialogScreen):
    def __init__(
        self,
        title: str,
        message: str,
        *,
        confirm_label: str = "Confirm",
        danger: bool = False,
        checkbox_label: str = "",
        checkbox_default: bool = False,
        **kwargs,
    ):
        super().__init__(title, **kwargs)
        self.message = message
        self.confirm_label = confirm_label
        self.danger = danger
        self.checkbox_label = checkbox_label
        self.checkbox_default = checkbox_default

    def compose_body(self) -> ComposeResult:
        yield Static(self.message, classes="dialog-body", markup=False)
        if self.checkbox_label:
            yield Checkbox(self.checkbox_label, id="confirm-checkbox", value=self.checkbox_default)
        with Horizontal(classes="dialog-buttons"):
            yield Button("Cancel", id="cancel")
            yield Button(
                self.confirm_label,
                id="confirm",
                variant="error" if self.danger else "primary",
            )

    def on_mount(self) -> None:
        self.query_one("#confirm", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            checked = (
                self.query_one("#confirm-checkbox", Checkbox).value
                if self.checkbox_label
                else False
            )
            self.dismiss({"confirmed": True, "checked": checked})
        else:
            self.dismiss(None)
