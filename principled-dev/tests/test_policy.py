import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from path_policy import decide


def payload(tool, working_dir, **tool_input):
    return {
        "event": "PreToolUse",
        "tool_name": tool,
        "tool_input": tool_input,
        "working_dir": str(working_dir),
    }


@pytest.fixture
def paths(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    worktree = tmp_path / "managed" / "feature"
    repo.mkdir()
    worktree.mkdir(parents=True)
    monkeypatch.setenv("PRINCIPLED_DEV_FEATURE_WORKTREE", str(worktree))
    monkeypatch.setenv("PRINCIPLED_DEV_BASE_BRANCH", "main")
    return repo, worktree


def test_write_inside_feature_worktree_allowed(paths):
    _, worktree = paths
    assert decide(payload("developer__write", worktree, path="src/new.py")) is None


def test_write_outside_feature_worktree_blocked(paths):
    repo, _ = paths
    decision = decide(payload("developer__edit", repo, path="src/app.py"))
    assert decision["decision"] == "block"
    assert "feature worktree" in decision["reason"]


def test_relative_paths_use_working_directory(paths):
    _, worktree = paths
    child = worktree / "src"
    child.mkdir()
    assert decide(payload("developer__write", child, path="module.py")) is None


def test_symlink_escape_is_blocked(paths, tmp_path):
    _, worktree = paths
    outside = tmp_path / "outside"
    outside.mkdir()
    (worktree / "escape").symlink_to(outside, target_is_directory=True)
    decision = decide(payload("developer__write", worktree, path="escape/file.py"))
    assert decision["decision"] == "block"


@pytest.mark.parametrize(
    "command",
    (
        "git merge feature",
        "git push origin HEAD:main",
        "git push origin main",
        "gh pr create --base main --head agent/x",
    ),
)
def test_human_owned_integration_commands_are_blocked(paths, command):
    _, worktree = paths
    decision = decide(payload("developer__shell", worktree, command=command))
    assert decision["decision"] == "block"
    assert "human-owned" in decision["reason"]


def test_read_only_shell_command_allowed(paths):
    _, worktree = paths
    assert decide(payload("developer__shell", worktree, command="git diff main...HEAD")) is None


def test_missing_feature_state_blocks_repository_edits(tmp_path, monkeypatch):
    monkeypatch.delenv("PRINCIPLED_DEV_FEATURE_WORKTREE", raising=False)
    decision = decide(payload("developer__write", tmp_path, path="file.py"))
    assert decision["decision"] == "block"
    assert "not configured" in decision["reason"]


def test_hook_cli_outputs_block_json(paths):
    repo, _ = paths
    script = Path(__file__).resolve().parents[1] / "scripts" / "path_policy.py"
    result = subprocess.run(
        (sys.executable, str(script)),
        input=json.dumps(payload("developer__write", repo, path="file.py")),
        capture_output=True,
        text=True,
        check=True,
        env=os.environ,
    )
    assert json.loads(result.stdout)["decision"] == "block"
