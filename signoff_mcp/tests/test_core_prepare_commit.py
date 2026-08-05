import hashlib

import pytest

from signoff_mcp import core
from signoff_mcp.adapters import GenericFileAdapter
from signoff_mcp.tests.helpers import commit_file, git, init_repo


def _adapter(tmp_path, data=b"transcript-bytes\n", cid="conv-1"):
    f = tmp_path / "transcript.log"
    f.write_bytes(data)
    return GenericFileAdapter(str(f), conversation_id=cid), data


def _missing_adapter(tmp_path):
    return GenericFileAdapter(str(tmp_path / "missing.log"), conversation_id="conv-x")


def _prepare(scratch_repo, adapter=None):
    repo = core.GitRepo(str(scratch_repo))
    return repo, core.prepare(repo, "HEAD", reference_ref="main", adapter=adapter)


def test_prepare_resolves_shas_and_diff(scratch_repo):
    repo, state = _prepare(scratch_repo)
    assert state.reviewed_commit_sha == repo.out("rev-parse", "HEAD")
    assert state.base_sha == repo.out("rev-parse", "main")
    assert state.tree_sha == repo.out("rev-parse", "HEAD^{tree}")
    assert len(state.reviewed_commit_sha) == 40 and len(state.tree_sha) == 40
    assert state.files == ["A\tfeat.txt"]
    assert "+feature" in state.diff
    assert "1 file changed" in state.stats
    assert state.harness_id == "unknown"
    assert state.conversation_id == "unavailable"
    assert state.transcript_available is False


def test_prepare_without_reference_and_no_upstream_errors(scratch_repo):
    repo = core.GitRepo(str(scratch_repo))
    with pytest.raises(core.SignoffError, match="reference_ref explicitly"):
        core.prepare(repo, "HEAD")


def test_prepare_defaults_reference_to_upstream(tmp_path):
    origin = tmp_path / "origin.git"
    origin.mkdir()
    git(origin, "init", "-q", "--bare", "-b", "main")
    work = init_repo(tmp_path / "work")
    commit_file(work, "base.txt", "base\n", "base commit")
    git(work, "remote", "add", "origin", str(origin))
    git(work, "push", "-q", "-u", "origin", "main")
    git(work, "checkout", "-q", "-b", "feature")
    commit_file(work, "feat.txt", "feature\n", "feature commit")
    git(work, "branch", "-q", "--set-upstream-to=origin/main")

    repo = core.GitRepo(str(work))
    state = core.prepare(repo, "HEAD")
    assert state.reference_ref == "origin/main"
    assert state.base_sha == repo.out("rev-parse", "origin/main")


def test_status_derivation_verified_by_human(scratch_repo, tmp_path):
    adapter, data = _adapter(tmp_path)
    repo, state = _prepare(scratch_repo, adapter)
    result = core.commit(
        repo, state, tradeoffs=["t1"], risks=["r1"], user_email="dev@example.com",
        adapter=adapter, agent="pytest/agent",
    )
    assert result.status == "VERIFIED_BY_HUMAN"
    assert result.transcript_digest == f"sha256:{hashlib.sha256(data).hexdigest()}"
    assert result.transcript_bytes == str(len(data))
    trailers = core.parse_trailers(result.message)
    assert trailers["Signoff-Status"] == ["VERIFIED_BY_HUMAN"]
    assert trailers["Signoff-Reviewed-Commit-SHA"] == [state.reviewed_commit_sha]
    assert trailers["Signoff-Reviewed-Tree-SHA"] == [state.tree_sha]
    assert trailers["Signoff-Conversation-ID"] == ["conv-1"]
    assert trailers["Signoff-Verified-By"] == ["dev@example.com"]
    # attestation commit: empty, parented on reviewed commit, same tree
    assert repo.out("rev-parse", "HEAD") == result.attestation_sha
    assert repo.out("rev-parse", "HEAD~1") == state.reviewed_commit_sha
    assert repo.out("rev-parse", "HEAD^{tree}") == state.tree_sha
    assert result.message.startswith(f"[SIGNOFF {state.reviewed_commit_sha[:7]}]")
    # dual persistence: note on both reviewed commit and tree SHA
    for sha in (state.reviewed_commit_sha, state.tree_sha):
        note = git(scratch_repo, "notes", "--ref=signoff", "show", sha).stdout
        assert core.parse_trailers(note)["Signoff-Status"] == ["VERIFIED_BY_HUMAN"]


