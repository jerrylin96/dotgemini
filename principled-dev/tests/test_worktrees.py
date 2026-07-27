import os
import subprocess
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from principled_dev.git import Git, is_within, repository_id
from principled_dev.lock import FileLock
from principled_dev.worktrees import WorktreeError, WorktreeManager


def run(*args, cwd=None, check=True, env=None):
    return subprocess.run(
        args,
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
        env=env,
    )


def git(repo, *args, check=True):
    return run("git", "-C", str(repo), *args, check=check)


def make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "principled-dev test")
    git(repo, "config", "user.email", "test@example.invalid")
    (repo / "tracked.txt").write_text("one\n", encoding="utf-8")
    git(repo, "add", "tracked.txt")
    git(repo, "commit", "-qm", "one")
    return repo, git(repo, "rev-parse", "HEAD").stdout.strip()


def commit(repo, text):
    (repo / "tracked.txt").write_text(text, encoding="utf-8")
    git(repo, "add", "tracked.txt")
    git(repo, "commit", "-qm", text.strip())
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def test_repository_identity_uses_canonical_common_dir(tmp_path):
    repo, head = make_repo(tmp_path)
    linked = tmp_path / "linked"
    git(repo, "worktree", "add", "-q", "--detach", str(linked), head)

    alias = tmp_path / "repo-alias"
    alias.symlink_to(repo, target_is_directory=True)

    assert Git(repo).common_dir() == Git(linked).common_dir()
    assert Git(repo).common_dir() == Git(alias).common_dir()
    assert repository_id(repo) == repository_id(linked) == repository_id(alias)


def test_containment_resolves_symlinks_before_comparison(tmp_path):
    root = tmp_path / "cache"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "escape").symlink_to(outside, target_is_directory=True)

    assert is_within(root / "ordinary" / "child", root)
    assert not is_within(root / "escape" / "victim", root)
    assert not is_within(root.parent / "cache-sibling", root)


def test_file_lock_is_a_posix_process_lock(tmp_path):
    lock_path = tmp_path / "repo.lock"
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    code = """
import sys
from principled_dev.lock import FileLock
try:
    with FileLock(sys.argv[1], blocking=False):
        print("acquired")
except BlockingIOError:
    print("locked")
"""
    env = {**os.environ, "PYTHONPATH": str(scripts)}

    with FileLock(lock_path):
        child = run(
            sys.executable, "-c", code, str(lock_path), cwd=tmp_path, check=False, env=env
        )
        assert child.returncode == 0, child.stderr
        assert child.stdout.strip() == "locked"

    child = run(
        sys.executable, "-c", code, str(lock_path), cwd=tmp_path, check=False, env=env
    )
    assert child.returncode == 0, child.stderr
    assert child.stdout.strip() == "acquired"


def test_feature_worktree_is_attached_and_reused_only_on_exact_state(tmp_path):
    repo, head = make_repo(tmp_path)
    manager = WorktreeManager(repo, tmp_path / "cache")

    feature = manager.create_feature("topic", head)
    assert feature.is_dir()
    assert Git(feature).head() == head
    assert Git(feature).symbolic_branch() == "refs/heads/topic"
    assert manager.create_feature("topic", head) == feature

    git(feature, "switch", "-qc", "impostor")
    with pytest.raises(WorktreeError, match="branch"):
        manager.create_feature("topic", head)
    assert feature.is_dir()
    assert Git(feature).symbolic_branch() == "refs/heads/impostor"


def test_dirty_feature_is_never_reset_or_deleted_and_removal_is_dirty_safe(tmp_path):
    repo, first = make_repo(tmp_path)
    manager = WorktreeManager(repo, tmp_path / "cache")
    feature = manager.create_feature("topic", first)
    second = commit(repo, "two\n")
    dirty = feature / "local.txt"
    dirty.write_text("keep me\n", encoding="utf-8")

    with pytest.raises(WorktreeError, match="dirty"):
        manager.create_feature("topic", second)
    assert feature.is_dir()
    assert dirty.read_text(encoding="utf-8") == "keep me\n"
    assert Git(feature).head() == first

    with pytest.raises(WorktreeError, match="dirty"):
        manager.remove_feature("topic")
    assert feature.is_dir()
    dirty.unlink()

    manager.remove_feature("topic")
    assert not feature.exists()
    assert git(repo, "show-ref", "--verify", "--quiet", "refs/heads/topic", check=False).returncode == 0


def test_review_worktree_is_detached_exact_and_disposable(tmp_path):
    repo, first = make_repo(tmp_path)
    second = commit(repo, "two\n")
    manager = WorktreeManager(repo, tmp_path / "cache")

    review = manager.create_review(first)
    assert Git(review).head() == first
    assert Git(review).symbolic_branch() is None

    git(review, "checkout", "-q", "--detach", second)
    scratch = review / "scratch.txt"
    scratch.write_text("discard me\n", encoding="utf-8")

    assert manager.create_review(first) == review
    assert Git(review).head() == first
    assert Git(review).symbolic_branch() is None
    assert not scratch.exists()
    assert not Git(review).is_dirty()


def test_review_pruning_preserves_features_kept_reviews_and_unknown_entries(tmp_path):
    repo, first = make_repo(tmp_path)
    second = commit(repo, "two\n")
    manager = WorktreeManager(repo, tmp_path / "cache")
    feature = manager.create_feature("topic", first)
    kept = manager.create_review(first)
    stale = manager.create_review(second)
    unknown = manager.review_root / "manual"
    unknown.parent.mkdir(parents=True, exist_ok=True)
    git(repo, "worktree", "add", "-q", "--detach", str(unknown), first)

    removed = manager.prune_reviews(keep={first})

    assert removed == [stale]
    assert feature.is_dir()
    assert kept.is_dir()
    assert not stale.exists()
    assert unknown.is_dir()
