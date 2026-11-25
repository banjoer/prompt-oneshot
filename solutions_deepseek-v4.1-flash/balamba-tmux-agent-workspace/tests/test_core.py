"""Core tests: state/config/git/worktree/restore. No Textual needed."""

from __future__ import annotations

import json
import os
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from balamba import gitops  # noqa: E402
from balamba.config import load_config  # noqa: E402
from balamba.state import (  # noqa: E402
    State,
    load_state,
    save_state,
    slugify,
)
from balamba.tmuxctl import layout_leaf_count  # noqa: E402
from balamba.workspace import Workspace, WorkspaceError  # noqa: E402

from helpers import Sandbox, base_config  # noqa: E402


class SlugTests(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(slugify("Fix Login Flow"), "fix-login-flow")
        self.assertEqual(slugify("  Many   spaces  "), "many-spaces")
        self.assertEqual(slugify("héllo/wörld"), "hllowrld")
        self.assertEqual(slugify("A__B..C"), "a__b..c")
        self.assertEqual(slugify("---"), "task")
        self.assertEqual(slugify(""), "task")


class LayoutTests(unittest.TestCase):
    def test_leaf_count(self):
        self.assertEqual(layout_leaf_count("b25d,80x24,0,0,1"), 1)
        self.assertEqual(
            layout_leaf_count("b8de,100x30,0,0{50x30,0,0,1,49x30,51,0[49x15,51,0,2,49x14,51,16,3]}"),
            3,
        )
        self.assertEqual(layout_leaf_count(""), 0)


class ConfigTests(unittest.TestCase):
    def test_bash_config_arrays_and_keys(self):
        with Sandbox("config") as box:
            agent = box.dir / "other-agent.sh"
            box.write_config(
                base_config(31, 37)
                + f'''
BALAMBA_AGENTS+=("other")
BALAMBA_AGENT_other_COMMAND="{agent} {{{{session}}}} {{{{dir}}}}"
BALAMBA_AGENT_other_RESUME="{agent} resume {{{{session}}}}"
BALAMBA_KEY_PREFIX="ctrl+b"
BALAMBA_KEY_NEW_TASK="Z"
BALAMBA_TREE_KEYS="down:n up:e collapse:q expand:r activate:space new-task:a new-terminal:s close-task:c editor:o add-project:i"
'''
            )
            cfg = load_config()
            self.assertEqual(cfg.tree_width, 31)
            self.assertEqual(cfg.git_width, 37)
            self.assertEqual(set(cfg.agents), {"opencode", "other"})
            self.assertEqual(cfg.agent("other").name, "other")
            self.assertIn(str(agent), cfg.agent("other").command)
            self.assertEqual(cfg.prefix_key, "ctrl+b")
            self.assertEqual(cfg.command_key("new-task"), "Z")
            self.assertEqual(cfg.tree_keys["down"], "n")
            self.assertEqual(cfg.tree_keys["activate"], "space")

    def test_agent_template(self):
        with Sandbox("template") as box:
            box.write_config(base_config())
            cfg = load_config()
            rendered = cfg.agent("opencode").render("ses_abc", "/tmp/work", resume=True)
            self.assertEqual(rendered, "opencode --session ses_abc")


class StateTests(unittest.TestCase):
    def test_spec_skeleton_loads_with_stable_ids_and_layout(self):
        with Sandbox("state") as box:
            state_file = box.dir / "state" / "state.json"
            skeleton = {
                "version": 1,
                "projects": [
                    {
                        "path": "/home/me/src/widget",
                        "expanded": True,
                        "scratch": [],
                        "tasks": [
                            {
                                "slug": "fix-login",
                                "name": "Fix login",
                                "path": "/home/me/balamba_worktrees/widget/fix-login",
                                "base": "origin/main",
                                "windows": [
                                    {
                                        "kind": "agent",
                                        "agent": "opencode",
                                        "session": "ses_0123456789abcdef0123456789abcdef",
                                        "cwd": "/home/me/balamba_worktrees/widget/fix-login",
                                    }
                                ],
                                "window_layout": "b25d,120x30,0,0,1",
                                "active_window": 0,
                                "active_pane": 2,
                            }
                        ],
                    }
                ],
            }
            state_file.write_text(json.dumps(skeleton), encoding="utf-8")
            state1, _ = load_state(state_file)
            state2, _ = load_state(state_file)
            tab1 = state1.projects[0].tasks[0].windows[0]
            tab2 = state2.projects[0].tasks[0].windows[0]
            self.assertTrue(tab1.id.startswith("tab_"))
            self.assertEqual(tab1.id, tab2.id)
            self.assertEqual(tab1.layout, "b25d,120x30,0,0,1")
            self.assertEqual(tab1.active_pane, 2)
            self.assertEqual(state1.active_project, "")

    def test_round_trip_and_backup_recovery(self):
        with Sandbox("state2") as box:
            path = box.dir / "state" / "state.json"
            state = State()
            from balamba.state import Project, Task, TerminalTab

            project = Project(path=str(box.dir / "src" / "p"))
            task = Task(slug="s", name="S", path=str(box.dir / "wt"))
            task.windows.append(
                TerminalTab(name="shell", kind="shell", cwd=str(box.dir), panes=[str(box.dir)])
            )
            project.tasks.append(task)
            state.projects.append(project)
            save_state(state, path)
            save_state(state, path)  # second write creates the .bak fallback
            self.assertTrue(path.exists())
            path.write_text("{ broken", encoding="utf-8")
            recovered, warnings = load_state(path)
            self.assertEqual(len(recovered.projects), 1)
            self.assertTrue(any("recovered" in w for w in warnings))

    def test_unknown_json_keys_ignored(self):
        with Sandbox("state3") as box:
            path = box.dir / "state" / "state.json"
            path.write_text(json.dumps({"version": 1, "projects": [], "future": {"x": 1}}))
            state, _ = load_state(path)
            self.assertEqual(state.projects, [])


class GitTests(unittest.TestCase):
    def test_project_validation_and_worktree_rejection(self):
        with Sandbox("git") as box:
            repo = box.repo("widget")
            good = gitops.validate_project(repo)
            self.assertTrue(good.ok)
            self.assertFalse(good.is_worktree)
            self.assertFalse(gitops.validate_project(repo / ".").is_worktree)
            bad = gitops.validate_project(repo / "app.py")
            self.assertFalse(bad.ok)
            sub = repo / "src"
            sub.mkdir(exist_ok=True)
            check = gitops.validate_project(sub)
            self.assertFalse(check.ok)

            wt = gitops.add_worktree(str(repo), "wt-one", "origin/main")
            self.assertTrue(wt.ok, wt.output)
            worktree_check = gitops.validate_project(wt.path)
            self.assertTrue(worktree_check.is_worktree)
            self.assertIn("linked worktree", (worktree_check.warning or "").lower())

    def test_unique_names_and_no_upstream(self):
        with Sandbox("git2") as box:
            repo = box.repo("widget")
            first = gitops.unique_slug(str(repo), "Fix login", "fix-login")
            self.assertEqual((first.slug, first.display), ("fix-login", "Fix login"))
            added = gitops.add_worktree(str(repo), first.slug, "origin/main")
            self.assertTrue(added.ok, added.output)
            upstream = box.git(
                ["rev-parse", "--abbrev-ref", f"{first.slug}@{{upstream}}"], repo, check=False
            )
            self.assertNotEqual(upstream.returncode, 0)
            second = gitops.unique_slug(str(repo), "Fix login", "fix-login")
            self.assertEqual((second.slug, second.display), ("fix-login-2", "Fix login-2"))

    def test_status_porcelain_markers(self):
        with Sandbox("git3") as box:
            repo = box.repo("widget")
            (repo / "README.md").write_text("changed\n")
            (repo / "new.txt").write_text("new\n")
            box.git(["add", "new.txt"], repo)
            status = gitops.repo_status(str(repo), "origin/main")
            self.assertTrue(status.ok)
            by_path = {f.path: f for f in status.files}
            self.assertTrue(by_path["README.md"].unstaged)
            self.assertTrue(by_path["new.txt"].staged)
            self.assertIn("origin/main", status.comparison)


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox("ws")
        self.box.__enter__()
        self.repo = self.box.repo("widget")
        self.box.write_config(base_config())
        self.ws = Workspace(load_config())
        self.project = self.ws.add_project(str(self.repo))

    def tearDown(self):
        self.box.__exit__(None, None, None)

    def new_task(self, name="Fix login", kind="shell"):
        unique = self.ws.prepare_task_names(self.project, name, name)
        return self.ws.create_task(
            self.project, unique.display, unique.slug, "origin/main", kind
        )

    def test_task_creation_and_path(self):
        task, tab = self.new_task()
        self.assertEqual(task.slug, "fix-login")
        self.assertEqual(
            Path(task.path),
            Path(self.repo).parent / "balamba_worktrees" / "widget" / "fix-login",
        )
        self.assertTrue(Path(task.path).is_dir())
        self.assertEqual(tab.kind, "shell")
        self.assertEqual(tab.cwd, task.path)
        self.assertTrue(Path(tab.cwd).is_dir())
        branch = self.box.git(["rev-parse", "--abbrev-ref", "HEAD"], Path(task.path))
        self.assertEqual(branch.stdout.strip(), "fix-login")
        upstream = self.box.git(
            ["rev-parse", "--abbrev-ref", "fix-login@{upstream}"], self.repo, check=False
        )
        self.assertNotEqual(upstream.returncode, 0)

    def test_collision_suffixes_name_and_slug(self):
        first, _ = self.new_task("Fix login")
        second, _ = self.new_task("Fix login")
        self.assertEqual(first.slug, "fix-login")
        self.assertEqual(second.slug, "fix-login-2")
        self.assertEqual(second.name, "Fix login-2")
        self.assertTrue(Path(second.path).exists())

    def test_close_task_branch_semantics(self):
        task, _ = self.new_task("Clean")
        result = self.ws.close_task(self.project, task, force=False, delete_branch=False)
        self.assertTrue(result.ok, result.message)
        self.assertFalse(Path(task.path).exists())
        self.assertEqual(
            self.box.git(["rev-parse", "--verify", "refs/heads/clean"], self.repo, check=False).returncode,
            0,
        )

        task2, _ = self.new_task("Dirty")
        (Path(task2.path) / "dirty.txt").write_text("dirty\n")
        self.box.git(["config", "user.email", "test@example.invalid"], Path(task2.path))
        self.box.git(["config", "user.name", "test"], Path(task2.path))
        self.box.git(["add", "."], Path(task2.path))
        self.box.git(["commit", "-qm", "unmerged work"], Path(task2.path))
        (Path(task2.path) / "still-dirty.txt").write_text("dirty\n")
        warnings = self.ws.task_warnings(self.project, task2)
        self.assertTrue(any("dirty" in w for w in warnings))
        result = self.ws.close_task(self.project, task2, force=True, delete_branch=True)
        self.assertTrue(result.ok, result.message)
        self.assertFalse(result.branch_deleted)
        self.assertIn("not fully merged", result.branch_message)
        self.assertEqual(
            self.box.git(["rev-parse", "--verify", "refs/heads/dirty"], self.repo, check=False).returncode,
            0,
        )

    def test_remove_project_keeps_disk(self):
        task, _ = self.new_task("Keep me")
        self.ws.remove_project(self.project)
        self.assertTrue(Path(self.repo).is_dir())
        self.assertTrue(Path(task.path).is_dir())
        self.assertEqual(self.ws.state.projects, [])

    def test_reconcile_drops_missing_worktrees(self):
        task, _ = self.new_task("Gone")
        self.box.git(["worktree", "remove", "--force", task.path], self.repo)
        self.ws.reconcile()
        self.assertEqual(self.project.tasks, [])

    def test_split_restore_active_tab_and_shell_cwd(self):
        task, tab = self.new_task("Restore me")
        win = self.ws.window_ids[tab.id]
        new_pane_id = self.ws.split_tab(tab, vertical=True)
        panes = self.ws.tmux.list_panes(win)
        self.assertEqual(len(panes), 2)
        shell = next(p for p in panes if p.id == new_pane_id)
        self.ws.tmux.send_literal(shell.id, "cd /tmp")
        self.ws.tmux.send_key(shell.id, "Enter")
        import time

        for _ in range(30):
            time.sleep(0.2)
            current = next(p for p in self.ws.tmux.list_panes(win) if p.id == new_pane_id)
            if current.cwd == "/tmp":
                break
        current = next(p for p in self.ws.tmux.list_panes(win) if p.id == new_pane_id)
        self.assertEqual(current.cwd, "/tmp")
        second = self.ws.create_tab(self.project, task, "shell")
        self.ws.state.active_tab = second.id
        task.active_window = 1
        self.ws.capture_metadata(save=False)
        self.ws.save()
        saved_ids = [(t.id, t.session) for t in task.windows]
        saved_layout = task.windows[0].layout
        self.ws.tmux.kill_server()

        restarted = Workspace(load_config())
        report = restarted.startup()
        self.assertTrue(report.restored)
        project2 = restarted.state.project_by_path(str(self.repo))
        self.assertIsNotNone(project2)
        task2 = project2.tasks[0]
        self.assertEqual([(t.id, t.session) for t in task2.windows], saved_ids)
        self.assertEqual(restarted.state.active_tab, second.id)
        restored_win = restarted.window_ids[task2.windows[0].id]
        restored_panes = restarted.tmux.list_panes(restored_win)
        self.assertEqual(len(restored_panes), 2)
        self.assertEqual(len(task2.windows[0].layout), len(saved_layout))
        self.assertIn("/tmp", [p.cwd for p in restored_panes])


class ExclusiveEnvTests(unittest.TestCase):
    def test_cli_doctor_and_project_validation(self):
        import subprocess

        with Sandbox("cli") as box:
            env = os.environ.copy()
            proc = subprocess.run(
                [str(ROOT / "bin" / "balamba"), "doctor"],
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("DeepSeek V4.1 Flash 1017", proc.stdout)
            self.assertIn("textual", proc.stdout.lower())

            bad = subprocess.run(
                [str(ROOT / "bin" / "balamba"), "project", "add", str(box.dir / "not-a-repo")],
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
            )
            self.assertNotEqual(bad.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
