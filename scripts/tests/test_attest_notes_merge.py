"""Diverged-notes concurrency merge per GSA §2.5 (tracking ref + cat_sort_uniq)."""

import pytest
from _attest_loader import attest as core
from helpers import commit_file, git, init_repo


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
    repo = core.GitRepo(str(path))
    head = repo.out("rev-parse", "HEAD")
    f = tmp_path / f"{who}.log"
    f.write_bytes(f"{who} transcript\nGSA-APPROVAL {head} 2026-01-01T00:00:00Z\n".encode())
    adapter = core.GenericFileAdapter(str(f), conversation_id=who)
    core.prepare(str(path), "origin/main", env={}, adapter=adapter)
    opts = core.CommitOptions(
        email=f"{who}@example.com", level="standard", reference="origin/main", push=False, timestamp=timestamp
    )
    result = core.commit(str(path), opts, env={"ANTHROPIC_MODEL": f"{who}-model"}, adapter=adapter)
    return repo, result, result.noted_shas[0]  # (repo, result, reviewed commit sha)


def test_diverged_notes_merge_and_push(two_clones, tmp_path):
    alice, bob = two_clones
    repo_a, result_a, state_a = _attest(alice, tmp_path, "alice", "2026-01-01T00:00:00Z")
    repo_b, result_b, state_b = _attest(bob, tmp_path, "bob", "2026-01-02T00:00:00Z")
    # prepare() after the attestation now sees the attestation commit as HEAD;
    # the noted (reviewed) SHAs are what must agree between the clones.
    assert result_a.noted_shas[0] == result_b.noted_shas[0]
    reviewed = result_b.noted_shas[0]

    assert core.push_notes(repo_a)[0] is True
    # Bob's local notes diverged from remote (both noted the same SHAs). A direct
    # fetch into refs/notes/signoff would be a rejected non-fast-forward; the
    # tracking-ref cat_sort_uniq flow must succeed and preserve both payloads.
    pushed, merged_remote, reason = core.push_notes(repo_b)
    assert merged_remote is True and pushed is True and reason is None

    merged = git(bob, "notes", "--ref=signoff", "show", reviewed).stdout
    trailers = core.parse_trailers(merged)
    assert sorted(trailers["Signoff-Conversation-ID"]) == ["alice", "bob"]
    assert sorted(a.split()[1] for a in trailers["Signoff-Agent"]) == ["model=alice-model", "model=bob-model"]
    # origin now holds the merged ref
    assert git(bob, "rev-parse", "refs/notes/signoff").stdout == git(
        bob, "ls-remote", "origin", "refs/notes/signoff"
    ).stdout.split()[0] + "\n"


def test_push_notes_idempotent_repeat_run(two_clones, tmp_path):
    alice, bob = two_clones
    repo_a, _, state_a = _attest(alice, tmp_path, "alice", "2026-01-01T00:00:00Z")
    repo_b, _, _ = _attest(bob, tmp_path, "bob", "2026-01-02T00:00:00Z")
    core.push_notes(repo_a)
    core.push_notes(repo_b)
    # Repeat run on alice: forced (+) tracking-ref fetch must not be rejected,
    # merge pulls in bob's payload, push succeeds.
    pushed, merged_remote, _ = core.push_notes(repo_a)
    assert merged_remote is True and pushed is True
    merged = git(alice, "notes", "--ref=signoff", "show", state_a).stdout
    assert sorted(core.parse_trailers(merged)["Signoff-Conversation-ID"]) == ["alice", "bob"]


def test_push_notes_first_ever_push_tolerates_missing_remote_ref(two_clones, tmp_path):
    alice, _ = two_clones
    repo_a, _, state_a = _attest(alice, tmp_path, "alice", "2026-01-01T00:00:00Z")
    pushed, merged_remote, _ = core.push_notes(repo_a)
    assert pushed is True and merged_remote is False
    assert git(alice, "ls-remote", "origin", "refs/notes/signoff").stdout.strip() != ""


def test_push_notes_bad_remote_is_reported_not_raised(two_clones, tmp_path):
    alice, _ = two_clones
    repo_a, _, _ = _attest(alice, tmp_path, "alice", "2026-01-01T00:00:00Z")
    pushed, merged_remote, reason = core.push_notes(repo_a, remote=str(tmp_path / "no-such-remote"))
    assert pushed is False and merged_remote is False
    assert reason and "notes push refused" in reason
