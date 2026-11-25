import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from balamba import common, task as task_mod


def load():
    return common.load_state()


def add_project(state, path):
    state["projects"].append({"path": str(path), "expanded": True,
                              "scratch": [], "tasks": []})
    common.save_state(state)
    return state


def create_and_save(project_path, name, slug, base, term):
    state = load()
    created = task_mod.create_task(state, str(project_path), name, slug, base,
                                   term)
    common.save_state(state)
    return created


def test_create_task_worktree_and_branch(repo, tmp_path):
    add_project(load(), repo)
    created = create_and_save(repo, "My Task", "my-task", "origin/main",
                              {"kind": "shell"})
    assert created.task["path"] == str(tmp_path / "srcroot" /
        "balamba_worktrees" / "widget" / "my-task")
    assert os.path.isdir(created.task["path"])
    assert Path(created.task["path"], ".git").exists()
    # branch exists, no upstream
    r = subprocess.run(["git", "-C", created.task["path"], "rev-parse",
                        "--abbrev-ref", "my-task@{upstream}"],
                       capture_output=True, text=True)
    assert r.returncode != 0
    # state persisted + base stored
    again = load()
    t = again["projects"][0]["tasks"][0]
    assert t["base"] == "origin/main" and t["slug"] == "my-task"
    assert t["windows"][0]["cwd"] == created.task["path"]
    # window_layout / active_pane fields kept for schema compatibility
    assert "windows" in t and "active_window" in t


def test_collision_suffixes(repo):
    add_project(load(), repo)
    c1 = create_and_save(repo, "Dup", "dup", "main", {"kind": "shell"})
    c2 = create_and_save(repo, "Dup", "dup", "main", {"kind": "shell"})
    c3 = create_and_save(repo, "Dup", "dup", "main", {"kind": "shell"})
    assert c1.task["slug"] == "dup" and c1.task["name"] == "Dup"
    assert c2.task["slug"] == "dup-2" and c2.task["name"] == "Dup-2"
    assert c3.task["slug"] == "dup-3" and c3.task["name"] == "Dup-3"
    assert os.path.isdir(c3.task["path"])


def test_close_task_keeps_branch_by_default(repo):
    add_project(load(), repo)
    created = create_and_save(repo, "Close me", "close-me", "main",
                              {"kind": "shell"})
    pi, ti = created.project_index, created.task_index
    assess = task_mod.assess_close(load(), pi, ti)
    assert not assess.dirty and not assess.detached
    res = task_mod.close_task(load(), pi, ti, delete_branch=False,
                              kill_windows=lambda t: None)
    assert res.ok
    assert not os.path.isdir(created.task["path"])
    rb = subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify",
                         "refs/heads/close-me"], capture_output=True, text=True)
    assert rb.returncode == 0            # branch kept!


def test_close_task_dirty_second_confirm_force(repo):
    add_project(load(), repo)
    created = create_and_save(repo, "Dirty", "dirty", "main", {"kind": "shell"})
    Path(created.task["path"], "junk.txt").write_text("mess\n")
    pi, ti = created.project_index, created.task_index
    assess = task_mod.assess_close(load(), pi, ti)
    assert assess.dirty
    killed = []
    res = task_mod.close_task(load(), pi, ti, delete_branch=False,
                              kill_windows=lambda t: killed.append(t["slug"]))
    assert res.ok                          # --force path (past confirm 2)
    assert not os.path.isdir(created.task["path"])
    assert killed == ["dirty"]


def test_close_task_delete_merged_branch(repo):
    add_project(load(), repo)
    created = create_and_save(repo, "Merged", "merged", "main", {"kind": "shell"})
    pi, ti = created.project_index, created.task_index
    res = task_mod.close_task(load(), pi, ti, delete_branch=True,
                              kill_windows=lambda t: None)
    assert res.ok and any("deleted branch" in n for n in res.notes)


def test_reconcile_drops_missing_worktrees(repo):
    add_project(load(), repo)
    created = create_and_save(repo, "Gone", "gone", "main", {"kind": "shell"})
    subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force",
                    created.task["path"]], check=True, capture_output=True)
    st = load()
    notes = task_mod.reconcile(st)
    assert any("gone" in n for n in notes)
    assert st["projects"][0]["tasks"] == []


def test_reconcile_ignores_unknown_dirs(repo, tmp_path):
    add_project(load(), repo)
    # a stray dir in balamba_worktrees that state knows nothing about
    stray = tmp_path / "srcroot" / "balamba_worktrees" / "widget" / "stray"
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "--detach",
                    str(stray), "main"], check=True, capture_output=True)
    st = load()
    task_mod.reconcile(st)
    assert st["projects"][0]["tasks"] == []   # never silently adopted


def test_terminal_spec_shell_and_agent():
    cfg = common.load_config()
    shell = task_mod.terminal_spec(cfg, {"kind": "shell", "cwd": "/x"})
    assert shell.startswith("/")
    agent = task_mod.terminal_spec(cfg, {"kind": "agent", "agent": "opencode",
                                         "session": "ses_" + "0" * 32,
                                         "cwd": "/x"})
    assert agent == "opencode --session ses_" + "0" * 32
