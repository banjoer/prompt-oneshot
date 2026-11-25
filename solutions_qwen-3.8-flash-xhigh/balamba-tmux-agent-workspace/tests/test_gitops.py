import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from balamba import gitops


def write(repo: Path, name: str, content: str):
    (repo / name).write_text(content)


def test_validate_main_checkout_ok(repo: Path):
    info = gitops.validate_main_checkout(str(repo))
    assert info.ok
    assert info.is_main_checkout, info.warning


def test_validate_rejects_non_repo(tmp_path):
    d = tmp_path / "plain"
    d.mkdir()
    info = gitops.validate_main_checkout(str(d))
    assert not info.ok


def test_validate_rejects_subdir(repo: Path):
    sub = repo / "sub"
    sub.mkdir()
    info = gitops.validate_main_checkout(str(sub))
    assert not info.ok


def test_validate_warns_on_linked_worktree(repo: Path, tmp_path):
    wt = tmp_path / "wt-linked"
    ok, err = gitops.worktree_add(str(repo), "side-branch", str(wt), "HEAD")
    assert ok, err
    info = gitops.validate_main_checkout(str(wt))
    assert info.ok and not info.is_main_checkout
    assert "worktree" in info.warning


def test_slug_validation(repo: Path):
    assert gitops.check_branch_name(str(repo), "fix-login")
    assert not gitops.check_branch_name(str(repo), "-bad name")


def test_ref_exists(repo: Path):
    assert gitops.ref_exists(str(repo), "origin/main")
    assert gitops.ref_exists(str(repo), "main")
    assert not gitops.ref_exists(str(repo), "origin/nope")


def test_worktree_add_no_upstream(repo: Path, tmp_path):
    wt = tmp_path / "wt" / "feat"
    ok, err = gitops.worktree_add(str(repo), "feat", str(wt), "origin/main")
    assert ok, err
    r = subprocess.run(["git", "-C", str(wt), "rev-parse", "--abbrev-ref",
                        "feat@{upstream}"], capture_output=True, text=True)
    assert r.returncode != 0
    ok2, _ = gitops.worktree_remove(str(repo), str(wt))
    assert ok2


def test_ahead_behind_and_upstream(repo: Path, tmp_path):
    wt = tmp_path / "wt-ab"
    ok, err = gitops.worktree_add(str(repo), "ab", str(wt), "origin/main")
    assert ok, err
    write(wt, "a.txt", "1\n")
    subprocess.run(["git", "add", "a.txt"], cwd=str(wt), check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-m", "c"], cwd=str(wt), check=True,
                   capture_output=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "--allow-empty", "-m", "c2"], cwd=str(wt),
                   check=True, capture_output=True)
    ab = gitops.ahead_behind(str(wt), "origin/main")
    assert ab == (2, 0)
    assert gitops.upstream_of(str(wt)) is None     # thanks to --no-track
    gitops.worktree_remove(str(repo), str(wt), force=True)


def test_status_markers_and_renames(repo: Path):
    write(repo, "tracked.txt", "x\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=str(repo), check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-m", "add"], cwd=str(repo), check=True,
                   capture_output=True)
    write(repo, "tracked.txt", "y\n")             # unstaged change
    write(repo, "brand-new.txt", "n\n")           # untracked
    (repo / "rm.txt").write_text("z\n")
    subprocess.run(["git", "add", "rm.txt"], cwd=str(repo), check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-m", "rm"], cwd=str(repo), check=True,
                   capture_output=True)
    (repo / "rm.txt").rename(repo / "mv.txt")     # rename
    entries = gitops.status_files(str(repo))
    kinds = {e.path: e.marker for e in entries}
    assert kinds.get("tracked.txt") in (" M", "M ")
    assert kinds.get("brand-new.txt") == "??"
    # stage just the rename so git reports it as R with the original path
    subprocess.run(["git", "add", "rm.txt", "mv.txt"], cwd=str(repo), check=True)
    entries = gitops.status_files(str(repo))
    mv = next((e for e in entries if e.path == "mv.txt"), None)
    assert mv is not None and mv.x == "R"
    assert mv.orig_path == "rm.txt"
    assert mv.staged and not mv.unstaged
    text, how = gitops.file_diff(str(repo), mv)
    assert "rm.txt" in text or "mv.txt" in text
    untracked = next(e for e in entries if e.path == "brand-new.txt")
    assert untracked.untracked
    text2, how2 = gitops.file_diff(str(repo), untracked)
    assert "n" in text2


def test_branch_delete_refuses_unmerged(repo: Path, tmp_path):
    wt = tmp_path / "wt-b"
    ok, err = gitops.worktree_add(str(repo), "unmerged", str(wt), "origin/main")
    assert ok, err
    write(wt, "f", "1")
    subprocess.run(["git", "add", "f"], cwd=str(wt), check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-m", "c"], cwd=str(wt), check=True,
                   capture_output=True)
    gitops.worktree_remove(str(repo), str(wt), force=True)
    ok2, err2 = gitops.branch_delete(str(repo), "unmerged")
    assert not ok2, "git branch -d must refuse an unmerged branch"


def test_dirty_and_detached(repo: Path, tmp_path):
    assert not gitops.worktree_is_dirty(str(repo))
    write(repo, "dirty", "1")
    assert gitops.worktree_is_dirty(str(repo))
    wt = tmp_path / "wt-d"
    gitops.worktree_add(str(repo), "det", str(wt), "origin/main")
    subprocess.run(["git", "checkout", "--detach", "origin/main"],
                   cwd=str(wt), check=True, capture_output=True)
    assert gitops.is_detached(str(wt))
    name, detached = gitops.current_branch(str(wt))
    assert detached and name not in ("", "HEAD")
