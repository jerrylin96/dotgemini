"""signoff-mcp: GSA Protocol v1.0 Phase 2 — deterministic MCP server mechanics.

Implements skills/signoff/specs/gsa-core.md §3 (TranscriptProvider adapters),
§4 (signoff_prepare / signoff_commit tools), and §2.5 (git-notes dual
persistence with tracking-ref cat_sort_uniq merge). The Socratic interview
stays in the agent prompt; this package is deterministic Git mechanics only.
"""

from signoff_mcp.adapters import (
    AntigravityAdapter,
    ClaudeCodeAdapter,
    CodexAdapter,
    GenericFileAdapter,
    TranscriptProvider,
    resolve_adapter,
)
from signoff_mcp.profile import (
    ProfileOverrideError,
    ProfileResolution,
    detect_science_signals,
    profile_block_digest,
    resolve_profile,
)
from signoff_mcp.core import (
    CommitResult,
    GitRepo,
    PrepareState,
    SignoffError,
    SignoffIntegrityError,
    SignoffPushError,
    SignoffStaleError,
    SignoffTranscriptError,
    commit,
    parse_trailers,
    prepare,
    push_notes,
)

__version__ = "0.3.0"

__all__ = [
    "AntigravityAdapter",
    "ClaudeCodeAdapter",
    "CodexAdapter",
    "CommitResult",
    "GenericFileAdapter",
    "GitRepo",
    "PrepareState",
    "ProfileOverrideError",
    "ProfileResolution",
    "SignoffError",
    "SignoffIntegrityError",
    "SignoffPushError",
    "SignoffStaleError",
    "SignoffTranscriptError",
    "TranscriptProvider",
    "commit",
    "detect_science_signals",
    "parse_trailers",
    "prepare",
    "profile_block_digest",
    "push_notes",
    "resolve_adapter",
    "resolve_profile",
]
