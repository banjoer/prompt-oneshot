"""balamba backend bridge (stdlib only): state, config, tmux backend, git.

Used by the Textual UI (app/main.py) and testable headlessly.
Twist: tmux is used ONLY to host terminal content. No chrome lives in tmux.
"""
import json
import os
import re
import secrets
import subprocess
import uuid

BALAMBA_VERSION = "1.0.0-textual"
BALAMBA_SIGNOFF = "2026-11-25 by Muse Spark 1.3 Contributor (opencode-go)"


def config_home():
    return os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config")) + "/balamba"


def state_home():
    return os.environ.get("XDG_STATE_HOME", os.path.join(os.path.expanduser("~"), ".local/state")) + "/balamba"


def config_file():
    return os.path.join(config_home(), "config")


def state_file():
    return os.path.join(state_home(), "state.json")


DEFAULT_CONFIG = """# balamba config
BALAMBA_TREE_WIDTH=30
BALAMBA_GIT_WIDTH=34
BALAMBA_EDITOR="${EDITOR:-nvim}"
BALAMBA_AGENT_DEFAULT=opencode
BALAMBA_AGENTS=("opencode")
BALAMBA_AGENT_opencode_COMMAND="opencode --session {{session}}"
BALAMBA_AGENT_opencode_RESUME="opencode --session {{session}}"
"""


def ensure_dirs():
    os.makedirs(config_home(), exist_ok=True)
    os.makedirs(state_home(), exist_ok=True)


def ensure_config():
    ensure_dirs()
    cf = config_file()
    if not os.path.exists(cf):
        with open(cf, "w") as f:
            f.write(DEFAULT_CONFIG)
    # install backend tmux.conf from repo if missing
    dest = os.path.join(config_home(), "tmux.conf")
    if not os.path.exists(dest):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        src = os.path.join(here, "tmux.conf")
        try:
            with open(src) as f:
                body = f.read()
            with open(dest, "w") as f:
                f.write(body)
        except OSError:
            pass
    return cf


