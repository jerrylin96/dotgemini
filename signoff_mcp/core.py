"""Deterministic GSA engine (spec §2, §4): git state, trailers, notes.

No MCP dependency — pure stdlib, fully testable against scratch repos.
"""

import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone

from signoff_mcp.adapters import TranscriptProvider, resolve_adapter
from signoff_mcp.profile import ProfileOverrideError, detect_science_signals, resolve_profile

SPEC_VERSION = "1.0"
NOTES_REF = "refs/notes/signoff"
NOTES_TRACKING_REF = "refs/notes/signoff-remote"
STATUS_VERIFIED = "VERIFIED_BY_HUMAN"
STATUS_NO_DIGEST = "VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST"
UNAVAILABLE = "unavailable"


class SignoffError(Exception):
    """Base error for signoff mechanics."""


class SignoffStaleError(SignoffError):
    """HEAD moved or worktree dirty between prepare and commit (§4 circuit breaker)."""


class SignoffTranscriptError(SignoffError):
    """Transcript unavailable and ack_no_transcript not set (§2.2 enforcement)."""


class SignoffIntegrityError(SignoffError):
    """Post-commit tree/parent verification failed."""


class SignoffPushError(SignoffError):
    """Notes fetch/merge/push failed (network, auth, or merge conflict)."""


class GitRepo:
    """Thin subprocess wrapper; every command runs with cwd=self.path."""

    def __init__(self, path: str):
        self.path = path

    def git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        proc = subprocess.run(
            ["git", *args],
            cwd=self.path,
            capture_output=True,
            text=True,
        )
        if check and proc.returncode != 0:
            raise SignoffError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
        return proc

    def out(self, *args: str) -> str:
        return self.git(*args).stdout.strip()


@dataclass
class PrepareState:
    reviewed_commit_sha: str
    base_sha: str
    tree_sha: str
    reference_ref: str
    diff: str
    files: list[str]
    stats: str
    harness_id: str
    conversation_id: str
    transcript_available: bool
    # Phase 3e mirrors of SKILL.md Section 1 step 5 and the science guard
    # (informative; the skill layer conducts the interview). profile_digest is
    # the 12-hex $PROFILE_DIGEST prefix, None when the embedded default runs.
    profile_source: str = "embedded-default"
    profile_path: str | None = None
    profile_id: str = "software-general"
    profile_digest: str | None = None
    profile_fallback_reason: str | None = None
    science_signals: list[str] = field(default_factory=list)


@dataclass
class CommitResult:
    attestation_sha: str
    status: str
    transcript_digest: str
    transcript_bytes: str
    message: str
    signed: bool
    noted_shas: list[str] = field(default_factory=list)


def _resolve_reference(repo: GitRepo, target_ref: str, reference_ref: str | None) -> str:
    if reference_ref:
        return reference_ref
    proc = repo.git("rev-parse", "--abbrev-ref", f"{target_ref}@{{upstream}}", check=False)
    if proc.returncode != 0:
        raise SignoffError(
            f"No upstream configured for '{target_ref}'; pass reference_ref explicitly "
            "(no hardcoded remote assumptions per GSA §2.3)."
        )
    return proc.stdout.strip()


