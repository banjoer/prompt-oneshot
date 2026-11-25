# balamba common: config, state paths, locking
# Sign-off: produced 2026-11-25 by Muse Spark 1.3 Contributor (opencode-go).
# Part of balamba-tmux-agent-workspace (Textual reinterpretation).
set -u

BALAMBA_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}/balamba"
BALAMBA_STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}/balamba"
BALAMBA_CONFIG_FILE="$BALAMBA_CONFIG_HOME/config"
BALAMBA_STATE_FILE="$BALAMBA_STATE_HOME/state.json"
BALAMBA_SOCKET="balamba"
BALAMBA_SESSION="balamba"

# Defaults (overridden by config file)
BALAMBA_TREE_WIDTH="${BALAMBA_TREE_WIDTH:-30}"
BALAMBA_GIT_WIDTH="${BALAMBA_GIT_WIDTH:-34}"
BALAMBA_EDITOR="${BALAMBA_EDITOR:-${EDITOR:-nvim}}"
BALAMBA_AGENT_DEFAULT="${BALAMBA_AGENT_DEFAULT:-opencode}"
BALAMBA_POLL_TERMINAL=0.5
BALAMBA_POLL_GIT=2
BALAMBA_POLL_INACTIVE=5

balamba_ensure_dirs() {
  mkdir -p "$BALAMBA_CONFIG_HOME" "$BALAMBA_STATE_HOME"
}

balamba_ensure_config() {
  balamba_ensure_dirs
  if [ ! -f "$BALAMBA_CONFIG_FILE" ]; then
    cat >"$BALAMBA_CONFIG_FILE" <<'EOF'
# balamba config
BALAMBA_TREE_WIDTH=30
BALAMBA_GIT_WIDTH=34
BALAMBA_EDITOR="${EDITOR:-nvim}"
BALAMBA_AGENT_DEFAULT=opencode
BALAMBA_AGENTS=("opencode")
BALAMBA_AGENT_opencode_COMMAND="opencode --session {{session}}"
BALAMBA_AGENT_opencode_RESUME="opencode --session {{session}}"
EOF
  fi
}

balamba_load_config() {
  balamba_ensure_config
  # shellcheck disable=SC1090
  . "$BALAMBA_CONFIG_FILE"
  BALAMBA_TREE_WIDTH="${BALAMBA_TREE_WIDTH:-30}"
  BALAMBA_GIT_WIDTH="${BALAMBA_GIT_WIDTH:-34}"
  BALAMBA_EDITOR="${BALAMBA_EDITOR:-${EDITOR:-nvim}}"
  BALAMBA_AGENT_DEFAULT="${BALAMBA_AGENT_DEFAULT:-opencode}"
}

balamba_ensure_state() {
  balamba_ensure_dirs
  if [ ! -f "$BALAMBA_STATE_FILE" ]; then
    printf '{"version":1,"projects":[],"active":{"project":0,"task":-1,"terminal":0}}\n' >"$BALAMBA_STATE_FILE"
  fi
}

# Run a python snippet with flock on the state file (exclusive for writers).
# Usage: balamba_with_state_lock python3 -c '...'
balamba_with_state_lock() {
  balamba_ensure_state
  exec 9>"$BALAMBA_STATE_FILE.lock"
  flock 9
  "$@"
  local rc=$?
  flock -u 9
  exec 9>&-
  return $rc
}

balamba_tmux() {
  tmux -L "$BALAMBA_SOCKET" -f "$BALAMBA_CONFIG_HOME/tmux.conf" "$@"
}

balamba_server_running() {
  tmux -L "$BALAMBA_SOCKET" has-session -t "$BALAMBA_SESSION" 2>/dev/null
}

balamba_state_python() {
  # $1 = python code reading/writing STATE_FILE env var
  STATE_FILE="$BALAMBA_STATE_FILE" python3 -c "$1"
}
