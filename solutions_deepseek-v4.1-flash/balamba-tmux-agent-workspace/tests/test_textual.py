"""Headless Textual tests: layout, keys, mouse, dialogs, diff, wheel."""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from balamba.app import BalambaApp  # noqa: E402
from balamba.config import load_config  # noqa: E402
from balamba.screens.dialogs import NewTaskScreen, TerminalMenuScreen  # noqa: E402
from balamba.screens.viewers import DiffScreen, InfoScreen  # noqa: E402
from balamba.tmuxctl import layout_leaf_count  # noqa: E402
from balamba.workspace import Workspace  # noqa: E402

from helpers import Sandbox, base_config  # noqa: E402


async def settle(pilot, delay: float = 0.4) -> None:
    await pilot.pause(delay)


async def boot(app, pilot) -> None:
    for _ in range(200):
        await pilot.pause(0.05)
        if not app.booting:
            break
    if app.booting:
        raise AssertionError("app did not finish booting")
    await pilot.pause(0.6)


class TextualTests(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox("ui")
        self.box.__enter__()
        self.repo = self.box.repo("widget")
        self.box.write_config(base_config(tree_width=28, git_width=30))
        self.ws = Workspace(load_config())
        self.project = self.ws.add_project(str(self.repo))
        unique = self.ws.prepare_task_names(self.project, "First task", "first-task")
        self.task, self.tab = self.ws.create_task(
            self.project, unique.display, unique.slug, "origin/main", "shell"
        )
        (Path(self.task.path) / "README.md").write_text("changed\n")
        (Path(self.task.path) / "new.txt").write_text("new\n")

    def tearDown(self):
        self.box.__exit__(None, None, None)

    def test_layout_tree_prefix_and_dialogs(self):
        async def scenario():
            app = BalambaApp(self.ws)
            async with app.run_test(size=(120, 36)) as pilot:
                await boot(app, pilot)
                self.assertIsNotNone(app.tree_panel)
                self.assertIsNotNone(app.git_panel)
                self.assertGreater(app.tree_panel.size.width, 15)
                self.assertGreater(app.git_panel.size.width, 15)
                self.assertGreater(app.terminal.size.width, 20)
                rows = app.tree_panel.view.rows
                self.assertEqual(rows[0].kind, "project")
                self.assertTrue(any(r.kind == "task" for r in rows))
                self.assertTrue(any(r.kind == "terminal" for r in rows))
                # content was captured and painted
                for _ in range(50):
                    await pilot.pause(0.1)
                    if app.terminal.views:
                        break
                self.assertTrue(app.terminal.views)
                # tree keyboard navigation and chevron mouse click
                app.focus_tree()
                await settle(pilot, 0.1)
                app.tree_panel.view.selected_key = rows[0].key
                app.tree_panel.selected_key = rows[0].key
                before = self.project.expanded
                await pilot.click(app.tree_panel.view, offset=(2, 0))
                await settle(pilot, 0.2)
                self.assertNotEqual(self.project.expanded, before)
                # restore expansion for later assertions
                self.project.expanded = True
                app.tree_panel.refresh_view()
                # prefix N opens the Textual wizard
                await pilot.press("ctrl+a", "N")
                await settle(pilot, 0.3)
                self.assertIsInstance(app.screen, NewTaskScreen)
                screen = app.screen
                self.assertTrue(screen.query_one("#task-input"))
                screen.dismiss(None)
                await asyncio.sleep(0.2)
                # prefix T opens the terminal menu
                await pilot.press("ctrl+a", "t")
                await settle(pilot, 0.3)
                self.assertIsInstance(app.screen, TerminalMenuScreen)
                app.screen.dismiss(None)
                await asyncio.sleep(0.2)
                # help screen and sign-off
                await pilot.press("f1")
                await settle(pilot, 0.3)
                self.assertIsInstance(app.screen, InfoScreen)
                body = str(app.screen.body)
                self.assertIn("DeepSeek V4.1 Flash 1017", body)
                app.screen.dismiss(None)
                await asyncio.sleep(0.2)
            try:
                self.ws.tmux.kill_server()
            except Exception:
                pass

        asyncio.run(scenario())

    def test_status_click_git_diff_and_wheel(self):
        async def scenario():
            # A second tab makes the clickable status list meaningful.
            second = self.ws.create_tab(self.project, self.task, "shell")
            app = BalambaApp(self.ws)
            async with app.run_test(size=(130, 38)) as pilot:
                await boot(app, pilot)
                # switch tabs through the status bar hit regions
                regions = [r for r in app.status_bar.regions if r[3].startswith("tab:")]
                self.assertGreaterEqual(len(regions), 2)
                target = next(
                    (r for r in regions if r[3] == f"tab:{self.tab.id}"), regions[0]
                )
                y, x0, x1, _, _ = target
                await pilot.click(app.status_bar, offset=((x0 + x1) // 2, y))
                await settle(pilot, 0.4)
                self.assertEqual(self.ws.state.active_tab, self.tab.id)
                # refresh the git panel and open a file diff
                await app._git_async()
                await settle(pilot, 0.2)
                body = app.git_panel.body
                self.assertTrue(body._file_rows)
                y, _ = body._file_rows[0]
                await pilot.click(body, offset=(4, y))
                await settle(pilot, 0.8)
                self.assertIsInstance(app.screen, DiffScreen)
                screen = app.screen
                screen.dismiss(None)
                await asyncio.sleep(0.2)
                # wheel scrolls captured terminal scrollback
                app.focus_terminal()
                await pilot.pause(0.2)
                from textual import events

                await pilot._post_mouse_events(
                    [events.MouseScrollUp], widget=app.terminal, offset=(5, 5), button=0
                )
                await pilot.pause(0.4)
                self.assertGreater(app.terminal.scrollback_offset, 0)
            try:
                self.ws.tmux.kill_server()
            except Exception:
                pass

        asyncio.run(scenario())

    def test_custom_prefix_and_tree_keys(self):
        self.box.write_config(
            base_config(26, 28)
            + 'BALAMBA_KEY_PREFIX="ctrl+b"\nBALAMBA_KEY_NEW_TASK="Z"\n'
            + 'BALAMBA_TREE_KEYS="down:n up:e collapse:q expand:r activate:space new-task:a new-terminal:s close-task:c editor:o add-project:i"\n'
        )
        cfg = load_config()
        ws = Workspace(cfg)
        async def scenario():
            app = BalambaApp(ws)
            async with app.run_test(size=(110, 34)) as pilot:
                await boot(app, pilot)
                await pilot.press("ctrl+b", "Z")
                await settle(pilot, 0.3)
                self.assertIsInstance(app.screen, NewTaskScreen)
                app.screen.dismiss(None)
                await asyncio.sleep(0.2)
                app.focus_tree()
                await settle(pilot, 0.1)
                # custom "a" is new-task in the tree; "n" is down
                self.assertEqual(ws.config.tree_keys["new-task"], "a")
                self.assertEqual(ws.config.tree_keys["down"], "n")
            try:
                ws.tmux.kill_server()
            except Exception:
                pass

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main(verbosity=2)
