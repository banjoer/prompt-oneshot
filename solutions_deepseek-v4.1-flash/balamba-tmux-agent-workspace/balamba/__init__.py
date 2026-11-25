"""balamba — a Textual re-creation of the tmux agent workspace.

The chrome (tree, tabs, git panel, status bar, dialogs, keys, mouse) is
implemented entirely in Python with Textual.  A dedicated tmux server is used
*only* to host the terminal content shown inside the app.

Produced: 2026-11-25 10:44 CET
Author / model: DeepSeek V4.1 Flash 1017
"""

__version__ = "1.0.0"

AUTHOR = "DeepSeek V4.1 Flash 1017"
PRODUCED = "2026-11-25 10:44 CET"
PRODUCED_ISO = "2026-11-25T10:44:00+01:00"
APP_NAME = "balamba"

SIGN_OFF = f"balamba {__version__} · built {PRODUCED} · by {AUTHOR}"
