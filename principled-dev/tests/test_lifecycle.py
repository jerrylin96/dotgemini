import multiprocessing
import subprocess
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from principled_dev.lifecycle import Lifecycle, LifecycleError, PublicationPartialSuccess
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


def invalidate(path, repository_id, feature_branch, started, attempted, completed):
    if not started.wait(timeout=10):
        return
    attempted.set()
    StateStore(path).set_artifact(repository_id, feature_branch, "build", "changed")
    completed.set()


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
    assert restored.published_remote == "origin"
    assert restored.review_digest == review.digest()


def test_publish_rejects_invalidation_before_atomic_token_capture(project, monkeypatch):
    _, _, lifecycle = project
    approve_plan(lifecycle)
    feature = lifecycle.create_feature("main")
    commit = commit_feature(feature)
    manifest = lifecycle.bind_manifest("summary")
    lifecycle.approve_manifest(manifest)
    review = record_review(
        lifecycle.base_sha,
        commit,
        git(feature, "rev-parse", "HEAD^{tree}"),
    )
    original = lifecycle.state.require_approved_and_token

    def invalidate_then_require(*args, **kwargs):
        StateStore(lifecycle.state.path).set_artifact(
            lifecycle.repository_id,
            lifecycle.feature_branch,
            "build",
            "concurrent changed build",
        )
        return original(*args, **kwargs)

    monkeypatch.setattr(lifecycle.state, "require_approved_and_token", invalidate_then_require)
    with pytest.raises(LifecycleError, match="approved fresh manifest"):
        lifecycle.publish(review)
    remote = git(feature, "ls-remote", "origin", "refs/heads/agent/topic")
    assert remote == ""


def test_publish_rejects_stale_state_without_restoring_publication(project, monkeypatch):
    _, _, lifecycle = project
    approve_plan(lifecycle)
    feature = lifecycle.create_feature("main")
    commit = commit_feature(feature)
    manifest = lifecycle.bind_manifest("summary")
    lifecycle.approve_manifest(manifest)
    review = record_review(
        lifecycle.base_sha,
        commit,
        git(feature, "rev-parse", "HEAD^{tree}"),
    )
    feature_git = lifecycle._feature_git()

    class InvalidatingGit:
        def __getattr__(self, name):
            return getattr(feature_git, name)

        def run(self, *args, **kwargs):
            if args[0] == "push":
                StateStore(lifecycle.state.path).set_artifact(
                    lifecycle.repository_id,
                    lifecycle.feature_branch,
                    "build",
                    "concurrent changed build",
                )
            return feature_git.run(*args, **kwargs)

    monkeypatch.setattr(lifecycle, "_feature_git", lambda: InvalidatingGit())

    with pytest.raises(PublicationPartialSuccess, match="publication succeeded.*state") as raised:
        lifecycle.publish(review)

    assert raised.value.remote == "origin"
    assert raised.value.branch == "agent/topic"
    assert raised.value.pushed_sha == commit
    assert git(feature, "ls-remote", "origin", "refs/heads/agent/topic").split()[0] == commit
    refreshed = StateStore(lifecycle.state.path)
    assert not refreshed.is_approved(
        lifecycle.repository_id, lifecycle.feature_branch, "build"
    )
    metadata = refreshed.get_metadata(lifecycle.repository_id, lifecycle.feature_branch)
    assert "remote_sha" not in metadata
    assert "published_remote" not in metadata
    assert "review_digest" not in metadata
    assert lifecycle.remote_sha is None
    assert lifecycle.published_remote is None
    assert lifecycle.review_digest is None


def prepare_publication(lifecycle):
    approve_plan(lifecycle)
    feature = lifecycle.create_feature("main")
    commit = commit_feature(feature)
    manifest = lifecycle.bind_manifest("summary")
    lifecycle.approve_manifest(manifest)
    review = record_review(
        lifecycle.base_sha,
        commit,
        git(feature, "rev-parse", "HEAD^{tree}"),
    )
    lifecycle.publish(review)
    return review


def test_signoff_holds_process_lock_through_attestation_output(project):
    _, _, lifecycle = project
    review = prepare_publication(lifecycle)
    context = multiprocessing.get_context("spawn")
    callback_started = context.Event()
    invalidation_attempted = context.Event()
    invalidation_completed = context.Event()
    process = context.Process(
        target=invalidate,
        args=(
            lifecycle.state.path,
            lifecycle.repository_id,
            lifecycle.feature_branch,
            callback_started,
            invalidation_attempted,
            invalidation_completed,
        ),
    )
    process.start()
    emitted = []

    def emit(attestation):
        callback_started.set()
        assert invalidation_attempted.wait(timeout=10)
        assert not invalidation_completed.wait(timeout=0.2)
        emitted.append(attestation)

    result = lifecycle.signoff(
        review,
        human_reviewed=True,
        identity="human@example.invalid",
        emitter=emit,
    )

    assert result is emitted[0]
    assert len(emitted) == 1
    assert invalidation_completed.wait(timeout=10)
    process.join(timeout=10)
    assert not process.is_alive()
    assert process.exitcode == 0


def test_signoff_emits_nothing_when_invalidation_wins_before_final_lock(
    project, monkeypatch
):
    _, _, lifecycle = project
    review = prepare_publication(lifecycle)
    original = lifecycle.state.with_valid_token
    emitted = []

    def invalidate_then_validate(*args, **kwargs):
        StateStore(lifecycle.state.path).set_artifact(
            lifecycle.repository_id, lifecycle.feature_branch, "build", "changed"
        )
        return original(*args, **kwargs)

    monkeypatch.setattr(lifecycle.state, "with_valid_token", invalidate_then_validate)
    with pytest.raises(LifecycleError, match="state changed during signoff"):
        lifecycle.signoff(
            review,
            human_reviewed=True,
            identity="human@example.invalid",
            emitter=emitted.append,
        )
    assert emitted == []


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