def test_ack_circuit_breaker_aborts_without_ack(scratch_repo, tmp_path):
    adapter = _missing_adapter(tmp_path)
    repo, state = _prepare(scratch_repo, adapter)
    head_before = repo.out("rev-parse", "HEAD")
    with pytest.raises(core.SignoffTranscriptError):
        core.commit(repo, state, [], [], "dev@example.com", adapter=adapter)
    assert repo.out("rev-parse", "HEAD") == head_before  # no commit created
    assert git(scratch_repo, "notes", "--ref=signoff", "show", head_before, check=False).returncode != 0


def test_ack_circuit_breaker_downgrades_with_ack(scratch_repo, tmp_path):
    adapter = _missing_adapter(tmp_path)
    repo, state = _prepare(scratch_repo, adapter)
    result = core.commit(
        repo, state, [], [], "dev@example.com", adapter=adapter, ack_no_transcript=True,
    )
    assert result.status == "VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST"
    trailers = core.parse_trailers(result.message)
    assert trailers["Signoff-Transcript-Digest"] == ["unavailable"]
    assert trailers["Signoff-Transcript-Bytes"] == ["unavailable"]
    assert trailers["Signoff-Harness-ID"] == ["generic-file"]


def test_stale_state_head_moved(scratch_repo, tmp_path):
    adapter, _ = _adapter(tmp_path)
    repo, state = _prepare(scratch_repo, adapter)
    commit_file(scratch_repo, "later.txt", "x\n", "moves HEAD after prepare")
    with pytest.raises(core.SignoffStaleError, match="no longer matches"):
        core.commit(repo, state, [], [], "dev@example.com", adapter=adapter)


def test_stale_state_unstaged_changes(scratch_repo, tmp_path):
    adapter, _ = _adapter(tmp_path)
    repo, state = _prepare(scratch_repo, adapter)
    (scratch_repo / "feat.txt").write_text("dirty\n")
    with pytest.raises(core.SignoffStaleError, match="Unstaged"):
        core.commit(repo, state, [], [], "dev@example.com", adapter=adapter)


def test_stale_state_staged_changes(scratch_repo, tmp_path):
    adapter, _ = _adapter(tmp_path)
    repo, state = _prepare(scratch_repo, adapter)
    (scratch_repo / "staged.txt").write_text("s\n")
    git(scratch_repo, "add", "staged.txt")
    with pytest.raises(core.SignoffStaleError, match="Staged"):
        core.commit(repo, state, [], [], "dev@example.com", adapter=adapter)


def test_trailer_repeat_and_none_rules(scratch_repo, tmp_path):
    adapter, _ = _adapter(tmp_path)
    repo, state = _prepare(scratch_repo, adapter)
    result = core.commit(
        repo, state, tradeoffs=["t1", "t2"], risks=[], user_email="dev@example.com", adapter=adapter,
    )
    trailers = core.parse_trailers(result.message)
    assert trailers["Signoff-Tradeoff"] == ["t1", "t2"]
    assert trailers["Signoff-Risk"] == ["none"]


def test_invalid_email_rejected(scratch_repo, tmp_path):
    adapter, _ = _adapter(tmp_path)
    repo, state = _prepare(scratch_repo, adapter)
    with pytest.raises(core.SignoffError, match="email"):
        core.commit(repo, state, [], [], "not-an-email", adapter=adapter)


def test_summary_paragraph_included(scratch_repo, tmp_path):
    adapter, _ = _adapter(tmp_path)
    repo, state = _prepare(scratch_repo, adapter)
    result = core.commit(
        repo, state, [], [], "dev@example.com", adapter=adapter, summary="Reviewed the widget refactor.",
    )
    lines = result.message.splitlines()
    assert lines[2] == "Reviewed the widget refactor."
