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

__version__ = "0.1.0"

__all__ = [
    "AntigravityAdapter",
    "ClaudeCodeAdapter",
    "CodexAdapter",
    "CommitResult",
    "GenericFileAdapter",
    "GitRepo",
    "PrepareState",
    "SignoffError",
    "SignoffIntegrityError",
    "SignoffPushError",
    "SignoffStaleError",
    "SignoffTranscriptError",
    "TranscriptProvider",
    "commit",
    "parse_trailers",
    "prepare",
    "push_notes",
    "resolve_adapter",
]
