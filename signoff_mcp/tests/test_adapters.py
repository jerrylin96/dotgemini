import os

from signoff_mcp.adapters import (
    AntigravityAdapter,
    ClaudeCodeAdapter,
    CodexAdapter,
    GenericFileAdapter,
    resolve_adapter,
)
from signoff_mcp.tests.helpers import git, init_repo


def _slug(p):
    return str(p).replace("/", "-")


def _plant_claude_transcript(home, root, sid, data=b'{"role":"user"}\n'):
    d = home / ".claude" / "projects" / _slug(root)
    d.mkdir(parents=True)
    (d / f"{sid}.jsonl").write_bytes(data)
    return data


def test_resolution_order_override_wins(tmp_path):
    f = tmp_path / "t.log"
    f.write_bytes(b"hello")
    env = {
        "SIGNOFF_TRANSCRIPT_FILE": str(f),
        "ANTIGRAVITY_CONVERSATION_ID": "ag-1",
        "CLAUDE_CODE_SESSION_ID": "cc-1",
    }
    a = resolve_adapter(env)
    assert isinstance(a, GenericFileAdapter)
    assert a.harness_id == "generic-file"
    assert a.resolve_conversation_id() == "ag-1"
    assert a.fetch_transcript_bytes() == b"hello"


def test_resolution_order_antigravity_over_claude(tmp_path):
    env = {"ANTIGRAVITY_CONVERSATION_ID": "ag-1", "CLAUDE_CODE_SESSION_ID": "cc-1"}
    a = resolve_adapter(env, home=str(tmp_path))
    assert isinstance(a, AntigravityAdapter)
    assert a.harness_id == "antigravity-cli"


def test_resolution_claude_then_none(tmp_path):
    a = resolve_adapter({"CLAUDE_CODE_SESSION_ID": "cc-1"}, cwd=str(tmp_path), home=str(tmp_path))
    assert isinstance(a, ClaudeCodeAdapter)
    assert a.harness_id == "claude-code"
    assert resolve_adapter({}) is None
    assert resolve_adapter({"SIGNOFF_TRANSCRIPT_FILE": "  "}) is None  # whitespace stripped


def test_generic_missing_file_degrades_to_none(tmp_path):
    a = GenericFileAdapter(str(tmp_path / "nope.log"))
    assert a.fetch_transcript_bytes() is None
    assert a.resolve_conversation_id() is None


def test_antigravity_transcript_path(tmp_path):
    cid = "conv-42"
    p = tmp_path / ".gemini" / "antigravity-cli" / "brain" / cid / ".system_generated" / "logs"
    p.mkdir(parents=True)
    (p / "transcript.jsonl").write_bytes(b"data")
    a = AntigravityAdapter(cid, home=str(tmp_path))
    assert a.fetch_transcript_bytes() == b"data"
    assert AntigravityAdapter("missing", home=str(tmp_path)).fetch_transcript_bytes() is None


def test_claude_primary_cwd_slug_hit(tmp_path):
    home, cwd = tmp_path / "home", tmp_path / "proj"
    cwd.mkdir()
    data = _plant_claude_transcript(home, cwd, "sid-1")
    a = ClaudeCodeAdapter("sid-1", cwd=str(cwd), home=str(home))
    assert a.fetch_transcript_bytes() == data


def test_claude_linked_worktree_fallback(tmp_path):
    """cwd slug misses inside a linked worktree; --git-common-dir resolves primary root."""
    home = tmp_path / "home"
    main = init_repo(tmp_path / "main")
    git(main, "commit", "-q", "--allow-empty", "-m", "base")
    wt = tmp_path / "wt"
    git(main, "worktree", "add", "-q", str(wt))
    data = _plant_claude_transcript(home, main, "sid-2")
    a = ClaudeCodeAdapter("sid-2", cwd=str(wt), home=str(home))
    assert a.fetch_transcript_bytes() == data


def test_claude_relative_git_common_dir_resolved_against_repo_cwd(tmp_path):
    """From a main-worktree subdirectory git returns a relative path (e.g. ../.git);
    it must be joined against the adapter's injected cwd, not the process cwd."""
    home = tmp_path / "home"
    main = init_repo(tmp_path / "main")
    git(main, "commit", "-q", "--allow-empty", "-m", "base")
    sub = main / "sub"
    sub.mkdir()
    data = _plant_claude_transcript(home, main, "sid-3")
    assert os.getcwd() != str(sub)  # process cwd differs from injected cwd
    a = ClaudeCodeAdapter("sid-3", cwd=str(sub), home=str(home))
    assert a.fetch_transcript_bytes() == data


def _plant_codex_rollout(base, day, ts, sid, data):
    d = base / "sessions" / "2026" / "08" / day
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"rollout-{ts}-{sid}.jsonl"
    f.write_bytes(data)
    return f


def test_codex_rollout_discovery(tmp_path):
    home = tmp_path / "home"
    _plant_codex_rollout(home / ".codex", "05", "2026-08-05T10-00-00", "sid-9", b"codex-data")
    a = CodexAdapter("sid-9", home=str(home))
    assert a.harness_id == "codex-cli"
    assert a.resolve_conversation_id() == "sid-9"
    assert a.fetch_transcript_bytes() == b"codex-data"
    assert CodexAdapter("missing", home=str(home)).fetch_transcript_bytes() is None


def test_codex_home_override_and_newest_match(tmp_path):
    codex_home = tmp_path / "custom-codex"
    old = _plant_codex_rollout(codex_home, "04", "2026-08-04T09-00-00", "sid-9", b"old")
    new = _plant_codex_rollout(codex_home, "05", "2026-08-05T10-00-00", "sid-9", b"new")
    os.utime(old, (1, 1))
    os.utime(new, (2, 2))
    a = CodexAdapter("sid-9", codex_home=str(codex_home), home=str(tmp_path / "unused-home"))
    assert a.fetch_transcript_bytes() == b"new"


def test_resolution_codex_after_claude(tmp_path):
    env = {"CLAUDE_CODE_SESSION_ID": "cc-1", "CODEX_SESSION_ID": "cx-1"}
    assert isinstance(resolve_adapter(env, cwd=str(tmp_path), home=str(tmp_path)), ClaudeCodeAdapter)
    a = resolve_adapter({"CODEX_SESSION_ID": "cx-1", "CODEX_HOME": str(tmp_path / "ch")}, home=str(tmp_path))
    assert isinstance(a, CodexAdapter)
    assert a.sessions_dir == str(tmp_path / "ch" / "sessions")


def test_claude_outside_git_repo_degrades_to_none(tmp_path):
    cwd = tmp_path / "plain"
    cwd.mkdir()
    a = ClaudeCodeAdapter("sid-4", cwd=str(cwd), home=str(tmp_path / "home"))
    assert a.fetch_transcript_bytes() is None
