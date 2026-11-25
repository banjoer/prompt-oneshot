"""Pytest fixtures: isolated HOME-ish dirs for balamba, fake git repo."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(Path(__file__).parent))

import helpers  # noqa: E402


@pytest.fixture(autouse=True)
def bal_dirs(tmp_path, monkeypatch):
    """Isolate config + state dirs per test."""
    cfg = tmp_path / "blm-config"
    st = tmp_path / "blm-state"
    cfg.mkdir(); st.mkdir()
    monkeypatch.setenv("BALAMBA_CONFIG_DIR", str(cfg))
    monkeypatch.setenv("BALAMBA_STATE_DIR", str(st))
    (cfg / "config").write_text(
        "BALAMBA_TREE_WIDTH=30\nBALAMBA_GIT_WIDTH=34\n"
        'BALAMBA_EDITOR="echo EDITOR-RAN"\n'
        'BALAMBA_AGENTS=("echoer")\n'
        'BALAMBA_AGENT_DEFAULT=echoer\n'
        'BALAMBA_AGENT_echoer_COMMAND="echo AGENT-START {{session}}; '
        'echo CWD {{dir}}; sleep 60"\n'
        'BALAMBA_AGENT_echoer_RESUME="echo AGENT-RESUME {{session}}; sleep 60"\n'
    )
    return cfg, st


@pytest.fixture()
def repo(tmp_path):
    """A git main checkout with origin/main, living OUTSIDE the state dirs."""
    src = tmp_path / "srcroot"
    src.mkdir()
    return helpers.make_repo(src)
