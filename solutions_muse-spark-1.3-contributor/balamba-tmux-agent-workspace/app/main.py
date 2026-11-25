#!/usr/bin/env python3
"""balamba Textual UI — ALL chrome lives here.

Three-column layout (tree | tabs+terminal | git) + status bar, tab handling,
dialogs, key bindings and mouse behaviour are Textual widgets/screens/events.
tmux (dedicated `balamba` server) is used underneath ONLY to host terminal
content (windows/panes, capture-pane, send-keys, restore). No tmux-driven
chrome, no tmux mouse bindings (mouse off in tmux.conf).

Sign-off: produced 2026-11-25 by Muse Spark 1.3 Contributor (opencode-go).
"""
import asyncio
import hashlib
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backend as B

from textual import events
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Select,
    Static,
    Tree,
)

VERSION_LINE = "balamba 1.0.0-textual (2026-11-25 by Muse Spark 1.3 Contributor)"


# ---------------- helpers ----------------

def ctx_of(state):
    """Return (project, task_or_None, terminal_or_None, cwd, label)."""
    projs = state.get("projects", [])
    if not projs:
        return None, None, None, os.path.expanduser("~"), "balamba · no project"
    a = state.get("active", {})
    pi = max(0, min(a.get("project", 0), len(projs) - 1))
    proj = projs[pi]
    ti = a.get("task", -1)
    task = None
    pool = []
    if isinstance(ti, int) and ti >= 0 and ti < len(proj.get("tasks", [])):
        task = proj["tasks"][ti]
        pool = task.get("windows", [])
    else:
        pool = proj.get("scratch", [])
    term = None
    if pool:
        ki = max(0, min(a.get("terminal", 0), len(pool) - 1))
        term = pool[ki]
    if task is not None:
        cwd = task.get("path", proj["path"])
        label = "balamba · %s / %s" % (os.path.basename(proj["path"]), task.get("name", task.get("slug", "")))
    else:
        cwd = proj["path"]
        label = "balamba · %s" % os.path.basename(proj["path"])
    if term is not None:
        label += " · %s" % term.get("title", term.get("id", ""))
    return proj, task, term, cwd, label


def all_terminals(state):
    out = []
    for pi, p in enumerate(state.get("projects", [])):
        for t in p.get("scratch", []):
            out.append((pi, -1, t))
        for ti, t in enumerate(p.get("tasks", [])):
            for k, w in enumerate(t.get("windows", [])):
                out.append((pi, ti, w))
    return out


def find_terminal(state, wid):
    for pi, p in enumerate(state.get("projects", [])):
        for t in p.get("scratch", []):
            if t.get("id") == wid:
                return pi, -1, t
        for ti, t in enumerate(p.get("tasks", [])):
            for w in t.get("windows", []):
                if w.get("id") == wid:
                    return pi, ti, w
    return None, None, None


# ---------------- modal screens ----------------

class AddProjectScreen(ModalScreen):
    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Add project (git main checkout path)"),
            Input(placeholder="/home/me/src/widget", id="path"),
            Horizontal(Button("Add", id="ok", variant="primary"), Button("Cancel", id="cancel")),
            id="dlg",
        )

    def on_button_pressed(self, e: Button.Pressed) -> None:
        if e.button.id == "ok":
            self.dismiss(self.query_one("#path", Input).value.strip())
        else:
            self.dismiss(None)


class NewTerminalScreen(ModalScreen):
    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("New terminal: agent | shell"),
            Select([("agent (opencode)", "agent"), ("shell", "shell")], value="agent", id="kind"),
            Horizontal(Button("Create", id="ok", variant="primary"), Button("Cancel", id="cancel")),
            id="dlg",
        )

    def on_button_pressed(self, e: Button.Pressed) -> None:
        if e.button.id == "ok":
            self.dismiss(self.query_one("#kind", Select).value)
        else:
            self.dismiss(None)


class NewTaskScreen(ModalScreen):
    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("New task"),
            Label("task name:"),
            Input(placeholder="Fix login", id="name"),
            Label("slug:"),
            Input(placeholder="fix-login", id="slug"),
            Label("create from (ref):"),
            Input(value="origin/main", id="base"),
            Label("terminal:"),
            Select([("agent (opencode)", "agent"), ("shell", "shell")], value="agent", id="kind"),
            Label("", id="err"),
            Horizontal(Button("Create", id="ok", variant="primary"), Button("Cancel", id="cancel")),
            id="dlg",
        )

    def on_input_changed(self, e: Input.Changed) -> None:
        if e.input.id == "name" and not self.query_one("#slug", Input).value:
            self.query_one("#slug", Input).value = B.slugify(e.value)

    def on_button_pressed(self, e: Button.Pressed) -> None:
        if e.button.id != "ok":
            self.dismiss(None)
            return
        name = self.query_one("#name", Input).value.strip() or "task"
        slug = self.query_one("#slug", Input).value.strip() or B.slugify(name)
        base = self.query_one("#base", Input).value.strip() or "origin/main"
        kind = self.query_one("#kind", Select).value
        self.dismiss({"name": name, "slug": slug, "base": base, "kind": kind})


