"""TranscriptProvider adapters (GSA spec §3.1–3.2).

Ports the empirically validated digest-helper resolution logic from
skills/signoff/SKILL.md. Adapters only locate and fetch raw transcript
bytes; the core engine computes digests and byte counts (§3.1).

All filesystem/env/cwd inputs are injectable for tests. Missing or
unreadable transcripts degrade cleanly to None — never raise.
"""

import glob
import os
import subprocess
from typing import Mapping, Protocol


class TranscriptProvider(Protocol):
    """Minimal interface for transcript discovery across AI agent runtimes."""

    harness_id: str

    def resolve_conversation_id(self) -> str | None:
        """Returns the active conversation/session ID string, or None if unresolvable."""
        ...

    def fetch_transcript_bytes(self) -> bytes | None:
        """Returns raw transcript file bytes as a snapshot at call time, or None if unavailable."""
        ...


def _slug(path: str) -> str:
    return path.replace("/", "-")


def _read_bytes(path: str | None) -> bytes | None:
    if not path:
        return None
    try:
        with open(os.path.expanduser(path), "rb") as f:
            return f.read()
    except OSError:
        return None


class GenericFileAdapter:
    """Explicit transcript override via SIGNOFF_TRANSCRIPT_FILE (§3.2)."""

    harness_id = "generic-file"

    def __init__(self, path: str, conversation_id: str | None = None):
        self.path = path
        self.conversation_id = conversation_id

    def resolve_conversation_id(self) -> str | None:
        return self.conversation_id

    def fetch_transcript_bytes(self) -> bytes | None:
        return _read_bytes(self.path)


class AntigravityAdapter:
    """Antigravity CLI harness (§3.2)."""

    harness_id = "antigravity-cli"

    def __init__(self, conversation_id: str, home: str | None = None):
        self.conversation_id = conversation_id
        self.home = home or os.path.expanduser("~")

    def resolve_conversation_id(self) -> str | None:
        return self.conversation_id

    def fetch_transcript_bytes(self) -> bytes | None:
        path = os.path.join(
            self.home,
            ".gemini",
            "antigravity-cli",
            "brain",
            self.conversation_id,
            ".system_generated",
            "logs",
            "transcript.jsonl",
        )
        return _read_bytes(path)


class ClaudeCodeAdapter:
    """Claude Code harness (§3.2) with linked-worktree fallback.

    Session transcripts are keyed to the primary repository root slug. Inside a
    linked worktree (or a subdirectory of the main worktree) the cwd slug
    misses, so fall back to the primary root via `git rev-parse
    --git-common-dir`. That command may return a path relative to cwd (e.g.
    `.git` or `../.git`), so both the subprocess and the join are anchored to
    the injected cwd rather than the process cwd.
    """

    harness_id = "claude-code"

    def __init__(self, session_id: str, cwd: str | None = None, home: str | None = None):
        self.session_id = session_id
        self.cwd = os.path.abspath(cwd or os.getcwd())
        self.home = home or os.path.expanduser("~")

    def resolve_conversation_id(self) -> str | None:
        return self.session_id

    def _transcript_path(self, root: str) -> str:
        return os.path.join(self.home, ".claude", "projects", _slug(root), f"{self.session_id}.jsonl")

    def fetch_transcript_bytes(self) -> bytes | None:
        path = self._transcript_path(self.cwd)
        if not os.path.exists(path):
            try:
                git_dir = subprocess.check_output(
                    ["git", "rev-parse", "--git-common-dir"],
                    text=True,
                    stderr=subprocess.DEVNULL,
                    cwd=self.cwd,
                ).strip()
                main_root = os.path.abspath(os.path.join(self.cwd, git_dir, os.pardir))
                path = self._transcript_path(main_root)
            except Exception:
                return None
        return _read_bytes(path)


class CodexAdapter:
    """ChatGPT Codex CLI harness.

    Codex stores session rollouts as date-partitioned JSONL files under
    `$CODEX_HOME/sessions/` (default `~/.codex/sessions/`), named
    `rollout-<timestamp>-<session-id>.jsonl`. Codex does not inject a session-id
    env var itself, so this adapter triggers on a user/wrapper-exported
    CODEX_SESSION_ID; without it, use the SIGNOFF_TRANSCRIPT_FILE override.
    """

    harness_id = "codex-cli"

    def __init__(self, session_id: str, codex_home: str | None = None, home: str | None = None):
        self.session_id = session_id
        base = codex_home or os.path.join(home or os.path.expanduser("~"), ".codex")
        self.sessions_dir = os.path.join(base, "sessions")

    def resolve_conversation_id(self) -> str | None:
        return self.session_id

    def fetch_transcript_bytes(self) -> bytes | None:
        pattern = os.path.join(glob.escape(self.sessions_dir), "**", f"*{self.session_id}.jsonl")
        try:
            matches = glob.glob(pattern, recursive=True)
            if not matches:
                return None
            newest = max(matches, key=os.path.getmtime)
        except OSError:
            return None
        return _read_bytes(newest)


def resolve_adapter(
    env: Mapping[str, str] | None = None,
    cwd: str | None = None,
    home: str | None = None,
) -> TranscriptProvider | None:
    """Resolve the active harness adapter, or None when no harness is detected.

    Resolution order: SIGNOFF_TRANSCRIPT_FILE → ANTIGRAVITY_CONVERSATION_ID →
    CLAUDE_CODE_SESSION_ID (the GSA §3.2 / SKILL.md order) → CODEX_SESSION_ID
    (appended; §3.2's adapter matrix is informative and adapter-owned).
    """
    env = os.environ if env is None else env
    override = env.get("SIGNOFF_TRANSCRIPT_FILE", "").strip()
    ag_cid = env.get("ANTIGRAVITY_CONVERSATION_ID", "").strip()
    cc_cid = env.get("CLAUDE_CODE_SESSION_ID", "").strip()
    codex_sid = env.get("CODEX_SESSION_ID", "").strip()

    if override:
        return GenericFileAdapter(override, conversation_id=ag_cid or cc_cid or codex_sid or None)
    if ag_cid:
        return AntigravityAdapter(ag_cid, home=home)
    if cc_cid:
        return ClaudeCodeAdapter(cc_cid, cwd=cwd, home=home)
    if codex_sid:
        return CodexAdapter(codex_sid, codex_home=env.get("CODEX_HOME", "").strip() or None, home=home)
    return None
