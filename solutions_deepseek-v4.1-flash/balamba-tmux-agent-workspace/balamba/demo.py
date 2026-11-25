"""Seeded, self-contained demo workspace.

`balamba demo` is deliberately sandboxed: it sets BALAMBA_STATE_DIR,
BALAMBA_CONFIG_DIR, BALAMBA_TMUX_SOCKET and BALAMBA_DEMO_ROOT before any
workspace object is created.  It never touches the real ~/.config/balamba or
the real `-L balamba` server.

The demo defines a second agent purely through config (the stretch goal): a
small scripted terminal that prints a colourful, fake agent transcript.  No
code in the application knows about it.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .config import Config, ensure_layout_files, load_config
from .workspace import Workspace, WorkspaceError

DEMO_AGENT = r'''#!/bin/bash
# Demo agent — defined entirely by BALAMBA_AGENT_demo_* in the demo config.
session="${1:-ses_demo}"
dir="${2:-$PWD}"
esc=$'\033'
clear
printf '%s[1;35m◆ demo agent%s[0m  %s\n' "$esc" "$esc" "${session:0:18}…"
printf '%s[2m%s%s[0m\n' "$esc" "$dir" "$esc"
printf '\n'
printf '%s[38;5;42m▸ reading working tree%s[0m\n' "$esc" "$esc"
sleep 0.4
printf '%s[38;5;42m▸ planning%s[0m\n' "$esc" "$esc"
printf '  1. inspect the login redirect\n  2. isolate the token refresh\n  3. add a regression test\n'
printf '\n'
printf '%s[38;5;214m● editing%s[0m src/session.ts\n' "$esc" "$esc"
for i in $(seq 1 4); do
  printf '  %s[38;5;244m[%s/4]%s[0m patching session refresh path…\n' "$esc" "$i" "$esc"
  sleep 0.7
done
printf '\n%s[38;5;42m✓ done%s[0m 2 files changed · tests pending\n' "$esc" "$esc"
printf '\n%s[2mtask board%s[0m\n' "$esc" "$esc"
printf '  %s[38;5;42m[x]%s[0m reproduce redirect loop\n' "$esc" "$esc"
printf '  %s[38;5;42m[x]%s[0m isolate token refresh\n' "$esc" "$esc"
printf '  %s[38;5;214m[ ]%s[0m add a regression test\n' "$esc" "$esc"
printf '  %s[38;5;214m[ ]%s[0m update the login docs\n' "$esc" "$esc"
printf '\n%s[2mchanged files%s[0m\n' "$esc" "$esc"
printf '  %s[38;5;214mM%s[0m  src/session.ts\n' "$esc" "$esc"
printf '  %s[38;5;214mM%s[0m  README.md\n' "$esc" "$esc"
printf '  %s[38;5;177m??%s[0m notes.md\n' "$esc" "$esc"
printf '\n%s[2mready for review · print the session id to resume later%s[0m\n' "$esc" "$esc"
printf '%s[2m────────────────────────────────────────────%s[0m\n' "$esc" "$esc"
printf 'agent> '
while true; do
  if IFS= read -r -t 10 line; then
    printf '\n%s[38;5;117magent%s[0m received: %s\n' "$esc" "$esc" "$line"
    printf '  %s[2m(scripted demo, no model was called)%s\n' "$esc" "$esc"
    printf 'agent> '
  else
    printf '\n%s[2m· still here — type something or switch tabs%s[0m\n' "$esc" "$esc"
    printf 'agent> '
  fi
done
'''


def _run(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=check,
        env={**os.environ, "GIT_AUTHOR_NAME": "balamba demo", "GIT_AUTHOR_EMAIL": "demo@example.invalid",
             "GIT_COMMITTER_NAME": "balamba demo", "GIT_COMMITTER_EMAIL": "demo@example.invalid"},
    )


def _make_repo(path: Path, files: dict[str, str]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-q", "-b", "main"], path)
    for name, content in files.items():
        target = path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    _run(["git", "add", "."], path)
    # Re-running the demo may find nothing new to commit; that is fine.
    subprocess.run(
        ["git", "commit", "-qm", "initial commit"],
        cwd=str(path),
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "balamba demo",
             "GIT_AUTHOR_EMAIL": "demo@example.invalid",
             "GIT_COMMITTER_NAME": "balamba demo",
             "GIT_COMMITTER_EMAIL": "demo@example.invalid"},
    )
    _run(["git", "update-ref", "refs/remotes/origin/main", "HEAD"], path)


AURORA_FILES = {
    "README.md": "# Aurora UI\n\nA small design-system playground.\n",
    "package.json": '{"name":"aurora-ui","version":"1.0.0"}\n',
    "src/app.ts": "export const app = () => {\n  return 'aurora';\n};\n",
    "src/session.ts": "export function refresh(token: string) {\n  return token;\n}\n",
    "src/login.ts": "export function login(user: string) {\n  return fetch('/login?user=' + user);\n}\n",
}

PIPELINE_FILES = {
    "README.md": "# Pipeline service\n\nJob runner and scheduler.\n",
    "src/worker.py": "def run(job):\n    return job.run()\n",
    "src/scheduler.py": "JOBS = []\n\ndef add(job):\n    JOBS.append(job)\n",
    "tests/test_worker.py": "def test_placeholder():\n    assert True\n",
}

DEMO_CONFIG_TEMPLATE = """\
# balamba demo config — sourced bash, all values are real.
BALAMBA_TREE_WIDTH=30
BALAMBA_GIT_WIDTH=34
BALAMBA_EDITOR="${{EDITOR:-vi}}"
BALAMBA_AGENT_DEFAULT=demo
BALAMBA_AGENTS=("demo")
BALAMBA_AGENT_demo_COMMAND="{agent} {{{{session}}}} {{{{dir}}}}"
BALAMBA_AGENT_demo_RESUME="{agent} {{{{session}}}} {{{{dir}}}}"
BALAMBA_KEY_PREFIX="ctrl+a"
BALAMBA_TREE_KEYS="down:j up:k collapse:h expand:l activate:enter new-task:n new-terminal:t close-task:d editor:e add-project:p"
BALAMBA_TMUX_SOCKET="{socket}"
BALAMBA_WORKTREES_ROOT="{worktrees}"
"""


def prepare(reset: bool = False) -> Workspace:
    root = Path(
        os.environ.get("BALAMBA_DEMO_ROOT")
        or (Path.home() / ".cache" / "balamba-demo")
    ).expanduser()
    import hashlib

    socket = "balamba-demo-" + hashlib.sha1(str(root.resolve()).encode()).hexdigest()[:6]
    if reset and root.exists():
        try:
            subprocess.run(
                ["tmux", "-L", socket, "kill-server"], capture_output=True, timeout=5
            )
        except Exception:
            pass
        shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    state_dir = root / "state"
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    os.environ["BALAMBA_DEMO_ROOT"] = str(root)
    os.environ["BALAMBA_STATE_DIR"] = str(state_dir)
    os.environ["BALAMBA_CONFIG_DIR"] = str(config_dir)
    os.environ["BALAMBA_TMUX_SOCKET"] = socket

    agent_script = root / "demo_agent.sh"
    agent_script.write_text(DEMO_AGENT, encoding="utf-8")
    agent_script.chmod(0o755)
    config_file = config_dir / "config"
    config_file.write_text(
        DEMO_CONFIG_TEMPLATE.format(
            agent=agent_script,
            socket=socket,
            worktrees=root / "balamba_worktrees",
        ),
        encoding="utf-8",
    )
    ensure_layout_files()

    ws = Workspace(load_config())
    if ws.state.projects:
        return ws

    src = root / "src"
    aurora = src / "aurora-ui"
    pipeline = src / "pipeline-service"
    _make_repo(aurora, AURORA_FILES)
    _make_repo(pipeline, PIPELINE_FILES)

    try:
        p_aurora = ws.add_project(str(aurora))
        t1, _ = ws.create_task(
            p_aurora, "Redesign login flow", "redesign-login", "origin/main", "agent", agent="demo"
        )
        t2, _ = ws.create_task(
            p_aurora, "Add OAuth callback", "oauth-callback", "origin/main", "agent", agent="demo"
        )
        scratch = ws.create_tab(p_aurora, None, "shell")
        p_pipeline = ws.add_project(str(pipeline))
        t3, _ = ws.create_task(
            p_pipeline, "Trace slow jobs", "trace-slow-jobs", "origin/main", "agent", agent="demo"
        )
        ws.create_tab(p_pipeline, t3, "shell")

        # Make the git panel interesting: staged, unstaged and untracked changes.
        readme = Path(t1.path) / "README.md"
        readme.write_text(readme.read_text() + "\n## Login redesign\n\nWork in progress.\n")
        (Path(t1.path) / "src/session.ts").write_text(
            "export function refresh(token: string, retry = true) {\n"
            "  if (retry) return token;\n"
            "  return token;\n"
            "}\n"
        )
        (Path(t1.path) / "notes.md").write_text("- [ ] reproduce redirect loop\n- [ ] token refresh\n")
        _run(["git", "add", "src/session.ts"], Path(t1.path))
        (Path(t2.path) / "src/oauth.ts").write_text("export const callback = '/oauth/callback';\n")
        (Path(t3.path) / "src/worker.py").write_text(
            "import time\n\ndef run(job):\n    started = time.time()\n    return job.run(), time.time() - started\n"
        )

        ws.state.active_project = p_aurora.path
        ws.state.active_task = t1.slug
        ws.state.active_tab = t1.windows[0].id if t1.windows else ""
        p_aurora.expanded = True
        t1.expanded = True
        t2.expanded = False
        p_pipeline.expanded = False
        ws.dirty = True
        ws.save()
    except WorkspaceError as exc:
        print(f"demo setup problem: {exc}")
    return ws