def prepare(
    repo: GitRepo,
    target_ref: str = "HEAD",
    reference_ref: str | None = None,
    adapter: TranscriptProvider | None = None,
) -> PrepareState:
    """Resolve reviewed/base/tree SHAs and range diff for Socratic auditing (§4.1)."""
    reviewed = repo.out("rev-parse", f"{target_ref}^{{commit}}")
    reference = _resolve_reference(repo, target_ref, reference_ref)
    base = repo.out("merge-base", reference, reviewed)
    tree = repo.out("rev-parse", f"{reviewed}^{{tree}}")

    diff = repo.git("diff", f"{base}..{reviewed}").stdout
    files = [line for line in repo.out("diff", "--name-status", f"{base}..{reviewed}").splitlines() if line]
    stats = repo.out("diff", "--shortstat", f"{base}..{reviewed}")

    if adapter is None:
        adapter = resolve_adapter(cwd=repo.path)
    harness_id = adapter.harness_id if adapter else "unknown"
    conversation_id = (adapter.resolve_conversation_id() if adapter else None) or UNAVAILABLE
    # Informative only (§4.1); the binding snapshot happens inside commit (§2.3).
    transcript_available = bool(adapter and adapter.fetch_transcript_bytes() is not None)

    try:
        prof = resolve_profile(repo.out("rev-parse", "--show-toplevel"))
    except ProfileOverrideError as e:
        raise SignoffError(str(e)) from e

    return PrepareState(
        reviewed_commit_sha=reviewed,
        base_sha=base,
        tree_sha=tree,
        reference_ref=reference,
        diff=diff,
        files=files,
        stats=stats,
        harness_id=harness_id,
        conversation_id=conversation_id,
        transcript_available=transcript_available,
        profile_source=prof.source,
        profile_path=prof.path,
        profile_id=prof.profile_id,
        profile_digest=prof.digest,
        profile_fallback_reason=prof.fallback_reason,
        science_signals=detect_science_signals(diff),
    )


def _check_clean_and_current(repo: GitRepo, state: PrepareState) -> None:
    head = repo.out("rev-parse", "HEAD")
    if head != state.reviewed_commit_sha:
        raise SignoffStaleError(
            f"HEAD ({head[:7]}) no longer matches reviewed commit ({state.reviewed_commit_sha[:7]}); signoff stale."
        )
    if repo.git("diff", "--quiet", check=False).returncode != 0:
        raise SignoffStaleError("Unstaged changes present; signoff stale.")
    if repo.git("diff", "--cached", "--quiet", check=False).returncode != 0:
        raise SignoffStaleError("Staged changes present; signoff stale.")


