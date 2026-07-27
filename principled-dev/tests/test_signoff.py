import stat
import subprocess
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from principled_dev.review import ReviewRecord, record_review
from principled_dev.signoff import create_attestation, export_session_digest


BASE = "a" * 40
COMMIT = "b" * 40
TREE = "c" * 40


def git(cwd, *args):
    return subprocess.run(
        ("git", *args), cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    git(path, "init", "-q")
    git(path, "config", "user.name", "Test Human")
    git(path, "config", "user.email", "human@example.invalid")
    (path / "file.txt").write_text("content\n", encoding="utf-8")
    git(path, "add", "file.txt")
    git(path, "commit", "-qm", "initial")
    return path


def approved(repo):
    commit = git(repo, "rev-parse", "HEAD")
    tree = git(repo, "rev-parse", "HEAD^{tree}")
    return record_review(commit, commit, tree)


def test_signoff_requires_human_review(repo):
    with pytest.raises(ValueError, match="human review"):
        create_attestation(repo, approved(repo), human_reviewed=False, identity="human")


def test_signoff_rejects_dirty_or_staged_repository(repo, tmp_path):
    record = approved(repo)
    branch = publish_to_local_remote(repo, record, tmp_path)
    (repo / "file.txt").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(ValueError, match="dirty"):
        create_attestation(repo, record, human_reviewed=True, identity="human", expected_review_digest=record.digest(), published_remote="origin", published_branch=branch, published_sha=record.commit_sha)

    git(repo, "restore", "file.txt")
    (repo / "new.txt").write_text("staged\n", encoding="utf-8")
    git(repo, "add", "new.txt")
    with pytest.raises(ValueError, match="dirty"):
        create_attestation(repo, record, human_reviewed=True, identity="human", expected_review_digest=record.digest(), published_remote="origin", published_branch=branch, published_sha=record.commit_sha)


def test_signoff_rejects_moved_head_or_wrong_tree(repo, tmp_path):
    record = approved(repo)
    branch = publish_to_local_remote(repo, record, tmp_path)
    (repo / "second.txt").write_text("next\n", encoding="utf-8")
    git(repo, "add", "second.txt")
    git(repo, "commit", "-qm", "second")
    with pytest.raises(ValueError, match="HEAD"):
        create_attestation(repo, record, human_reviewed=True, identity="human", expected_review_digest=record.digest(), published_remote="origin", published_branch=branch, published_sha=record.commit_sha)

    fresh = approved(repo)
    wrong_tree = ReviewRecord(
        fresh.verdict,
        fresh.base_sha,
        fresh.commit_sha,
        "d" * 40,
    )
    with pytest.raises(ValueError, match="tree"):
        create_attestation(
            repo,
            wrong_tree,
            human_reviewed=True,
            identity="human",
            expected_review_digest=wrong_tree.digest(),
            published_remote="origin",
            published_branch=branch,
            published_sha=fresh.commit_sha,
        )


def test_signoff_rejects_non_approve_and_arbitrary_mapping(repo):
    valid = approved(repo)
    changes = ReviewRecord(
        "REQUEST_CHANGES", valid.base_sha, valid.commit_sha, valid.tree_sha
    )
    with pytest.raises(ValueError, match="APPROVE"):
        create_attestation(repo, changes, human_reviewed=True, identity="human")
    with pytest.raises(TypeError, match="ReviewRecord"):
        create_attestation(
            repo,
            valid.to_dict(),
            human_reviewed=True,
            identity="human",
        )


def test_signoff_requires_matching_review_digest(repo, tmp_path):
    valid = approved(repo)
    branch = publish_to_local_remote(repo, valid, tmp_path)
    with pytest.raises(ValueError, match="persisted review digest"):
        create_attestation(repo, valid, human_reviewed=True, identity="human")
    with pytest.raises(ValueError, match="digest"):
        create_attestation(
            repo,
            valid,
            human_reviewed=True,
            identity="human",
            expected_review_digest="0" * 64,
        )
    result = create_attestation(
        repo,
        valid,
        human_reviewed=True,
        identity="human",
        expected_review_digest=valid.digest(),
        published_remote="origin",
        published_branch=branch,
        published_sha=valid.commit_sha,
    )
    assert result["review_digest"] == valid.digest()


def publish_to_local_remote(repo, record, tmp_path, branch="agent/topic"):
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-q", "origin", f"{record.commit_sha}:refs/heads/{branch}")
    return branch


def test_signoff_rejects_missing_deleted_or_mismatched_remote(repo, tmp_path):
    record = approved(repo)
    branch = publish_to_local_remote(repo, record, tmp_path)
    git(repo, "push", "-q", "origin", "--delete", branch)
    with pytest.raises(ValueError, match="missing"):
        create_attestation(
            repo,
            record,
            human_reviewed=True,
            identity="human",
            expected_review_digest=record.digest(),
            published_remote="origin",
            published_branch=branch,
            published_sha=record.commit_sha,
        )


def test_signoff_rejects_live_remote_and_persisted_publication_mismatch(repo, tmp_path):
    record = approved(repo)
    branch = publish_to_local_remote(repo, record, tmp_path)
    with pytest.raises(ValueError, match="persisted publication"):
        create_attestation(
            repo,
            record,
            human_reviewed=True,
            identity="human",
            expected_review_digest=record.digest(),
            published_remote="origin",
            published_branch=branch,
            published_sha="d" * 40,
        )

    (repo / "next.txt").write_text("next\n", encoding="utf-8")
    git(repo, "add", "next.txt")
    git(repo, "commit", "-qm", "next")
    moved = git(repo, "rev-parse", "HEAD")
    git(repo, "push", "-q", "--force", "origin", f"{moved}:refs/heads/{branch}")
    git(repo, "reset", "-q", "--hard", record.commit_sha)
    with pytest.raises(ValueError, match="live remote"):
        create_attestation(
            repo,
            record,
            human_reviewed=True,
            identity="human",
            expected_review_digest=record.digest(),
            published_remote="origin",
            published_branch=branch,
            published_sha=record.commit_sha,
        )


def test_successful_report_only_attestation(repo, tmp_path):
    record = approved(repo)
    branch = publish_to_local_remote(repo, record, tmp_path)
    attestation = create_attestation(
        repo,
        record,
        human_reviewed=True,
        identity="human@example.invalid",
        published_remote="origin",
        published_branch=branch,
        published_sha=record.commit_sha,
        tradeoffs=("POSIX only",),
        risks=("Hook policy fails open",),
        session_id="session-1",
        session_digest="sha256:" + "e" * 64,
        expected_review_digest=record.digest(),
    )
    assert attestation["status"] == "VERIFIED_BY_HUMAN"
    assert attestation["commit_sha"] == record.commit_sha
    assert attestation["tree_sha"] == record.tree_sha
    assert attestation["remote"] == "origin"
    assert attestation["branch"] == branch
    assert attestation["identity"] == "human@example.invalid"
    assert attestation["tradeoffs"] == ["POSIX only"]
    assert git(repo, "rev-parse", "HEAD") == record.commit_sha


def test_export_session_digest_uses_exact_export_bytes(tmp_path):
    goose = tmp_path / "goose"
    goose.write_text(
        "#!/bin/sh\nprintf '%s' '{\"id\":\"session-1\"}' > \"$8\"\n",
        encoding="utf-8",
    )
    goose.chmod(goose.stat().st_mode | stat.S_IXUSR)
    digest = export_session_digest("session-1", goose=str(goose))
    assert digest["session_id"] == "session-1"
    assert digest["sha256"] == "80c84e9dfd0e06667d807bb5672acbecee5cd5aaf6725dc1416888e20ba86de5"
