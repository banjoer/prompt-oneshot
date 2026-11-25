"""End-to-end UI tests with the Textual pilot (headless driver)."""

import os
import sys
import json
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

import pytest
from textual.widgets import Input

from balamba import common
from balamba.app import BalambaApp
from balamba.dialogs import (ChoiceScreen, ConfirmScreen, DiffScreen,
                             EditorScreen, PromptScreen)


def make_app():
    cfg = common.load_config()
    state = common.load_state()
    return BalambaApp(cfg, state)


@pytest.fixture()
async def app_under_test(bal_dirs, repo):
    cfg, st = bal_dirs
    state = common.load_state()
    state["projects"].append({"path": str(repo), "expanded": True,
                              "scratch": [], "tasks": []})
    common.save_state(state)
    app = make_app()
    return app


class TestProjectAddCLI:
    def test_project_add_rejects_non_repo(self, tmp_path, monkeypatch):
        from balamba import cli
        monkeypatch.setenv("BALAMBA_STATE_DIR", str(tmp_path))
        plain = tmp_path / "plain"
        plain.mkdir()
        assert cli.cmd_project_add(str(plain)) == 1

    def test_project_add_ok(self, repo, tmp_path, monkeypatch):
        from balamba import cli
        st = tmp_path / "state"
        st.mkdir()
        monkeypatch.setenv("BALAMBA_STATE_DIR", str(st))
        assert cli.cmd_project_add(str(repo)) == 0
        state = common.load_state()
        assert state["projects"][0]["path"] == str(repo)


