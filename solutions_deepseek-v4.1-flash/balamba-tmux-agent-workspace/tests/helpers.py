"""Shared helpers for the balamba test-suite (stdlib unittest only)."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class Sandbox:
    def __init__(self, name: str = "test"):
        self.name = name
        self.dir: Path | None = None
        self._env_backup: dict[str, str | None] = {}

    def __enter__(self) -> "Sandbox":
        self.dir = Path(tempfile.mkdtemp(prefix=f"balamba-{self.name}-"))
        socket = "balamba-test-" + uuid.uuid4().hex[:8]
        env = {
            "BALAMBA_STATE_DIR": str(self.dir / "state"),
            "BALAMBA_CONFIG_DIR": str(self.dir / "config"),
            "BALAMBA_TMUX_SOCKET": socket,
            "SHELL": os.environ.get("SHELL", "/bin/bash"),
        }
        for key, value in env.items():
            self._env_backup[key] = os.environ.get(key)
            os.environ[key] = value
        (self.dir / "config").mkdir(parents=True, exist_ok=True)
        (self.dir / "state").mkdir(parents=True, exist_ok=True)
        self.socket = socket
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            subprocess.run(
                ["tmux", "-L", self.socket, "kill-server"],
                capture_output=True,
                timeout=5,
            )
        except Exception:
            pass
        for key, old in self._env_backup.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old
        if self.dir:
            shutil.rmtree(self.dir, ignore_errors=True)

    # -- repos ---------------------------------------------------------
    def repo(self, name: str = "widget", files: dict[str, str] | None = None) -> Path:
        assert self.dir
        path = self.dir / "src" / name
        path.mkdir(parents=True, exist_ok=True)
        self.git(["init", "-q", "-b", "main"], path)
        self.git(["config", "user.email", "test@example.invalid"], path)
        self.git(["config", "user.name", "balamba test"], path)
        files = files or {"README.md": "# widget\n", "app.py": "print('hi')\n"}
        for filename, content in files.items():
            target = path / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        self.git(["add", "."], path)
        self.git(["commit", "-qm", "initial"], path)
        # A local remote-tracking ref makes the spec's default base work without
        # any network or remote configuration.
        self.git(["update-ref", "refs/remotes/origin/main", "HEAD"], path)
        return path

    def git(self, args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "balamba test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "balamba test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
        }
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            env=env,
            check=check,
        )

    def write_config(self, text: str) -> Path:
        assert self.dir
        path = self.dir / "config" / "config"
        path.write_text(text, encoding="utf-8")
        return path


def base_config(tree_width: int = 28, git_width: int = 30) -> str:
    return f"""\
BALAMBA_TREE_WIDTH={tree_width}
BALAMBA_GIT_WIDTH={git_width}
BALAMBA_EDITOR="vi"
BALAMBA_AGENT_DEFAULT=opencode
BALAMBA_AGENTS=("opencode")
BALAMBA_AGENT_opencode_COMMAND="opencode --session {{{{session}}}}"
BALAMBA_AGENT_opencode_RESUME="opencode --session {{{{session}}}}"
BALAMBA_KEY_PREFIX="ctrl+a"
BALAMBA_TREE_KEYS="down:j up:k collapse:h expand:l activate:enter new-task:n new-terminal:t close-task:d editor:e add-project:p"
"""