class CloseTaskScreen1(ModalScreen):
    def __init__(self, warnings):
        super().__init__()
        self.warnings = warnings

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Close task?"),
            Label(self.warnings or "The worktree is clean."),
            Horizontal(Button("Cancel", id="cancel", variant="primary"), Button("Continue", id="ok", variant="error")),
            id="dlg",
        )

    def on_button_pressed(self, e: Button.Pressed) -> None:
        self.dismiss(e.button.id == "ok")


class CloseTaskScreen2(ModalScreen):
    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("The worktree directory will be DELETED from disk."),
            Checkbox("delete branch too (git branch -d)", id="delbr"),
            Horizontal(Button("Cancel", id="cancel", variant="primary"), Button("Delete worktree", id="ok", variant="error")),
            id="dlg",
        )

    def on_button_pressed(self, e: Button.Pressed) -> None:
        if e.button.id == "ok":
            self.dismiss(self.query_one("#delbr", Checkbox).value)
        else:
            self.dismiss(None)


class DiffScreen(ModalScreen):
    def __init__(self, title, body):
        super().__init__()
        self.title = title
        self.body = body

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label(self.title),
            ScrollableContainer(Static(self.body or "(no diff)", id="diffbody")),
            Button("Close (Esc)", id="ok", variant="primary"),
            id="dlg",
        )

    def on_button_pressed(self, e: Button.Pressed) -> None:
        self.dismiss(None)


class ContextMenuScreen(ModalScreen):
    def __init__(self, actions):
        super().__init__()
        self.actions = actions

    def compose(self) -> ComposeResult:
        items = [Button(a, id="m-%d" % i) for i, a in enumerate(self.actions)]
        items.append(Button("Cancel", id="cancel"))
        yield Vertical(Label("Actions"), *items, id="dlg")

    def on_button_pressed(self, e: Button.Pressed) -> None:
        if e.button.id == "cancel":
            self.dismiss(None)
        else:
            idx = int(e.button.id.split("-")[1])
            self.dismiss(self.actions[idx])


class HelpScreen(ModalScreen):
    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("balamba keys (Textual UI)"),
            Static(
                "Prefix C-a then: N new task · P add project · T new terminal ·\n"
                "e editor · d detach/quit UI · r redraw · 1..9 tab · n/p next/prev tab\n"
                "Tree focused (no prefix): j/k/arrows move · h/l collapse/expand ·\n"
                "Enter activate · n new task · t new terminal · d close task ·\n"
                "e editor · p add project · ? help\n"
                "Mouse: click row select/activate · click chevron toggle ·\n"
                "right-click menu · wheel scrolls in-app.",
            ),
            Button("Close", id="ok", variant="primary"),
            id="dlg",
        )

    def on_button_pressed(self, e: Button.Pressed) -> None:
        self.dismiss(None)


# ---------------- main app ----------------

