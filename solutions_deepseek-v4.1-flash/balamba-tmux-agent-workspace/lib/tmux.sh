#!/usr/bin/env bash
# lib/tmux.sh — dedicated content server helpers.
#
# The Textual app owns all chrome.  This library only wraps the `-L balamba`
# content server (status off, mouse off, one window per tab).  It never
# attaches to or modifies the user's default tmux server.

if [ -n "${BASH_SOURCE[0]:-}" ]; then
  BALAMBA_LIB_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
else
  BALAMBA_LIB_DIR="$(pwd)/lib"
fi
BALAMBA_ROOT="${BALAMBA_ROOT:-$(cd -- "$BALAMBA_LIB_DIR/.." && pwd)}"
# shellcheck source=lib/common.sh
. "$BALAMBA_LIB_DIR/common.sh"

BALAMBA_TMUX_SOCKET="${BALAMBA_TMUX_SOCKET:-$(balamba_config_value socket)}"
BALAMBA_TMUX_CONF="${BALAMBA_TMUX_CONF:-$(balamba_py -c 'from balamba.config import tmux_conf_path; print(tmux_conf_path())')}"

# Call tmux against the dedicated balamba server.
balamba_tmux() {
  tmux -L "$BALAMBA_TMUX_SOCKET" "$@"
}

balamba_server_running() {
  balamba_tmux has-session -t balamba 2>/dev/null
}

balamba_server_socket() {
  if balamba_server_running; then
    balamba_tmux display-message -p '#{socket_path}'
  else
    printf '/tmp/tmux-%s/%s\n' "$(id -u)" "$BALAMBA_TMUX_SOCKET"
  fi
}

balamba_content_windows() {
  balamba_tmux list-windows -t balamba -F '#{window_id}\t#{window_name}\t#{window_activity_flag}'
}

# Attach a human to the content-only server (there is no chrome there; this is
# for debugging by hand, not the normal workflow).
balamba_attach_content() {
  balamba_tmux attach-session -t balamba
}

# Print state and live server metadata, without changing anything.
balamba_snapshot() {
  printf 'socket  %s\n' "$(balamba_server_socket)"
  printf 'state   %s\n' "$(balamba_state_path)"
  if balamba_server_running; then
    printf 'windows\n'
    balamba_content_windows
  else
    printf 'server  stopped\n'
  fi
}
