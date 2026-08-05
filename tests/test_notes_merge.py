"""Diverged-notes concurrency merge per GSA §2.5 (tracking ref + cat_sort_uniq)."""

import pytest

from signoff_mcp import core
from signoff_mcp.adapters import GenericFileAdapter
from signoff_mcp.tests.helpers import commit_file, git, init_repo


@pytest.fixture
def two_clones(tmp_path):
    """Bare origin plus two clones sharing the same reviewed commit."""
    origin = tmp_path / "origin.git"
    origin.mkdir()
    git(origin, "init", "-q", "--bare", "-b", "main")
    seed = init_repo(tmp_path / "seed")
    commit_file(seed, "base.txt", "base\n", "base commit")
    commit_file(seed, "feat.txt", "feature\n", "feature commit")
    git(seed, "remote", "add", "origin", str(origin))
    git(seed, "push", "-q", "origin", "main")

    clones = []
    for name in ("alice", "bob"):
        path = tmp_path / name
        git(tmp_path, "clone", "-q", str(origin), name)
        git(path, "config", "user.email", f"{name}@example.com")
        git(path, "config", "user.name", name)
        git(path, "config", "commit.gpgsign", "false")
        clones.append(path)
    return clones


def _attest(path, tmp_path, who, timestamp):
    f = tmp_path / f"{who}.log"
    f.write_bytes(f"{who} transcript\n".encode())
    adapter = GenericFileAdapter(str(f), conversation_id=who)
    repo = core.GitRepo(str(path))
    state = core.prepare(repo, "HEAD", reference_ref="origin/main", adapter=adapter)
    result = core.commit(
        repo, state, [], [], f"{who}@example.com", adapter=adapter,
        agent=f"{who}/agent", timestamp=timestamp,
    )
    return repo, state, result


def test_diverged_notes_merge_and_push(two_clones, tmp_path):
    alice, bob = two_clones
    repo_a, state_a, result_a = _attest(alice, tmp_path, "alice", "2026-01-01T00:00:00Z")
    repo_b, state_b, result_b = _attest(bob, tmp_path, "bob", "2026-01-02T00:00:00Z")
    assert state_a.reviewed_commit_sha == state_b.reviewed_commit_sha

    assert core.push_notes(repo_a)["pushed"] is True
    # Bob's local notes diverged from remote (both noted the same SHAs). A direct
    # fetch into refs/notes/signoff would be a rejected non-fast-forward; the
    # tracking-ref cat_sort_uniq flow must succeed and preserve both payloads.
    out = core.push_notes(repo_b)
    assert out["merged_remote_notes"] is True and out["pushed"] is True

    merged = git(bob, "notes", "--ref=signoff", "show", state_b.reviewed_commit_sha).stdout
    trailers = core.parse_trailers(merged)
    assert sorted(trailers["Signoff-Conversation-ID"]) == ["alice", "bob"]
    assert sorted(trailers["Signoff-Agent"]) == ["alice/agent", "bob/agent"]
    # origin now holds the merged ref
    assert git(bob, "rev-parse", "refs/notes/signoff").stdout == git(
        bob, "ls-remote", "origin", "refs/notes/signoff"
    ).stdout.split()[0] + "\n"


def test_push_notes_idempotent_repeat_run(two_clones, tmp_path):
    alice, bob = two_clones
    repo_a, state_a, _ = _attest(alice, tmp_path, "alice", "2026-01-01T00:00:00Z")
    repo_b, _, _ = _attest(bob, tmp_path, "bob", "2026-01-02T00:00:00Z")
    core.push_notes(repo_a)
    core.push_notes(repo_b)
    # Repeat run on alice: forced (+) tracking-ref fetch must not be rejected,
    # merge pulls in bob's payload, push succeeds.
    out = core.push_notes(repo_a)
    assert out["merged_remote_notes"] is True and out["pushed"] is True
    merged = git(alice, "notes", "--ref=signoff", "show", state_a.reviewed_commit_sha).stdout
    assert sorted(core.parse_trailers(merged)["Signoff-Conversation-ID"]) == ["alice", "bob"]


def test_push_notes_first_ever_push_tolerates_missing_remote_ref(two_clones, tmp_path):
    alice, _ = two_clones
    repo_a, state_a, _ = _attest(alice, tmp_path, "alice", "2026-01-01T00:00:00Z")
    out = core.push_notes(repo_a)
    assert out["pushed"] is True and out["merged_remote_notes"] is False
    assert git(alice, "ls-remote", "origin", "refs/notes/signoff").stdout.strip() != ""


def test_push_notes_bad_remote_raises_structured_error(two_clones, tmp_path):
    alice, _ = two_clones
    repo_a, _, _ = _attest(alice, tmp_path, "alice", "2026-01-01T00:00:00Z")
    with pytest.raises(core.SignoffPushError, match="push failed"):
        core.push_notes(repo_a, remote=str(tmp_path / "no-such-remote"))