class BalambaApp(App):
    CSS = """
    #main { height: 1fr; }
    #left { width: 30; border: solid green; }
    #right { width: 34; border: solid blue; }
    #mid { border: solid yellow; }
    #tabbar { height: 3; }
    #termview { height: 1fr; }
    #statusbar { height: 3; }
    #dlg { padding: 1 2; border: solid red; background: $surface; }
    .pane-title { text-style: bold; }
    .activetab { text-style: bold; }
    """

    def __init__(self):
        super().__init__()
        self.cfg = B.load_config()
        self.state = B.load_state()
        self.state = B.reconcile_state(self.state)
        B.save_state(self.state)
        self.prefix = False
        self.term_text = {}   # wid -> last capture
        self.term_hash = {}
        self.focused_pane = {}  # wid -> pane_id
        self._git_files = []
        self._restored = B.server_running()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main"):
            with Vertical(id="left"):
                yield Label("projects", classes="pane-title")
                yield Tree("balamba", id="tree")
            with Vertical(id="mid"):
                yield ScrollableContainer(id="tabbar")
                yield ScrollableContainer(Static("", id="termcontent"), id="termview")
                yield Input(placeholder="type here, Enter to send (prefix C-a …)", id="terminput")
            with Vertical(id="right"):
                yield Label("git", classes="pane-title")
                yield ScrollableContainer(Static("", id="gitcontent"), id="gitview")
                yield ListView(id="filelist")
        with Horizontal(id="statusbar"):
            yield Label("balamba", id="ctx")
            yield ScrollableContainer(Horizontal(id="tabbuttons"))
        yield Footer()

    async def on_mount(self) -> None:
        self.apply_widths()
        self.rebuild_tree()
        await self.restore_backend()
        await self.refresh_tabs()
        self.set_interval(0.5, self.poll_terminals)
        self.set_interval(2.0, self.poll_git)
        self.set_interval(5.0, self.poll_inactive)
        self.query_one("#tree", Tree).focus()

    # ---- layout / widths ----
    def apply_widths(self):
        try:
            self.query_one("#left").styles.width = int(self.cfg.get("BALAMBA_TREE_WIDTH", 30))
            self.query_one("#right").styles.width = int(self.cfg.get("BALAMBA_GIT_WIDTH", 34))
        except Exception:
            pass

    # ---- tree ----
    def rebuild_tree(self):
        tree = self.query_one("#tree", Tree)
        tree.clear()
        tree.root.expand()
        projs = self.state.get("projects", [])
        if not projs:
            tree.root.add_leaf("(p) add a project", data={"type": "hint"})
            return
        for pi, p in enumerate(projs):
            pname = os.path.basename(p.get("path", "?"))
            pnode = tree.root.add(
                "%s %s" % ("▾" if p.get("expanded", True) else "▸", pname),
                data={"type": "project", "pi": pi},
                expand=bool(p.get("expanded", True)),
            )
            if not p.get("expanded", True):
                continue
            for t in p.get("scratch", []):
                dot = "● " if t.get("unread") else ""
                pnode.add_leaf("%s⌁ %s (%s)" % (dot, t.get("title", t.get("id")), t.get("kind", "shell")),
                               data={"type": "terminal", "pi": pi, "ti": -1, "wid": t.get("id")})
            for ti, t in enumerate(p.get("tasks", [])):
                und = any(w.get("unread") for w in t.get("windows", []))
                dot = "● " if und else ""
                tnode = pnode.add("%s▾ %s [%s]" % (dot, t.get("name", t.get("slug")), t.get("slug")),
                                  data={"type": "task", "pi": pi, "ti": ti}, expand=True)
                for w in t.get("windows", []):
                    wdot = "● " if w.get("unread") else ""
                    tnode.add_leaf("%s%s %s (%s)" % (wdot, w.get("title", w.get("id")), w.get("kind", "?"), w.get("agent", "")) if w.get("kind") == "agent" else "%s%s (%s)" % (wdot, w.get("title", w.get("id")), w.get("kind", "shell")),
                                   data={"type": "terminal", "pi": pi, "ti": ti, "wid": w.get("id")})

    def selected_ref(self):
        tree = self.query_one("#tree", Tree)
        node = tree.cursor_node
        if node is None or node.data is None:
            a = self.state.get("active", {})
            return {"type": "project", "pi": a.get("project", 0)}
        return node.data

    # ---- tabs / status ----
    def _tabs_soon(self):
        """Schedule an async tab refresh from sync contexts."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self.refresh_tabs())

    async def refresh_tabs(self):
        proj, task, term, cwd, label = ctx_of(self.state)
        try:
            self.query_one("#ctx", Label).update(label + ("  [C-a…]" if self.prefix else ""))
        except Exception:
            pass
        bar = self.query_one("#tabbuttons", Horizontal)
        await bar.remove_children()
        terms = all_terminals(self.state)
        active_id = term.get("id") if term else None
        for (pi, ti, t) in terms[:18]:
            wid = t.get("id")
            title = t.get("title", wid)
            mark = "●" if t.get("unread") else ""
            btn = Button("%s%s" % (mark, title), id="tab-%s" % wid,
                         variant="primary" if wid == active_id else "default")
            bar.mount(btn)

    def on_button_pressed(self, e: Button.Pressed) -> None:
        bid = e.button.id or ""
        if bid.startswith("tab-"):
            self.activate_terminal(bid[4:])
        elif e.button.id == "ok":
            pass

    def activate_terminal(self, wid):
        pi, ti, t = find_terminal(self.state, wid)
        if t is None:
            return
        self.state.setdefault("active", {})["project"] = pi
        self.state["active"]["task"] = ti
        pool = self._pool(pi, ti)
        try:
            self.state["active"]["terminal"] = next(i for i, w in enumerate(pool) if w.get("id") == wid)
        except StopIteration:
            self.state["active"]["terminal"] = 0
        t["unread"] = False
        B.save_state(self.state)
        self.rebuild_tree()
        self._tabs_soon()
        self.poll_terminals()
        self.poll_git()

    def _pool(self, pi, ti):
        p = self.state["projects"][pi]
        if ti is not None and ti >= 0:
            return p["tasks"][ti].get("windows", [])
        return p.get("scratch", [])

    # ---- backend restore ----
    async def restore_backend(self):
        B.ensure_config()
        B.mirror_config_to_tmux(self.cfg)
        already = self._restored and B.server_running()
        B.ensure_backend_session()
        if already:
            # attach: ensure every terminal has a backend window; create missing
            for (pi, ti, t) in all_terminals(self.state):
                if not B.window_exists(t["id"]):
                    self.launch_backend(t, stagger=False)
        else:
            # rebuild from saved state in order, staggered. NOTE: the
            # placeholder __init__ window is removed only AFTER the rebuild:
            # killing a session's last window destroys the session.
            for i, (pi, ti, t) in enumerate(all_terminals(self.state)):
                if not B.window_exists(t["id"]):
                    self.launch_backend(t, stagger=False)
                    if i:
                        await asyncio.sleep(0.6)
            # restore saved layout when pane counts match, else equal splits
            for (pi, ti, t) in all_terminals(self.state):
                saved = t.get("window_layout", "")
                if saved:
                    live = len(B.list_panes(t["id"]))
                    leaves = saved.count(",") + 1 if saved else 1
                    # leaf-count heuristic: only reapply when counts match
                    if live and live == leaves:
                        B.tmux("select-layout", "-t", "balamba:" + t["id"], saved)
        # drop the placeholder window once real content exists
        wins = [w["name"] for w in B.list_windows()]
        if "__init__" in wins and len(wins) > 1:
            B.kill_window("__init__")
        self.apply_widths()
        await self.refresh_tabs()

    def launch_backend(self, t, stagger=True):
        B.ensure_backend_session()
        cwd = t.get("cwd", os.path.expanduser("~"))
        if not os.path.isdir(cwd):
            cwd = os.path.expanduser("~")
        if t.get("kind") == "agent":
            cmd = B.agent_command(self.cfg, t.get("agent", "opencode"),
                                  t.get("session", ""), cwd)
            if not t.get("session"):
                t["session"] = B.new_session_id()
                cmd = B.agent_command(self.cfg, t.get("agent", "opencode"), t["session"], cwd)
            # run in cwd: `cd dir; exec cmd`
            full = "cd %s && exec %s" % (_shq(cwd), cmd)
            B.new_window(t["id"], cwd, full)
        else:
            B.new_window(t["id"], cwd, os.environ.get("SHELL", "/bin/bash"))
        t["window_layout"] = B.window_layout(t["id"])

    # ---- polling ----
    def poll_terminals(self) -> None:
        proj, task, term, cwd, label = ctx_of(self.state)
        if term is None:
            try:
                self.query_one("#termcontent", Static).update("(no terminal — press t for new terminal, n for new task)")
            except Exception:
                pass
            return
        wid = term["id"]
        panes = B.list_panes(wid)
        if not panes:
            # backend window missing (server restarted?): relaunch
            self.launch_backend(term, stagger=False)
            panes = B.list_panes(wid)
        if panes and wid not in self.focused_pane:
            for p in panes:
                if p["active"]:
                    self.focused_pane[wid] = p["id"]
        # capture each pane
        chunks = []
        for p in panes or [{"id": "?", "cwd": cwd, "active": True}]:
            pid = p["id"]
            if pid == "?":
                text = "(backend window missing — relaunching…)"
            else:
                text = B.capture_pane(pid, 120)
                # unread: content changed while not viewing
                h = hashlib.sha1(text.encode(errors="replace")).hexdigest()
                if wid in self.term_hash and h != self.term_hash[wid] and p.get("active"):
                    # only mark unread when this window is not the viewed one
                    cur = ctx_of(self.state)[2]
                    if cur is None or cur.get("id") != wid:
                        term["unread"] = True
                if pid == self.focused_pane.get(wid, pid):
                    self.term_hash[wid] = h
                # persist cwd
                if p.get("cwd"):
                    term["cwd"] = p["cwd"]
            mark = "▣" if p["id"] == self.focused_pane.get(wid) else "▢"
            chunks.append("%s [%s]\n%s" % (mark, pid, text.rstrip("\n")[-4000:]))
        self.term_text[wid] = "\n\n".join(chunks)
        try:
            self.query_one("#termcontent", Static).update(self.term_text[wid] or "(empty)")
        except Exception:
            pass
        # activity-flag OR: keep monitor-activity semantics for doctor/unread
        try:
            if B.window_activity(wid):
                cur = ctx_of(self.state)[2]
                if cur is None or cur.get("id") != wid:
                    if not term.get("unread"):
                        term["unread"] = True
                        self.rebuild_tree()
                        self._tabs_soon()
        except Exception:
            pass
        B.save_state(self.state)

    def poll_git(self) -> None:
        proj, task, term, cwd, label = ctx_of(self.state)
        if proj is None:
            return
        repo = task.get("path", proj["path"]) if task else proj["path"]
        if not os.path.isdir(repo):
            return
        branch = B.git_branch(repo)
        base = task.get("base", "origin/main") if task else None
        up = B.git_upstream(repo)
        if up:
            a, b = B.git_ahead_behind(repo, "@{upstream}")
            ab = "ahead %d · behind %d (vs %s)" % (b, a, up)
        elif base and B.verify_ref(base, repo):
            a, b = B.git_ahead_behind(repo, base)
            ab = "ahead %d · behind %d (vs base %s)" % (b, a, base)
        else:
            ab = "no base/upstream"
        files = B.git_status_files(repo)
        lines = ["branch: %s" % branch, ab, "%d changed file(s)" % len(files), ""]
        for (x, y, p) in files[:40]:
            tag = "?"
            if x not in (" ", "?"):
                tag = "staged"
            elif y == "?":
                tag = "untracked"
            elif y != " ":
                tag = "unstaged"
            lines.append("[%s] %s" % (tag, p))
        try:
            self.query_one("#gitcontent", Static).update("\n".join(lines) or "(clean)")
        except Exception:
            pass
        try:
            lv = self.query_one("#filelist", ListView)
            lv.clear()
            self._git_files = [p for (x, y, p) in files[:40]]
            for i, p in enumerate(self._git_files):
                lv.append(ListItem(Label(p), name="f%d" % i))
        except Exception:
            pass

    def poll_inactive(self) -> None:
        # ~0.2Hz activation check for inactive windows (spec): only poll
        # activity flags, never full captures.
        try:
            cur = ctx_of(self.state)[2]
            curid = cur.get("id") if cur else None
            changed = False
            for (pi, ti, t) in all_terminals(self.state):
                if t.get("id") == curid:
                    continue
                try:
                    if B.window_activity(t["id"]) and not t.get("unread"):
                        t["unread"] = True
                        changed = True
                except Exception:
                    pass
            if changed:
                B.save_state(self.state)
                self.rebuild_tree()
                self._tabs_soon()
        except Exception:
            pass

    def on_list_view_selected(self, e: ListView.Selected) -> None:
        try:
            idx = e.index if hasattr(e, "index") else -1
            path = (self._git_files or [])[idx]
        except (IndexError, TypeError):
            return
        self.show_diff(path)

    def show_diff(self, path):
        proj, task, term, cwd, label = ctx_of(self.state)
        repo = task.get("path", proj["path"]) if task else proj["path"]
        body = B.git_diff(repo, path)
        self.push_screen(DiffScreen("diff: " + path, body))

    # ---- key handling: prefix C-a + tree keys ----
    async def on_key(self, e: events.Key) -> None:
        # text inputs keep their keys (prefix/help never hijack typing)
        focused = self.focused
        if isinstance(focused, Input):
            return
        # global help
        if e.key == "?":
            self.push_screen(HelpScreen())
            return
        if e.key == "ctrl+a":
            self.prefix = True
            await self.refresh_tabs()
            e.prevent_default()
            return
        if self.prefix:
            self.prefix = False
            await self.refresh_tabs()
            k = e.key
            mapping = {"N": "new_task", "P": "add_project", "T": "new_terminal",
                       "e": "editor", "d": "detach", "r": "redraw",
                       "n": "next_tab", "p": "prev_tab"}
            if k in mapping:
                await self.app_action(mapping[k])
                e.prevent_default()
                return
            if len(k) == 1 and k.isdigit() and k != "0":
                self.goto_tab(int(k) - 1)
                e.prevent_default()
                return
            return
        # tree-level keys (no prefix) when tree focused
        from textual.widgets import Tree as _Tree
        if isinstance(focused, _Tree):
            k = e.key
            if k in ("j", "down"):
                self.query_one("#tree", Tree).action_cursor_down()
                e.prevent_default()
            elif k in ("k", "up"):
                self.query_one("#tree", Tree).action_cursor_up()
                e.prevent_default()
            elif k in ("h", "left"):
                await self.tree_collapse()
                e.prevent_default()
            elif k in ("l", "right"):
                await self.tree_expand()
                e.prevent_default()
            elif k == "enter":
                self.tree_activate()
                e.prevent_default()
            elif k == "n":
                await self.app_action("new_task")
                e.prevent_default()
            elif k == "t":
                await self.app_action("new_terminal")
                e.prevent_default()
            elif k == "d":
                await self.app_action("close_task")
                e.prevent_default()
            elif k == "e":
                await self.app_action("editor")
                e.prevent_default()
            elif k == "p":
                await self.app_action("add_project")
                e.prevent_default()
            return
        # middle-pane terminal key forwarding (when not in Input)
        if e.key == "enter" and not isinstance(focused, Input):
            pass  # let focus be in input normally

    def on_tree_node_selected(self, e: Tree.NodeSelected) -> None:
        data = (e.node.data or {})
        if data.get("type") == "terminal":
            self.activate_terminal(data["wid"])
        elif data.get("type") == "task":
            st = self.state
            st.setdefault("active", {})["project"] = data["pi"]
            st["active"]["task"] = data["ti"]
            st["active"]["terminal"] = 0
            B.save_state(st)
            self._tabs_soon()
            self.poll_git()
        elif data.get("type") == "project":
            st = self.state
            st.setdefault("active", {})["project"] = data["pi"]
            B.save_state(st)
            self._tabs_soon()
            self.poll_git()

    async def on_mouse_down(self, e: events.MouseDown) -> None:
        # right-click on tree -> context menu (button 3)
        if e.button == 3:
            try:
                tree = self.query_one("#tree", Tree)
                if tree.has_focus or True:
                    self.show_context_menu()
                    e.prevent_default()
            except Exception:
                pass

    def show_context_menu(self):
        ref = self.selected_ref()
        if ref.get("type") == "terminal":
            actions = ["copy path", "reveal in editor", "restart agent", "split horizontal", "split vertical"]
        elif ref.get("type") == "task":
            actions = ["copy path", "reveal in editor", "new terminal", "close task"]
        elif ref.get("type") == "project":
            actions = ["copy path", "new task", "new terminal", "remove project"]
        else:
            actions = ["add project"]

        async def _handle(choice):
            if choice is None:
                return
            await self.context_action(choice, ref)
        self.push_screen(ContextMenuScreen(actions), _handle)

    async def context_action(self, choice, ref):
        if choice == "copy path":
            proj, task, term, cwd, label = ctx_of(self.state)
            self.notify("path: " + cwd)
        elif choice == "reveal in editor":
            await self.app_action("editor")
        elif choice == "restart agent":
            self.restart_agent(ref)
        elif choice in ("split horizontal", "split vertical"):
            proj, task, term, cwd, label = ctx_of(self.state)
            if term:
                B.split_window(term["id"], "h" if choice.endswith("horizontal") else "v", term.get("cwd", cwd))
        elif choice == "new terminal":
            await self.app_action("new_terminal")
        elif choice == "close task":
            await self.app_action("close_task")
        elif choice == "new task":
            await self.app_action("new_task")
        elif choice == "add project":
            await self.app_action("add_project")
        elif choice == "remove project":
            self.remove_project(ref.get("pi"))

    def restart_agent(self, ref):
        pi, ti, t = None, None, None
        if ref.get("type") == "terminal":
            pi, ti, t = find_terminal(self.state, ref["wid"])
        else:
            proj, task, term, cwd, label = ctx_of(self.state)
            t = term
        if not t or t.get("kind") != "agent":
            self.notify("not an agent terminal")
            return
        panes = B.list_panes(t["id"])
        target = self.focused_pane.get(t["id"], (panes[0]["id"] if panes else None))
        if target:
            B.send_keys(target, "C-c")
            B.send_literal(target, B.agent_command(self.cfg, t.get("agent", "opencode"), t.get("session", ""), t.get("cwd", "~")))
            B.send_keys(target, "Enter")

    async def tree_collapse(self):
        ref = self.selected_ref()
        if ref.get("type") == "project":
            self.state["projects"][ref["pi"]]["expanded"] = False
            B.save_state(self.state)
            self.rebuild_tree()
        self.query_one("#tree", Tree).focus()

    async def tree_expand(self):
        ref = self.selected_ref()
        if ref.get("type") == "project":
            self.state["projects"][ref["pi"]]["expanded"] = True
            B.save_state(self.state)
            self.rebuild_tree()
        self.query_one("#tree", Tree).focus()

    def tree_activate(self):
        self.on_tree_node_selected(type("E", (), {"node": self.query_one("#tree", Tree).cursor_node})())

    def goto_tab(self, idx):
        terms = all_terminals(self.state)
        if 0 <= idx < len(terms):
            self.activate_terminal(terms[idx][2]["id"])

    async def app_action(self, name):
        if name == "new_task":
            await self.do_new_task()
        elif name == "new_terminal":
            await self.do_new_terminal()
        elif name == "add_project":
            await self.do_add_project()
        elif name == "close_task":
            await self.do_close_task()
        elif name == "editor":
            await self.do_editor()
        elif name == "detach":
            await self.action_quit()
        elif name == "redraw":
            self.apply_widths()
            self.rebuild_tree()
            await self.refresh_tabs()
            self.poll_terminals()
            self.poll_git()
        elif name == "next_tab":
            terms = all_terminals(self.state)
            proj, task, term, cwd, label = ctx_of(self.state)
            if terms and term:
                ids = [t["id"] for (_, _, t) in terms]
                self.activate_terminal(ids[(ids.index(term["id"]) + 1) % len(ids)])
        elif name == "prev_tab":
            terms = all_terminals(self.state)
            proj, task, term, cwd, label = ctx_of(self.state)
            if terms and term:
                ids = [t["id"] for (_, _, t) in terms]
                self.activate_terminal(ids[(ids.index(term["id"]) - 1) % len(ids)])

    # ---- actions ----
    async def do_add_project(self):
        def _done(path):
            if not path:
                return
            try:
                resolved, warn = B.validate_project(os.path.expanduser(path))
            except ValueError as ex:
                self.notify(str(ex), severity="error")
                return
            if any(p["path"] == resolved for p in self.state.get("projects", [])):
                self.notify("project already added")
                return
            self.state["projects"].append({"path": resolved, "expanded": True, "scratch": [], "tasks": []})
            B.save_state(self.state)
            self.rebuild_tree()
            self._tabs_soon()
            if warn:
                self.notify(warn, severity="warning")
        self.push_screen(AddProjectScreen(), _done)

    def remove_project(self, pi):
        # removal is from balamba only; never touches disk
        try:
            self.state["projects"].pop(pi)
            B.save_state(self.state)
            self.rebuild_tree()
            self._tabs_soon()
        except Exception:
            pass

    async def do_new_terminal(self):
        projs = self.state.get("projects", [])
        if not projs:
            self.notify("add a project first (p)", severity="warning")
            return

        def _done(kind):
            if not kind:
                return
            a = self.state.get("active", {})
            pi = max(0, min(a.get("project", 0), len(self.state["projects"]) - 1))
            proj = self.state["projects"][pi]
            ti = a.get("task", -1)
            cwd = proj["path"]
            if isinstance(ti, int) and ti >= 0 and ti < len(proj.get("tasks", [])):
                cwd = proj["tasks"][ti].get("path", cwd)
            t = {"id": B.new_terminal_id(), "kind": kind,
                 "agent": self.cfg.get("BALAMBA_AGENT_DEFAULT", "opencode") if kind == "agent" else "",
                 "session": B.new_session_id() if kind == "agent" else "",
                 "cwd": cwd, "title": "%s %d" % (kind, len(all_terminals(self.state)) + 1)}
            if isinstance(ti, int) and ti >= 0:
                proj["tasks"][ti].setdefault("windows", []).append(t)
                self.state["active"]["terminal"] = len(proj["tasks"][ti]["windows"]) - 1
            else:
                proj.setdefault("scratch", []).append(t)
                self.state["active"]["task"] = -1
                self.state["active"]["terminal"] = len(proj["scratch"]) - 1
            B.save_state(self.state)
            self.launch_backend(t)
            self.rebuild_tree()
            self._tabs_soon()
            self.activate_terminal(t["id"])
        self.push_screen(NewTerminalScreen(), _done)

    async def do_new_task(self):
        projs = self.state.get("projects", [])
        if not projs:
            self.notify("add a project first (p)", severity="warning")
            return

        def _done(res):
            if not res:
                return
            self.create_task(res["name"], res["slug"], res["base"], res["kind"])
        self.push_screen(NewTaskScreen(), _done)

    def create_task(self, name, slug, base, kind):
        a = self.state.get("active", {})
        pi = max(0, min(a.get("project", 0), len(self.state["projects"]) - 1))
        proj = self.state["projects"][pi]
        repo = proj["path"]
        slug = B.slugify(slug or name)
        if not B.check_branch_valid(slug, repo):
            self.notify("invalid slug: %s" % slug, severity="error")
            return
        if not B.verify_ref(base, repo):
            self.notify("bad ref: %s" % base, severity="error")
            return
        parent = os.path.join(os.path.dirname(os.path.realpath(repo)),
                              "balamba_worktrees", os.path.basename(os.path.realpath(repo)))
        os.makedirs(parent, exist_ok=True)
        uniq = B.unique_slug(repo, slug, parent)
        dname = name if uniq == slug else "%s-%s" % (name, uniq[len(slug):].lstrip("-") or uniq.split("-")[-1])
        if uniq != slug:
            dname = name + uniq[len(slug):]
        path = os.path.join(parent, uniq)
        # exactly: git worktree add --no-track -b <slug> <path> <ref>
        r = B.git("worktree", "add", "--no-track", "-b", uniq, path, base, cwd=repo)
        if r is None or r.returncode != 0:
            self.notify("worktree add failed: %s" % ((r.stderr if r else "git error") or ""), severity="error")
            return
        t = {"id": B.new_terminal_id(), "kind": kind,
             "agent": self.cfg.get("BALAMBA_AGENT_DEFAULT", "opencode") if kind == "agent" else "",
             "session": B.new_session_id() if kind == "agent" else "",
             "cwd": path, "title": uniq}
        task = {"slug": uniq, "name": dname, "path": path, "base": base,
                "windows": [t], "window_layout": "", "active_window": 0, "active_pane": 0}
        proj.setdefault("tasks", []).append(task)
        self.state["active"]["task"] = len(proj["tasks"]) - 1
        self.state["active"]["terminal"] = 0
        B.save_state(self.state)
        self.launch_backend(t)
        t["window_layout"] = B.window_layout(t["id"])
        B.save_state(self.state)
        self.rebuild_tree()
        self._tabs_soon()
        self.activate_terminal(t["id"])
        self.notify("task %s created" % uniq)

    async def do_close_task(self):
        ref = self.selected_ref()
        if ref.get("type") != "task":
            # fall back to active task
            proj, task, term, cwd, label = ctx_of(self.state)
            a = self.state.get("active", {})
            if task is None:
                self.notify("select a task (d closes tasks)", severity="warning")
                return
            ref = {"type": "task", "pi": a.get("project", 0), "ti": a.get("task", -1)}
        proj = self.state["projects"][ref["pi"]]
        task = proj["tasks"][ref["ti"]]
        repo, path = proj["path"], task["path"]
        warns = []
        if B.git_dirty(path):
            warns.append("worktree is DIRTY (uncommitted changes).")
        if B.git_head_detached(path):
            warns.append("HEAD is DETACHED.")
        warns.append("path: " + path)

        def _step1(ok):
            if not ok:
                return
            def _step2(delbr):
                if delbr is None:
                    return
                self.close_task(ref["pi"], ref["ti"], delbr)
            self.push_screen(CloseTaskScreen2(), _step2)
        self.push_screen(CloseTaskScreen1("\n".join(warns)), _step1)

    def close_task(self, pi, ti, delete_branch):
        proj = self.state["projects"][pi]
        task = proj["tasks"][ti]
        for w in task.get("windows", []):
            B.kill_window(w["id"])
        # git worktree remove <path> (--force only after 2nd confirmation — granted here)
        r = B.git("worktree", "remove", "--force", task["path"], cwd=proj["path"])
        if r is None or r.returncode != 0:
            r2 = B.git("worktree", "remove", task["path"], cwd=proj["path"])
            if r2 is None or r2.returncode != 0:
                self.notify("worktree remove failed", severity="error")
                return
        if delete_branch:
            # git branch -d so unmerged is never silently dropped
            rb = B.git("branch", "-d", task["slug"], cwd=proj["path"])
            if rb is None or rb.returncode != 0:
                self.notify("branch kept (not fully merged?)", severity="warning")
        proj["tasks"].pop(ti)
        self.state["active"]["task"] = -1
        self.state["active"]["terminal"] = 0
        B.save_state(self.state)
        self.rebuild_tree()
        self._tabs_soon()
        self.poll_git()

    async def do_editor(self):
        proj, task, term, cwd, label = ctx_of(self.state)
        if proj is None:
            return
        repo = task.get("path", proj["path"]) if task else proj["path"]
        editor = self.cfg.get("BALAMBA_EDITOR", os.environ.get("EDITOR", "nvim"))
        suspend = getattr(self, "suspend", None)
        if callable(suspend):
            with self.suspend():
                subprocess.run([editor], cwd=repo)
        else:
            # fallback: display-popup equivalent = modal notice
            self.push_screen(DiffScreen("editor", "run in a shell:\ncd %s && %s" % (repo, editor)))

    # ---- terminal input ----
    def on_input_submitted(self, e: Input.Submitted) -> None:
        if e.input.id != "terminput":
            return
        proj, task, term, cwd, label = ctx_of(self.state)
        if term is None:
            e.input.value = ""
            return
        panes = B.list_panes(term["id"])
        target = self.focused_pane.get(term["id"])
        if target is None and panes:
            target = panes[0]["id"]
        if target:
            B.send_literal(target, e.value)
            B.send_keys(target, "Enter")
        e.input.value = ""


def _shq(s):
    return "'" + s.replace("'", "'\\''") + "'"


def main():
    app = BalambaApp()
    app.run()


if __name__ == "__main__":
    main()
