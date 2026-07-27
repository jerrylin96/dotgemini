import subprocess
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from principled_dev.lifecycle import Lifecycle
from principled_dev.review import Finding, record_review
from principled_dev.signoff import create_attestation
from principled_dev.state import StateStore


def git(cwd, *args):
    return subprocess.run(
        ("git", *args), cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def test_complete_local_lifecycle_keeps_primary_checkout_untouched(tmp_path):
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    primary = tmp_path / "primary"
    git(tmp_path, "clone", "-q", str(remote), str(primary))
    git(primary, "config", "user.name", "Test")
    git(primary, "config", "user.email", "test@example.invalid")
    git(primary, "switch", "-qc", "main")
    (primary / "logic.py").write_text("def divide(a, b):\n    return a / b\n", encoding="utf-8")
    git(primary, "add", "logic.py")
    git(primary, "commit", "-qm", "base")
    git(primary, "push", "-q", "-u", "origin", "main")

    original_branch = git(primary, "symbolic-ref", "HEAD")
    original_head = git(primary, "rev-parse", "HEAD")
    original_status = git(primary, "status", "--porcelain=v1", "--untracked-files=all")

    lifecycle = Lifecycle(
        primary,
        tmp_path / "worktrees",
        StateStore(tmp_path / "state.json"),
        feature_branch="agent/safe-divide",
        base_branch="main",
    )
    lifecycle.record_artifact("spec", "division by zero raises ValueError")
    lifecycle.approve("spec")
    lifecycle.record_artifact("plan", "test then guard denominator")
    lifecycle.approve("plan")
    feature = lifecycle.create_feature(original_head)

    logic = feature / "logic.py"
    logic.write_text(
        "def divide(a, b):\n    if b == 0:\n        raise ValueError('zero denominator')\n    return a / b\n",
        encoding="utf-8",
    )
    git(feature, "add", "logic.py")
    git(feature, "commit", "-qm", "add incorrect guard message")
    first = git(feature, "rev-parse", "HEAD")
    first_tree = git(feature, "rev-parse", "HEAD^{tree}")
    manifest = lifecycle.bind_manifest("guard denominator")
    lifecycle.approve_manifest(manifest)

    review_worktree = lifecycle.worktrees.create_review(first)
    request_changes = record_review(
        lifecycle.base_sha,
        first,
        first_tree,
        findings=(
            Finding(
                "IMPORTANT",
                "logic.py",
                3,
                "raise ValueError('zero denominator')",
                "Public error contract requires exact message 'division by zero'.",
                "Use the specified error message and add regression assertion.",
            ),
        ),
        builder_worktree=str(feature),
        reviewer_worktree=str(review_worktree),
    )
    assert request_changes.verdict == "REQUEST_CHANGES"

    logic.write_text(
        "def divide(a, b):\n    if b == 0:\n        raise ValueError('division by zero')\n    return a / b\n",
        encoding="utf-8",
    )
    git(feature, "add", "logic.py")
    git(feature, "commit", "-qm", "fix error contract")
    second = git(feature, "rev-parse", "HEAD")
    second_tree = git(feature, "rev-parse", "HEAD^{tree}")
    assert not request_changes.is_fresh(lifecycle.base_sha, second, second_tree)

    manifest = lifecycle.bind_manifest("guard denominator with exact contract")
    lifecycle.approve_manifest(manifest)
    fresh_review_worktree = lifecycle.worktrees.create_review(second)
    approval = record_review(
        lifecycle.base_sha,
        second,
        second_tree,
        validations={"contract": "passed"},
        required_checks=("contract",),
        builder_worktree=str(feature),
        reviewer_worktree=str(fresh_review_worktree),
    )
    published = lifecycle.publish(approval)
    assert published["pushed_sha"] == second

    attestation = create_attestation(
        feature,
        approval,
        human_reviewed=True,
        identity="human@example.invalid",
        remote_sha=second,
        tradeoffs=("POSIX-only initial release",),
        risks=("Policy hook is not a sandbox",),
        expected_review_digest=approval.digest(),
    )
    assert attestation["status"] == "VERIFIED_BY_HUMAN"

    # Simulate a human merge in a separate integration checkout, never through lifecycle code.
    integration = tmp_path / "integration"
    git(tmp_path, "clone", "-q", str(remote), str(integration))
    git(integration, "config", "user.name", "Human")
    git(integration, "config", "user.email", "human@example.invalid")
    git(integration, "switch", "-q", "main")
    git(integration, "merge", "--ff-only", "origin/agent/safe-divide")
    git(integration, "push", "-q", "origin", "main")

    lifecycle.worktrees.remove_feature("agent/safe-divide")
    lifecycle.worktrees.prune_reviews()
    assert not feature.exists()
    assert git(primary, "symbolic-ref", "HEAD") == original_branch
    assert git(primary, "rev-parse", "HEAD") == original_head
    assert git(primary, "status", "--porcelain=v1", "--untracked-files=all") == original_status