@pytest.mark.asyncio()
class TestAppUI:
    async def test_layout_and_scratch_shell(self, app_under_test, repo):
        app = app_under_test
        async with app.run_test(size=(110, 30)) as pilot:
            await pilot.pause(1.2)
            # three-column chrome present
            assert app.query("#tree") and app.query("#content") and \
                app.query("#git") and app.query("#status")
            # empty project context got one shell tab
            assert len(app.ctx_terms()) == 1
            assert app.ctx_terms()[0]["kind"] == "shell"
            # tree shows project + scratch terminal
            lines = [t.plain for t in app.tree_lines()]
            assert any("widget" in ln for ln in lines)
            # status bar shows context + tab list
            status = app.status_text(110).plain
            assert status.startswith("balamba · widget")
            assert "[1:sh:widget]" in status
            # shell is live; type `echo hi`
            uid = app._active_uid()
            run = app.runs[uid]
            assert run.session is not None and run.session.alive()
            for ch in "echo hi":
                await pilot.press(ch)
            await pilot.press("enter")
            screen = ""
            for _ in range(30):
                await pilot.pause(0.2)
                screen = "\n".join(run.vt.screen_text())
                if "hi" in screen:
                    break
            assert "hi" in screen

    async def test_prefix_new_task_flow_and_tabs(self, app_under_test):
        app = app_under_test
        async with app.run_test(size=(110, 30)) as pilot:
            await pilot.pause(1.2)
            await pilot.press("ctrl+a")          # prefix
            await pilot.press("N")
            await pilot.pause(0.3)
            assert isinstance(app.screen, PromptScreen)
            app.screen.query_one(Input).value = "Add Tests"
            await pilot.press("enter")           # name
            await pilot.pause(0.3)
            # slug prefilled from name
            assert app.screen.query_one(Input).value == "add-tests"
            await pilot.press("enter")           # slug
            await pilot.pause(0.3)
            assert app.screen.query_one(Input).value == "origin/main"
            await pilot.press("enter")           # base
            await pilot.pause(0.3)
            assert isinstance(app.screen, ChoiceScreen)
            await pilot.press("enter")           # agent (first choice)
            await pilot.pause(1.5)
            assert len(app._projects()[0]["tasks"]) == 1
            task = app._projects()[0]["tasks"][0]
            assert task["slug"] == "add-tests"
            assert os.path.isdir(task["path"])
            # activated: ctx = task, one agent tab with ses_ id
            assert app.ctx_ti == 0
            w = task["windows"][0]
            assert w["kind"] == "agent" and w["session"].startswith("ses_")
            uid = app._active_uid()
            run = app.runs[uid]
            await pilot.pause(1.0)
            # echoer agent prints its session id (poll: reader thread timing)
            joined = ""
            for _ in range(30):
                await pilot.pause(0.2)
                joined = "\n".join(run.vt.screen_text())
                if "AGENT-START ses_" in joined:
                    break
            assert "AGENT-START ses_" in joined
            # branch has no upstream
            import subprocess
            r = subprocess.run(["git", "-C", task["path"], "rev-parse",
                                "--abbrev-ref", "add-tests@{upstream}"],
                               capture_output=True, text=True)
            assert r.returncode != 0

    async def test_tab_switch_and_unread_dot(self, app_under_test):
        app = app_under_test
        async with app.run_test(size=(110, 30)) as pilot:
            await pilot.pause(1.0)
            # add a second shell tab via tree key t
            app.tree_key("t")
            await pilot.pause(0.3)
            assert isinstance(app.screen, ChoiceScreen)
            await pilot.press("j")               # choose shell (2nd row)
            await pilot.press("enter")
            await pilot.pause(1.0)
            assert len(app.ctx_terms()) == 2
            first_uid = app.ctx_terms()[0]["uid"]
            second_uid = app.ctx_terms()[1]["uid"]
            assert app._active_uid() == second_uid
            # switch back to tab 1 with prefix digits
            await pilot.press("ctrl+a")
            await pilot.press("1")
            await pilot.pause(0.2)
            assert app._active_uid() == first_uid
            # output in the *inactive* tab 2 sets unread
            run2 = app.runs[second_uid]
            run2.session.write(b"printf 'bg-output\\n'\r")
            joined = ""
            for _ in range(25):
                await pilot.pause(0.2)
                joined = "\n".join(run2.vt.screen_text())
                if "bg-output" in joined:
                    break
            assert "bg-output" in joined
            assert run2.unread is True
            # activate tab 2 -> dot clears
            await pilot.press("ctrl+a")
            await pilot.press("2")
            await pilot.pause(0.3)
            assert app.runs[second_uid].unread is False

    async def test_git_panel_and_diff_popup(self, app_under_test, repo):
        app = app_under_test
        async with app.run_test(size=(110, 30)) as pilot:
            await pilot.pause(1.5)
            (repo / "untracked.md").write_text("hello diff\n")
            app._start_git_refresh()
            await pilot.pause(1.5)
            assert any("untracked.md" in t.plain for t in app.git_lines())
            # click the file row to open diff popup
            lines = app.git_lines()
            idx = next(i for i, t in enumerate(lines)
                       if "untracked.md" in t.plain)
            # simulate click hit-testing logic directly
            app.git_click_row(idx)
            await pilot.pause(1.5)
            assert isinstance(app.screen, DiffScreen)
            assert "hello diff" in app.screen.lines[0] or \
                any("hello diff" in ln for ln in app.screen.lines)
            await pilot.press("q")
            await pilot.pause(0.3)
            assert not isinstance(app.screen, DiffScreen)

    async def test_close_task_two_confirmations(self, app_under_test, repo):
        app = app_under_test
        async with app.run_test(size=(110, 30)) as pilot:
            await pilot.pause(1.0)
            # create a task programmatically through the flow entrypoints
            from balamba import task as task_mod
            state = app.state
            created = task_mod.create_task(state, str(repo), "To Close",
                                           "to-close", "main",
                                           task_mod.make_shell_terminal(""))
            app._build_runs_missing()
            app._repoint_run_contexts()
            app.set_ctx(created.project_index, created.task_index)
            await pilot.pause(1.0)
            task_path = created.task["path"]
            assert os.path.isdir(task_path)
            app.flow_close_task(created.project_index, created.task_index)
            await pilot.pause(0.3)
            assert isinstance(app.screen, ConfirmScreen)     # step 1
            await pilot.press("enter")
            await pilot.pause(0.3)
            assert isinstance(app.screen, ConfirmScreen)     # step 2
            # cancel at step 2 -> nothing happens
            await pilot.press("escape")
            await pilot.pause(0.3)
            assert os.path.isdir(task_path)
            # full confirm this time
            app.flow_close_task(created.project_index, created.task_index)
            await pilot.pause(0.3)
            await pilot.press("enter")
            await pilot.pause(0.3)
            await pilot.press("space")      # toggle "delete branch too" ON
            await pilot.press("enter")
            await pilot.pause(1.0)
            assert not os.path.isdir(task_path)
            import subprocess
            rb = subprocess.run(["git", "-C", str(repo), "rev-parse",
                                 "--verify", "refs/heads/to-close"],
                                capture_output=True, text=True)
            assert rb.returncode != 0        # branch was deleted (merged → -d ok)

    async def test_click_tree_and_chevron(self, app_under_test):
        app = app_under_test
        async with app.run_test(size=(110, 30)) as pilot:
            await pilot.pause(1.0)
            tree = app.query_one("#tree")
            # project row at y=1 (border), chevron column x<3
            from textual import events as tev
            rect = tree.region
            await pilot.click("#tree", offset=(1, 1), button=1)
            await pilot.pause(0.3)
            # clicking chevron collapsed the project (it was expanded)
            assert app._projects()[0]["expanded"] is False or \
                app.rows[0].expanded is False
            await pilot.click("#tree", offset=(1, 1), button=1)
            await pilot.pause(0.3)

    async def test_wheel_scrollback_select_mode(self, app_under_test):
        app = app_under_test
        async with app.run_test(size=(110, 30)) as pilot:
            await pilot.pause(1.0)
            run = app.runs[app._active_uid()]
            # generate scrollback: print 200 lines
            run.session.write(b"seq 1 200\r")
            for _ in range(30):
                await pilot.pause(0.2)
                if len(run.vt.scrollback) > 50:
                    break
            assert len(run.vt.scrollback) > 50
            # select mode on → wheel no longer forwarded to the app
            app.toggle_select_mode()
            run.widget._scroll_lines(5)
            assert run.widget.history_back == 5
            run.widget._scroll_lines(-5)
            assert run.widget.history_back == 0
            app.toggle_select_mode()
            assert app.select_mode is False

    async def test_restore_across_restart(self, app_under_test, repo):
        app = app_under_test
        async with app.run_test(size=(110, 30)) as pilot:
            await pilot.pause(1.0)
            from balamba import task as task_mod
            created = task_mod.create_task(app.state, str(repo), "Persist",
                                           "persist", "main",
                                           {"kind": "agent", "agent": "echoer",
                                            "session": "ses_" + "ab" * 16})
            app._build_runs_missing()
            app._repoint_run_contexts()
            app.set_ctx(created.project_index, created.task_index)
            await pilot.pause(1.0)
        # first app fully exits (ctx exit above ended the run_test); sessions
        # died with it. Start a NEW app from the persisted state:
        app2 = make_app()
        async with app2.run_test(size=(110, 30)) as pilot:
            t = app2._projects()[0]["tasks"][0]
            assert t["slug"] == "persist"
            uid = t["windows"][0]["uid"]
            run = app2.runs[uid]
            joined = ""
            for _ in range(40):
                await pilot.pause(0.2)
                run = app2.runs[uid]
                assert run.session is not None
                joined = "\n".join(run.vt.screen_text())
                if "AGENT-RESUME" in joined:
                    break
            assert "AGENT-RESUME" in joined      # resume template was used
            assert "ses_abab" in joined

    async def test_editor_popup(self, app_under_test):
        app = app_under_test
        async with app.run_test(size=(110, 30)) as pilot:
            await pilot.pause(1.0)
            app.flow_editor()
            await pilot.pause(1.5)
            # EDITOR is 'echo EDITOR-RAN' → exits instantly → screen pops back
            assert not isinstance(app.screen, EditorScreen)

    async def test_redraw_and_widths(self, app_under_test):
        app = app_under_test
        async with app.run_test(size=(110, 30)) as pilot:
            await pilot.pause(0.5)
            app.cfg.tree_width = 26
            app.action_redraw()
            await pilot.pause(0.5)
            assert app.query_one("#tree").region.width == 26

    async def test_status_tab_click(self, app_under_test):
        app = app_under_test
        async with app.run_test(size=(110, 30)) as pilot:
            await pilot.pause(1.0)
            # add a second tab
            app.flow_new_terminal()
            await pilot.pause(0.3)
            await pilot.press("j")
            await pilot.press("enter")       # shell tab #2
            await pilot.pause(1.0)
            assert len(app.ctx_terms()) == 2
            assert app._active_uid() == app.ctx_terms()[1]["uid"]
            # click tab 1 in the status bar
            app.status_text(110)
            x0, x1, _ = app._tab_rects[0]
            status = app.query_one("#status")
            sx = (x0 + x1) // 2
            await pilot.click(status, offset=(sx, 0))
            await pilot.pause(0.5)
            assert app._active_uid() == app.ctx_terms()[0]["uid"]

    async def test_right_click_menu(self, app_under_test):
        app = app_under_test
        async with app.run_test(size=(110, 30)) as pilot:
            await pilot.pause(1.0)
            app.tree_right_click(0, 4, 2)
            await pilot.pause(0.4)
            assert isinstance(app.screen, ChoiceScreen)
            labels = [c[1] for c in app.screen.choices]
            assert any("remove" in l for l in labels)
            assert any("new task" in l for l in labels)
            await pilot.press("escape")
            await pilot.pause(0.3)
            assert not isinstance(app.screen, ChoiceScreen)

    async def test_focus_cycle_and_tree_scroll(self, app_under_test):
        app = app_under_test
        async with app.run_test(size=(110, 30)) as pilot:
            await pilot.pause(1.2)
            tree = app.query_one("#tree")
            gitp = app.query_one("#git")
            uid = app._active_uid()
            term_w = app.runs[uid].widget
            assert app.focused is term_w          # content focused on boot
            app.action_cycle_focus()
            await pilot.pause(0.3)
            assert app.focused is gitp
            app.action_cycle_focus()
            await pilot.pause(0.3)
            assert app.focused is tree
            app.action_cycle_focus()
            await pilot.pause(0.3)
            assert app.focused is term_w
            tree.scroll_by(1)
            assert tree.view_top == 1
            tree.scroll_by(-1)
            assert tree.view_top == 0

    async def test_close_single_terminal_tab(self, app_under_test):
        app = app_under_test
        async with app.run_test(size=(110, 30)) as pilot:
            await pilot.pause(1.0)
            uid = app.ctx_terms()[0]["uid"]
            app.close_terminal(uid)
            await pilot.pause(0.5)
            assert app.ctx_terms() == []
            assert uid not in app.runs
            import json
            saved = json.loads(
                Path(os.environ["BALAMBA_STATE_DIR"], "state.json")
                .read_text())
            assert saved["projects"][0]["scratch"] == []

    async def test_detach_saves_state(self, app_under_test):
        app = app_under_test
        async with app.run_test(size=(110, 30)) as pilot:
            await pilot.pause(1.0)
            await pilot.press("ctrl+a")
            await pilot.press("d")
            await pilot.pause(0.6)
        saved = json.loads(
            Path(os.environ["BALAMBA_STATE_DIR"], "state.json").read_text())
        assert saved["projects"][0]["scratch"]
        # shell tab cwd captured
        assert saved["projects"][0]["scratch"][0]["cwd"].startswith("/")