def _sha256(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def build_message(
    state: PrepareState,
    status: str,
    timestamp: str,
    harness_id: str,
    conversation_id: str,
    transcript_digest: str,
    transcript_bytes: str,
    tradeoffs: list[str],
    risks: list[str],
    user_email: str,
    agent: str,
    summary: str | None = None,
) -> str:
    short_sha = state.reviewed_commit_sha[:7]
    lines = [f"[SIGNOFF {short_sha}]: human comprehension and risk attestation", ""]
    if summary:
        lines += [summary.strip(), ""]
    lines += [
        f"Signoff-Spec-Version: {SPEC_VERSION}",
        f"Signoff-Status: {status}",
        f"Signoff-Timestamp: {timestamp}",
        f"Signoff-Base-SHA: {state.base_sha}",
        f"Signoff-Reviewed-Commit-SHA: {state.reviewed_commit_sha}",
        f"Signoff-Reviewed-Tree-SHA: {state.tree_sha}",
        f"Signoff-Harness-ID: {harness_id}",
        f"Signoff-Conversation-ID: {conversation_id}",
        f"Signoff-Transcript-Digest: {transcript_digest}",
        f"Signoff-Transcript-Bytes: {transcript_bytes}",
    ]
    # Repeat rule (§2.3): one trailer per item; 'none' exactly once when empty.
    lines += [f"Signoff-Tradeoff: {t}" for t in tradeoffs] or ["Signoff-Tradeoff: none"]
    lines += [f"Signoff-Risk: {r}" for r in risks] or ["Signoff-Risk: none"]
    lines += [
        f"Signoff-Verified-By: {user_email}",
        f"Signoff-Agent: {agent}",
    ]
    return "\n".join(lines)


def commit(
    repo: GitRepo,
    state: PrepareState,
    tradeoffs: list[str],
    risks: list[str],
    user_email: str,
    sign_commit: bool = True,
    ack_no_transcript: bool = False,
    adapter: TranscriptProvider | None = None,
    agent: str = "unknown",
    summary: str | None = None,
    timestamp: str | None = None,
) -> CommitResult:
    """Execute the attestation commit + git-notes dual persistence (§4.1, §2.5).

    Status is derived server-side from transcript availability; callers cannot
    override it (§2.2).
    """
    if not user_email or "@" not in user_email:
        raise SignoffError(f"Invalid Signoff-Verified-By email: {user_email!r}")

    _check_clean_and_current(repo, state)

    if adapter is None:
        adapter = resolve_adapter(cwd=repo.path)
    harness_id = adapter.harness_id if adapter else "unknown"
    conversation_id = (adapter.resolve_conversation_id() if adapter else None) or UNAVAILABLE

    # Snapshot timing (§2.3): capture bytes+digest here, immediately before the commit.
    data = adapter.fetch_transcript_bytes() if adapter else None
    if data is not None:
        status = STATUS_VERIFIED
        transcript_digest = f"sha256:{_sha256(data)}"
        transcript_bytes = str(len(data))
    elif ack_no_transcript:
        status = STATUS_NO_DIGEST
        transcript_digest = UNAVAILABLE
        transcript_bytes = UNAVAILABLE
    else:
        raise SignoffTranscriptError(
            "Transcript unavailable and ack_no_transcript=False; aborting. "
            "Re-run with ack_no_transcript=True only after explicit user confirmation of the downgraded status."
        )

    message = build_message(
        state,
        status,
        timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        harness_id,
        conversation_id,
        transcript_digest,
        transcript_bytes,
        tradeoffs,
        risks,
        user_email,
        agent,
        summary,
    )

    signed = bool(sign_commit and repo.git("config", "user.signingkey", check=False).stdout.strip())
    commit_args = ["commit", "--allow-empty"] + (["-S"] if signed else []) + ["-m", message]
    repo.git(*commit_args)

    attestation_sha = repo.out("rev-parse", "HEAD")
    if repo.out("rev-parse", "HEAD^{tree}") != state.tree_sha or repo.out("rev-parse", "HEAD~1") != state.reviewed_commit_sha:
        raise SignoffIntegrityError("Post-commit integrity check failed: tree or parent changed.")

    # Dual persistence (§2.5): note on both the reviewed commit and its tree.
    noted = [state.reviewed_commit_sha, state.tree_sha]
    for sha in noted:
        repo.git("notes", "--ref=signoff", "append", "-m", message, sha)

    return CommitResult(
        attestation_sha=attestation_sha,
        status=status,
        transcript_digest=transcript_digest,
        transcript_bytes=transcript_bytes,
        message=message,
        signed=signed,
        noted_shas=noted,
    )


def push_notes(repo: GitRepo, remote: str = "origin") -> dict:
    """Push refs/notes/signoff via the §2.5 tracking-ref cat_sort_uniq merge.

    The fetch guard tolerates remotes with no signoff notes yet (first
    attestation ever pushed). All git failures surface as SignoffPushError.
    """
    fetch = repo.git("fetch", remote, f"+{NOTES_REF}:{NOTES_TRACKING_REF}", check=False)
    merged = False
    if fetch.returncode == 0:
        merge = repo.git("notes", "--ref=signoff", "merge", "-s", "cat_sort_uniq", NOTES_TRACKING_REF, check=False)
        if merge.returncode != 0:
            raise SignoffPushError(f"Notes merge failed: {merge.stderr.strip()}")
        merged = True
    push = repo.git("push", remote, NOTES_REF, check=False)
    if push.returncode != 0:
        raise SignoffPushError(f"Notes push failed: {push.stderr.strip()}")
    return {"remote": remote, "merged_remote_notes": merged, "pushed": True}


_TRAILER_RE = re.compile(r"^(Signoff-[A-Za-z0-9-]+):\s*(.*)$")


def parse_trailers(message: str) -> dict[str, list[str]]:
    """Parse flat GSA trailers (repeated-key aware) from an attestation payload.

    Works on single attestations and on cat_sort_uniq-concatenated note blobs.
    """
    trailers: dict[str, list[str]] = {}
    for line in message.splitlines():
        m = _TRAILER_RE.match(line)
        if m:
            trailers.setdefault(m.group(1), []).append(m.group(2).strip())
    return trailers
