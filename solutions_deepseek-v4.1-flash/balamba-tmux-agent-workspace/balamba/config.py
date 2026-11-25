"""Configuration loading for balamba.

The on-disk config is still a *sourced bash file* (as specified), so the stock
example in the spec keeps working verbatim.  We source it in a throw-away bash
and print the resulting ``BALAMBA_*`` variables in a machine-readable stream.
Everything else in the application consumes :class:`Config`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

DEFAULT_CONFIG = """\
# balamba config — sourced bash, exactly like the original tmux build.
# Chrome is Textual; these values are still mirrored into Textual widgets.
BALAMBA_TREE_WIDTH=30
BALAMBA_GIT_WIDTH=34
BALAMBA_EDITOR="${EDITOR:-nvim}"
BALAMBA_AGENT_DEFAULT=opencode
BALAMBA_AGENTS=("opencode")
BALAMBA_AGENT_opencode_COMMAND="opencode --session {{session}}"
BALAMBA_AGENT_opencode_RESUME="opencode --session {{session}}"

# Prefix key for app commands (Textual key name or a single character).
BALAMBA_KEY_PREFIX="ctrl+a"

# Prefix commands. Case matters: uppercase N/P/T are the defaults.
BALAMBA_KEY_NEW_TASK="N"
BALAMBA_KEY_ADD_PROJECT="P"
BALAMBA_KEY_NEW_TERMINAL="T"
BALAMBA_KEY_EDITOR="e"
BALAMBA_KEY_DETACH="d"
BALAMBA_KEY_REDRAW="r"
BALAMBA_KEY_CLOSE_TAB="x"
BALAMBA_KEY_SPLIT_V="\\\\"
BALAMBA_KEY_SPLIT_H="-"
BALAMBA_KEY_CYCLE_PANE="o"
BALAMBA_KEY_FOCUS_CYCLE="f"
BALAMBA_KEY_ABOUT="a"
BALAMBA_KEY_HELP="?"

# Tree-level keys (no prefix), colon separated action:key pairs.
BALAMBA_TREE_KEYS="down:j up:k collapse:h expand:l activate:enter new-task:n new-terminal:t close-task:d editor:e add-project:p"

# Optional: worktrees root. Defaults to <project parent>/balamba_worktrees.
# BALAMBA_WORKTREES_ROOT="$HOME/balamba_worktrees"

# Optional: dedicated tmux socket name (default: balamba).
# BALAMBA_TMUX_SOCKET="balamba"

