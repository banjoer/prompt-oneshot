"""common.py — config, state read/write, locking, and small shared helpers.

Spec file mapping: this file re-implements `lib/common.sh` in Python
(see README.md "File-layout reinterpretation").

Config lives in ``~/.config/balamba/config`` (sourced-bash style; parsed here
without executing shell).  State lives in
``~/.local/state/balamba/state.json`` with ``fcntl.flock`` (the Python
analogue of the spec's `flock`) guarding every read-modify-write.

Environment overrides (used by tests, documented in README):
  BALAMBA_CONFIG_DIR   -> replaces ``$XDG_CONFIG_HOME/balamba``
  BALAMBA_STATE_DIR    -> replaces ``$XDG_STATE_HOME/balamba``
"""

from __future__ import annotations

import errno
import fcntl
import json
import os
import re
import uuid
from contextlib import contextmanager
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def config_dir() -> Path:
    override = os.environ.get("BALAMBA_CONFIG_DIR")
    if override:
        return Path(override)
    xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(xdg) / "balamba"


def state_dir() -> Path:
    override = os.environ.get("BALAMBA_STATE_DIR")
    if override:
        return Path(override)
    xdg = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return Path(xdg) / "balamba"


def config_path() -> Path:
    return config_dir() / "config"


def state_path() -> Path:
    return state_dir() / "state.json"


def lock_path() -> Path:
    return state_dir() / "state.json.lock"


def instance_lock_path() -> Path:
    return state_dir() / "balamba.lock"


DEFAULT_CONFIG_TEXT = """\
# balamba config (sourced-bash style; balamba parses — does not execute — this file)
BALAMBA_TREE_WIDTH=30
BALAMBA_GIT_WIDTH=34
BALAMBA_EDITOR="${EDITOR:-nvim}"
BALAMBA_AGENT_DEFAULT=opencode
BALAMBA_AGENTS=("opencode")
BALAMBA_AGENT_opencode_COMMAND="opencode --session {{session}}"
BALAMBA_AGENT_opencode_RESUME="opencode --session {{session}}"
"""


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class Config:
    """Parsed balamba configuration with sane defaults."""

    def __init__(self) -> None:
        self.tree_width = 30
        self.git_width = 34
        self.editor = "nvim"
        self.agent_default = "opencode"
        self.prefix = "ctrl+a"
        self.agents: list[str] = ["opencode"]
        # agent name -> {"command": template, "resume": template}
        self.agent_defs: dict[str, dict[str, str]] = {
            "opencode": {
                "command": "opencode --session {{session}}",
                "resume": "opencode --session {{session}}",
            }
        }
        self.errors: list[str] = []

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _expand(value: str) -> str:
        """Expand $VAR / ${VAR} / ${VAR:-default} against os.environ only.

        The spec config is "sourced bash"; we parse KEY=VALUE lines and expand
        simple parameter references without running a shell (safer, and keeps
        balamba a pure Python program — see README deviations).
        """

        def sub(m: re.Match[str]) -> str:
            name = m.group("name") or m.group("bare")
            fallback = m.group("default")
            val = os.environ.get(name or "")
            if val:
                return val
            return fallback if fallback is not None else ""

        return re.sub(
            r"\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?::-(?P<default>[^}]*))?\}"
            r"|\$(?P<bare>[A-Za-z_][A-Za-z0-9_]*)",
            sub,
            value,
        )

    @staticmethod
    def _unquote(raw: str) -> str:
        raw = raw.strip()
        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
            raw = raw[1:-1]
        return raw

    def load(self, path: Path | None = None) -> "Config":
        path = path or config_path()
        if not path.exists():
            self.errors.append(f"no config at {path}; defaults in effect")
            return self
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:  # pragma: no cover
            self.errors.append(f"cannot read config: {exc}")
            return self
        agent_re = re.compile(
            r"^BALAMBA_AGENT_(?P<name>[A-Za-z0-9_]+)_(?P<what>COMMAND|RESUME)=(?P<val>.*)$"
        )
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" not in stripped:
                continue  # `export X=1` style lines without a leading var are skipped
            if stripped.startswith("export "):
                stripped = stripped[len("export "):].strip()
            key, _, raw = stripped.partition("=")
            key = key.strip()
            raw = raw.strip()
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                continue
            if key == "BALAMBA_TREE_WIDTH":
                self._set_int("tree_width", raw)
            elif key == "BALAMBA_GIT_WIDTH":
                self._set_int("git_width", raw)
            elif key == "BALAMBA_EDITOR":
                self.editor = self._expand(self._unquote(raw)) or self.editor
            elif key == "BALAMBA_AGENT_DEFAULT":
                self.agent_default = self._unquote(raw)
            elif key == "BALAMBA_PREFIX":
                self.prefix = self._unquote(raw) or self.prefix
            elif key == "BALAMBA_AGENTS":
                # array form: ("opencode" "claude") or plain list "a b"
                items = re.findall(r'"([^"]*)"|\'([^\']*)\'|(\S+)', raw.strip("() "))
                names = [a or b or c for a, b, c in items]
                names = [n for n in names if n and not n.startswith("#")]
                if names:
                    self.agents = names
            else:
                m = agent_re.match(stripped)
                if m:
                    name = m.group("name")
                    d = self.agent_defs.setdefault(name, {"command": "", "resume": ""})
                    tmpl = self._expand(self._unquote(m.group("val")))
                    d[m.group("what").lower()] = tmpl
                    if name not in self.agents:
                        self.agents.append(name)
        return self

    def _set_int(self, attr: str, raw: str) -> None:
        try:
            val = int(self._unquote(raw))
            if val > 0:
                setattr(self, attr, val)
        except ValueError:
            self.errors.append(f"bad int for {attr}: {raw!r}")

    # -- agent helpers -------------------------------------------------------
    def agent_command(self, name: str, session: str, cwd: str, resume: bool = False) -> str | None:
        """Render the agent's launch template. Returns None if undefined."""
        d = self.agent_defs.get(name)
        if not d:
            return None
        tmpl = d.get("resume" if resume else "command") or d.get("command")
        if not tmpl:
            return None
        out = tmpl.replace("{{session}}", session).replace("{{dir}}", cwd)
        out = out.replace("{{cwd}}", cwd)  # tolerated alias
        return out


