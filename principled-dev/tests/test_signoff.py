import stat
import subprocess
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

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
    return {"base_sha": commit, "commit_sha": commit, "tree_sha": tree}


def test_signoff_requires_human_review(repo):
    with pytest.raises(ValueError, match="human review"):
        create_attestation(repo, approved(repo), human_reviewed=False, identity="human")


def test_signoff_rejects_dirty_or_staged_repository(repo):
    record = approved(repo)
    (repo / "file.txt").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(ValueError, match="dirty"):
        create_attestation(repo, record, human_reviewed=True, identity="human")

    git(repo, "restore", "file.txt")
    (repo / "new.txt").write_text("staged\n", encoding="utf-8")
    git(repo, "add", "new.txt")
    with pytest.raises(ValueError, match="dirty"):
        create_attestation(repo, record, human_reviewed=True, identity="human")


def test_signoff_rejects_moved_head_or_wrong_tree(repo):
    record = approved(repo)
    (repo / "second.txt").write_text("next\n", encoding="utf-8")
    git(repo, "add", "second.txt")
    git(repo, "commit", "-qm", "second")
    with pytest.raises(ValueError, match="HEAD"):
        create_attestation(repo, record, human_reviewed=True, identity="human")

    fresh = approved(repo)
    fresh["tree_sha"] = "d" * 40
    with pytest.raises(ValueError, match="tree"):
        create_attestation(repo, fresh, human_reviewed=True, identity="human")


def test_signoff_rejects_remote_mismatch(repo):
    record = approved(repo)
    with pytest.raises(ValueError, match="remote"):
        create_attestation(
            repo,
            record,
            human_reviewed=True,
            identity="human",
            remote_sha="d" * 40,
        )


def test_successful_report_only_attestation(repo):
    record = approved(repo)
    attestation = create_attestation(
        repo,
        record,
        human_reviewed=True,
        identity="human@example.invalid",
        remote_sha=record["commit_sha"],
        tradeoffs=("POSIX only",),
        risks=("Hook policy fails open",),
        session_id="session-1",
        session_digest="sha256:" + "e" * 64,
    )
    assert attestation["status"] == "VERIFIED_BY_HUMAN"
    assert attestation["commit_sha"] == record["commit_sha"]
    assert attestation["tree_sha"] == record["tree_sha"]
    assert attestation["identity"] == "human@example.invalid"
    assert attestation["tradeoffs"] == ["POSIX only"]
    assert git(repo, "rev-parse", "HEAD") == record["commit_sha"]


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
