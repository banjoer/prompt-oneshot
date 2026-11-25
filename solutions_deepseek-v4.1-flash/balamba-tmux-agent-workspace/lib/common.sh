#!/usr/bin/env bash
# lib/common.sh — configuration, state and locking helpers.
#
# Compatibility shim for the file layout in the original challenge.  The real
# implementation is Python (balamba/config.py, balamba/state.py) because the
# UI is Textual.  These helpers are usable from bash scripts and always forward
# to the same config/state code as the app, so there is only one source of
# truth.

if [ -n "${BASH_SOURCE[0]:-}" ]; then
  BALAMBA_LIB_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
else
  BALAMBA_LIB_DIR="$(pwd)/lib"
fi
BALAMBA_ROOT="${BALAMBA_ROOT:-$(cd -- "$BALAMBA_LIB_DIR/.." && pwd)}"

balamba_py() {
  PYTHONPATH="$BALAMBA_ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 "$@"
}

# Print the state.json path.
balamba_state_path() {
  balamba_py -c 'from balamba.config import state_path; print(state_path())'
}

# Print the config path.
balamba_config_path() {
  balamba_py -c 'from balamba.config import config_path; print(config_path())'
}

# Print state as compact JSON; exits non-zero if the file is invalid.
balamba_state_read() {
  balamba_py -c '
import json, sys
from balamba.state import load_state
try:
    state, warnings = load_state()
except Exception as exc:
    print(exc, file=sys.stderr); raise SystemExit(1)
print(json.dumps(state.to_dict()))
' "$@"
}

# Atomically write state from a JSON document on stdin.
balamba_state_write() {
  balamba_py -c '
import json, sys
from balamba.state import State, save_state
raw = json.load(sys.stdin)
print(save_state(State.from_dict(raw)))
'
}

# Source the user's bash config in the caller's environment.  Arrays are not
# exported, so prefer the Python config loader in scripts that need agents.
balamba_config_source() {
  local cfg
  cfg="$(balamba_config_path)"
  if [ -f "$cfg" ]; then
    # shellcheck disable=SC1090
    set -a; . "$cfg"; set +a
  fi
}

# Print a resolved config value via the Python loader.
balamba_config_value() {
  balamba_py -c '
import sys
from balamba.config import load_config
cfg = load_config()
name = sys.argv[1]
value = {
    "tree_width": cfg.tree_width,
    "git_width": cfg.git_width,
    "editor": cfg.editor,
    "agent_default": cfg.agent_default,
    "agents": ",".join(cfg.agents),
    "prefix": cfg.prefix_key,
    "socket": cfg.tmux_socket,
}.get(name, "")
print(value)
' "$1"
}

# Print a small state summary.
balamba_state_summary() {
  balamba_py -c '
from balamba.state import load_state, state_stats
state, _ = load_state()
print(state_stats(state))
' "$@"
}
