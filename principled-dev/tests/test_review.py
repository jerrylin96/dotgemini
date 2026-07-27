import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from principled_dev.review import Finding, ReviewRecord, record_review


BASE = "a" * 40
COMMIT = "b" * 40
TREE = "c" * 40


def finding(severity="IMPORTANT"):
    return Finding(
        severity=severity,
        path="src/auth.py",
        line=42,
        evidence="if token == user_input:",
        consequence="Untrusted token is accepted.",
        remediation="Verify a signed token before use.",
    )


def test_finding_requires_exact_evidence_contract():
    with pytest.raises(ValueError, match="evidence"):
        Finding("IMPORTANT", "src/auth.py", 42, "", "bad", "fix")
    with pytest.raises(ValueError, match="line"):
        Finding("IMPORTANT", "src/auth.py", 0, "code", "bad", "fix")
    with pytest.raises(ValueError, match="severity"):
        Finding("HIGH", "src/auth.py", 1, "code", "bad", "fix")


def test_blocking_findings_prevent_approval():
    for severity in ("CRITICAL", "IMPORTANT"):
        review = record_review(BASE, COMMIT, TREE, findings=[finding(severity)])
        assert review.verdict == "REQUEST_CHANGES"


def test_suggestions_can_be_approved_and_unverified_checks_are_recorded():
    review = record_review(
        BASE,
        COMMIT,
        TREE,
        findings=[finding("SUGGESTION")],
        validations={"unit": "passed"},
        required_checks=("unit", "lint", "build"),
    )
    assert review.verdict == "APPROVE"
    assert review.unverified_checks == ("build", "lint")


def test_blocked_reason_forces_blocked_verdict():
    review = record_review(BASE, COMMIT, TREE, blocked_reason="reviewer unavailable")
    assert review.verdict == "BLOCKED"
    assert review.blocked_reason == "reviewer unavailable"


def test_review_requires_separate_builder_and_reviewer_worktrees():
    with pytest.raises(ValueError, match="separate"):
        record_review(
            BASE,
            COMMIT,
            TREE,
            builder_worktree="/tmp/worktree",
            reviewer_worktree="/tmp/worktree",
        )


def test_approval_is_bound_to_exact_base_commit_and_tree():
    review = record_review(BASE, COMMIT, TREE)
    assert review.verdict == "APPROVE"
    assert review.is_fresh(BASE, COMMIT, TREE)
    assert not review.is_fresh("d" * 40, COMMIT, TREE)
    assert not review.is_fresh(BASE, "d" * 40, TREE)
    assert not review.is_fresh(BASE, COMMIT, "d" * 40)


def test_review_round_trip_preserves_contract():
    review = record_review(
        BASE,
        COMMIT,
        TREE,
        findings=[finding("FYI")],
        validations={"tests": "12 passed"},
    )
    assert ReviewRecord.from_dict(review.to_dict()) == review
    rendered = review.to_markdown()
    assert "Verdict: APPROVE" in rendered
    assert f"Reviewed-Commit-SHA: {COMMIT}" in rendered
    assert "src/auth.py:42" in rendered