def load_config():
    ensure_config()
    cfg = {
        "BALAMBA_TREE_WIDTH": 30,
        "BALAMBA_GIT_WIDTH": 34,
        "BALAMBA_EDITOR": os.environ.get("EDITOR", "nvim"),
        "BALAMBA_AGENT_DEFAULT": "opencode",
        "BALAMBA_AGENTS": ["opencode"],
        "BALAMBA_AGENT_opencode_COMMAND": "opencode --session {{session}}",
        "BALAMBA_AGENT_opencode_RESUME": "opencode --session {{session}}",
    }
    try:
        with open(config_file()) as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                m = re.match(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$', line)
                if not m:
                    continue
                k, v = m.group(1), m.group(2).strip()
                if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                    v = v[1:-1]
                if k in ("BALAMBA_TREE_WIDTH", "BALAMBA_GIT_WIDTH"):
                    try:
                        cfg[k] = int(v)
                    except ValueError:
                        pass
                elif k == "BALAMBA_AGENTS":
                    inner = re.sub(r'[()"\' ]', '', v)
                    if inner:
                        cfg[k] = inner.split()
                else:
                    # expand ${EDITOR:-nvim} style minimally
                    v = v.replace("${EDITOR:-nvim}", os.environ.get("EDITOR", "nvim"))
                    v = v.replace("$EDITOR", os.environ.get("EDITOR", "nvim"))
                    v = v.replace("$SHELL", os.environ.get("SHELL", "/bin/bash"))
                    cfg[k] = v
    except OSError:
        pass
    return cfg


def blank_state():
    return {"version": 1, "projects": [], "active": {"project": 0, "task": -1, "terminal": 0}}


def load_state():
    ensure_dirs()
    sf = state_file()
    if not os.path.exists(sf):
        st = blank_state()
        save_state(st)
        return st
    try:
        with open(sf) as f:
            st = json.load(f)
        if not isinstance(st, dict) or "projects" not in st:
            raise ValueError("bad state")
        st.setdefault("active", {"project": 0, "task": -1, "terminal": 0})
        return st
    except (OSError, ValueError, json.JSONDecodeError):
        # keep corrupt file aside, start blank
        try:
            os.replace(sf, sf + ".corrupt")
        except OSError:
            pass
        st = blank_state()
        save_state(st)
        return st


def save_state(st):
    """Writer path: exclusive flock, atomic replace (spec: flock for writers)."""
    ensure_dirs()
    import fcntl
    lock_path = state_file() + ".lock"
    tmp = state_file() + ".tmp"
    with open(lock_path, "a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            with open(tmp, "w") as f:
                json.dump(st, f, indent=2)
            os.replace(tmp, state_file())
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def mirror_config_to_tmux(cfg):
    """Best-effort mirror of config into tmux @balamba_* options.

    The Textual UI reads config directly (authoritative); the tmux options
    exist so `tmux show -g @balamba_*` and doctor report the same values,
    preserving the original config-mirroring contract.
    """
    pairs = {
        "@balamba_tree_width": str(cfg.get("BALAMBA_TREE_WIDTH", 30)),
        "@balamba_git_width": str(cfg.get("BALAMBA_GIT_WIDTH", 34)),
        "@balamba_editor": str(cfg.get("BALAMBA_EDITOR", "nvim")),
        "@balamba_agent_default": str(cfg.get("BALAMBA_AGENT_DEFAULT", "opencode")),
    }
    for k, v in pairs.items():
        tmux("set-option", "-g", k, v)


# ---------------- tmux backend ----------------

def tmux(*args, timeout=10):
    cmd = ["tmux", "-L", "balamba", "-f", os.path.join(config_home(), "tmux.conf")] + list(args)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r
    except (OSError, subprocess.SubprocessError):
        return None


def server_running():
    r = tmux("has-session", "-t", "balamba")
    return r is not None and r.returncode == 0


def ensure_backend_session():
    if not server_running():
        tmux("new-session", "-d", "-s", "balamba", "-n", "__init__",
             "-c", os.path.expanduser("~"), os.environ.get("SHELL", "/bin/bash"))


def list_windows():
    """Return list of dicts {name, activity(bool), active(bool)}."""
    r = tmux("list-windows", "-t", "balamba", "-F", "#{window_name} #{window_activity_flag} #{window_active}")
    if r is None or r.returncode != 0:
        return []
    out = []
    for line in r.stdout.strip().splitlines():
        parts = line.split()
        if not parts:
            continue
        out.append({"name": parts[0],
                    "activity": len(parts) > 1 and parts[1] == "1",
                    "active": len(parts) > 2 and parts[2] == "1"})
    return out


def window_exists(name):
    return any(w["name"] == name for w in list_windows())


def new_window(name, cwd, command):
    return tmux("new-window", "-d", "-t", "balamba", "-n", name, "-c", cwd, command)


def kill_window(name):
    tmux("kill-window", "-t", "balamba:" + name)


def list_panes(window):
    r = tmux("list-panes", "-t", "balamba:" + window, "-F", "#{pane_id} #{pane_current_path} #{pane_active}")
    if r is None or r.returncode != 0:
        return []
    panes = []
    for line in r.stdout.strip().splitlines():
        parts = line.split()
        if not parts:
            continue
        panes.append({"id": parts[0],
                      "cwd": parts[1] if len(parts) > 1 else "",
                      "active": len(parts) > 2 and parts[2] == "1"})
    return panes


def capture_pane(target, lines=200):
    r = tmux("capture-pane", "-p", "-S", "-%d" % lines, "-t", target)
    if r is None or r.returncode != 0:
        return ""
    return r.stdout


def send_literal(target, text):
    tmux("send-keys", "-t", target, "-l", text)


def send_keys(target, *keys):
    tmux("send-keys", "-t", target, *keys)


def window_layout(window):
    r = tmux("display-message", "-p", "-t", "balamba:" + window, "#{window_layout}")
    if r is None or r.returncode != 0:
        return ""
    return r.stdout.strip()


def window_activity(window):
    r = tmux("display-message", "-p", "-t", "balamba:" + window, "#{window_activity_flag}")
    if r is None or r.returncode != 0:
        return False
    return r.stdout.strip() == "1"


def split_window(window, direction, cwd):
    if direction == "h":
        tmux("split-window", "-h", "-t", "balamba:" + window, "-c", cwd, os.environ.get("SHELL", "/bin/bash"))
    else:
        tmux("split-window", "-v", "-t", "balamba:" + window, "-c", cwd, os.environ.get("SHELL", "/bin/bash"))


# ---------------- git ----------------

def git(*args, cwd=None, timeout=10):
    try:
        r = subprocess.run(["git", "-C", cwd or "."] + list(args),
                           capture_output=True, text=True, timeout=timeout)
        return r
    except (OSError, subprocess.SubprocessError):
        return None


def git_toplevel(path):
    r = git("rev-parse", "--show-toplevel", cwd=path)
    if r is None or r.returncode != 0:
        return None
    return r.stdout.strip()


def validate_project(path):
    """Return (toplevel, warning) or raise ValueError."""
    import subprocess as sp
    resolved = os.path.realpath(path)
    top = git_toplevel(resolved)
    if top is None:
        raise ValueError("not a git repository: %s" % path)
    if os.path.realpath(top) != resolved:
        raise ValueError("not the main checkout (toplevel %s)" % top)
    warn = None
    r = git("rev-parse", "--git-dir", cwd=resolved)
    r2 = git("rev-parse", "--git-common-dir", cwd=resolved)
    if r and r2 and r.returncode == 0 and r2.returncode == 0:
        if r.stdout.strip() != r2.stdout.strip() and r.stdout.strip() != ".git":
            warn = "path looks like a linked worktree"
    return resolved, warn


def slugify(name):
    s = name.strip().lower().replace(" ", "-").replace("\t", "-")
    s = re.sub(r"[^a-z0-9._-]", "-", s)
    s = re.sub(r"-+", "-", s).strip("-._")
    return (s[:80] or "task")


def check_branch_valid(slug, cwd):
    r = git("check-ref-format", "--branch", slug, cwd=cwd)
    return r is not None and r.returncode == 0


def verify_ref(ref, cwd):
    r = git("rev-parse", "--verify", ref + "^{commit}", cwd=cwd)
    return r is not None and r.returncode == 0


def branch_exists(slug, cwd):
    r = git("show-ref", "--verify", "--quiet", "refs/heads/" + slug, cwd=cwd)
    return r is not None and r.returncode == 0


def unique_slug(repo, want, parent):
    cand, i = want, 2
    while os.path.exists(os.path.join(parent, cand)) or branch_exists(cand, repo):
        cand = "%s-%d" % (want, i)
        i += 1
    return cand


def worktree_path(project_path, slug):
    parent = os.path.dirname(os.path.realpath(project_path))
    folder = os.path.basename(os.path.realpath(project_path))
    return os.path.join(parent, "balamba_worktrees", folder, slug)


def worktree_list(repo):
    r = git("worktree", "list", "--porcelain", cwd=repo)
    if r is None or r.returncode != 0:
        return []
    paths = []
    for line in r.stdout.splitlines():
        if line.startswith("worktree "):
            paths.append(line[len("worktree "):].strip())
    return paths


def git_status_files(repo):
    """Return list of (x, y, path). Parses porcelain v1 -z."""
    try:
        r = subprocess.run(["git", "-C", repo, "status", "--porcelain=v1", "-z"],
                           capture_output=True, text=True, timeout=10)
        if r is None or r.returncode != 0:
            return []
        out = []
        for entry in r.stdout.split("\0"):
            if len(entry) < 4:
                continue
            out.append((entry[0], entry[1], entry[3:].strip()))
        return out
    except (OSError, subprocess.SubprocessError):
        return []


def git_branch(repo):
    r = git("rev-parse", "--abbrev-ref", "HEAD", cwd=repo)
    if r is None or r.returncode != 0:
        return "(detached)"
    return r.stdout.strip()


def git_ahead_behind(repo, base):
    r = git("rev-list", "--left-right", "--count", base + "...HEAD", cwd=repo)
    if r is None or r.returncode != 0:
        return (0, 0)
    try:
        a, b = r.stdout.strip().split()
        return (int(a), int(b))
    except ValueError:
        return (0, 0)


def git_upstream(repo):
    r = git("rev-parse", "--abbrev-ref", "@{upstream}", cwd=repo)
    if r is None or r.returncode != 0:
        return None
    return r.stdout.strip()


def git_dirty(repo):
    return len(git_status_files(repo)) > 0


def git_head_detached(repo):
    r = git("symbolic-ref", "-q", "HEAD", cwd=repo)
    return r is None or r.returncode != 0


def git_diff(repo, path):
    r = git("diff", "--", path, cwd=repo)
    if r is None or r.returncode != 0:
        return ""
    if not r.stdout.strip():
        r2 = git("diff", "--cached", "--", path, cwd=repo)
        if r2 and r2.returncode == 0:
            return r2.stdout
    return r.stdout


def new_terminal_id():
    return "t-" + secrets.token_hex(4)


def new_session_id():
    return "ses_" + uuid.uuid4().hex


def agent_command(cfg, agent, session, d):
    tmpl = cfg.get("BALAMBA_AGENT_%s_COMMAND" % agent, "opencode --session {{session}}")
    return tmpl.replace("{{session}}", session).replace("{{dir}}", d)


def reconcile_state(st):
    """Drop tasks whose worktree path vanished from `git worktree list`."""
    for p in st.get("projects", []):
        try:
            known = set(worktree_list(p["path"]))
        except Exception:
            continue
        kept = []
        for t in p.get("tasks", []):
            if t.get("path") in known or not os.path.exists(t.get("path", "")):
                # keep tasks whose path is registered; drop only if the repo
                # no longer lists it AND path is gone... spec: removed-by-hand
                # worktrees disappear. Use worktree-list as authority when
                # the repo is readable.
                if t.get("path") in known:
                    kept.append(t)
                elif not known:
                    kept.append(t)
                # else: dropped (removed by hand)
            else:
                kept.append(t)
        p["tasks"] = kept
    return st
