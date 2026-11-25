"""cli.py — subcommands for bin/balamba: doctor, save, task list, project add/remove.

The spec's `bin/balamba` was bash calling shell functions; the twist makes the
whole program Python, so the same subcommand surface lives here.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time

from . import SIGNOFF_LINE, __version__, common, gitops, task as task_mod, term


def cmd_project_add(path: str) -> int:
    raw = os.path.expanduser(path)
    real = os.path.realpath(raw)
    info = gitops.validate_main_checkout(real)
    if not info.ok:
        print(f"balamba: refusing project: {info.warning}", file=sys.stderr)
        return 1
    state = common.load_state()
    for p in state["projects"]:
        if os.path.realpath(p["path"]) == real:
            print("balamba: project already added")
            return 0
    if not info.is_main_checkout:
        print(f"balamba: {info.warning}", file=sys.stderr)
    state["projects"].append({"path": real, "expanded": True,
                              "scratch": [], "tasks": []})
    common.save_state(state)
    print(f"balamba: added project {real}")
    if _tui_running():
        print("balamba: note — the running balamba UI picks this up at its "
              "next start (README: no live-server attach)")
    return 0


def cmd_project_remove(path: str) -> int:
    real = os.path.realpath(os.path.expanduser(path))
    state = common.load_state()
    before = len(state["projects"])
    state["projects"] = [p for p in state["projects"]
                         if os.path.realpath(p["path"]) != real]
    if len(state["projects"]) == before:
        print(f"balamba: project not found in state: {real}", file=sys.stderr)
        return 1
    common.save_state(state)
    print(f"balamba: removed {real} from balamba only (folder untouched)")
    return 0


def cmd_task_list() -> int:
    state = common.load_state()
    for p in state["projects"]:
        print(f"project {p['path']}")
        for w in p.get("scratch", []):
            print(f"  [scratch] {common.tab_label(w)}  cwd={w.get('cwd')}")
        for t in p["tasks"]:
            print(f"  task {t['slug']} · {t['name']}")
            print(f"    worktree: {t['path']}  base: {t.get('base', '')}")
            for i, w in enumerate(t["windows"]):
                label = common.tab_label(w)
                extra = (f"session={w.get('session')}" if w.get("kind") == "agent"
                         else f"cwd={w.get('cwd')}")
                print(f"    tab {i + 1}: {w.get('kind'):<5} {label:<12} {extra}")
    if not state["projects"]:
        print("balamba: no projects yet — `balamba project add <path>`")
    return 0


def cmd_save() -> int:
    state = common.load_state()
    notes = task_mod.reconcile(state)
    for note in notes:
        print(f"reconcile: {note}")
    common.save_state(state)
    print(f"balamba: state validated and written to {common.state_path()}")
    if _tui_running():
        print("balamba: note — a live UI owns the freshest state; this "
              "command normalised the on-disk copy")
    return 0


def _tui_running() -> bool:
    fd = common.acquire_instance_lock()
    if fd is None:
        return True
    common.release_instance_lock(fd)
    return False


def cmd_doctor() -> int:
    print(f"balamba doctor · v{__version__}")
    print(SIGNOFF_LINE)
    print()
    ok = True

    # server / socket → reinterpretation
    print("[server]")
    print("  spec: dedicated tmux server `tmux -L balamba` + prefix C-a")
    print("  this build: no tmux chrome (textualize twist); terminal "
          "content is hosted in plain PTY sessions owned by the balamba "
          "Textual process")
    if _tui_running():
        print("  balamba UI: RUNNING (instance lock held)")
    else:
        print("  balamba UI: not running (lock free)")
    try:
        tmux_ver = subprocess.run(["tmux", "-V"], capture_output=True,
                                  text=True).stdout.strip()
    except OSError:
        tmux_ver = ""
    print(f"  tmux (present, deliberately unused for chrome): "
          f"{tmux_ver or 'not installed'}")

    # state validity
    print()
    print("[state]")
    sp = common.state_path()
    if not sp.exists():
        print(f"  {sp}: missing (a fresh state will be created on first run)")
    else:
        st = common.load_state(sp)
        errs = st.get("_balamba_errors", [])
        if errs:
            ok = False
            for e in errs:
                print(f"  ✗ {e}")
        else:
            print(f"  ✓ {sp} parses (version {st.get('version')})")
        print(f"  projects: {len(st['projects'])}")
        for p in st["projects"]:
            missing_tasks = []
            if not os.path.isdir(p["path"]):
                ok = False
                print(f"  ✗ project missing on disk: {p['path']}")
                continue
            known = {os.path.realpath(w["path"])
                     for w in gitops.worktree_list(p["path"])}
            for t in p["tasks"]:
                if os.path.realpath(t["path"]) not in known:
                    ok = False
                    missing_tasks.append(t["slug"])
            if missing_tasks:
                print(f"  ✗ worktrees gone (reconcile drops them): "
                      f"{', '.join(missing_tasks)} in {p['path']}")
            else:
                print(f"  ✓ {p['path']} — {len(p['tasks'])} task worktree(s) "
                      "present")

    # config
    print()
    print("[config]")
    cp = common.config_path()
    cfg_msg = "✓ present" if cp.exists() else \
        "missing (defaults; first run writes a sample)"
    print(f"  {cp}: {cfg_msg}")
    cfg = common.load_config()
    print(f"  tree width: {cfg.tree_width} · git width: {cfg.git_width}")
    print(f"  prefix: {cfg.prefix!r} · editor: {cfg.editor}")
    print(f"  agents: {', '.join(cfg.agents) or '(none)'} "
          f"(default {cfg.agent_default})")

    # tools
    print()
    print("[tools]")
    git = shutil.which("git")
    print(f"  git:      {'✓ ' + git if git else '✗ MISSING'}")
    oc = shutil.which("opencode")
    if oc:
        print(f"  opencode: ✓ {oc} ({term.quick_version('opencode')})")
    else:
        ok = False
        print("  opencode: ✗ not on PATH — agent tabs would fail to launch")
    shell = term.default_shell()
    print(f"  shell:    {'✓' if os.path.exists(shell) else '✗'} {shell}")
    editor = shutil.which(cfg.editor.split()[0]) if cfg.editor else None
    print(f"  editor:   {'✓ ' + editor if editor else '✗ ' + (cfg.editor or '?') + ' not found'}")
    print(f"  pty:      {'✓ openpty + subprocess hosting available' if term.pty_available() else '✗ pty unsupported'}")
    try:
        import textual
        print(f"  textual:  ✓ {textual.__version__}")
    except ImportError:
        ok = False
        print("  textual:  ✗ MISSING — pip install textual")
    print()
    print("doctor verdict: " + ("everything looks fine" if ok
                                else "see ✗ items above"))
    return 0 if ok else 1


def version_line() -> str:
    return f"balamba {__version__} — {SIGNOFF_LINE}"
