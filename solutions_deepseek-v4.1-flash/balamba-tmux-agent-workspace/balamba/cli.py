"""Command line entry points: attach/build, project, task, save, doctor."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

from . import AUTHOR, PRODUCED, SIGN_OFF, __version__
from .config import config_path, config_summary, ensure_layout_files, load_config, state_path
from .state import load_state, state_stats
from .workspace import Workspace, WorkspaceError, make_workspace


def _launch(ws: Workspace | None = None, demo: bool = False) -> int:
    try:
        from .app import BalambaApp
    except ModuleNotFoundError as exc:
        print(
            "balamba needs Textual (the UI is Textual-based).\n"
            "Install it with:  python3 -m pip install 'textual>=0.80'\n"
            f"Missing module: {exc}",
            file=sys.stderr,
        )
        return 2
    ws = ws or make_workspace()
    BalambaApp(ws).run()
    return 0


def cmd_project_add(path: str) -> int:
    ws = make_workspace()
    if ws.startup_error:
        print(f"balamba: state file is invalid; refusing to modify it: {ws.startup_error}", file=sys.stderr)
        return 1
    try:
        project = ws.add_project(path)
    except WorkspaceError as exc:
        print(f"balamba: {exc}", file=sys.stderr)
        return 1
    print(f"added project {project.name}")
    print(f"  path    {project.path}")
    print(f"  state   {ws.config.state_file}")
    return 0


def cmd_project_remove(path: str) -> int:
    ws = make_workspace()
    if ws.startup_error:
        print(f"balamba: state file is invalid; refusing to modify it: {ws.startup_error}", file=sys.stderr)
        return 1
    project = ws.state.project_by_path(path)
    if not project:
        print(f"balamba: project not found: {path}", file=sys.stderr)
        return 1
    ws.remove_project(project)
    print(f"removed project {project.name} from balamba only; the folder was not touched")
    return 0


def cmd_task_list() -> int:
    ws = make_workspace()
    if ws.startup_error:
        print(f"balamba: state file is invalid: {ws.startup_error}", file=sys.stderr)
        return 1
    state = ws.state
    if not state.projects:
        print("no projects yet — add one with: balamba project add <path>")
        return 0
    for project in state.projects:
        marker = "*" if project.path == state.active_project else " "
        print(f"{marker} {project.name}  {project.path}")
        for tab in project.scratch:
            print(f"    scratch  {tab.label():<22} {tab.cwd}")
        for task in project.tasks:
            print(f"    task     {task.name}  [{task.slug}]  base={task.base}")
            print(f"             {task.path}")
            for tab in task.windows:
                print(f"             {tab.label():<20} {tab.session or ''} {tab.cwd}")
    print()
    stats = state_stats(state)
    print(
        f"{stats['projects']} projects · {stats['tasks']} tasks · "
        f"{stats['tabs']} terminals · state {state_path()}"
    )
    return 0


def cmd_save() -> int:
    ws = make_workspace()
    if ws.startup_error:
        print(f"balamba: state file is invalid; not overwriting it: {ws.startup_error}", file=sys.stderr)
        return 1
    try:
        if ws.tmux.server_running():
            ws.capture_metadata(save=False)
        path = ws.save()
    except Exception as exc:
        print(f"balamba: could not save state: {exc}", file=sys.stderr)
        return 1
    print(f"saved {path}")
    return 0


def _check_row(label: str, ok: bool, detail: str) -> str:
    mark = "ok  " if ok else "FAIL"
    return f"  [{mark}] {label:<12} {detail}"


def cmd_doctor() -> int:
    print(SIGN_OFF)
    print(f"  produced {PRODUCED} · by {AUTHOR}")
    print()
    ws = make_workspace()
    issues = 0
    cfg = ws.config
    print("environment")
    print(_check_row("python", True, sys.version.split()[0]))
    try:
        import textual

        print(_check_row("textual", True, textual.__version__))
    except Exception as exc:
        print(_check_row("textual", False, f"missing: {exc}"))
        issues += 1
    git_path = shutil.which("git")
    tmux_path = shutil.which("tmux")
    print(_check_row("git", git_path is not None, git_path or "not on PATH"))
    print(_check_row("tmux", tmux_path is not None, tmux_path or "not on PATH"))
    if not git_path:
        issues += 1
    if not tmux_path:
        issues += 1
    opencode = shutil.which("opencode")
    print(_check_row("opencode", opencode is not None, opencode or "not on PATH (agent tabs need it)"))
    if not opencode:
        issues += 1
    print()
    print("tmux server")
    try:
        running = ws.tmux.server_running()
        socket = ws.tmux.socket_path()
    except Exception as exc:
        running = False
        socket = f"unavailable: {exc}"
    print(
        _check_row(
            "session",
            True,
            f"{'running' if running else 'stopped (starts on launch)'} · session balamba",
        )
    )
    print(_check_row("socket", True, socket))
    if running:
        windows = ws.tmux.list_windows()
        content = [w for w in windows if w.name.startswith("bw_")]
        print(
            _check_row(
                "windows",
                True,
                f"{len(content)} content windows · "
                f"{sum(1 for w in windows if w.name.startswith('ed_'))} editor windows",
            )
        )
    print()
    print("configuration")
    print(_check_row("config", cfg.config_file.exists(), str(cfg.config_file)))
    print(_check_row("tmux.conf", bool(cfg.tmux_conf and cfg.tmux_conf.exists()), str(cfg.tmux_conf)))
    print(_check_row("values", True, config_summary(cfg)))
    for error in cfg.errors:
        print(f"         warning: {error}")
    print()
    print("state")
    if ws.startup_error:
        print(_check_row("state", False, ws.startup_error))
        issues += 1
    else:
        stats = ws.stats()
        print(
            _check_row(
                "state",
                True,
                f"{ws.config.state_file} · {stats['projects']} projects · "
                f"{stats['tasks']} tasks · {stats['tabs']} terminals",
            )
        )
        missing: list[str] = []
        for project in ws.state.projects:
            if not Path(project.path).is_dir():
                missing.append(f"project folder missing: {project.path}")
                continue
            if not (Path(project.path) / ".git").exists():
                missing.append(f"not a git checkout: {project.path}")
            for task in project.tasks:
                from .gitops import worktree_present

                if not worktree_present(project.path, task.path):
                    missing.append(f"missing worktree: {task.path}")
        if missing:
            issues += len(missing)
            for entry in missing:
                print(_check_row("worktree", False, entry))
        else:
            print(_check_row("worktrees", True, "all saved worktrees are present"))
        for warning in ws.warnings:
            print(f"         note: {warning}")
    print()
    print(f"  {SIGN_OFF}")
    return 0 if issues == 0 else 1


def cmd_version() -> int:
    print(f"balamba {__version__}")
    print(f"produced {PRODUCED} by {AUTHOR}")
    print("chrome: Python + Textual · content host: tmux")
    return 0


def cmd_demo(reset: bool) -> int:
    from . import demo

    ws = demo.prepare(reset=reset)
    print(f"demo workspace: {os.environ.get('BALAMBA_DEMO_ROOT')}")
    print("launching Textual workspace…")
    return _launch(ws, demo=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="balamba",
        description="Textual agent workspace: projects → worktrees → terminals.",
    )
    parser.add_argument("--version", action="version", version=f"balamba {__version__}")
    sub = parser.add_subparsers(dest="command")

    project = sub.add_parser("project", help="add or remove projects")
    project_sub = project.add_subparsers(dest="project_command", required=True)
    add = project_sub.add_parser("add", help="add a git main checkout")
    add.add_argument("path")
    remove = project_sub.add_parser("remove", help="remove from balamba (never touches disk)")
    remove.add_argument("path")

    task = sub.add_parser("task", help="task commands")
    task_sub = task.add_subparsers(dest="task_command", required=True)
    task_sub.add_parser("list", help="list projects, tasks and terminals")

    sub.add_parser("save", help="capture live tmux metadata and write state.json")
    sub.add_parser("doctor", help="workspace health check")
    sub.add_parser("version", help="version and sign-off")
    demo = sub.add_parser("demo", help="build a colourful demo workspace and launch it")
    demo.add_argument("--reset", action="store_true", help="delete and rebuild the demo sandbox")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command is None:
            return _launch()
        if args.command == "project":
            if args.project_command == "add":
                return cmd_project_add(args.path)
            return cmd_project_remove(args.path)
        if args.command == "task":
            return cmd_task_list()
        if args.command == "save":
            return cmd_save()
        if args.command == "doctor":
            return cmd_doctor()
        if args.command == "version":
            return cmd_version()
        if args.command == "demo":
            return cmd_demo(args.reset)
    except KeyboardInterrupt:
        return 130
    except WorkspaceError as exc:
        print(f"balamba: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
