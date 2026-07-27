import configparser
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLUGIN_ROOT.parent
CLI = PLUGIN_ROOT / "scripts" / "principled_dev.py"


def load_cli_module():
    spec = importlib.util.spec_from_file_location("principled_dev_cli", CLI)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_pytest_default_collection_includes_plugin_suite():
    config = configparser.ConfigParser()
    config.read(REPOSITORY_ROOT / "pytest.ini")
    testpaths = config["pytest"]["testpaths"].split()

    assert "principled-dev/tests" in testpaths
    workflow = (REPOSITORY_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "python3 scripts/run_in_env.py . pytest" in workflow


def test_cli_reports_publication_partial_success_as_structured_stderr(
    tmp_path, monkeypatch, capsys
):
    cli = load_cli_module()
    review_path = tmp_path / "review.json"
    review_path.write_text(
        json.dumps(
            {
                "verdict": "APPROVE",
                "base_sha": "1" * 40,
                "commit_sha": "2" * 40,
                "tree_sha": "3" * 40,
            }
        ),
        encoding="utf-8",
    )

    class PartiallyPublishingLifecycle:
        def publish(self, review, remote=None):
            raise cli.PublicationPartialSuccess("origin", "agent/topic", "2" * 40)

    monkeypatch.setattr(cli, "make_lifecycle", lambda args: PartiallyPublishingLifecycle())

    assert cli.main(
        [
            "--repo",
            str(tmp_path),
            "--feature",
            "agent/topic",
            "publish",
            str(review_path),
        ]
    ) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "error": "publication_partial_success",
        "message": (
            "publication succeeded on remote origin branch agent/topic at intended SHA "
            f"{'2' * 40}, but local_state_persistence failed"
        ),
        "remote": "origin",
        "branch": "agent/topic",
        "pushed_sha": "2" * 40,
        "phase": "local_state_persistence",
        "observed_sha": None,
        "cause": None,
    }


def test_cli_partial_success_redacts_cause_and_structured_stderr(
    tmp_path, monkeypatch, capsys
):
    cli = load_cli_module()
    review_path = tmp_path / "review.json"
    review_path.write_text(
        json.dumps(
            {
                "verdict": "APPROVE",
                "base_sha": "1" * 40,
                "commit_sha": "2" * 40,
                "tree_sha": "3" * 40,
            }
        ),
        encoding="utf-8",
    )
    credential_url = (
        "https://alice:remote-secret@example.invalid/repo.git"
        "?token=query-secret&password=password-secret"
    )

    class PartiallyPublishingLifecycle:
        def publish(self, review, remote=None):
            raise cli.PublicationPartialSuccess(
                "credentialed",
                "agent/topic",
                "2" * 40,
                phase="remote_verification",
                cause=f"cannot read {credential_url}",
            )

    monkeypatch.setattr(cli, "make_lifecycle", lambda args: PartiallyPublishingLifecycle())

    assert cli.main(
        [
            "--repo",
            str(tmp_path),
            "--feature",
            "agent/topic",
            "publish",
            str(review_path),
            "--remote",
            "credentialed",
        ]
    ) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    error = json.loads(captured.err)
    assert error["remote"] == "credentialed"
    assert error["phase"] == "remote_verification"
    for secret in ("alice", "remote-secret", "query-secret", "password-secret"):
        assert secret not in captured.err


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
    credential_remote = (
        "https://alice:remote-secret@example.invalid/repo.git?token=query-secret"
    )
    rejected = subprocess.run(
        (
            sys.executable,
            str(CLI),
            "--repo",
            str(repo),
            *identity,
            "publish",
            str(review_path),
            "--remote",
            credential_remote,
        ),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert rejected.returncode != 0
    for exposed in (
        rejected.stdout,
        rejected.stderr,
        (tmp_path / "state" / "lifecycle.json").read_text(encoding="utf-8"),
    ):
        assert "remote-secret" not in exposed
        assert "query-secret" not in exposed
    assert git(feature, "ls-remote", "origin", "refs/heads/agent/topic") == ""

    published = run_cli(repo, env, *identity, "publish", str(review_path))
    assert published["pushed_sha"] == commit
    assert published["remote"] == "origin"

    signed = run_cli(
        repo,
        env,
        *identity,
        "signoff",
        str(review_path),
        "--identity",
        "human@example.invalid",
        "--human-reviewed",
    )
    assert signed["commit_sha"] == commit
    assert git(repo, "rev-parse", "HEAD") == base

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
