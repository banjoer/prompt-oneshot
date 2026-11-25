"""Thin, explicit control of balamba's dedicated tmux server.

Under the Textual reinterpretation the server has *no chrome*: status bar off,
mouse off, no workspace bindings.  It hosts one window per terminal tab and,
inside a tab, zero or more panes for native-style splits.  Textual renders the
content itself from ``capture-pane`` and forwards keys with ``send-keys``.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .config import Config

SESSION = "balamba"
WINDOW_PREFIX = "bw_"
IDLE_WINDOW = "__balamba_idle"
EDITOR_PREFIX = "ed_"

LAYOUT_GEOMETRY = re.compile(r"(\d+)x(\d+),(\d+),(\d+)")


class TmuxError(RuntimeError):
    pass


@dataclass
class WindowInfo:
    id: str
    name: str
    activity_flag: bool = False
    activity: int = 0
    layout: str = ""
    active: bool = False


@dataclass
class PaneInfo:
    id: str
    index: int
    left: int
    top: int
    width: int
    height: int
    active: bool = False
    cwd: str = ""
    dead: bool = False
    command: str = ""

    @property
    def geometry(self) -> tuple[int, int, int, int]:
        return (self.left, self.top, self.width, self.height)


def layout_leaf_count(layout: str) -> int:
    """Count terminal leaves in a tmux layout string."""
    if not layout:
        return 0
    count = 0
    for match in LAYOUT_GEOMETRY.finditer(layout):
        tail = layout[match.end() : match.end() + 1]
        if tail not in ("{", "["):
            count += 1
    return count


class Tmux:
    def __init__(self, config: Config):
        self.config = config
        self.socket = config.tmux_socket or "balamba"
        self.base = ["tmux", "-L", self.socket]

    # -- low level -----------------------------------------------------
    def run(
        self,
        args: Sequence[str],
        *,
        check: bool = False,
        timeout: float = 10.0,
        conf: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        cmd = list(self.base)
        if conf is not None:
            cmd += ["-f", str(conf)]
        cmd += list(args)
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, "LC_ALL": "C.UTF-8"},
            )
        except FileNotFoundError as exc:
            raise TmuxError("tmux is not installed or not on PATH") from exc
        except subprocess.TimeoutExpired as exc:
            raise TmuxError(f"tmux {' '.join(args)} timed out") from exc
        if check and proc.returncode != 0:
            raise TmuxError(
                f"tmux {' '.join(args)} failed ({proc.returncode}): "
                f"{(proc.stderr or proc.stdout).strip()}"
            )
        return proc

    def text(self, args: Sequence[str], *, check: bool = False, timeout: float = 10.0) -> str:
        return self.run(args, check=check, timeout=timeout).stdout.strip()

    # -- server --------------------------------------------------------
    @property
    def conf(self) -> Path | None:
        return self.config.tmux_conf

    def server_running(self) -> bool:
        proc = self.run(["has-session", "-t", SESSION], timeout=4)
        return proc.returncode == 0

    def socket_path(self) -> str:
        if not self.server_running():
            tmp = Path(os.environ.get("TMUX_TMPDIR", f"/tmp/tmux-{os.getuid()}"))
            return str(tmp / self.socket)
        try:
            return self.text(["display-message", "-p", "#{socket_path}"])
        except TmuxError:
            return f"/tmp/tmux-{os.getuid()}/{self.socket}"

    def start_server(self) -> None:
        if self.server_running():
            return
        conf = self.conf
        args = [
            "new-session",
            "-d",
            "-s",
            SESSION,
            "-n",
            IDLE_WINDOW,
            "-c",
            str(Path.home()),
            "--",
            "/bin/sh",
            "-c",
            "exec sleep 86400",
        ]
        self.run(args, check=True, conf=conf)
        # Configuration is read once at server start; reassert the essentials in
        # case a stale config file was used.
        for opt in (
            "status off",
            "mouse off",
            "monitor-activity on",
            "history-limit 5000",
            "remain-on-exit off",
        ):
            self.run(["set-option", "-g", *opt.split(" ", 1)], timeout=5)

    def kill_server(self) -> None:
        self.run(["kill-server"], timeout=5)

    def mirror_options(self) -> None:
        """Mirror config into @balamba_* options (spec requirement 11).

        The Textual app reads the config directly, but the options are kept in
        sync so the server remains introspectable and other tools see the same
        values, just like the original tmux implementation.
        """
        cfg = self.config
        values = {
            "@balamba_tree_width": str(cfg.tree_width),
            "@balamba_git_width": str(cfg.git_width),
            "@balamba_editor": cfg.editor,
            "@balamba_agent_default": cfg.agent_default,
            "@balamba_agents": ",".join(cfg.agents),
            "@balamba_prefix": cfg.prefix_key,
            "@balamba_content_only": "1",
        }
        for name, value in values.items():
            try:
                self.run(["set-option", "-g", name, value], timeout=4)
            except TmuxError:
                pass

    # -- windows -------------------------------------------------------
    def list_windows(self) -> list[WindowInfo]:
        proc = self.run(
            [
                "list-windows",
                "-t",
                SESSION,
                "-F",
                "#{window_id}\t#{window_name}\t#{window_activity_flag}\t"
                "#{window_activity}\t#{window_layout}\t#{window_active}",
            ]
        )
        if proc.returncode != 0:
            return []
        windows: list[WindowInfo] = []
        for line in proc.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) < 6:
                continue
            win_id, name, flag, activity, layout, active = parts[:6]
            try:
                activity_int = int(activity)
            except ValueError:
                activity_int = 0
            windows.append(
                WindowInfo(
                    id=win_id,
                    name=name,
                    activity_flag=flag == "1",
                    activity=activity_int,
                    layout=layout,
                    active=active == "1",
                )
            )
        return windows

    def window_map(self) -> dict[str, WindowInfo]:
        return {w.name: w for w in self.list_windows()}

    def window_for_tab(self, tab_id: str) -> WindowInfo | None:
        name = WINDOW_PREFIX + tab_id
        return next((w for w in self.list_windows() if w.name == name), None)

    def new_window(
        self,
        name: str,
        cwd: str,
        command: str,
        *,
        width: int = 100,
        height: int = 30,
    ) -> str:
        safe_cwd = cwd if cwd and Path(cwd).is_dir() else str(Path.home())
        args = [
            "new-window",
            "-d",
            "-P",
            "-F",
            "#{window_id}",
            "-t",
            f"{SESSION}:",
            "-n",
            name,
            "-c",
            safe_cwd,
            "--",
            "/bin/sh",
            "-c",
            f'exec {command}',
        ]
        proc = self.run(args, timeout=20)
        if proc.returncode != 0:
            raise TmuxError((proc.stderr or proc.stdout).strip() or "could not create window")
        win_id = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
        if win_id:
            try:
                self.resize_window(win_id, width, height)
            except TmuxError:
                pass
        return win_id

    def kill_window(self, target: str) -> None:
        self.run(["kill-window", "-t", target], timeout=8)

    def resize_window(self, target: str, width: int, height: int) -> None:
        width = max(20, min(500, int(width)))
        height = max(5, min(200, int(height)))
        self.run(
            ["resize-window", "-t", target, "-x", str(width), "-y", str(height)],
            timeout=8,
        )

    def window_name_for(self, window_id: str) -> str:
        return self.text(["display-message", "-p", "-t", window_id, "#{window_name}"], timeout=5)

    # -- panes ---------------------------------------------------------
    def list_panes(self, target: str) -> list[PaneInfo]:
        proc = self.run(
            [
                "list-panes",
                "-t",
                target,
                "-F",
                "#{pane_id}\t#{pane_index}\t#{pane_left}\t#{pane_top}\t"
                "#{pane_width}\t#{pane_height}\t#{pane_active}\t"
                "#{pane_current_path}\t#{pane_dead}\t#{pane_current_command}",
            ],
            timeout=8,
        )
        if proc.returncode != 0:
            return []
        panes: list[PaneInfo] = []
        for line in proc.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) < 10:
                continue
            try:
                panes.append(
                    PaneInfo(
                        id=parts[0],
                        index=int(parts[1]),
                        left=int(parts[2]),
                        top=int(parts[3]),
                        width=int(parts[4]),
                        height=int(parts[5]),
                        active=parts[6] == "1",
                        cwd=parts[7],
                        dead=parts[8] == "1",
                        command=parts[9],
                    )
                )
            except ValueError:
                continue
        return panes

    def capture(self, pane_id: str, history: int = 0) -> list[str]:
        args = ["capture-pane", "-p", "-e", "-t", pane_id]
        if history:
            args += ["-S", f"-{int(history)}"]
        proc = self.run(args, timeout=8)
        if proc.returncode != 0:
            return []
        return proc.stdout.split("\n")

    def resize_pane(self, pane_id: str, width: int, height: int) -> None:
        self.run(
            ["resize-pane", "-t", pane_id, "-x", str(max(5, width)), "-y", str(max(3, height))],
            timeout=5,
        )

    def select_pane(self, pane_id: str) -> None:
        self.run(["select-pane", "-t", pane_id], timeout=5)

    def split_window(
        self,
        target: str,
        cwd: str,
        *,
        vertical: bool = False,
        command: str | None = None,
        width: int = 100,
        height: int = 30,
    ) -> str:
        safe_cwd = cwd if cwd and Path(cwd).is_dir() else str(Path.home())
        args = ["split-window", "-t", target, "-c", safe_cwd]
        args.append("-h" if vertical else "-v")
        shell_cmd = command or f'exec "{os.environ.get("SHELL") or "/bin/sh"}"'
        args += ["--", "/bin/sh", "-c", shell_cmd]
        proc = self.run(args, timeout=15)
        if proc.returncode != 0:
            raise TmuxError((proc.stderr or proc.stdout).strip() or "could not split pane")
        panes = self.list_panes(target)
        return panes[-1].id if panes else ""

    def kill_pane(self, pane_id: str) -> None:
        self.run(["kill-pane", "-t", pane_id], timeout=5)

    # -- layouts -------------------------------------------------------
    def window_layout(self, target: str) -> str:
        proc = self.run(["display-message", "-p", "-t", target, "#{window_layout}"], timeout=5)
        return proc.stdout.strip() if proc.returncode == 0 else ""

    def apply_layout(self, target: str, layout: str) -> bool:
        if not layout:
            return False
        proc = self.run(["select-layout", "-t", target, layout], timeout=8)
        return proc.returncode == 0

    # -- input ---------------------------------------------------------
    def send_literal(self, pane_id: str, text: str) -> None:
        if text:
            self.run(["send-keys", "-t", pane_id, "-l", text], timeout=5)

    def send_key(self, pane_id: str, key: str) -> None:
        self.run(["send-keys", "-t", pane_id, key], timeout=5)

    def send_keys(self, pane_id: str, *keys: str) -> None:
        if keys:
            self.run(["send-keys", "-t", pane_id, *keys], timeout=5)

    # -- environment ---------------------------------------------------
    def set_window_option(self, target: str, option: str, value: str) -> None:
        self.run(["set-window-option", "-t", target, option, value], timeout=5)

    def pane_dead(self, pane_id: str) -> bool:
        return self.text(
            ["display-message", "-p", "-t", pane_id, "#{pane_dead}"], timeout=4
        ) == "1"

    def display(self, target: str, fmt: str) -> str:
        return self.text(["display-message", "-p", "-t", target, fmt], timeout=5)


def shell_command() -> str:
    return os.environ.get("SHELL") or "/bin/sh"


def agent_window_name(tab_id: str) -> str:
    return WINDOW_PREFIX + tab_id


def editor_window_name(token: str) -> str:
    return EDITOR_PREFIX + token
