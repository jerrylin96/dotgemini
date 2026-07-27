import hashlib
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .review import ReviewRecord


class SignoffError(ValueError):
    pass


def _git(repo, *args):
    result = subprocess.run(
        ("git", *args), cwd=repo, capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise SignoffError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def _require_clean(repo):
    if _git(repo, "status", "--porcelain"):
        raise SignoffError("repository is dirty")


def create_attestation(
    repo,
    approved_review,
    *,
    human_reviewed,
    identity,
    published_remote=None,
    published_branch=None,
    published_sha=None,
    tradeoffs=(),
    risks=(),
    session_id="unavailable",
    session_digest="unavailable",
    expected_review_digest=None,
):
    if not isinstance(approved_review, ReviewRecord):
        raise TypeError("approved_review must be a ReviewRecord")
    if approved_review.verdict != "APPROVE":
        raise SignoffError("APPROVE review is required before signoff")
    review_digest = approved_review.digest()
    if not human_reviewed:
        raise SignoffError("human review confirmation is required")
    if not identity:
        raise SignoffError("confirmed identity is required")
    if expected_review_digest is None:
        raise SignoffError("persisted review digest is required before signoff")
    if expected_review_digest != review_digest:
        raise SignoffError("review digest does not match persisted approval")
    if not published_remote or not published_branch or not published_sha:
        raise SignoffError("persisted publication state is required before signoff")
    _require_clean(repo)

    head = _git(repo, "rev-parse", "HEAD^{commit}")
    if head != approved_review.commit_sha:
        raise SignoffError("HEAD no longer matches approved review")
    tree = _git(repo, "rev-parse", "HEAD^{tree}")
    if tree != approved_review.tree_sha:
        raise SignoffError("tree no longer matches approved review")
    if published_sha != head:
        raise SignoffError("persisted publication SHA no longer matches reviewed HEAD")
    result = subprocess.run(
        ("git", "ls-remote", "--heads", published_remote, f"refs/heads/{published_branch}"),
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise SignoffError("live remote query failed")
    fields = result.stdout.split()
    if not fields:
        raise SignoffError("published remote branch is missing")
    if fields[0] != head:
        raise SignoffError("live remote branch no longer matches reviewed HEAD")

    return {
        "status": "VERIFIED_BY_HUMAN",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "base_sha": approved_review.base_sha,
        "commit_sha": head,
        "tree_sha": tree,
        "review_digest": review_digest,
        "remote": published_remote,
        "branch": published_branch,
        "session_id": session_id,
        "session_digest": session_digest,
        "tradeoffs": list(tradeoffs),
        "risks": list(risks),
        "identity": identity,
    }


def export_session_digest(session_id, *, goose="goose"):
    if not session_id:
        raise SignoffError("session ID is required")
    fd, path = tempfile.mkstemp(prefix="principled-dev-session-", suffix=".json")
    os.close(fd)
    try:
        result = subprocess.run(
            (
                goose,
                "session",
                "export",
                "--session-id",
                session_id,
                "--format",
                "json",
                "--output",
                path,
            ),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            raise SignoffError(result.stderr.strip() or "session export failed")
        digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        return {"session_id": session_id, "sha256": digest}
    finally:
        Path(path).unlink(missing_ok=True)