# Optional: extra agent, zero code changes:
# BALAMBA_AGENTS+=("codex")
# BALAMBA_AGENT_codex_COMMAND="codex --cd {{dir}}"
# BALAMBA_AGENT_codex_RESUME="codex resume --cd {{dir}}"
"""

DEFAULT_TMUX_CONF = """\
# balamba tmux server — CONTENT ONLY.
# The Textual app owns every piece of chrome (panes, status bar, tabs, mouse).
set -g status off
set -g mouse off
set -g prefix C-a
unbind C-b
set -g history-limit 5000
set -g escape-time 20
set -g focus-events off
set -g monitor-activity on
set -g default-terminal "screen-256color"
set -g set-titles off
set -g visual-activity off
set -g visual-bell off
set -g bell-action none
set -g allow-rename off
set -g automatic-rename off
set -g pane-border-style "fg=#30363d"
set -g pane-active-border-style "fg=#58a6ff"
# No bindings here: all keys and mouse gestures are handled by Textual.
"""

KEY_ALIASES = {
    "esc": "escape",
    "return": "enter",
    "del": "delete",
    "pgup": "pageup",
    "pgdn": "pagedown",
}

DEFAULT_COMMAND_KEYS = {
    "new-task": "N",
    "add-project": "P",
    "new-terminal": "T",
    "editor": "e",
    "detach": "d",
    "redraw": "r",
    "close-tab": "x",
    "split-v": "\\",
    "split-h": "-",
    "cycle-pane": "o",
    "focus-cycle": "f",
    "about": "a",
    "help": "?",
    "next-tab": "n",
    "prev-tab": "p",
    "quit": "q",
}


def _norm_key(value: str) -> str:
    value = value.strip()
    if not value:
        return value
    low = value.lower()
    if low in KEY_ALIASES:
        return KEY_ALIASES[low]
    return low


@dataclass(frozen=True)
class AgentDef:
    name: str
    command: str
    resume: str

    def render(self, session: str, directory: str, *, resume: bool) -> str:
        template = self.resume if resume else self.command
        return (
            template.replace("{{session}}", session)
            .replace("{{dir}}", directory)
            .replace("{{agent}}", self.name)
        )


@dataclass
class Config:
    tree_width: int = 30
    git_width: int = 34
    editor: str = "nvim"
    agent_default: str = "opencode"
    agents: dict[str, AgentDef] = field(default_factory=dict)
    prefix_key: str = "ctrl+a"
    tree_keys: dict[str, str] = field(default_factory=dict)
    command_keys: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_COMMAND_KEYS))
    worktrees_root: Path | None = None
    tmux_socket: str = "balamba"
    tmux_conf: Path | None = None
    config_file: Path | None = None
    state_file: Path | None = None
    raw: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def key_for(self, action: str, default: str = "") -> str:
        return self.tree_keys.get(action, default)

    def command_for(self, char: str) -> str:
        for action, key in self.command_keys.items():
            if key == char:
                return action
        return ""

    def command_key(self, action: str) -> str:
        return self.command_keys.get(action, DEFAULT_COMMAND_KEYS.get(action, ""))

    def agent(self, name: str | None) -> AgentDef:
        if name and name in self.agents:
            return self.agents[name]
        if self.agent_default in self.agents:
            return self.agents[self.agent_default]
        if self.agents:
            return next(iter(self.agents.values()))
        return AgentDef("shell", "", "")


def home_dir() -> Path:
    return Path(os.environ.get("HOME", str(Path.home()))).expanduser()


def state_dir() -> Path:
    override = os.environ.get("BALAMBA_STATE_DIR")
    return Path(override).expanduser() if override else home_dir() / ".local/state/balamba"


def config_dir() -> Path:
    override = os.environ.get("BALAMBA_CONFIG_DIR")
    return Path(override).expanduser() if override else home_dir() / ".config/balamba"


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def state_path() -> Path:
    return state_dir() / "state.json"


def config_path() -> Path:
    return config_dir() / "config"


def tmux_conf_path() -> Path:
    return config_dir() / "tmux.conf"


def ensure_layout_files() -> tuple[Path, Path]:
    """Create the config directory with stock config + tmux.conf if needed.

    Returns ``(config_file, tmux_conf)``.  Existing files are never touched.
    """
    cdir = config_dir()
    cdir.mkdir(parents=True, exist_ok=True)
    cfg = cdir / "config"
    if not cfg.exists():
        cfg.write_text(DEFAULT_CONFIG, encoding="utf-8")
    conf = cdir / "tmux.conf"
    if not conf.exists():
        shipped = repo_root() / "tmux.conf"
        try:
            text = shipped.read_text(encoding="utf-8") if shipped.exists() else DEFAULT_TMUX_CONF
        except OSError:
            text = DEFAULT_TMUX_CONF
        conf.write_text(text, encoding="utf-8")
    state_dir().mkdir(parents=True, exist_ok=True)
    return cfg, conf


def _parse_dump(text: str) -> tuple[dict[str, str], dict[str, list[str]]]:
    scalars: dict[str, str] = {}
    arrays: dict[str, list[str]] = {}
    for record in text.split("\x1e"):
        if not record:
            continue
        kind, _, payload = record.partition("\x1f")
        name, _, value = payload.partition("\x1f")
        if kind == "S":
            scalars[name] = value
        elif kind == "A":
            arrays.setdefault(name, []).append(value)
        elif kind == "X":
            scalars["__error__"] = value
    return scalars, arrays


def _source_bash(path: Path) -> tuple[dict[str, str], list[str]]:
    """Source a bash config and return (variables, errors)."""
    script = r'''
set +e
source "$1" >/dev/null 2>&1
status=$?
if [ "$status" -ne 0 ]; then
  printf 'X\037\037source failed with status %s\036' "$status"
fi
while IFS= read -r name; do
  decl=$(declare -p "$name" 2>/dev/null) || continue
  case "$decl" in
    "declare -a"*|"declare -A"*)
      eval 'items=("${'"$name"'[@]}")'
      for item in "${items[@]}"; do
        printf 'A\037%s\037%s\036' "$name" "$item"
      done
      ;;
    *)
      printf 'S\037%s\037%s\036' "$name" "${!name}"
      ;;
  esac
done < <(compgen -v | grep '^BALAMBA_')
'''
    try:
        proc = subprocess.run(
            ["bash", "-c", script, "_", str(path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {}, [f"could not source {path}: {exc}"]
    scalars, arrays = _parse_dump(proc.stdout)
    errors: list[str] = []
    if "__error__" in scalars:
        errors.append(f"{path}: {scalars.pop('__error__')}")
    if proc.stderr.strip():
        errors.append(proc.stderr.strip().splitlines()[-1])
    for name, values in arrays.items():
        scalars[name] = "\n".join(values)
    return scalars, errors


def _int(value: str | None, default: int, lo: int, hi: int) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, parsed))


def _parse_tree_keys(value: str) -> dict[str, str]:
    keys: dict[str, str] = {}
    for token in value.split():
        action, _, key = token.partition(":")
        if action and key:
            keys[action.strip()] = _norm_key(key)
    return keys


def load_config(path: Path | None = None) -> Config:
    cfg = Config()
    cfg.config_file = Path(path) if path else config_path()
    cfg.state_file = state_path()
    seed = Config()
    seed.agents["opencode"] = AgentDef(
        "opencode", "opencode --session {{session}}", "opencode --session {{session}}"
    )
    cfg.agents = dict(seed.agents)
    cfg.tree_keys = _parse_tree_keys(
        "down:j up:k collapse:h expand:l activate:enter new-task:n "
        "new-terminal:t close-task:d editor:e add-project:p"
    )
    env_socket = os.environ.get("BALAMBA_TMUX_SOCKET")
    if env_socket:
        cfg.tmux_socket = env_socket
    env_root = os.environ.get("BALAMBA_WORKTREES_ROOT")
    if env_root:
        cfg.worktrees_root = Path(env_root).expanduser()

    if cfg.config_file.exists():
        scalars, errors = _source_bash(cfg.config_file)
        cfg.errors.extend(errors)
        cfg.raw = dict(scalars)
        cfg.tree_width = _int(scalars.get("BALAMBA_TREE_WIDTH"), 30, 18, 60)
        cfg.git_width = _int(scalars.get("BALAMBA_GIT_WIDTH"), 34, 20, 70)
        cfg.editor = scalars.get("BALAMBA_EDITOR") or os.environ.get("EDITOR") or "nvim"
        cfg.agent_default = scalars.get("BALAMBA_AGENT_DEFAULT") or "opencode"
        cfg.prefix_key = _norm_key(scalars.get("BALAMBA_KEY_PREFIX") or "ctrl+a")
        if scalars.get("BALAMBA_TREE_KEYS"):
            cfg.tree_keys = _parse_tree_keys(scalars["BALAMBA_TREE_KEYS"]) or cfg.tree_keys
        if scalars.get("BALAMBA_TMUX_SOCKET"):
            cfg.tmux_socket = scalars["BALAMBA_TMUX_SOCKET"].strip()
        if scalars.get("BALAMBA_WORKTREES_ROOT"):
            cfg.worktrees_root = Path(scalars["BALAMBA_WORKTREES_ROOT"]).expanduser()
        for action in DEFAULT_COMMAND_KEYS:
            env_name = "BALAMBA_KEY_" + action.upper().replace("-", "_")
            if scalars.get(env_name):
                cfg.command_keys[action] = scalars[env_name]

        agent_names: list[str] = []
        if scalars.get("BALAMBA_AGENTS"):
            agent_names = [a for a in scalars["BALAMBA_AGENTS"].split("\n") if a.strip()]
        if not agent_names:
            agent_names = ["opencode"]
        cfg.agents = {}
        for name in agent_names:
            name = name.strip()
            command = scalars.get(f"BALAMBA_AGENT_{name}_COMMAND") or ""
            resume = scalars.get(f"BALAMBA_AGENT_{name}_RESUME") or command
            if command:
                cfg.agents[name] = AgentDef(name, command, resume)
        if not cfg.agents:
            cfg.agents["opencode"] = seed.agents["opencode"]
        if cfg.agent_default not in cfg.agents:
            cfg.agent_default = next(iter(cfg.agents))
    else:
        cfg.editor = os.environ.get("EDITOR") or cfg.editor

    # Environment overrides win over the sourced file (used by tests, the demo
    # and anyone running several isolated workspaces).
    if env_socket:
        cfg.tmux_socket = env_socket
    if env_root:
        cfg.worktrees_root = Path(env_root).expanduser()
    env_state = os.environ.get("BALAMBA_STATE_FILE")
    if env_state:
        cfg.state_file = Path(env_state).expanduser()

    cfg.tmux_conf = tmux_conf_path()
    if not cfg.tmux_conf.exists():
        shipped = repo_root() / "tmux.conf"
        cfg.tmux_conf = shipped if shipped.exists() else None
    return cfg


def config_summary(cfg: Config) -> str:
    return (
        f"tree={cfg.tree_width} git={cfg.git_width} prefix={cfg.prefix_key} "
        f"agents={','.join(cfg.agents)} socket={cfg.tmux_socket}"
    )


def which_all(names: Iterable[str]) -> dict[str, str | None]:
    return {name: shutil.which(name) for name in names}
