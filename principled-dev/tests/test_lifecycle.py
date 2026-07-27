import subprocess
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from principled_dev.lifecycle import Lifecycle, LifecycleError
from principled_dev.review import record_review
from principled_dev.state import StateStore


def git(cwd, *args, check=True):
    result = subprocess.run(
        ("git", *args), cwd=cwd, check=check, capture_output=True, text=True
    )
    return result.stdout.strip()


@pytest.fixture
def project(tmp_path):
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    repo = tmp_path / "repo"
    git(tmp_path, "clone", "-q", str(remote), str(repo))
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "user.email", "test@example.invalid")
    git(repo, "switch", "-qc", "main")
    (repo / "app.txt").write_text("base\n", encoding="utf-8")
    git(repo, "add", "app.txt")
    git(repo, "commit", "-qm", "base")
    git(repo, "push", "-q", "-u", "origin", "main")
    store = StateStore(tmp_path / "state.json")
    lifecycle = Lifecycle(
        repo,
        tmp_path / "worktrees",
        store,
        feature_branch="agent/topic",
        base_branch="main",
    )
    return repo, remote, lifecycle


def approve_plan(lifecycle):
    lifecycle.record_artifact("spec", "approved spec")
    lifecycle.approve("spec")
    lifecycle.record_artifact("plan", "approved plan")
    lifecycle.approve("plan")


def commit_feature(feature, content="feature\n"):
    (feature / "app.txt").write_text(content, encoding="utf-8")
    git(feature, "add", "app.txt")
    git(feature, "commit", "-qm", content.strip())
    return git(feature, "rev-parse", "HEAD")


def test_feature_creation_requires_approved_plan(project):
    _, _, lifecycle = project
    with pytest.raises(LifecycleError, match="plan"):
        lifecycle.create_feature("main")


def test_feature_starts_at_exact_base_sha(project):
    repo, _, lifecycle = project
    approve_plan(lifecycle)
    base = git(repo, "rev-parse", "main")
    feature = lifecycle.create_feature(base)
    assert git(feature, "rev-parse", "HEAD") == base
    assert git(feature, "symbolic-ref", "HEAD") == "refs/heads/agent/topic"


def test_constructor_restores_feature_and_manifest_context(project):
    repo, _, lifecycle = project
    approve_plan(lifecycle)
    base = git(repo, "rev-parse", "main")
    feature = lifecycle.create_feature(base)
    commit_feature(feature)
    manifest = lifecycle.bind_manifest("not persisted")

    restored = Lifecycle(
        repo,
        lifecycle.worktrees.root.parent,
        lifecycle.state,
        feature_branch="agent/topic",
        base_branch="wrong-default",
    )

    assert restored.base_branch == "main"
    assert restored.base_sha == base
    assert restored.feature_branch == "agent/topic"
    assert restored.feature_worktree == feature
    assert restored.manifest_is_fresh()
    assert restored.bind_manifest("new output summary")["commit_sha"] == manifest["commit_sha"]


def test_manifest_binds_commit_tree_and_diff_and_stales_on_change(project):
    _, _, lifecycle = project
    approve_plan(lifecycle)
    feature = lifecycle.create_feature("main")
    commit = commit_feature(feature)
    manifest = lifecycle.bind_manifest("summary")
    assert manifest["commit_sha"] == commit
    assert manifest["tree_sha"] == git(feature, "rev-parse", "HEAD^{tree}")
    assert len(manifest["diff_digest"]) == 64
    lifecycle.approve_manifest(manifest)
    assert lifecycle.manifest_is_fresh()
    assert lifecycle.state.is_approved(
        lifecycle.repository_id, lifecycle.feature_branch, "build"
    )

    (feature / "app.txt").write_text("dirty\n", encoding="utf-8")
    assert not lifecycle.manifest_is_fresh()


def test_push_requires_fresh_approve_for_exact_head(project):
    _, _, lifecycle = project
    approve_plan(lifecycle)
    feature = lifecycle.create_feature("main")
    commit = commit_feature(feature)
    manifest = lifecycle.bind_manifest("summary")
    lifecycle.approve_manifest(manifest)

    with pytest.raises(LifecycleError, match="APPROVE"):
        lifecycle.publish(None)

    review = record_review(
        lifecycle.base_sha,
        commit,
        git(feature, "rev-parse", "HEAD^{tree}"),
    )
    result = lifecycle.publish(review)
    assert result["pushed_sha"] == commit
    assert git(feature, "ls-remote", "origin", "refs/heads/agent/topic").split()[0] == commit
    restored = Lifecycle(
        lifecycle.repository,
        lifecycle.worktrees.root.parent,
        StateStore(lifecycle.state.path),
        feature_branch="agent/topic",
        base_branch="main",
    )
    assert restored.remote_sha == commit


def test_new_commit_invalidates_review_and_blocks_push(project):
    _, _, lifecycle = project
    approve_plan(lifecycle)
    feature = lifecycle.create_feature("main")
    first = commit_feature(feature)
    manifest = lifecycle.bind_manifest("summary")
    lifecycle.approve_manifest(manifest)
    review = record_review(
        lifecycle.base_sha,
        first,
        git(feature, "rev-parse", "HEAD^{tree}"),
    )

    commit_feature(feature, "second\n")
    with pytest.raises(LifecycleError, match="reviewed SHA"):
        lifecycle.publish(review)


def test_integration_branch_cannot_be_publication_target(project):
    repo, _, lifecycle = project
    approve_plan(lifecycle)
    lifecycle.feature_branch = "main"
    lifecycle.feature_worktree = repo
    with pytest.raises(LifecycleError, match="integration"):
        lifecycle.publish(record_review("a", "b", "c"))