class TestCLI:
    def test_task_list_output(self, repo, capsys):
        from balamba import cli
        st = common.load_state()
        st["projects"].append({"path": str(repo), "expanded": True,
                               "scratch": [], "tasks": []})
        common.save_state(st)
        cli.cmd_task_list()
        out = capsys.readouterr().out
        assert "widget" in out

    def test_doctor_reports_all_sections(self, repo, capsys, monkeypatch):
        from balamba import cli
        st = common.load_state()
        st["projects"].append({"path": str(repo), "expanded": True,
                               "scratch": [], "tasks": []})
        common.save_state(st)
        rc = cli.cmd_doctor()
        out = capsys.readouterr().out
        for needle in ("[server]", "[state]", "[config]", "[tools]",
                       "opencode", "Qwen 3.8 Flash", "balamba doctor"):
            assert needle in out, needle
        assert rc in (0, 1)

    def test_version_signoff(self, capsys):
        from balamba import cli
        print(cli.version_line())
        out = capsys.readouterr().out
        assert "2026-11-25" in out and "Qwen" in out

    def test_reconcile_via_save(self, repo, tmp_path, capsys):
        from balamba import cli, task as task_mod
        st = common.load_state()
        st["projects"].append({"path": str(repo), "expanded": True,
                               "scratch": [], "tasks": []})
        common.save_state(st)
        task_mod.create_task(common.load_state(), str(repo), "Ghost", "ghost",
                             "main", {"kind": "shell"})   # does not persist
        rc = cli.cmd_save()
        out = capsys.readouterr().out
        assert rc == 0
        assert "state" in out.lower()
