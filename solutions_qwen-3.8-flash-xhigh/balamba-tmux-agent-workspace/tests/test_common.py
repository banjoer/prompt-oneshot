import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from balamba import common


def test_slug_rules():
    assert common.make_slug("Fix Login!") == "fix-login"
    assert common.make_slug("  Weird   chars *** here  ") == "weird-chars-here"
    assert common.make_slug("UPPER case 2.0") == "upper-case-2.0"
    assert common.make_slug("----") == "task"
    assert common.make_slug("a__b--c") == "a__b-c"


def test_agent_session_id_shape():
    sid = common.new_agent_session_id()
    assert sid.startswith("ses_") and len(sid) == 36
    int(sid[4:], 16)  # hex


def test_config_parses_spec_sample(tmp_path):
    cfg_file = tmp_path / "config"
    cfg_file.write_text(
        "# balamba config\n"
        "BALAMBA_TREE_WIDTH=30\n"
        "BALAMBA_GIT_WIDTH=34\n"
        'BALAMBA_EDITOR="${EDITOR:-nvim}"\n'
        "BALAMBA_AGENT_DEFAULT=opencode\n"
        'BALAMBA_AGENTS=("opencode")\n'
        'BALAMBA_AGENT_opencode_COMMAND="opencode --session {{session}}"\n'
        'BALAMBA_AGENT_opencode_RESUME="opencode --session {{session}}"\n'
    )
    cfg = common.load_config(cfg_file)
    assert cfg.tree_width == 30 and cfg.git_width == 34
    assert cfg.editor in ("nvim",) or cfg.editor  # EDITOR env respected
    cmd = cfg.agent_command("opencode", "ses_abc", "/x")
    assert cmd == "opencode --session ses_abc"


def test_config_second_agent_by_config_only(tmp_path):
    cfg_file = tmp_path / "config"
    cfg_file.write_text(
        'BALAMBA_AGENTS=("opencode" "mybot")\n'
        'BALAMBA_AGENT_mybot_COMMAND="mybot --resume {{session}} --dir {{dir}}"\n'
        'BALAMBA_AGENT_mybot_RESUME="mybot --resume {{session}} --dir {{dir}}"\n'
    )
    cfg = common.load_config(cfg_file)
    assert "mybot" in cfg.agents
    out = cfg.agent_command("mybot", "ses_1", "/tmp/wt")
    assert out == "mybot --resume ses_1 --dir /tmp/wt"


def test_state_roundtrip_and_locking(tmp_path, monkeypatch):
    monkeypatch.setenv("BALAMBA_STATE_DIR", str(tmp_path))
    st = common.empty_state()
    st["projects"].append({"path": "/x", "expanded": False, "scratch": [],
                           "tasks": []})
    common.save_state(st)
    got = common.load_state()
    assert got["projects"][0]["path"] == "/x"
    with common.state_write_lock():
        st2 = common.load_state()
        st2["projects"][0]["expanded"] = True
        common.save_state(st2)
    assert common.load_state()["projects"][0]["expanded"] is True


def test_state_corrupt_recovers(tmp_path, monkeypatch):
    monkeypatch.setenv("BALAMBA_STATE_DIR", str(tmp_path))
    Path(tmp_path, "state.json").write_text("{not json")
    st = common.load_state()
    assert st["projects"] == []
    assert st["_balamba_errors"]


def test_worktree_path_mapping():
    assert common.worktree_path_for("/path/to/project_folder", "slug") == \
        "/path/to/balamba_worktrees/project_folder/slug"


def test_instance_lock(tmp_path, monkeypatch):
    monkeypatch.setenv("BALAMBA_STATE_DIR", str(tmp_path))
    fd = common.acquire_instance_lock()
    assert fd is not None
    assert common.acquire_instance_lock() is None      # second refuses
    common.release_instance_lock(fd)
    fd2 = common.acquire_instance_lock()
    assert fd2 is not None
    common.release_instance_lock(fd2)