def load_config(path: Path | None = None) -> Config:
    cfg = Config()
    cfg.load(path)
    return cfg


def ensure_config_file() -> Path:
    """Create ~/.config/balamba/config with the sample content if missing."""
    path = config_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(DEFAULT_CONFIG_TEXT, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

def empty_state() -> dict:
    return {"version": 1, "projects": []}


def _locking(fn):  # noqa: D401 - tiny decorator for read-modify-write safety
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with state_write_lock():
            return fn(*args, **kwargs)

    return wrapper


@contextmanager
def state_write_lock():
    """Exclusive flock over the state lock file (Python analogue of `flock`)."""
    d = state_dir()
    d.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path()), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield fd
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def acquire_instance_lock():
    """Hold a non-blocking flock so only one balamba TUI runs at a time.

    Reinterpretation of the spec's "a live balamba tmux server": the running
    Textual process *is* the server. If the lock is held we refuse to start a
    second one (attaching to another process's screens is not possible in this
    model). Returns an open file descriptor that must stay open, or None.
    """
    d = state_dir()
    d.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(instance_lock_path()), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        os.close(fd)
        if exc.errno in (errno.EACCES, errno.EAGAIN):
            return None
        raise
    return fd


def release_instance_lock(fd: int | None) -> None:
    if fd is None:
        return
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def load_state(path: Path | None = None) -> dict:
    """Load state.json; tolerate (and log via .errors) malformed files."""
    path = path or state_path()
    errors: list[str] = []
    if not path.exists():
        st = empty_state()
    else:
        try:
            with open(path, encoding="utf-8") as fh:
                st = json.load(fh)
            if not isinstance(st, dict) or not isinstance(st.get("projects"), list):
                errors.append("state.json malformed; starting empty")
                st = empty_state()
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"state.json unreadable ({exc}); starting empty")
            st = empty_state()
    st.setdefault("version", 1)
    st.setdefault("projects", [])
    st["_balamba_errors"] = errors
    _normalize_state(st)
    return st


def _normalize_state(st: dict) -> None:
    """Fill in fields so old/partial files are safe to use."""
    for p in st.get("projects", []):
        p.setdefault("expanded", False)
        p.setdefault("scratch", [])
        p.setdefault("tasks", [])
        for t in p["tasks"]:
            t.setdefault("windows", [])
            t.setdefault("active_window", 0)
            t.setdefault("active_pane", 0)
            t.setdefault("window_layout", "")
        for w in _iter_terminals(p):
            w.setdefault("kind", "shell")
            w.setdefault("cwd", p.get("path", os.getcwd()))
            w.setdefault("uid", new_uid())


def _iter_terminals(project: dict):
    for w in project.get("scratch", []):
        yield w
    for t in project.get("tasks", []):
        for w in t.get("windows", []):
            yield w


def save_state(st: dict, path: Path | None = None) -> None:
    path = path or state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {k: v for k, v in st.items() if not k.startswith("_balamba")}
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


@_locking
def update_state(mutator) -> dict:
    """Atomically read-modify-write the state file.

    `mutator(state_dict)` may return a replacement dict; otherwise the same
    dict is saved. Returns the saved state.
    """
    st = load_state()
    result = mutator(st) or st
    save_state(result)
    return result


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------

def new_uid() -> str:
    return uuid.uuid4().hex[:12]


def new_agent_session_id() -> str:
    """`ses_` + 32 hex chars — opencode rejects ids that do not start with ses_."""
    return "ses_" + uuid.uuid4().hex


def make_slug(name: str) -> str:
    """lowercase, spaces -> '-', strip everything but [a-z0-9._-], collapse dashes."""
    s = name.lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9._-]", "", s)
    s = re.sub(r"-{2,}", "-", s)
    s = s.strip("-._")
    if not s:
        s = "task"
    return s[:80]


def tab_label(term: dict) -> str:
    kind = term.get("kind", "shell")
    if kind == "agent":
        name = term.get("name") or term.get("agent") or "agent"
        return str(name)
    cwd = term.get("cwd") or ""
    base = os.path.basename(cwd.rstrip("/")) if cwd else ""
    return f"sh:{base}" if base else "sh"


def worktrees_root_for(project_path: str) -> str:
    """/path/to/project_folder -> /path/to/balamba_worktrees (spec mapping)."""
    parent = os.path.dirname(project_path.rstrip(os.sep)) or os.sep
    base = os.path.basename(project_path.rstrip(os.sep))
    return os.path.join(parent, "balamba_worktrees", base)


def worktree_path_for(project_path: str, slug: str) -> str:
    return os.path.join(worktrees_root_for(project_path), slug)
