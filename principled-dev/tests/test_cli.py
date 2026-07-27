import json
import os
import subprocess
import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CLI = PLUGIN_ROOT / "scripts" / "principled_dev.py"


def git(cwd, *args):
    return subprocess.run(
        ("git", *args), cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def run_cli(repo, env, *args):
    result = subprocess.run(
        (sys.executable, str(CLI), "--repo", str(repo), *args),
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_cli_resumes_lifecycle_across_processes(tmp_path):
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
    base = git(repo, "rev-parse", "HEAD")

    env = {
        **os.environ,
        "PRINCIPLED_DEV_WORKTREE_ROOT": str(tmp_path / "worktrees"),
        "PRINCIPLED_DEV_STATE_ROOT": str(tmp_path / "state"),
    }
    spec = tmp_path / "spec.md"
    spec.write_text("secret-free spec\n", encoding="utf-8")
    plan = tmp_path / "plan.md"
    plan.write_text("approved plan\n", encoding="utf-8")
    identity = ("--feature", "agent/topic")

    run_cli(repo, env, *identity, "record-artifact", "spec", str(spec))
    run_cli(repo, env, *identity, "approve", "spec")
    run_cli(repo, env, *identity, "record-artifact", "plan", str(plan))
    run_cli(repo, env, *identity, "approve", "plan")
    created = run_cli(repo, env, "feature", "agent/topic", "--base", base)
    feature = Path(created["worktree_path"])
    assert git(feature, "rev-parse", "HEAD") == base

    (feature / "app.txt").write_text("feature\n", encoding="utf-8")
    git(feature, "add", "app.txt")
    git(feature, "commit", "-qm", "feature")
    commit = git(feature, "rev-parse", "HEAD")
    tree = git(feature, "rev-parse", "HEAD^{tree}")

    manifest_path = tmp_path / "manifest.json"
    manifest = run_cli(
        repo,
        env,
        *identity,
        "bind-manifest",
        "summary is output-only",
        "--output",
        str(manifest_path),
    )
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest
    assert manifest["base_sha"] == base
    assert manifest["commit_sha"] == commit
    run_cli(repo, env, *identity, "approve-manifest", str(manifest_path))

    review_worktree = run_cli(repo, env, *identity, "review-worktree")
    assert git(review_worktree["worktree_path"], "rev-parse", "HEAD") == commit

    review_path = tmp_path / "review.json"
    review_path.write_text(
        json.dumps(
            {
                "verdict": "APPROVE",
                "base_sha": base,
                "commit_sha": commit,
                "tree_sha": tree,
                "findings": [],
                "validations": {"tests": "passed"},
                "unverified_checks": [],
                "blocked_reason": "",
            }
        ),
        encoding="utf-8",
    )
    published = run_cli(repo, env, *identity, "publish", str(review_path))
    assert published["pushed_sha"] == commit

    state_text = (tmp_path / "state" / "lifecycle.json").read_text(encoding="utf-8")
    for excluded in (
        str(repo),
        str(remote),
        spec.read_text(encoding="utf-8").strip(),
        plan.read_text(encoding="utf-8").strip(),
        "summary is output-only",
        "tests",
    ):
        assert excluded not in state_text
    assert commit in state_text
