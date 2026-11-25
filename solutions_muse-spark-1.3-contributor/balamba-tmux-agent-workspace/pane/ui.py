#!/usr/bin/env python3
"""pane/ui.py — compatibility shim.

TWIST DEVIATION (see README.md): in the original tmux-chrome design this file
was the stdlib-only tree+git pane renderer running inside tmux panes. In this
Textual reinterpretation ALL chrome (tree pane, git pane, status bar, tabs,
dialogs, mouse) is implemented as Textual widgets in app/main.py, and tmux is
used underneath only to host terminal content. This shim preserves the
deliverable path `pane/ui.py`: invoked directly it launches the Textual UI.
"""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP_MAIN = os.path.join(os.path.dirname(HERE), "app", "main.py")


def main(argv):
    sys.argv = [APP_MAIN] + list(argv)
    runpy.run_path(APP_MAIN, run_name="__main__")


if __name__ == "__main__":
    main(sys.argv[1:])
