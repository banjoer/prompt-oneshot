"""Shared test helpers: git repo fixture + app factory with isolated dirs."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SOLUTION_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOLUTION_DIR / "lib"))


def git(cwd, *args, env_extra=None):
    env = dict(os.environ)
    env.update({
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
        "HOME": str(cwd),
    })
    if env_extra:
        env.update(env_extra)
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True, check=True, env=env)


def make_repo(root: Path, name: str = "widget", with_origin: bool = True) -> Path:
    """Create a main checkout with one commit; optionally an origin remote."""
    repo = root / name
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, "init", "-b", "main")
    (repo / "README.md").write_text("hello\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "first")
    if with_origin:
        bare = root / (name + ".git")
        git(root, "clone", "--bare", str(repo), str(bare))
        git(repo, "remote", "add", "origin", str(bare))
        git(repo, "fetch", "origin")
    return repo
