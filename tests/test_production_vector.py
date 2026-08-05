"""Real production attestation [SIGNOFF 453c633] as a test vector.

The fixture is the exact payload of attestation commit 2fe1e76, mirrored in
refs/notes/signoff on both the reviewed commit and tree SHAs. Live-repo
checks skip when the notes ref or history is unavailable (e.g. unfetched CI).
"""

import os
import subprocess

import pytest

from signoff_mcp import core

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "production_attestation.txt")
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
REVIEWED_SHA = "453c633078ecdd82d93c33eefac4d5f4cbe2ef55"
# Tree SHA recorded in the production trailers. NOTE: it does NOT match the
# actual tree of the reviewed commit (60856e6...) — the Phase 1 prompt-driven
# run captured a stale tree, which is precisely the failure class Phase 2's
# server-derived SHAs and post-commit integrity check eliminate. Notes were
# mirrored onto this trailer value, so lookups still use it.
TRAILER_TREE_SHA = "83679c5222ef2c7a7b8e5c83bc56c526d7f95567"
ATTESTATION_SHA = "2fe1e7621d8c2ad391f572b2458c4c791387e0f5"


def _payload() -> str:
    with open(FIXTURE, encoding="utf-8") as f:
        return f.read()


def _git(*args):
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True)


def test_parse_trailers_production_vector():
    trailers = core.parse_trailers(_payload())
    assert trailers["Signoff-Spec-Version"] == ["1.0"]
    assert trailers["Signoff-Status"] == ["VERIFIED_BY_HUMAN"]
    assert trailers["Signoff-Reviewed-Commit-SHA"] == [REVIEWED_SHA]
    assert trailers["Signoff-Reviewed-Tree-SHA"] == [TRAILER_TREE_SHA]
    assert trailers["Signoff-Tradeoff"] == [
        "Accumulate repeat attestations via git notes append",
        "Defer MCP server implementation to Phase 2",
    ]
    assert trailers["Signoff-Risk"] == ["none"]
    assert trailers["Signoff-Transcript-Digest"] == [
        "sha256:1675b639de65cab2ef732bf418f37d9583023ffe77a166a835ca1828e1a3738e"
    ]
    assert trailers["Signoff-Transcript-Bytes"] == ["121474"]
    assert trailers["Signoff-Verified-By"] == ["jerrylin247365@gmail.com"]
    assert trailers["Signoff-Harness-ID"] == ["antigravity-cli"]
    assert len(trailers) == 14


def test_build_message_roundtrips_production_vector():
    """build_message must byte-for-byte reproduce the production payload."""
    t = {k: v for k, v in core.parse_trailers(_payload()).items()}
    state = core.PrepareState(
        reviewed_commit_sha=t["Signoff-Reviewed-Commit-SHA"][0],
        base_sha=t["Signoff-Base-SHA"][0],
        tree_sha=t["Signoff-Reviewed-Tree-SHA"][0],
        reference_ref="main",
        diff="",
        files=[],
        stats="",
        harness_id=t["Signoff-Harness-ID"][0],
        conversation_id=t["Signoff-Conversation-ID"][0],
        transcript_available=True,
    )
    message = core.build_message(
        state,
        status=t["Signoff-Status"][0],
        timestamp=t["Signoff-Timestamp"][0],
        harness_id=t["Signoff-Harness-ID"][0],
        conversation_id=t["Signoff-Conversation-ID"][0],
        transcript_digest=t["Signoff-Transcript-Digest"][0],
        transcript_bytes=t["Signoff-Transcript-Bytes"][0],
        tradeoffs=t["Signoff-Tradeoff"],
        risks=[],  # 'none' in the vector means zero acknowledged risks
        user_email=t["Signoff-Verified-By"][0],
        agent=t["Signoff-Agent"][0],
    )
    assert message == _payload().rstrip("\n")


def _notes_available() -> bool:
    return _git("rev-parse", "--verify", "-q", "refs/notes/signoff").returncode == 0


def test_live_notes_mirror_production_vector():
    if not _notes_available():
        pytest.skip("refs/notes/signoff not fetched in this checkout")
    expected = core.parse_trailers(_payload())
    for sha in (REVIEWED_SHA, TRAILER_TREE_SHA):
        show = _git("notes", "--ref=signoff", "show", sha)
        assert show.returncode == 0, f"no signoff note on {sha}: {show.stderr}"
        assert core.parse_trailers(show.stdout) == expected


def test_live_attestation_commit_matches_fixture():
    log = _git("log", "-1", "--format=%B", ATTESTATION_SHA)
    if log.returncode != 0:
        pytest.skip("attestation commit not present in this checkout")
    assert log.stdout.rstrip("\n") == _payload().rstrip("\n")
    # Empty attestation commit: parented on the reviewed commit and sharing its
    # actual tree. The trailer's tree SHA is stale (see TRAILER_TREE_SHA note),
    # so assert against the real tree, and pin the known mismatch so this test
    # documents the Phase 1 inconsistency Phase 2 prevents.
    actual_tree = _git("rev-parse", f"{REVIEWED_SHA}^{{tree}}").stdout.strip()
    assert _git("rev-parse", f"{ATTESTATION_SHA}^{{tree}}").stdout.strip() == actual_tree
    assert _git("rev-parse", f"{ATTESTATION_SHA}~1").stdout.strip() == REVIEWED_SHA
    assert actual_tree == "60856e66e6ce95a68a03cf2f084e399f6411f86c"
    assert actual_tree != TRAILER_TREE_SHA
