#!/usr/bin/env python3
"""pane/ui.py — the Textual renderer for the tree + git + terminal workspace.

In the original tmux design this file rendered two tmux panes with curses/ANSI.
Under the Textual reinterpretation it launches the complete UI: the tree pane,
git pane, tab strip, status bar, terminal content and every dialog.  It stays
here to preserve the documented file layout; ``bin/balamba`` calls the same CLI.

Run directly:  python3 pane/ui.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from balamba.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
