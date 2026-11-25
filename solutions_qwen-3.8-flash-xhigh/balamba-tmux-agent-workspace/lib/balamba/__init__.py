"""Balamba — a Textual (textualize) workspace manager: projects → tasks → terminals.

This is a re-implementation of the tmux-based "balamba" specification in which the
ENTIRE interface — chrome, three-column layout, tree pane, git pane, status bar,
tab handling, dialogs, key bindings, and mouse behaviour — is implemented as
Python + Textual widgets, screens and events. Terminal content (agent / shell /
editor sessions) is hosted underneath in plain PTY sessions driven by an embedded
stdlib VT/ANSI emulator. No tmux-driven chrome and no tmux mouse bindings are
used; see README.md for the full list of reinterpretations and deviations.
"""

__version__ = "1.0.0"

# ---------------------------------------------------------------------------
# Sign-off (requirement 15). Printed in `bin/balamba` header, `balamba doctor`,
# and in the app's About / help screen.
# ---------------------------------------------------------------------------
SIGNOFF_DATE = "2026-11-25"
SIGNOFF_LINE = (
    "Produced 2026-11-25 by Qwen 3.8 Flash (thinking effort: xhigh) — "
    "Textual rewrite of the balamba tmux workspace spec"
)
