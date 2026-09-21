"""Shared fixtures for scripts/tests: env isolation and scratch repositories."""

import pytest
from helpers import commit_file, git, init_repo


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch):
    """Neutralize harness env vars and user/system git config for scratch repos.

    GIT_SIGNOFF_NO_UPDATE_CHECK=1 keeps the verifier's stale-pin check from
    reaching the network during tests; the stale-pin tests unset it and point
    GIT_SIGNOFF_PIN_REMOTE at a local bare repository.
    """
    for var in (
        "GIT_SIGNOFF_PROFILE_FILE",
        "GIT_SIGNOFF_TRANSCRIPT_FILE",
        "GIT_SIGNOFF_VERIFIED_BY",
        "GIT_SIGNOFF_PIN_REMOTE",
        "ANTIGRAVITY_CONVERSATION_ID",
        "CLAUDE_CODE_SESSION_ID",
        "CLAUDE_CODE_VERSION",
        "CLAUDE_EFFORT",
        "ANTHROPIC_MODEL",
        "CODEX_SESSION_ID",
        "CODEX_HOME",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GIT_SIGNOFF_NO_UPDATE_CHECK", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", "/dev/null")


@pytest.fixture
def scratch_repo(tmp_path):
    """Repo on branch 'feature', one commit ahead of 'main'."""
    path = init_repo(tmp_path / "repo")
    commit_file(path, "base.txt", "base\n", "base commit")
    git(path, "checkout", "-q", "-b", "feature")
    commit_file(path, "feat.txt", "feature\n", "feature commit")
    return path
