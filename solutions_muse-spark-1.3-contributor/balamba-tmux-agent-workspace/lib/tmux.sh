# balamba tmux backend helpers.
# TWIST DEVIATION (documented in README.md): this file drives tmux ONLY as a
# headless backend that hosts terminal content (sessions/windows/panes,
# capture-pane, send-keys, activity flags, restore). It creates NO chrome:
# no tree/git panes, no status-bar chrome, no mouse bindings, no key tables
# for the UI. All chrome is Textual widgets in app/main.py.
# Sign-off: produced 2026-11-25 by Muse Spark 1.3 Contributor (opencode-go).
set -u

tmux_backend_new_session() {
  # Create detached backend session if missing
  if ! balamba_tmux has-session -t "$BALAMBA_SESSION" 2>/dev/null; then
    balamba_tmux new-session -d -s "$BALAMBA_SESSION" -n "__init__" -c "$HOME" "$SHELL"
  fi
}

tmux_backend_has_window() {
  balamba_tmux list-windows -t "$BALAMBA_SESSION" -F '#{window_name}' 2>/dev/null | grep -qx "$1"
}

tmux_backend_new_window() {
  # $1=window-name $2=cwd $3=command...
  local name="$1" cwd="$2"; shift 2
  balamba_tmux new-window -d -t "$BALAMBA_SESSION" -n "$name" -c "$cwd" "$@"
}

tmux_backend_kill_window() {
  balamba_tmux kill-window -t "$BALAMBA_SESSION:$1" 2>/dev/null || true
}

tmux_backend_capture() {
  # $1=window target, $2=lines (default 200)
  local win="$1" lines="${2:-200}"
  balamba_tmux capture-pane -p -S "-$lines" -t "$BALAMBA_SESSION:$win" 2>/dev/null || true
}

tmux_backend_capture_pane() {
  # $1=pane id (e.g. %3), $2=lines
  local pane="$1" lines="${2:-200}"
  balamba_tmux capture-pane -p -S "-$lines" -t "$pane" 2>/dev/null || true
}

tmux_backend_send() {
  # $1=target(window or pane) $2...=keys; literal text callers use -l
  local target="$1"; shift
  balamba_tmux send-keys -t "$target" "$@" 2>/dev/null || true
}

tmux_backend_send_literal() {
  local target="$1" text="$2"
  balamba_tmux send-keys -t "$target" -l "$text" 2>/dev/null || true
}

tmux_backend_panes() {
  # list pane ids for window: "id cwd active"
  balamba_tmux list-panes -t "$BALAMBA_SESSION:$1" -F '#{pane_id} #{pane_current_path} #{pane_active}' 2>/dev/null || true
}

tmux_backend_windows() {
  balamba_tmux list-windows -t "$BALAMBA_SESSION" -F '#{window_name} #{window_activity_flag} #{window_active}' 2>/dev/null || true
}

tmux_backend_activity() {
  # echo 1 if window has activity flag else 0
  local out
  out="$(balamba_tmux display-message -p -t "$BALAMBA_SESSION:$1" '#{window_activity_flag}' 2>/dev/null || echo 0)"
  [ "$out" = "1" ] && echo 1 || echo 0
}

tmux_backend_layout() {
  balamba_tmux display-message -p -t "$BALAMBA_SESSION:$1" '#{window_layout}' 2>/dev/null || true
}

tmux_backend_pane_cwds() {
  # window -> newline list of pane_current_path
  balamba_tmux list-panes -t "$BALAMBA_SESSION:$1" -F '#{pane_current_path}' 2>/dev/null || true
}

tmux_backend_set_cwd_capture() {
  # nothing to do: pane_current_path is live; kept for API compat
  true
}

tmux_backend_split() {
  # $1=window $2=direction(h|v) $3=cwd
  local win="$1" dir="$2" cwd="$3"
  if [ "$dir" = "h" ]; then
    balamba_tmux split-window -h -t "$BALAMBA_SESSION:$win" -c "$cwd" "$SHELL" 2>/dev/null || true
  else
    balamba_tmux split-window -v -t "$BALAMBA_SESSION:$win" -c "$cwd" "$SHELL" 2>/dev/null || true
  fi
}

tmux_backend_select_layout() {
  # $1=window $2=layout string
  balamba_tmux select-layout -t "$BALAMBA_SESSION:$1" "$2" 2>/dev/null || true
}
