import pytest

from signoff_mcp.tests.helpers import commit_file, git, init_repo


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch):
    """Neutralize harness env vars and user/system git config for scratch repos."""
    for var in (
        "SIGNOFF_TRANSCRIPT_FILE",
        "ANTIGRAVITY_CONVERSATION_ID",
        "CLAUDE_CODE_SESSION_ID",
        "CODEX_SESSION_ID",
        "CODEX_HOME",
    ):
        monkeypatch.delenv(var, raising=False)
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
