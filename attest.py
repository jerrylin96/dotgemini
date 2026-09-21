#!/usr/bin/env python3
"""Git Signoff Attestation (GSA) producer — deterministic mechanics for /git-signoff.

The interviewing agent conducts the Socratic interview; this helper does every
mechanical step of the attestation so the agent never computes a digest,
derives a status, formats a trailer, or merges notes. Standard library only,
Python 3.10+, vendored into adopter repositories with the rest of this folder.

Commands:

  attest.py practice-start [--json]
      Record the actual start of practice in local, shared Git metadata.
      This session cannot prepare or write a real attestation afterward.

  attest.py prepare  [--target BRANCH] [--reference REF] [--json]
                    [--explain | --practice] [--check-snapshot SHA256]
      Resolve reviewed/base/tree SHAs, the range diff summary, the active
      interview profile, science-guard signals, transcript availability,
      intensity hints, and the approval marker the agent must emit; record
      the prepared state under .git/git-signoff/prepared.json. With
      --target, the reviewed commit is origin/BRANCH's tip after a fetch and
      the working tree is not consulted (target mode: attest any branch from
      wherever you sit).
  attest.py targets  [--reference REF] [--limit N] [--all] [--json]
      List branches awaiting review: fetched remote branches not merged into
      the integration branch (or REF), excluding the integration branch and
      tips that are already attestations, most recent first, ten by default.
  attest.py commit   --email EMAIL --level {cursory,standard,skeptical}
                     [--tradeoff T]... [--risk R]... [--summary TEXT]
                     [--model ID] [--reference REF] [--ack-no-transcript]
                     [--no-sign] [--dry-run] [--no-push] [--json]
      Attest exactly the state prepare recorded (refusing if HEAD, the tree,
      or the profile changed since), snapshot the transcript, require the
      approval marker, derive the status, write the empty attestation commit
      and the refs/notes/signoff mirror, self-check with the sibling
      verifier, and push the notes. In target mode (the record names a
      target) the commit object is built with commit-tree, self-checked,
      the notes are pushed, and only then is the object pushed to
      origin/BRANCH under a lease on the reviewed SHA; no local ref moves.
  attest.py marker   [--reference REF]
      Reprint the recorded approval marker. Read-only: no record, or a
      record that no longer matches HEAD, is exit 3 — only `prepare` starts
      a new review.
  attest.py --version

Exit codes:

  0  success (a refused notes push is reported, not fatal: the attestation
     commit and local notes stand; the recovery workflow rebuilds notes)
  2  usage or argument error, including a line break or a `Signoff-` line in
     free text, or a missing sibling verify_signoff.py
  3  stale or dirty: no preparation record (prepare has not run), HEAD or its
     tree moved since prepare, the interview profile changed since prepare,
     unstaged / staged changes, HEAD is already an attestation commit
     (nothing new to attest), or — target mode — origin/BRANCH moved since
     prepare or the lease push was rejected (the notes published just before
     it stand: they describe the reviewed commit and tree truthfully)
  4  transcript problem: unresolvable without --ack-no-transcript, or the
     approval marker for this reviewed commit is not in the resolved transcript
  5  profile problem: GIT_SIGNOFF_PROFILE_FILE is set but unreadable (a
     malformed repo-local profile is not an error: it falls back, reported)
  6  git failure (rev-parse, commit, notes append)
  7  self-check failure: the verifier rejects the produced attestation; the
     empty commit and the notes just written are removed before exit. If a
     rollback step itself fails, the message says ROLLBACK INCOMPLETE and
     names the step, so the exit never describes a state that is not true.

Environment:

  GIT_SIGNOFF_TRANSCRIPT_FILE  explicit transcript path (generic-file adapter;
                               takes precedence over every harness adapter)
  ANTIGRAVITY_CONVERSATION_ID, CLAUDE_CODE_SESSION_ID, CODEX_SESSION_ID
                               harness adapters, in that resolution order
  CODEX_HOME                   Codex sessions root (default ~/.codex)
  GIT_SIGNOFF_PROFILE_FILE     interview profile override (unreadable → exit 5)
  CLAUDE_CODE_VERSION, CLAUDE_EFFORT, ANTHROPIC_MODEL
                               Signoff-Agent provenance (Claude Code only for
                               version and reasoning)

Repository config (.git-signoff/config.json, committed, written by init.py):

  {"integration_branch": "dev"}   the branch pull requests merge into. Read as
  the fallback reference (below) and to recognise when HEAD *is* that branch.

Reference precedence (the base the range is diffed against), in order:
  --reference; HEAD's upstream when it is a strict ancestor of HEAD (your own
  unpushed commits, also the direct-push case on the integration branch);
  the configured integration branch (origin/<name>, then <name>);
  origin/HEAD's branch; main, then master. On the integration branch itself
  with nothing unpushed there is no range to attest (exit 2); with an upstream
  that has diverged from HEAD the state must be reconciled first (exit 3).

Preparation record:

  `prepare` writes .git/git-signoff/prepared.json (per worktree): reviewed,
  base and tree SHAs, reference, timestamp, and the resolved profile. `commit`
  attests that record and nothing else: it re-verifies HEAD, the tree, and the
  profile against it and refuses (exit 3) on any drift, whether or not a
  transcript is available. Without it, `--ack-no-transcript` would let a
  commit made after the interview be attested as if it had been reviewed. A
  successful commit removes the record. Only `prepare` writes it: `marker`
  and `commit` never re-prepare on a stale record, so a refusal cannot be
  cleared by any command other than the one that begins a new review.

Learning inspection (init-v10):

  `prepare --explain` and `prepare --practice` capture current tracked working
  files, or a fetched target commit, without writing a preparation record,
  approval marker, index, commit, or notes. Dirty integration branches and
  local-only repositories fall back to HEAD as the base for uncommitted work.
  JSON includes the captured diff, state_kind, mode, and snapshot_id. Repeat
  with --check-snapshot to detect drift (exit 3); an empty diff is explicit.
  For working files, context_head_sha is context and reviewed_commit_sha /
  tree_sha are null. Untracked files are excluded and reported.

  Inspection does not start practice. Before the first probe, practice-start
  writes <git-common-dir>/git-signoff/practice-sessions/<session-key>.json.
  Real prepare, marker, and commit/dry-run refuse a recorded session (exit 3),
  even with an opaque/missing transcript or --ack-no-transcript. Linked
  worktrees share the record. Write failures stop practice (exit 6); unreadable
  guard state stops signoff (exit 3); even a partial record stays blocking.
  The key uses the conversation id, or a generic transcript's canonical path.
  Without either, separation relies on the skill's fresh-conversation rule.

  As backup, practice-start returns a session-bound GSA-PRACTICE line for the
  agent to emit as a dedicated assistant message. Commit checks the full final
  transcript for that event, including retries; quotations/tool results do not
  count. Records are local to the repository, not copied by clone/push, and
  cannot prevent deliberate deletion or identity changes. Explanation never
  starts practice and can precede a fresh real interview on request.

Approval marker (gsa-core §2.3, SHOULD for producers):

  GSA-APPROVAL <reviewed-commit-sha> <utc-timestamp-of-prepare>

`prepare` prints it; after the human explicitly approves the trade-offs,
risks, and email, the agent emits that line verbatim as its own paragraph,
then runs `commit`. `commit` requires the marker to appear in the last 64 KiB
of the transcript snapshot it hashes, and the last marker's SHA must equal
HEAD. A stale session file from another conversation cannot name this
reviewed commit, so a resolution error fails closed (exit 4) instead of
producing a well-formed digest of the wrong file. Note that the marker
printed by `prepare` is itself recorded in the transcript as tool output; the
check binds the file and the reviewed commit — the approval turn precedes
`commit` and is therefore inside the hashed bytes regardless.
"""

import sys

if sys.version_info < (3, 10):  # loud, before anything that only parses on newer Pythons
    sys.exit(
        "attest.py needs Python 3.10 or newer; this is Python %d.%d. "
        "Run it with a newer interpreter (python3.10+)." % sys.version_info[:2]
    )

import argparse  # noqa: E402
import glob  # noqa: E402
import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
from dataclasses import asdict, dataclass, field  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Mapping, Protocol  # noqa: E402

VERSION = "0.5.0"
SPEC_VERSION = "1.0"
NOTES_REF = "refs/notes/signoff"
NOTES_TRACKING_REF = "refs/notes/signoff-remote"
RECORD_RELPATH = os.path.join("git-signoff", "prepared.json")  # under the (per-worktree) git dir
CONFIG_RELPATH = os.path.join(".git-signoff", "config.json")  # committed, repository-level settings
BRANCH_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
TARGET_REMOTE = "origin"
TARGETS_DEFAULT_LIMIT = 10
RECORD_VERSION = 1
STATUS_VERIFIED = "VERIFIED_BY_HUMAN"
STATUS_NO_DIGEST = "VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST"
UNAVAILABLE = "unavailable"
LEVELS = ("cursory", "standard", "skeptical")
MODES = ("attest", "practice", "explain")
PRACTICE_RE = re.compile(r"GSA-PRACTICE ([0-9a-f]{24}) (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)")

MARKER_PREFIX = "GSA-APPROVAL"
MARKER_RE = re.compile(rb"GSA-APPROVAL ([0-9a-f]{40}) (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)")
MARKER_WINDOW = 64 * 1024
# Harnesses append the assistant's reply before executing its next tool call;
# one short retry covers a slow flush, after which a missing marker is real.
MARKER_RETRY_DELAY = 1.0

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_STALE = 3
EXIT_TRANSCRIPT = 4
EXIT_PROFILE = 5
EXIT_GIT = 6
EXIT_SELFCHECK = 7

TOKEN_RE = re.compile(r"^[A-Za-z0-9._:/-]+$")
ATTESTATION_SUBJECT_RE = re.compile(r"^\[SIGNOFF [0-9a-f]{7,40}\]: ")
TRAILER_LINE_RE = re.compile(r"^Signoff-[A-Za-z0-9-]+:")
TRAILER_RE = re.compile(r"^(Signoff-[A-Za-z0-9-]+):\s*(.*)$")


class AttestError(Exception):
    """Every failure the helper reports: an exit code and a message."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- git ---------------------------------------------------------------------


class GitRepo:
    """Thin subprocess wrapper; every command runs with cwd=self.path."""

    def __init__(self, path: str):
        self.path = path

    def git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        try:
            proc = subprocess.run(["git", *args], cwd=self.path, capture_output=True, text=True)
        except OSError as exc:
            raise AttestError(EXIT_GIT, f"git {' '.join(args)} could not run: {exc}") from exc
        if check and proc.returncode != 0:
            raise AttestError(EXIT_GIT, f"git {' '.join(args)} failed: {proc.stderr.strip()}")
        return proc

    def out(self, *args: str) -> str:
        return self.git(*args).stdout.strip()


def repo_root(cwd: str | None = None) -> str:
    """Repository root of the working directory (`git rev-parse --show-toplevel`)."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], cwd=cwd or os.getcwd(), capture_output=True, text=True
        )
    except OSError as exc:
        raise AttestError(EXIT_GIT, f"git could not run: {exc}") from exc
    if proc.returncode != 0 or not proc.stdout.strip():
        raise AttestError(EXIT_GIT, f"not inside a git repository: {proc.stderr.strip()}")
    return proc.stdout.strip()


# --- transcript adapters (gsa-core §3) ---------------------------------------


class TranscriptProvider(Protocol):
    """Minimal interface for transcript discovery across AI agent runtimes."""

    harness_id: str

    def resolve_conversation_id(self) -> str | None: ...

    def fetch_transcript_bytes(self) -> bytes | None: ...

    def describe_path(self) -> str | None: ...


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
    """Explicit transcript override via GIT_SIGNOFF_TRANSCRIPT_FILE (§3.2)."""

    harness_id = "generic-file"

    def __init__(self, path: str, conversation_id: str | None = None):
        self.path = path
        self.conversation_id = conversation_id

    def resolve_conversation_id(self) -> str | None:
        return self.conversation_id

    def describe_path(self) -> str | None:
        return os.path.expanduser(self.path)

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

    def describe_path(self) -> str | None:
        return os.path.join(
            self.home,
            ".gemini",
            "antigravity-cli",
            "brain",
            self.conversation_id,
            ".system_generated",
            "logs",
            "transcript.jsonl",
        )

    def fetch_transcript_bytes(self) -> bytes | None:
        return _read_bytes(self.describe_path())


class ClaudeCodeAdapter:
    """Claude Code harness (§3.2) with linked-worktree fallback.

    Session transcripts are keyed to the primary repository root slug. Inside a
    linked worktree (or a subdirectory of the main worktree) the cwd slug
    misses, so fall back to the primary root via `git rev-parse
    --git-common-dir`, anchored to the injected cwd rather than the process cwd.
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

    def describe_path(self) -> str | None:
        path = self._transcript_path(self.cwd)
        if os.path.exists(path):
            return path
        try:
            git_dir = subprocess.check_output(
                ["git", "rev-parse", "--git-common-dir"], text=True, stderr=subprocess.DEVNULL, cwd=self.cwd
            ).strip()
        except Exception:
            return path
        main_root = os.path.abspath(os.path.join(self.cwd, git_dir, os.pardir))
        return self._transcript_path(main_root)

    def fetch_transcript_bytes(self) -> bytes | None:
        return _read_bytes(self.describe_path())


class CodexAdapter:
    """ChatGPT Codex CLI harness: newest `$CODEX_HOME/sessions/**/rollout-*-<sid>.jsonl`."""

    harness_id = "codex-cli"

    def __init__(self, session_id: str, codex_home: str | None = None, home: str | None = None):
        self.session_id = session_id
        base = codex_home or os.path.join(home or os.path.expanduser("~"), ".codex")
        self.sessions_dir = os.path.join(base, "sessions")

    def resolve_conversation_id(self) -> str | None:
        return self.session_id

    def describe_path(self) -> str | None:
        escaped_sid = glob.escape(self.session_id)
        pattern = os.path.join(glob.escape(self.sessions_dir), "**", f"rollout-*-{escaped_sid}.jsonl")
        try:
            matches = glob.glob(pattern, recursive=True)
            if not matches:
                return None
            return max(matches, key=lambda p: (os.path.getmtime(p), p))
        except OSError:
            return None

    def fetch_transcript_bytes(self) -> bytes | None:
        return _read_bytes(self.describe_path())


def resolve_adapter(
    env: Mapping[str, str] | None = None,
    cwd: str | None = None,
    home: str | None = None,
) -> TranscriptProvider | None:
    """Resolve the active harness adapter, or None when no harness is detected.

    Resolution order: GIT_SIGNOFF_TRANSCRIPT_FILE → ANTIGRAVITY_CONVERSATION_ID →
    CLAUDE_CODE_SESSION_ID → CODEX_SESSION_ID (gsa-core §3.2; the matrix is
    informative and adapter-owned).
    """
    env = os.environ if env is None else env
    override = env.get("GIT_SIGNOFF_TRANSCRIPT_FILE", "").strip()
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


# --- interview profile (SKILL.md Section 1) ----------------------------------

PROFILE_ENV_VAR = "GIT_SIGNOFF_PROFILE_FILE"
REPO_PROFILE_RELPATH = os.path.join(".git-signoff", "profile.md")
EMBEDDED_PROFILE_ID = "software-general"

SOURCE_ENV_OVERRIDE = "env-override"
SOURCE_REPO_LOCAL = "repo-local"
SOURCE_EMBEDDED = "embedded-default"

_BEGIN_MARKER = b"INTERVIEW-PROFILE:BEGIN"
_END_MARKER = b"INTERVIEW-PROFILE:END"
_PROFILE_ID_RE = re.compile(rb"^Profile-ID:[ \t]*([a-z0-9-]+)[ \t]*$", re.MULTILINE)


@dataclass
class ProfileResolution:
    """``digest`` is the 12-hex prefix written as ``/sha256:<digest>`` in the
    ``interview=`` token; None exactly when the embedded default is active.
    ``fallback_reason`` is set when a file-sourced profile was malformed and
    therefore announced-and-ignored in favor of the embedded default."""

    source: str
    path: str | None
    profile_id: str
    digest: str | None
    fallback_reason: str | None = None


def profile_block_digest(data: bytes) -> str:
    """12-hex digest prefix of the delimited profile block.

    Byte-equivalent to the historical pipeline
    ``sed -n '/INTERVIEW-PROFILE:BEGIN/,/INTERVIEW-PROFILE:END/p' | sha256sum | cut -c1-12``,
    including sed's range semantics (the end pattern is not tested on the line
    that opened the range, and an unclosed range runs to EOF). Pinned by the
    digest-parity test so file-sourced profile digests never change meaning.
    """
    selected = []
    in_range = False
    for line in data.splitlines(keepends=True):
        if in_range:
            selected.append(line)
            if _END_MARKER in line:
                in_range = False
        elif _BEGIN_MARKER in line:
            selected.append(line)
            in_range = True
    return hashlib.sha256(b"".join(selected)).hexdigest()[:12]


def _validate_profile(data: bytes) -> tuple[str | None, str | None]:
    begins = data.count(_BEGIN_MARKER)
    ends = data.count(_END_MARKER)
    if begins != 1 or ends != 1:
        return None, (
            f"expected exactly one delimited INTERVIEW-PROFILE block, found {begins} BEGIN / {ends} END marker(s)"
        )
    start = data.index(_BEGIN_MARKER)
    end = data.index(_END_MARKER)
    if end < start:
        return None, "INTERVIEW-PROFILE:END marker precedes BEGIN marker"
    m = _PROFILE_ID_RE.search(data, start, end)
    if not m:
        return None, "missing or malformed Profile-ID line inside the profile block"
    return m.group(1).decode("ascii"), None


def _embedded(fallback_reason: str | None = None) -> ProfileResolution:
    return ProfileResolution(SOURCE_EMBEDDED, None, EMBEDDED_PROFILE_ID, None, fallback_reason)


def _resolve_file(path: str, source: str) -> ProfileResolution:
    with open(path, "rb") as f:
        data = f.read()
    profile_id, reason = _validate_profile(data)
    if profile_id is None:
        return _embedded(f"malformed profile at {path} ({reason}); using embedded default")
    return ProfileResolution(source, path, profile_id, profile_block_digest(data))


def resolve_profile(root: str, env: Mapping[str, str] | None = None) -> ProfileResolution:
    """GIT_SIGNOFF_PROFILE_FILE (unreadable → exit 5, never a fallback) →
    <root>/.git-signoff/profile.md → embedded default."""
    environ = os.environ if env is None else env
    override = (environ.get(PROFILE_ENV_VAR) or "").strip()
    if override:
        expanded = os.path.expanduser(override)
        if not (os.path.isfile(expanded) and os.access(expanded, os.R_OK)):
            raise AttestError(EXIT_PROFILE, f"{PROFILE_ENV_VAR} is set but unreadable: {override}. Aborting signoff.")
        return _resolve_file(expanded, SOURCE_ENV_OVERRIDE)
    repo_local = os.path.join(root, REPO_PROFILE_RELPATH)
    if os.path.isfile(repo_local) and os.access(repo_local, os.R_OK):
        return _resolve_file(repo_local, SOURCE_REPO_LOCAL)
    return _embedded()


# --- science guard and intensity hints (SKILL.md Section 2) -------------------

# Content signals match added (+) diff lines only; file signals also match diff
# headers, so renames and deletions of e.g. notebooks still count.
SCIENCE_SIGNAL_PATTERNS: dict[str, re.Pattern] = {
    "scientific-imports": re.compile(
        r"^\+\s*(?:import|from)\s+(?:numpy|scipy|jax|torch|astropy|pandas|xarray)\b", re.MULTILINE
    ),
    "notebooks": re.compile(r"^(?:diff --git|\+\+\+|---) .*\.ipynb\b", re.MULTILINE),
    "rng-seeding": re.compile(r"^\+.*(?:\bseed\s*=|\.seed\(|default_rng|random_state\s*=|manual_seed)", re.MULTILINE),
    "units-or-constants": re.compile(
        r"^\+.*(?:\bhPa\b|\bkPa\b|\bkg/kg\b|\bkg[ /]?m(?:\^?-?[23]|²|³)?\b|\bm\s?s\^?-2\b|\bW[ /]?m-?2\b"
        r"|9\.80665|6\.674\d*e-11|1\.380649e-23|6\.02214)",
        re.MULTILINE,
    ),
    "solvers-integrators": re.compile(
        r"^\+.*(?:solve_ivp|odeint|scipy\.integrate|np\.linalg|scipy\.linalg|trapezoid\(|cumulative_trapezoid"
        r"|runge.?kutta|newton_krylov)",
        re.MULTILINE | re.IGNORECASE,
    ),
    "datasets-model-config": re.compile(
        r"^(?:diff --git|\+\+\+|---|\+).*(?:\.nc4?\b|netcdf|\.grib2?\b|\.zarr\b|to_zarr|open_zarr)",
        re.MULTILINE | re.IGNORECASE,
    ),
}


def detect_science_signals(diff: str) -> list[str]:
    """Names of science-guard signal categories present in a range diff, sorted."""
    return sorted(name for name, pattern in SCIENCE_SIGNAL_PATTERNS.items() if pattern.search(diff))


DOC_SUFFIXES = {".md", ".markdown", ".rst", ".txt", ".adoc", ".cff", ".html", ".css", ".svg"}
DOC_BASENAMES = {"LICENSE", "NOTICE", "CHANGELOG", "AUTHORS", "CODEOWNERS"}
DOC_BASENAME_PREFIXES = ("LICENSE", "NOTICE", "COPYING")  # LICENSE-APACHE, NOTICE.txt, COPYING.LESSER, ...
LOCKFILE_RE = re.compile(r"(^|/)(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|poetry\.lock|Cargo\.lock|uv\.lock|Pipfile\.lock)$")
TEST_PATH_RE = re.compile(r"(^|/)(tests?|__tests__|spec)/|(^|/)test_[^/]*$|(_test|\.test|_spec|\.spec)\.[A-Za-z0-9]+$")

# Canonical High-Impact Tier 2 triggers (SKILL.md), by path and by content.
TIER2_PATH_TRIGGERS: tuple[tuple[str, re.Pattern], ...] = (
    ("security-auth", re.compile(r"(^|/)(auth|crypto|permissions)/", re.IGNORECASE)),
    ("schemas-migrations", re.compile(r"(^|/)migrations/|(^|/)schema\.sql$", re.IGNORECASE)),
    ("public-api-contracts", re.compile(r"\.proto$|(^|/)[^/]*(openapi|swagger)[^/]*\.(ya?ml|json)$", re.IGNORECASE)),
)
TIER2_CONTENT_TRIGGERS: tuple[tuple[str, re.Pattern], ...] = (
    ("schemas-migrations", re.compile(r"^\+.*\bALTER\s+TABLE\b", re.MULTILINE | re.IGNORECASE)),
)


def _is_doc_path(path: str) -> bool:
    name = os.path.basename(path)
    return (
        name in DOC_BASENAMES
        or name.startswith(DOC_BASENAME_PREFIXES)
        or os.path.splitext(name)[1].lower() in DOC_SUFFIXES
    )


def _is_test_path(path: str) -> bool:
    return bool(TEST_PATH_RE.search(path))


def intensity_hints(numstat: str, diff: str, science_signals: list[str]) -> dict:
    """Informative counts for the agent's intensity classification.

    The agent remains authoritative for classification; these numbers keep it
    from miscounting. `executable_lines_changed` excludes documentation,
    lockfiles, tests, and binary files (numstat `-`).
    """
    changed_files = 0
    executable_files = 0
    executable_lines = 0
    components: set[str] = set()
    tier2: dict[str, set[str]] = {}
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        added, deleted, path = parts
        # renames are reported as `old => new` or `{a => b}/c`; use the new name
        path = re.sub(r"\{[^{}]* => ([^{}]*)\}", r"\1", path)
        if " => " in path:
            path = path.split(" => ", 1)[1]
        changed_files += 1
        for name, pattern in TIER2_PATH_TRIGGERS:
            if pattern.search(path) and not _is_doc_path(path):
                tier2.setdefault(name, set()).add(path)
        if _is_doc_path(path) or _is_test_path(path) or LOCKFILE_RE.search(path):
            continue
        executable_files += 1
        # A component is a directory with executable changes (a root file is
        # its own component): the unit that fails, and reverts, on its own.
        components.add(os.path.dirname(path) or path)
        if added.isdigit() and deleted.isdigit():
            executable_lines += int(added) + int(deleted)
    for name, pattern in TIER2_CONTENT_TRIGGERS:
        if pattern.search(diff):
            tier2.setdefault(name, set()).add("<diff content>")
    if science_signals:
        tier2["scientific-computation"] = set(science_signals)
    if executable_files > 5 or executable_lines > 200:
        tier2["executable-blast-radius"] = {f"{executable_files} files / {executable_lines} lines"}
    return {
        "changed_files": changed_files,
        "executable_files": executable_files,
        "executable_lines_changed": executable_lines,
        "components": sorted(components),
        # Skeptical floor for expansive ranges (SKILL.md Section 2): eight
        # probes, plus two for every component beyond the second, so a range
        # that bundles several independently revertable changes is probed on
        # each of their failure modes rather than on a sample of them.
        "skeptical_min_probes": skeptical_min_probes(len(components)),
        "tier2_triggers": {name: sorted(paths) for name, paths in sorted(tier2.items())},
    }


def skeptical_min_probes(components: int) -> int:
    return max(8, 4 + 2 * components)


# --- prepare -----------------------------------------------------------------


@dataclass
class PrepareState:
    reviewed_commit_sha: str
    base_sha: str
    tree_sha: str
    reference: str
    name_status: list[str]
    shortstat: str
    numstat: str
    diff: str
    profile: ProfileResolution
    science_signals: list[str]
    harness_id: str
    conversation_id: str
    transcript_available: bool
    transcript_path: str | None
    hints: dict
    prepared_at: str
    warnings: list[str] = field(default_factory=list)
    record_path: str | None = None
    integration_branch: str | None = None
    target: str | None = None  # target mode: the branch whose origin tip is reviewed
    mode: str = "attest"
    snapshot_id: str | None = None
    practice_marker: str | None = None
    untracked_files: list[str] = field(default_factory=list)
    staged_differs: bool = False

    @property
    def marker(self) -> str:
        return f"{MARKER_PREFIX} {self.reviewed_commit_sha} {self.prepared_at}"

    def to_record(self) -> dict:
        p = self.profile
        return {
            "record_version": RECORD_VERSION,
            "attest_version": VERSION,
            "reviewed_commit_sha": self.reviewed_commit_sha,
            "base_sha": self.base_sha,
            "tree_sha": self.tree_sha,
            "reference": self.reference,
            "prepared_at": self.prepared_at,
            "profile": {"source": p.source, "path": p.path, "id": p.profile_id, "digest": p.digest},
            "science_signals": self.science_signals,
            "harness_id": self.harness_id,
            "conversation_id": self.conversation_id,
            "transcript_path": self.transcript_path,
            "integration_branch": self.integration_branch,
            "target": self.target,
        }

    @classmethod
    def from_record(cls, rec: dict, profile: ProfileResolution, path: str) -> "PrepareState":
        return cls(
            reviewed_commit_sha=rec["reviewed_commit_sha"],
            base_sha=rec["base_sha"],
            tree_sha=rec["tree_sha"],
            reference=rec["reference"],
            name_status=[],
            shortstat="",
            numstat="",
            diff="",
            profile=profile,
            science_signals=list(rec.get("science_signals", [])),
            harness_id=rec.get("harness_id", "unknown"),
            conversation_id=rec.get("conversation_id", UNAVAILABLE),
            transcript_available=False,
            transcript_path=rec.get("transcript_path"),
            hints={},
            prepared_at=rec["prepared_at"],
            record_path=path,
            integration_branch=rec.get("integration_branch"),
            target=rec.get("target"),
        )

    def to_json(self) -> dict:
        result = {
            "ok": True,
            "command": "prepare",
            "mode": self.mode,
            "reviewed_commit_sha": self.reviewed_commit_sha,
            "short_sha": self.reviewed_commit_sha[:7],
            "base_sha": self.base_sha,
            "tree_sha": self.tree_sha,
            "reference": self.reference,
            "diff_command": f"git diff {self.base_sha}..{self.reviewed_commit_sha}",
            "name_status": self.name_status,
            "shortstat": self.shortstat,
            "profile": {
                "source": self.profile.source,
                "path": self.profile.path,
                "id": self.profile.profile_id,
                "digest": self.profile.digest,
                "fallback_reason": self.profile.fallback_reason,
            },
            "science_signals": self.science_signals,
            "transcript": {
                "harness_id": self.harness_id,
                "conversation_id": self.conversation_id,
                "available": self.transcript_available,
                "path": self.transcript_path,
            },
            "hints": self.hints,
            "marker": self.marker,
            "record": self.record_path,
            "integration_branch": self.integration_branch,
            "target": self.target,
            "target_ref": f"refs/remotes/{TARGET_REMOTE}/{self.target}" if self.target else None,
            "warnings": self.warnings,
        }
        if self.mode != "attest":
            result.pop("marker")
            result.pop("record")
            result.update(
                state_kind="commit" if self.target else "working-tree",
                context_head_sha=self.reviewed_commit_sha,
                snapshot_id=self.snapshot_id,
                diff=self.diff,
                numstat=self.numstat,
                untracked_files=self.untracked_files,
                staged_differs=self.staged_differs,
                empty=not self.diff,
            )
            if not self.target:
                result.update(reviewed_commit_sha=None, short_sha=None, tree_sha=None,
                              diff_command=f"git diff {self.base_sha}")
            if self.mode == "practice":
                result["practice_marker"] = self.practice_marker
        return result


def read_config(root: str) -> dict:
    """`.git-signoff/config.json`, or {} when absent. Malformed is a usage error:
    a setting that silently fell back would point the interview at the wrong base."""
    path = os.path.join(root, CONFIG_RELPATH)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        raise AttestError(EXIT_USAGE, f"unreadable {CONFIG_RELPATH} ({exc}); fix or remove it.") from exc
    if not isinstance(data, dict):
        raise AttestError(EXIT_USAGE, f"{CONFIG_RELPATH} must be a JSON object.")
    branch = data.get("integration_branch")
    if branch is not None and (not isinstance(branch, str) or not BRANCH_NAME_RE.match(branch)):
        raise AttestError(EXIT_USAGE, f"{CONFIG_RELPATH}: integration_branch must be a branch name, got {branch!r}.")
    return data


def integration_branch(repo: GitRepo, config: Mapping[str, object]) -> tuple[str | None, str]:
    """(name, source): the configured integration branch, else the remote's
    default branch (origin/HEAD), else None."""
    name = config.get("integration_branch")
    if isinstance(name, str) and name:
        return name, CONFIG_RELPATH
    proc = repo.git("symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD", check=False)
    head = proc.stdout.strip()
    if proc.returncode == 0 and "/" in head:
        return head.split("/", 1)[1], "origin/HEAD"
    return None, "none"


def current_branch(repo: GitRepo) -> str | None:
    proc = repo.git("symbolic-ref", "-q", "--short", "HEAD", check=False)
    return proc.stdout.strip() or None if proc.returncode == 0 else None


def normalize_target(name: str) -> str:
    """`feature`, `origin/feature`, `refs/heads/feature`, `refs/remotes/origin/feature`
    all name the remote branch `feature` (docs/attest-any-target.md §2.9)."""
    for prefix in (f"refs/remotes/{TARGET_REMOTE}/", "refs/heads/", f"{TARGET_REMOTE}/"):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    if not BRANCH_NAME_RE.match(name):
        raise AttestError(EXIT_USAGE, f"--target {name!r} is not a branch name")
    return name


def fetch_target(repo: GitRepo, target: str) -> str:
    """Fetch origin/<target> and return its tip. The PR check reads the remote,
    so the remote is what is reviewed; a branch that exists only locally is an
    error, not a fallback."""
    fetch = repo.git("fetch", "-q", TARGET_REMOTE, f"+refs/heads/{target}:refs/remotes/{TARGET_REMOTE}/{target}", check=False)
    if fetch.returncode != 0:
        err = fetch.stderr.strip().splitlines()
        detail = err[-1] if err else f"exit {fetch.returncode}"
        if "couldn't find remote ref" in fetch.stderr or "Could not find" in fetch.stderr:
            raise AttestError(EXIT_USAGE, f"--target {target!r} does not exist on {TARGET_REMOTE} ({detail}); push it first.")
        raise AttestError(EXIT_GIT, f"could not fetch {TARGET_REMOTE}/{target}: {detail}")
    return repo.out("rev-parse", f"refs/remotes/{TARGET_REMOTE}/{target}^{{commit}}")


def _is_attestation_commit(repo: GitRepo, sha: str) -> bool:
    subject = repo.git("log", "-1", "--format=%s", sha, check=False).stdout.strip()
    return bool(ATTESTATION_SUBJECT_RE.match(subject))


def _range_is_empty(repo: GitRepo, reference: str, reviewed: str) -> bool:
    """True when `reference` already contains `reviewed`: there is nothing to review."""
    return repo.git("merge-base", "--is-ancestor", reviewed, reference, check=False).returncode == 0


def _resolve_reference(
    repo: GitRepo,
    reference: str | None,
    reviewed: str,
    warnings: list[str],
    integration: str | None = None,
    integration_source: str = "none",
    branch_name: str | None = None,
    skip_upstream: bool = False,
    learning: bool = False,
) -> str:
    if reference:
        if repo.git("rev-parse", "--verify", "-q", f"{reference}^{{commit}}", check=False).returncode != 0:
            raise AttestError(EXIT_USAGE, f"--reference {reference!r} does not resolve to a commit")
        if not learning and _range_is_empty(repo, reference, reviewed):
            warnings.append(
                f"--reference {reference!r} already contains HEAD: the range to review is empty "
                "(nothing between the base and the reviewed commit)."
            )
        return reference

    branch = branch_name if branch_name is not None else current_branch(repo)
    on_integration = bool(integration) and branch == integration
    upstream = ""
    if not skip_upstream:
        proc = repo.git("rev-parse", "--abbrev-ref", "HEAD@{upstream}", check=False)
        upstream = proc.stdout.strip() if proc.returncode == 0 else ""
    # After `git push -u origin <feature>` the upstream is the branch's own
    # remote counterpart: it contains HEAD, so the range would be empty.
    # Only an upstream that is *behind* HEAD (the base branch, or the not-yet-
    # pushed part of the integration branch) is usable.
    if upstream and not _range_is_empty(repo, upstream, reviewed):
        upstream_sha = repo.out("rev-parse", f"{upstream}^{{commit}}")
        if not learning and on_integration and repo.git("merge-base", "--is-ancestor", upstream_sha, reviewed, check=False).returncode != 0:
            raise AttestError(
                EXIT_STALE,
                f"'{branch}' ({reviewed[:7]}) and its upstream '{upstream}' ({upstream_sha[:7]}) have diverged; "
                "reconcile them (pull, rebase, or merge) before attesting anything on the integration branch.",
            )
        return upstream
    if upstream:
        warnings.append(
            f"Upstream '{upstream}' already contains HEAD (it is this branch's own remote counterpart, "
            "not a base); falling back."
        )
    if on_integration:
        if learning:
            warnings.append("No unpushed integration-branch range; using the current commit as the learning base.")
            return reviewed
        raise AttestError(
            EXIT_USAGE,
            f"HEAD is the integration branch '{integration}' with nothing unpushed: there is no range to attest "
            "here. Attest the branch under review instead (SKILL.md Section 1), or pass --reference for a "
            "different base.",
        )
    candidates: list[str] = []
    if integration:
        candidates += [f"origin/{integration}", integration]
    if branch not in ("main", "master"):
        candidates += ["main", "master", "origin/main", "origin/master"]
    for candidate in candidates:
        if candidate == branch or candidate == f"origin/{branch}":
            continue
        if repo.git("rev-parse", "--verify", "-q", f"{candidate}^{{commit}}", check=False).returncode == 0:
            if integration and candidate.endswith(integration):
                warnings.append(f"No usable upstream for HEAD; using the integration branch '{candidate}' ({integration_source}).")
            else:
                warnings.append(
                    f"No usable upstream for HEAD; assuming base branch '{candidate}'. "
                    "If this is incorrect, pass --reference explicitly."
                )
            return candidate
    if learning:
        warnings.append("No base reference found; using the current commit to inspect uncommitted work. Use --reference for an earlier base.")
        return reviewed
    raise AttestError(
        EXIT_USAGE,
        "No base reference: HEAD has no usable upstream and none of "
        + ", ".join(candidates or ["main", "master"])
        + " resolve; pass --reference <branch>.",
    )


def check_clean_tree(repo: GitRepo) -> None:
    """Unstaged or staged changes → exit 3: the interview must cover the committed state."""
    unstaged = repo.git("diff", "--quiet", check=False)
    if unstaged.returncode == 1:
        raise AttestError(EXIT_STALE, "Unstaged changes present; commit or stash them (the interview covers the committed state).")
    if unstaged.returncode != 0:
        raise AttestError(EXIT_GIT, f"git diff --quiet failed: {unstaged.stderr.strip()}")
    staged = repo.git("diff", "--cached", "--quiet", check=False)
    if staged.returncode == 1:
        raise AttestError(EXIT_STALE, "Staged changes present; commit or unstage them (the interview covers the committed state).")
    if staged.returncode != 0:
        raise AttestError(EXIT_GIT, f"git diff --cached --quiet failed: {staged.stderr.strip()}")


def prepare(
    root: str,
    reference: str | None = None,
    env: Mapping[str, str] | None = None,
    adapter: TranscriptProvider | None = None,
    target: str | None = None,
    mode: str = "attest",
    check_snapshot: str | None = None,
) -> PrepareState:
    if mode not in MODES:
        raise AttestError(EXIT_USAGE, f"unknown mode {mode!r}")
    if mode != "attest":
        return _prepare_learning(root, reference, env, adapter, target, mode, check_snapshot)
    if check_snapshot is not None:
        raise AttestError(EXIT_USAGE, "--check-snapshot requires --practice or --explain")
    repo = GitRepo(root)
    environ = os.environ if env is None else env
    if adapter is None:
        adapter = resolve_adapter(environ, cwd=root)
    _check_practice_record(repo, adapter)
    warnings: list[str] = []
    config = read_config(root)
    integration, integration_source = integration_branch(repo, config)

    if target is not None:
        # Target mode (docs/attest-any-target.md §2.1, §2.9): the reviewed
        # commit is origin/<target>'s tip after a fetch. The checkout supplies
        # only the repository-level inputs (config, profile); its working tree
        # is neither read nor required to be clean.
        target = normalize_target(target)
        if integration and target == integration:
            raise AttestError(
                EXIT_USAGE,
                f"--target {target!r} is the integration branch; it is never a target (§2.4). From the "
                "integration branch itself, attest your own unpushed commits with the bare command.",
            )
        reviewed = fetch_target(repo, target)
        if _is_attestation_commit(repo, reviewed):
            raise AttestError(
                EXIT_STALE,
                f"{TARGET_REMOTE}/{target} already ends in an attestation commit ({reviewed[:7]}); there is nothing "
                "new to attest. If the branch changed since, its author must push the new commits first.",
            )
        ref = _resolve_reference(
            repo, reference, reviewed, warnings, integration, integration_source, branch_name=target, skip_upstream=True
        )
        return _prepare_range(root, repo, environ, adapter, reviewed, ref, warnings, integration, target)

    head = repo.git("rev-parse", "--verify", "-q", "HEAD^{commit}", check=False)
    if head.returncode != 0 or not head.stdout.strip():
        raise AttestError(EXIT_GIT, "HEAD does not point at a commit (unborn branch?); nothing to attest.")
    reviewed = head.stdout.strip()
    subject = repo.git("log", "-1", "--format=%s", reviewed, check=False).stdout.strip()
    if ATTESTATION_SUBJECT_RE.match(subject):
        # Attesting an attestation is never meaningful, and this is exactly the
        # state a failed rollback leaves behind: a rejected attestation commit at
        # HEAD. Re-running from Section 1 here would attest *that* commit and the
        # verifier would pass it. Stop instead.
        parent = repo.git("rev-parse", f"{reviewed}~1", check=False).stdout.strip()
        raise AttestError(
            EXIT_STALE,
            f"HEAD {reviewed[:7]} is already an attestation commit ({subject[:40]}...) on top of {parent[:7]}; "
            "there is nothing new to attest. If it was left behind by a failed rollback, remove it with "
            "`git reset --soft HEAD~1` and re-run; if it is a valid attestation, the branch is done.",
        )
    check_clean_tree(repo)

    ref = _resolve_reference(repo, reference, reviewed, warnings, integration, integration_source)
    return _prepare_range(root, repo, environ, adapter, reviewed, ref, warnings, integration, None)


def _prepare_range(
    root: str,
    repo: GitRepo,
    environ: Mapping[str, str],
    adapter: TranscriptProvider | None,
    reviewed: str,
    ref: str,
    warnings: list[str],
    integration: str | None,
    target: str | None,
) -> PrepareState:
    base = repo.out("merge-base", ref, reviewed)
    tree = repo.out("rev-parse", f"{reviewed}^{{tree}}")
    rng = f"{base}..{reviewed}"
    diff = repo.git("diff", rng).stdout
    name_status = [line for line in repo.out("diff", "--name-status", rng).splitlines() if line]
    shortstat = repo.out("diff", "--shortstat", rng)
    numstat = repo.git("diff", "--numstat", rng).stdout

    profile = resolve_profile(root, environ)
    if profile.fallback_reason:
        warnings.append(profile.fallback_reason)
    signals = detect_science_signals(diff)

    if adapter is None:
        adapter = resolve_adapter(environ, cwd=root)
    harness_id = adapter.harness_id if adapter else "unknown"
    conversation_id = (adapter.resolve_conversation_id() if adapter else None) or UNAVAILABLE
    transcript_path = adapter.describe_path() if adapter else None
    # Informative only; the binding snapshot happens inside commit (§2.3).
    transcript_data = adapter.fetch_transcript_bytes() if adapter else None
    transcript_available = transcript_data is not None
    practice = find_practice_marker(transcript_data, adapter)
    if practice:
        warnings.append(_practice_refusal(practice, transcript_path))
    if adapter is None:
        warnings.append(
            "No transcript adapter detected (no GIT_SIGNOFF_TRANSCRIPT_FILE or harness session id); "
            "commit will need --ack-no-transcript after the human's explicit second confirmation."
        )
    elif not transcript_available:
        warnings.append(f"Transcript not readable at {transcript_path}; commit will need --ack-no-transcript.")

    state = PrepareState(
        reviewed_commit_sha=reviewed,
        base_sha=base,
        tree_sha=tree,
        reference=ref,
        name_status=name_status,
        shortstat=shortstat,
        numstat=numstat,
        diff=diff,
        profile=profile,
        science_signals=signals,
        harness_id=harness_id,
        conversation_id=conversation_id,
        transcript_available=transcript_available,
        transcript_path=transcript_path,
        hints=intensity_hints(numstat, diff, signals),
        prepared_at=_utc_now(),
        warnings=warnings,
        integration_branch=integration,
        target=target,
    )
    state.record_path = write_record(repo, state)
    return state


def _prepare_learning(root, reference, env, adapter, target, mode, check_snapshot):
    """Capture a learning diff without creating attestation state or changing the index.

    The returned patch is the inspected content, not a command to rerun later.
    A stateless fingerprint lets the agent detect drift before claiming coverage.
    """
    repo = GitRepo(root)
    environ = os.environ if env is None else env
    warnings = []
    integration, source = integration_branch(repo, read_config(root))
    if target is not None:
        target = normalize_target(target)
        reviewed = fetch_target(repo, target)
    else:
        head = repo.git("rev-parse", "--verify", "-q", "HEAD^{commit}", check=False)
        if head.returncode or not head.stdout.strip():
            raise AttestError(EXIT_GIT, "HEAD does not point at a commit; learning needs an initial commit as its base.")
        reviewed = head.stdout.strip()
    if _is_attestation_commit(repo, reviewed):
        warnings.append("The inspected tip is already an attestation; learning does not create another attestation.")
    ref = _resolve_reference(repo, reference, reviewed, warnings, integration, source,
                             branch_name=target, skip_upstream=target is not None, learning=True)
    base = repo.out("merge-base", ref, reviewed)
    endpoints = (base, reviewed) if target else (base,)
    diff_args = ("--no-optional-locks", "diff", "--no-ext-diff", "--no-textconv", "--no-color", "--find-renames")
    patch = repo.git(*diff_args, *endpoints, "--").stdout
    name_status = repo.git(*diff_args, "--name-status", *endpoints, "--").stdout.splitlines()
    shortstat = repo.out(*diff_args, "--shortstat", *endpoints, "--")
    numstat = repo.git(*diff_args, "--numstat", *endpoints, "--").stdout
    untracked, staged = [], ""
    if not target:
        untracked = [p for p in repo.git("--no-optional-locks", "ls-files", "--others", "--exclude-standard", "-z").stdout.split("\0") if p]
        staged = repo.git(*diff_args, "--cached", base, "--").stdout
        if staged != patch:
            warnings.append("Scope is current tracked working files, not the staged snapshot; the next git commit may contain different changes.")
        if untracked:
            warnings.append(f"{len(untracked)} untracked file(s) are excluded; use `git add -N -- <path>` yourself to include selected files, then inspect again.")
        if repo.out("rev-parse", "HEAD") != reviewed:
            raise AttestError(EXIT_STALE, "HEAD changed while capturing the learning diff; inspect again.")
    if repo.git(*diff_args, *endpoints, "--").stdout != patch:
        raise AttestError(EXIT_STALE, "Files changed while capturing the learning diff; inspect again.")
    profile = resolve_profile(root, environ)
    if profile.fallback_reason:
        warnings.append(profile.fallback_reason)
    signals = detect_science_signals(patch)
    if adapter is None:
        adapter = resolve_adapter(environ, cwd=root)
    transcript = adapter.fetch_transcript_bytes() if adapter else None
    path = adapter.describe_path() if adapter else None
    practice = find_practice_marker(transcript, adapter)
    if practice:
        warnings.append(_practice_refusal(practice, path))
    stamp = _utc_now()
    key = practice_session_key(adapter)
    if mode == "practice":
        warnings.append("Before the first practice probe, run `attest.py practice-start --json` to record this session locally. A fresh conversation is required before real signoff.")
        if not key:
            warnings.append("No session identity or transcript path is available; practice separation can only be enforced by the skill instructions.")
    if not patch:
        warnings.append("No differences in the selected learning scope. Choose --reference for an earlier base or include the intended files; do not start an empty interview.")
    fingerprint = hashlib.sha256(json.dumps({
        "base": base, "head": reviewed, "target": target, "diff": patch,
        "staged": staged, "untracked": untracked,
        "profile": [profile.source, profile.profile_id, profile.digest],
    }, sort_keys=True).encode("utf-8")).hexdigest()
    if check_snapshot is not None and check_snapshot != fingerprint:
        raise AttestError(EXIT_STALE, "Learning scope changed since inspection; capture a new snapshot and revisit affected topics or probes.")
    return PrepareState(
        reviewed_commit_sha=reviewed, base_sha=base, tree_sha=repo.out("rev-parse", f"{reviewed}^{{tree}}"),
        reference=ref, name_status=name_status, shortstat=shortstat, numstat=numstat, diff=patch,
        profile=profile, science_signals=signals, harness_id=adapter.harness_id if adapter else "unknown",
        conversation_id=(adapter.resolve_conversation_id() if adapter else None) or UNAVAILABLE,
        transcript_available=transcript is not None, transcript_path=path,
        hints=intensity_hints(numstat, patch, signals), prepared_at=stamp, warnings=warnings,
        integration_branch=integration, target=target, mode=mode, snapshot_id=fingerprint,
        practice_marker=f"GSA-PRACTICE {key} {stamp}" if mode == "practice" and key else None,
        untracked_files=untracked, staged_differs=not target and staged != patch,
    )


# --- targets: branches awaiting review (docs/attest-any-target.md §2.2, §3.8) -----


def list_targets(root: str, reference: str | None = None, limit: int | None = TARGETS_DEFAULT_LIMIT) -> dict:
    """Fetched remote branches not merged into the base, excluding the base
    itself and tips that are already attestations, most recent commit first.
    `limit=None` lists all. The base is REF, else the integration branch."""
    repo = GitRepo(root)
    config = read_config(root)
    integration, source = integration_branch(repo, config)
    fetch = repo.git("fetch", "-q", "--prune", TARGET_REMOTE, check=False)
    if fetch.returncode != 0:
        err = fetch.stderr.strip().splitlines()
        raise AttestError(EXIT_GIT, f"could not fetch {TARGET_REMOTE}: {err[-1] if err else f'exit {fetch.returncode}'}")
    base_name = reference or integration
    if not base_name:
        raise AttestError(
            EXIT_USAGE,
            "no base to list against: set integration_branch in .git-signoff/config.json (init.py does), "
            "or pass --reference <branch>.",
        )
    base = None
    for candidate in ([base_name] if reference else [f"{TARGET_REMOTE}/{base_name}", base_name]):
        if repo.git("rev-parse", "--verify", "-q", f"{candidate}^{{commit}}", check=False).returncode == 0:
            base = candidate
            break
    if base is None:
        raise AttestError(EXIT_USAGE, f"base {base_name!r} does not resolve to a commit")
    base_sha = repo.out("rev-parse", f"{base}^{{commit}}")
    listing = repo.git(
        "for-each-ref", "--sort=-committerdate",
        "--format=%(refname)%09%(objectname)%09%(committerdate:short)%09%(subject)",
        f"refs/remotes/{TARGET_REMOTE}/", check=False,
    ).stdout
    candidates = []
    skipped = {"integration": 0, "merged": 0, "attested": 0}
    for line in listing.splitlines():
        parts = line.split("\t", 3)
        if len(parts) != 4:
            continue
        refname, sha, date, subject = parts
        prefix = f"refs/remotes/{TARGET_REMOTE}/"
        name = refname[len(prefix):] if refname.startswith(prefix) else refname
        if name == "HEAD":  # the symbolic ref for the remote's default branch, not a branch
            continue
        if name == base_name or (integration and name == integration):
            skipped["integration"] += 1
            continue
        if repo.git("merge-base", "--is-ancestor", sha, base_sha, check=False).returncode == 0:
            skipped["merged"] += 1
            continue
        if ATTESTATION_SUBJECT_RE.match(subject):
            skipped["attested"] += 1
            continue
        ahead = repo.git("rev-list", "--count", f"{base_sha}..{sha}", check=False).stdout.strip() or "?"
        candidates.append({"branch": name, "sha": sha, "short_sha": sha[:7], "date": date, "ahead": int(ahead) if ahead.isdigit() else None, "subject": subject})
    total = len(candidates)
    shown = candidates if limit is None else candidates[:limit]
    return {
        "ok": True,
        "command": "targets",
        "base": base,
        "base_source": "reference" if reference else source,
        "integration_branch": integration,
        "candidates": shown,
        "total": total,
        "truncated": total > len(shown),
        "skipped": skipped,
    }


# --- preparation record: the reviewed state is an explicit input to commit ---------


def record_path(repo: GitRepo) -> str:
    git_dir = repo.out("rev-parse", "--git-dir")
    if not os.path.isabs(git_dir):
        git_dir = os.path.join(repo.path, git_dir)
    return os.path.join(git_dir, RECORD_RELPATH)


def write_record(repo: GitRepo, state: PrepareState) -> str:
    if state.mode != "attest":
        raise AttestError(EXIT_USAGE, "Learning modes cannot create an attestation preparation record.")
    path = record_path(repo)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(state.to_record(), fh, indent=2)
            fh.write("\n")
    except OSError as exc:
        raise AttestError(EXIT_GIT, f"could not write the preparation record at {path}: {exc}") from exc
    return path


def clear_record(repo: GitRepo) -> None:
    try:
        os.remove(record_path(repo))
    except (OSError, AttestError):
        pass


_RECORD_KEYS = ("reviewed_commit_sha", "base_sha", "tree_sha", "reference", "prepared_at", "profile")


def load_prepared(root: str, reference: str | None = None, env: Mapping[str, str] | None = None) -> PrepareState:
    """The state `commit` attests: what `prepare` recorded, re-verified against
    the repository now. Nothing about the reviewed range is re-derived here.
    The interview covered the recorded range, so the attestation must carry
    exactly it; any drift is a refusal (exit 3), with or without a transcript.
    (Before this record, `commit` re-ran `prepare` and took whatever HEAD was;
    with `--ack-no-transcript` nothing tied that HEAD to the one reviewed.)"""
    repo = GitRepo(root)
    environ = os.environ if env is None else env
    path = record_path(repo)
    try:
        with open(path, encoding="utf-8") as fh:
            rec = json.load(fh)
    except FileNotFoundError:
        raise AttestError(
            EXIT_STALE,
            f"no preparation record at {path}: run `attest.py prepare` first. commit attests only the range "
            "prepare resolved and the interview covered.",
        ) from None
    except (OSError, ValueError) as exc:
        raise AttestError(EXIT_STALE, f"unreadable preparation record at {path} ({exc}); re-run `attest.py prepare`.") from exc
    if not isinstance(rec, dict) or rec.get("record_version") != RECORD_VERSION or any(k not in rec for k in _RECORD_KEYS):
        raise AttestError(EXIT_STALE, f"preparation record at {path} is not one this attest.py wrote; re-run `attest.py prepare`.")

    reviewed = rec["reviewed_commit_sha"]
    target = rec.get("target")
    if target:
        # Target mode: the remote branch, not HEAD, must still be where the
        # interview left it; the reviewer's working tree is irrelevant.
        tip = fetch_target(repo, target)
        if tip != reviewed:
            raise AttestError(
                EXIT_STALE,
                f"stale: prepare reviewed {TARGET_REMOTE}/{target} at {reviewed} but it is now at {tip}. The interview "
                "covered the prepared range only; re-run `attest.py prepare --target` and cover the new state.",
            )
    else:
        head = repo.git("rev-parse", "--verify", "-q", "HEAD^{commit}", check=False).stdout.strip()
        if head != reviewed:
            raise AttestError(
                EXIT_STALE,
                f"stale: prepare was run for {reviewed} but HEAD is now {head or 'unborn'}. The interview covered the "
                "prepared range only; re-run `attest.py prepare` and cover the new state before attesting.",
            )
        check_clean_tree(repo)
    tree = repo.out("rev-parse", f"{reviewed}^{{tree}}")
    if tree != rec["tree_sha"]:
        raise AttestError(
            EXIT_STALE,
            f"stale: the tree of {reviewed[:7]} is {tree[:7]} but prepare recorded {rec['tree_sha'][:7]}; re-run `attest.py prepare`.",
        )
    if reference:
        want = repo.git("rev-parse", "--verify", "-q", f"{reference}^{{commit}}", check=False)
        if want.returncode != 0:
            raise AttestError(EXIT_USAGE, f"--reference {reference!r} does not resolve to a commit")
        have = repo.git("rev-parse", "--verify", "-q", f"{rec['reference']}^{{commit}}", check=False).stdout.strip()
        if want.stdout.strip() != have:
            raise AttestError(
                EXIT_USAGE,
                f"--reference {reference!r} ({want.stdout.strip()[:7]}) differs from the prepared reference "
                f"{rec['reference']!r} ({have[:7] or 'unresolvable'}); re-run `attest.py prepare --reference {reference}` "
                "so the interview and the attestation agree on the base.",
            )
    profile = resolve_profile(root, environ)
    recorded = rec["profile"] if isinstance(rec["profile"], dict) else {}
    if (profile.source, profile.profile_id, profile.digest) != (recorded.get("source"), recorded.get("id"), recorded.get("digest")):
        def _desc(source, pid, digest):
            return f"{pid} from {source}" + (f" sha256:{digest}" if digest else "")
        raise AttestError(
            EXIT_STALE,
            "stale: the interview profile changed since prepare (was "
            f"{_desc(recorded.get('source'), recorded.get('id'), recorded.get('digest'))}; now "
            f"{_desc(profile.source, profile.profile_id, profile.digest)}). Re-run `attest.py prepare` so the "
            "attestation records the questions actually asked.",
        )
    return PrepareState.from_record(rec, profile, path)


# --- message construction (gsa-core §2.1, §2.3) --------------------------------


def parse_trailers(message: str) -> dict[str, list[str]]:
    trailers: dict[str, list[str]] = {}
    for line in message.splitlines():
        m = TRAILER_RE.match(line)
        if m:
            trailers.setdefault(m.group(1), []).append(m.group(2).strip())
    return trailers


def reject_unsafe_text(name: str, value: str, *, multiline: bool = False) -> None:
    """Free text is interpolated into a line-oriented trailer format (§2.3).

    A line break inside a tradeoff, risk, agent string, or email would start a
    new line that the verifier reads as a trailer — a second
    Signoff-Reviewed-Tree-SHA smuggled that way anchors an unreviewed tree.
    The summary paragraph may span lines but none of them may look like a
    trailer. Carriage returns are refused everywhere.
    """
    if "\r" in value:
        raise AttestError(EXIT_USAGE, f"{name} must not contain carriage returns (line-oriented trailer format)")
    if not multiline and "\n" in value:
        raise AttestError(EXIT_USAGE, f"{name} must be a single line (line-oriented trailer format): {value!r}")
    if multiline:
        for line in value.splitlines():
            if TRAILER_LINE_RE.match(line.strip()):
                raise AttestError(EXIT_USAGE, f"{name} must not contain a line that reads as a Signoff- trailer: {line!r}")
    if not multiline and not value.strip():
        raise AttestError(EXIT_USAGE, f"{name} must not be empty")


def agent_provenance(
    env: Mapping[str, str], data: bytes | None, level: str, profile: ProfileResolution, model_override: str | None
) -> str:
    """Signoff-Agent value (§2.3 grammar). Version/reasoning are Claude Code
    env vars and are scoped to that harness; the model comes from
    ANTHROPIC_MODEL, else the last "model" field in the same snapshot bytes as
    the digest, else the agent's self-report (--model), else `unavailable`."""
    in_claude_code = bool(env.get("CLAUDE_CODE_SESSION_ID", "").strip())
    hver = env.get("CLAUDE_CODE_VERSION", "").strip() if in_claude_code else ""
    reasoning = env.get("CLAUDE_EFFORT", "").strip() if in_claude_code else ""
    model = env.get("ANTHROPIC_MODEL", "").strip()
    if not model and data:
        hits = re.findall(rb'"model"\s*:\s*"([^"]+)"', data)
        if hits:
            model = hits[-1].decode("utf-8", "replace")
    if not model and model_override:
        model = model_override
    hver, model, reasoning = [
        value if value and TOKEN_RE.match(value) else missing
        for value, missing in ((hver, "N/A"), (model, UNAVAILABLE), (reasoning, "N/A"))
    ]
    harness_id = _harness_id(env)
    interview = f"{level}/{profile.profile_id}"
    if profile.digest:
        interview += f"/sha256:{profile.digest}"
    return f"harness={harness_id}/{hver} model={model} reasoning={reasoning} interview={interview}"


def _harness_id(env: Mapping[str, str]) -> str:
    adapter = resolve_adapter(env)
    return adapter.harness_id if adapter else "unknown"


def build_message(
    state: PrepareState,
    status: str,
    timestamp: str,
    transcript_digest: str,
    transcript_bytes: str,
    tradeoffs: list[str],
    risks: list[str],
    user_email: str,
    agent: str,
    summary: str | None = None,
    harness_id: str | None = None,
    conversation_id: str | None = None,
) -> str:
    lines = [f"[SIGNOFF {state.reviewed_commit_sha[:7]}]: human comprehension and risk attestation", ""]
    if summary and summary.strip():
        lines += [summary.strip(), ""]
    lines += [
        f"Signoff-Spec-Version: {SPEC_VERSION}",
        f"Signoff-Status: {status}",
        f"Signoff-Timestamp: {timestamp}",
        f"Signoff-Base-SHA: {state.base_sha}",
        f"Signoff-Reviewed-Commit-SHA: {state.reviewed_commit_sha}",
        f"Signoff-Reviewed-Tree-SHA: {state.tree_sha}",
        f"Signoff-Harness-ID: {harness_id or state.harness_id}",
        f"Signoff-Conversation-ID: {conversation_id or state.conversation_id}",
        f"Signoff-Transcript-Digest: {transcript_digest}",
        f"Signoff-Transcript-Bytes: {transcript_bytes}",
    ]
    # Repeat rule (§2.3): one trailer per item; 'none' exactly once when empty.
    lines += [f"Signoff-Tradeoff: {t}" for t in tradeoffs] or ["Signoff-Tradeoff: none"]
    lines += [f"Signoff-Risk: {r}" for r in risks] or ["Signoff-Risk: none"]
    lines += [f"Signoff-Verified-By: {user_email}", f"Signoff-Agent: {agent}"]
    return "\n".join(lines)


# --- learning-session guard and approval marker (§2.3) -----------------------------


def practice_session_key(adapter: TranscriptProvider | None) -> str | None:
    """Bind practice state and its backup event to a session id or transcript path.

    This is an identity hint, not a secret or proof against transcript editing.
    Session ids keep the binding stable when using a different linked worktree.
    """
    if adapter is None:
        return None
    sid = adapter.resolve_conversation_id()
    path = adapter.describe_path()
    if sid and sid != UNAVAILABLE:
        identity = f"session:{sid}"
    elif path:
        identity = f"transcript:{os.path.realpath(os.path.expanduser(path))}"
    else:
        return None
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def practice_record_path(repo: GitRepo, adapter: TranscriptProvider | None) -> str | None:
    """A repository-local session guard shared by all its linked worktrees."""
    key = practice_session_key(adapter)
    if key is None:
        return None
    common = os.path.realpath(os.path.join(repo.path, repo.out("rev-parse", "--git-common-dir")))
    return os.path.join(common, "git-signoff", "practice-sessions", f"{key}.json")


def _check_practice_record(repo: GitRepo, adapter: TranscriptProvider | None) -> None:
    path = practice_record_path(repo, adapter)
    if path is None:
        return
    try:
        # Presence is enough: an empty/partial record must not clear the guard.
        # lstat also treats a broken symlink as present, without following it.
        os.lstat(path)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise AttestError(EXIT_STALE, f"Cannot check practice-session record at {path}: {exc}. Refusing signoff while session state is unknown.") from exc
    raise AttestError(
        EXIT_STALE,
        f"Practice started in this conversation (local session record: {path}). "
        "Start a new conversation and run a fresh real /git-signoff interview before attesting.",
    )


def start_practice(root: str, env: Mapping[str, str] | None = None,
                   adapter: TranscriptProvider | None = None) -> dict:
    """Record an actual practice start, separately from read-only inspection.

    Exclusive creation never overwrites an existing session record. Even a
    partial write remains blocking; a failed write must stop the practice run.
    There is deliberately no reset command or expiry within a conversation.
    """
    if adapter is None:
        adapter = resolve_adapter(os.environ if env is None else env, cwd=root)
    key = practice_session_key(adapter)
    path = practice_record_path(GitRepo(root), adapter)
    stamp = _utc_now()
    warnings = []
    created = False
    if path is None:
        warnings.append("No session identity or transcript path is available; no local practice record can be bound to this conversation. Separation relies on the skill instructions: start a fresh conversation before real signoff.")
    else:
        try:
            os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
            try:
                with open(path, "x", encoding="utf-8") as stream:
                    json.dump({"version": 1, "session_key": key, "started_at": stamp}, stream)
                    stream.write("\n")
                created = True
            except FileExistsError:
                pass  # Already blocking; retries never replace the first record.
        except OSError as exc:
            raise AttestError(EXIT_GIT, f"Could not record practice start at {path}: {exc}. Do not begin practice until this write succeeds.") from exc
    return {
        "ok": True, "command": "practice-start",
        "guard": "local-record" if path else "instruction-only",
        "practice_record": path, "created": created,
        "practice_marker": f"GSA-PRACTICE {key} {stamp}" if key else None,
        "warnings": warnings,
    }


def _assistant_text(record: dict) -> str | None:
    """Recognize message envelopes, never JSON quoted inside message/tool text.

    Native Claude and Codex envelopes and normalized {role, content} JSONL
    are supported. Antigravity/generic exports can use the normalized form.
    """
    if record.get("type") == "response_item":
        message = record.get("payload")
        if not isinstance(message, dict) or message.get("type") != "message":
            return None
    elif record.get("type") == "assistant":
        message = record.get("message")
    elif record.get("type") in (None, "message"):
        message = record
    else:
        return None
    if not isinstance(message, dict) or message.get("role") != "assistant":
        return None
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list) and content:
        # A control message must consist entirely of visible text, without a
        # tool call, tool result, image, or quoted attachment alongside it.
        if all(isinstance(part, dict) and part.get("type") in ("text", "output_text")
               and isinstance(part.get("text"), str) for part in content):
            return "".join(part["text"] for part in content)
    return None


def find_practice_marker(data: bytes | None, adapter: TranscriptProvider | None) -> tuple[str, int] | None:
    """Find a dedicated practice-start assistant message in this session.

    A raw substring search would treat reading this implementation or its
    fixtures as running practice. Parse only top-level JSONL message records,
    and require their entire text to be the session-bound control message.
    Opaque text exports and absent transcripts cannot supply this backup;
    the local practice record remains the primary guard.
    """
    key = practice_session_key(adapter)
    if not data or key is None:
        return None
    sid = adapter.resolve_conversation_id()
    offset = 0
    for line in data.splitlines(keepends=True):
        start, offset = offset, offset + len(line)
        try:
            record = json.loads(line)
        except (ValueError, UnicodeError):
            continue
        if not isinstance(record, dict):
            continue
        event_sid = record.get("sessionId", record.get("session_id"))
        if sid and event_sid is not None and event_sid != sid:
            continue
        text = _assistant_text(record)
        match = PRACTICE_RE.fullmatch(text.strip()) if text is not None else None
        if match and match[1] == key:
            return match[0], start
    return None


def _practice_refusal(practice: tuple[str, int], path: str | None) -> str:
    marker, offset = practice
    return (
        f"Practice started in this conversation ({marker}; event at byte {offset} of {path or 'transcript'}). "
        "Start a new conversation and run a fresh real /git-signoff interview before attesting."
    )


def _check_no_practice(data, adapter, path):
    practice = find_practice_marker(data, adapter)
    if practice:
        raise AttestError(EXIT_STALE, _practice_refusal(practice, path))


@dataclass
class MarkerCheck:
    found: bool
    sha: str | None = None
    timestamp: str | None = None
    window_bytes: int = 0


def find_marker(data: bytes) -> MarkerCheck:
    """Last GSA-APPROVAL marker in the final MARKER_WINDOW bytes of a snapshot."""
    window = data[-MARKER_WINDOW:]
    matches = list(MARKER_RE.finditer(window))
    if not matches:
        return MarkerCheck(False, window_bytes=len(window))
    last = matches[-1]
    return MarkerCheck(True, last.group(1).decode("ascii"), last.group(2).decode("ascii"), len(window))


def _marker_error(repo: GitRepo, reviewed: str, check: MarkerCheck, path: str | None, nbytes: int) -> AttestError:
    expected = f"{MARKER_PREFIX} {reviewed} <utc-timestamp>"
    where = f"transcript {path} ({nbytes} bytes; last {check.window_bytes} bytes searched)"
    if not check.found:
        return AttestError(
            EXIT_TRANSCRIPT,
            f"approval marker not found in {where}. Expected a line `{expected}`. "
            "Emit the marker line in the conversation (as its own paragraph, after the human's explicit "
            "approval), then re-run commit. If the resolved file is not this conversation's transcript, "
            "set GIT_SIGNOFF_TRANSCRIPT_FILE to the right file.",
        )
    ancestor = repo.git("merge-base", "--is-ancestor", check.sha, reviewed, check=False).returncode == 0
    if ancestor:
        return AttestError(
            EXIT_STALE,
            f"stale: the last approval marker in {where} names {check.sha}, but HEAD is now {reviewed} "
            "(the branch moved after prepare). Re-run prepare, re-confirm with the human, emit a new marker, "
            "then re-run commit.",
        )
    return AttestError(
        EXIT_TRANSCRIPT,
        f"the last approval marker in {where} names commit {check.sha}, but the reviewed commit (HEAD) is "
        f"{reviewed}. This transcript is not this conversation's approval of this commit; check "
        "GIT_SIGNOFF_TRANSCRIPT_FILE / the harness session id, then re-run prepare and commit.",
    )


# --- commit ------------------------------------------------------------------


@dataclass
class CommitOptions:
    email: str
    level: str
    tradeoffs: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    summary: str | None = None
    model: str | None = None
    reference: str | None = None
    ack_no_transcript: bool = False
    sign: bool = True
    dry_run: bool = False
    push: bool = True
    timestamp: str | None = None


@dataclass
class CommitResult:
    attestation_sha: str | None
    status: str
    transcript_digest: str
    transcript_bytes: str
    transcript_path: str | None
    marker_found: bool
    message: str
    signed: bool
    dry_run: bool
    noted_shas: list[str] = field(default_factory=list)
    notes_pushed: bool = False
    notes_push_reason: str | None = None
    notes_merged_remote: bool = False
    verifier: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    target: str | None = None
    branch_pushed: bool = False

    def to_json(self) -> dict:
        d = asdict(self)
        d.update({"ok": True, "command": "commit"})
        return d


def validate_commit_options(opts: CommitOptions) -> None:
    if not opts.email or "@" not in opts.email:
        raise AttestError(EXIT_USAGE, f"--email must be an address containing '@': {opts.email!r}")
    reject_unsafe_text("--email", opts.email)
    if opts.level not in LEVELS:
        raise AttestError(EXIT_USAGE, f"--level must be one of {', '.join(LEVELS)}: {opts.level!r}")
    for t in opts.tradeoffs:
        reject_unsafe_text("--tradeoff", t)
    for r in opts.risks:
        reject_unsafe_text("--risk", r)
    if opts.summary:
        reject_unsafe_text("--summary", opts.summary, multiline=True)
    if opts.model is not None and not TOKEN_RE.match(opts.model):
        raise AttestError(EXIT_USAGE, f"--model must match [A-Za-z0-9._:/-]+: {opts.model!r}")


def load_verifier():
    """Import the sibling verify_signoff.py (same folder, vendored together)."""
    here = Path(__file__).resolve().parent
    path = here / "verify_signoff.py"
    if not path.is_file():
        raise AttestError(
            EXIT_USAGE,
            f"verify_signoff.py not found next to attest.py ({path}); the skill folder must be copied whole.",
        )
    spec = importlib.util.spec_from_file_location("gsa_verifier", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _snapshot(adapter: TranscriptProvider | None) -> bytes | None:
    return adapter.fetch_transcript_bytes() if adapter else None


def _note_blob(repo: GitRepo, target: str) -> str | None:
    proc = repo.git("notes", f"--ref={NOTES_REF}", "list", target, check=False)
    return proc.stdout.strip() if proc.returncode == 0 and proc.stdout.strip() else None


def _restore_notes(repo: GitRepo, prior: dict[str, str | None]) -> list[str]:
    """Put each note back as it was before this run. Returns the steps that failed."""
    failures = []
    for target, blob in prior.items():
        if blob is None:
            proc = repo.git("notes", f"--ref={NOTES_REF}", "remove", "--ignore-missing", target, check=False)
            action = f"remove the note on {target[:7]}"
        else:
            proc = repo.git("notes", f"--ref={NOTES_REF}", "add", "-f", "-C", blob, target, check=False)
            action = f"restore the prior note on {target[:7]}"
        if proc.returncode != 0:
            failures.append(f"{action}: {proc.stderr.strip() or f'exit {proc.returncode}'}")
    return failures


def _rollback_commit(repo: GitRepo) -> list[str]:
    """Drop the attestation commit just written (soft: its tree equals its parent's).
    Returns the failure, if any, so the caller never claims a removal that did not happen."""
    proc = repo.git("reset", "-q", "--soft", "HEAD~1", check=False)
    if proc.returncode != 0:
        return [f"remove the attestation commit (git reset --soft HEAD~1): {proc.stderr.strip() or f'exit {proc.returncode}'}"]
    return []


def _rollback_error(code: int, message: str, failures: list[str]) -> AttestError:
    """The exit message must describe the repository as it *is*: when any
    rollback step failed, say so loudly instead of asserting a clean state."""
    if not failures:
        return AttestError(code, message)
    return AttestError(
        code,
        message
        + " ROLLBACK INCOMPLETE — the repository is NOT back in its pre-commit state: "
        + "; ".join(failures)
        + ". Inspect `git log -1` and `git notes --ref=signoff list` before doing anything else.",
    )


def push_notes(repo: GitRepo, remote: str = "origin") -> tuple[bool, bool, str | None]:
    """(pushed, merged_remote, reason). Fetch origin's notes into the tracking
    ref (tolerating a remote with no notes yet), merge with cat_sort_uniq, push.
    Refusals are reported, never raised: the attestation commit stands."""
    fetch = repo.git("fetch", remote, f"+{NOTES_REF}:{NOTES_TRACKING_REF}", check=False)
    merged = False
    if fetch.returncode == 0:
        merge = repo.git("notes", f"--ref={NOTES_REF}", "merge", "-s", "cat_sort_uniq", NOTES_TRACKING_REF, check=False)
        if merge.returncode != 0:
            err = merge.stderr.strip().splitlines()
            return False, False, f"notes merge failed: {err[-1] if err else 'unknown error'}"
        merged = True
    push = repo.git("push", remote, NOTES_REF, check=False)
    if push.returncode != 0:
        err = push.stderr.strip().splitlines()
        return False, merged, f"notes push refused: {err[-1] if err else 'unknown error'}"
    return True, merged, None


def _commit_target(root: str, repo: GitRepo, state: PrepareState, opts: CommitOptions, message: str, signed: bool, verifier, result: CommitResult) -> CommitResult:
    """Target mode (docs/attest-any-target.md §2.5), one order: build the
    commit object (nothing references it), self-check it, publish the notes,
    then lease-push the object to origin/<target>. Nothing before the push
    needs undoing; a rejected push leaves the branch untouched and the notes
    published, which is accepted and reported. No local ref moves (§2.11)."""
    target, reviewed, tree = state.target, state.reviewed_commit_sha, state.tree_sha
    if not opts.push:
        raise AttestError(EXIT_USAGE, "target mode attests by pushing to the target branch; --no-push is not available with a --target record.")
    tip = fetch_target(repo, target)
    if tip != reviewed:
        raise AttestError(EXIT_STALE, f"stale: {TARGET_REMOTE}/{target} moved to {tip[:7]} during commit (reviewed {reviewed[:7]}); re-run prepare.")

    # 1. the object
    args = ["commit-tree", tree, "-p", reviewed] + (["-S"] if signed else []) + ["-m", message]
    proc = repo.git(*args, check=False)
    if proc.returncode != 0:
        raise AttestError(EXIT_GIT, f"git commit-tree failed: {proc.stderr.strip()}")
    attestation_sha = proc.stdout.strip()
    if repo.out("rev-parse", f"{attestation_sha}^{{tree}}") != tree or repo.out("rev-parse", f"{attestation_sha}~1") != reviewed:
        raise AttestError(EXIT_SELFCHECK, "post-commit-tree integrity check failed: tree or parent differ; nothing referenced the object, nothing to undo.")

    # 2. self-check on the unreferenced object
    try:
        ok, lines = verifier.check_head(root, attestation_sha)
    except SystemExit as exc:
        ok, lines = False, [str(exc)]
    if not ok:
        raise AttestError(EXIT_SELFCHECK, "the verifier rejected the attestation object before anything was published: " + " ".join(lines))

    # 3. notes: on the reviewed commit and its tree, which already exist on the remote
    for sha in (reviewed, tree):
        proc = repo.git("notes", f"--ref={NOTES_REF}", "append", "-m", message, sha, check=False)
        if proc.returncode != 0:
            raise AttestError(EXIT_GIT, f"git notes append on {sha[:7]} failed: {proc.stderr.strip()}; nothing published.")
    result.noted_shas = [reviewed, tree]
    pushed, merged, reason = push_notes(repo)
    result.notes_pushed, result.notes_merged_remote, result.notes_push_reason = pushed, merged, reason
    if not pushed:
        result.warnings.append(
            f"notes push refused ({reason}): this attestation will survive a squash or rebase merge only through "
            "the recovery path (verify-v1.5 scans the merged pull request's head; recovery reconstructs the tree note)."
        )

    # 4. the branch, last, under a lease on the reviewed tip
    push = repo.git(
        "push", "-q", TARGET_REMOTE, f"{attestation_sha}:refs/heads/{target}",
        f"--force-with-lease=refs/heads/{target}:{reviewed}", check=False,
    )
    if push.returncode != 0:
        err = push.stderr.strip().splitlines()
        raise AttestError(
            EXIT_STALE,
            f"push to {TARGET_REMOTE}/{target} rejected ({err[-1] if err else f'exit {push.returncode}'}): the branch "
            f"moved after prepare or the lease on {reviewed[:7]} failed. The branch is untouched and the attestation "
            f"object {attestation_sha[:7]} is unreferenced. The notes on {reviewed[:7]} and tree {tree[:7]} "
            + ("were published" if pushed else "are local")
            + " and stand: they describe the reviewed state truthfully. Re-run prepare --target to review the new tip.",
        )
    repo.git("fetch", "-q", TARGET_REMOTE, f"+refs/heads/{target}:refs/remotes/{TARGET_REMOTE}/{target}", check=False)
    result.attestation_sha = attestation_sha
    result.branch_pushed = True
    result.verifier = lines
    clear_record(repo)
    return result


def commit(root: str, opts: CommitOptions, env: Mapping[str, str] | None = None, adapter=None, verifier=None) -> CommitResult:
    environ = os.environ if env is None else env
    validate_commit_options(opts)
    verifier = verifier or load_verifier()
    repo = GitRepo(root)

    if adapter is None:
        adapter = resolve_adapter(environ, cwd=root)
    _check_practice_record(repo, adapter)
    state = load_prepared(root, opts.reference, environ)
    reviewed, tree = state.reviewed_commit_sha, state.tree_sha
    harness_id = adapter.harness_id if adapter else "unknown"
    conversation_id = (adapter.resolve_conversation_id() if adapter else None) or UNAVAILABLE
    transcript_path = adapter.describe_path() if adapter else None

    # Snapshot timing (§2.3): read the bytes once, immediately before the
    # commit; every later check — marker, digest, provenance — uses this snapshot.
    data = _snapshot(adapter)
    marker_found = False
    marker_warning = None
    if data is not None:
        _check_no_practice(data, adapter, transcript_path)
        check = find_marker(data)
        if not (check.found and check.sha == reviewed) and not opts.dry_run:
            time.sleep(MARKER_RETRY_DELAY)
            data = _snapshot(adapter) or data
            check = find_marker(data)
            # The retry may have flushed a practice-start event as well as the
            # approval marker. Check the exact final bytes used for the digest.
            _check_no_practice(data, adapter, transcript_path)
        marker_found = bool(check.found and check.sha == reviewed)
        if not marker_found:
            if not opts.dry_run:
                raise _marker_error(repo, reviewed, check, transcript_path, len(data))
            # The dry run presents trailers *before* approval, so the marker
            # cannot be there yet; the real commit re-snapshots and requires it.
            marker_warning = (
                "dry run: approval marker not yet in the transcript (expected before approval); "
                "digest and byte count are provisional and are recomputed at commit"
            )
        status = STATUS_VERIFIED
        digest = f"sha256:{hashlib.sha256(data).hexdigest()}"
        nbytes = str(len(data))
    elif opts.ack_no_transcript:
        status = STATUS_NO_DIGEST
        digest = UNAVAILABLE
        nbytes = UNAVAILABLE
    else:
        where = f" at {transcript_path}" if transcript_path else ""
        raise AttestError(
            EXIT_TRANSCRIPT,
            f"transcript unavailable{where} (harness {harness_id}). Re-run with --ack-no-transcript only after the "
            "human's explicit second confirmation of the downgraded status VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST.",
        )

    agent = agent_provenance(environ, data, opts.level, state.profile, opts.model)
    message = build_message(
        state,
        status,
        opts.timestamp or _utc_now(),
        digest,
        nbytes,
        opts.tradeoffs,
        opts.risks,
        opts.email,
        agent,
        opts.summary,
        harness_id=harness_id,
        conversation_id=conversation_id,
    )

    # Pre-commit structural self-check: a problem here is a bug in this helper.
    problems = verifier.validate_single(verifier.parse_trailers(message))
    if problems:
        raise AttestError(
            EXIT_SELFCHECK,
            "the helper produced a message the verifier rejects before committing — this is a bug in attest.py, "
            "not in your input: " + "; ".join(problems),
        )

    signed = bool(opts.sign and repo.git("config", "user.signingkey", check=False).stdout.strip())
    result = CommitResult(
        attestation_sha=None,
        status=status,
        transcript_digest=digest,
        transcript_bytes=nbytes,
        transcript_path=transcript_path,
        marker_found=marker_found,
        message=message,
        signed=signed,
        dry_run=opts.dry_run,
        warnings=list(state.warnings) + ([marker_warning] if marker_warning else []),
    )
    result.target = state.target
    # Recheck after snapshotting/retries, including for dry-run and target mode.
    _check_practice_record(repo, adapter)
    if opts.dry_run:
        return result
    if state.target:
        return _commit_target(root, repo, state, opts, message, signed, verifier, result)

    # Re-check immediately before writing: HEAD recomputed, tree clean.
    if repo.out("rev-parse", "HEAD") != reviewed:
        raise AttestError(EXIT_STALE, f"HEAD moved during commit (expected {reviewed[:7]}); signoff stale.")
    check_clean_tree(repo)

    prior_notes = {reviewed: _note_blob(repo, reviewed), tree: _note_blob(repo, tree)}
    commit_args = ["commit", "--allow-empty", "-q"] + (["-S"] if signed else []) + ["-m", message]
    repo.git(*commit_args)
    attestation_sha = repo.out("rev-parse", "HEAD")

    if repo.out("rev-parse", "HEAD^{tree}") != tree or repo.out("rev-parse", "HEAD~1") != reviewed:
        failures = _rollback_commit(repo)
        raise _rollback_error(
            EXIT_SELFCHECK,
            "post-commit integrity check failed: tree or parent changed; "
            + ("commit removed." if not failures else "commit removal attempted."),
            failures,
        )

    # Dual persistence (§2.5): note on both the reviewed commit and its tree.
    for sha in (reviewed, tree):
        proc = repo.git("notes", f"--ref={NOTES_REF}", "append", "-m", message, sha, check=False)
        if proc.returncode != 0:
            failures = _restore_notes(repo, prior_notes) + _rollback_commit(repo)
            raise _rollback_error(
                EXIT_GIT,
                f"git notes append on {sha[:7]} failed: {proc.stderr.strip()}; "
                + ("commit removed and notes restored." if not failures else "rollback attempted."),
                failures,
            )

    # Post-commit self-check with the sibling verifier, on our own output.
    try:
        ok, lines = verifier.check_head(root, "HEAD")
    except SystemExit as exc:  # the verifier's git() raises SystemExit on git errors
        ok, lines = False, [str(exc)]
    if not ok:
        failures = _restore_notes(repo, prior_notes) + _rollback_commit(repo)
        raise _rollback_error(
            EXIT_SELFCHECK,
            "the verifier rejected the attestation just written; "
            + ("commit and notes removed: " if not failures else "rollback attempted: ")
            + " ".join(lines),
            failures,
        )

    result.attestation_sha = attestation_sha
    result.noted_shas = [reviewed, tree]
    result.verifier = lines
    if opts.push:
        pushed, merged, reason = push_notes(repo)
        result.notes_pushed = pushed
        result.notes_merged_remote = merged
        result.notes_push_reason = reason
    else:
        result.notes_push_reason = "skipped (--no-push)"
    clear_record(repo)  # the prepared state has been attested; the next interview starts from prepare
    return result


# --- CLI ---------------------------------------------------------------------


def _print_prepare(state: PrepareState) -> None:
    if state.mode != "attest":
        _print_learning(state)
        return
    p = state.profile
    print(f"reviewed commit: {state.reviewed_commit_sha}")
    print(f"base (merge-base with {state.reference}): {state.base_sha}")
    if state.target:
        print(f"target: {TARGET_REMOTE}/{state.target} (target mode: the attestation will be pushed to that branch; your checkout is not touched)")
    if state.integration_branch:
        print(f"integration branch: {state.integration_branch}")
    print(f"tree: {state.tree_sha}")
    print(f"diff: git diff {state.base_sha}..{state.reviewed_commit_sha}")
    print(f"files ({len(state.name_status)}): {state.shortstat or 'no changes'}")
    for line in state.name_status:
        print(f"  {line}")
    prof = f"profile: {p.profile_id} ({p.source}"
    if p.path:
        prof += f", {p.path}"
    if p.digest:
        prof += f", sha256:{p.digest}"
    print(prof + ")")
    print(f"science signals: {', '.join(state.science_signals) or 'none'}")
    print(
        f"transcript: harness={state.harness_id} conversation={state.conversation_id} "
        f"available={'yes' if state.transcript_available else 'no'}"
        + (f" path={state.transcript_path}" if state.transcript_path else "")
    )
    h = state.hints
    triggers = ", ".join(f"{k} [{', '.join(v)}]" for k, v in h["tier2_triggers"].items()) or "none"
    print(
        f"intensity hints (informative): changed_files={h['changed_files']} executable_files={h['executable_files']} "
        f"executable_lines_changed={h['executable_lines_changed']} tier2_triggers={triggers}"
    )
    print(
        f"components with executable changes ({len(h['components'])}): {', '.join(h['components']) or 'none'}; "
        f"skeptical minimum probes: {h['skeptical_min_probes']}"
    )
    if state.record_path:
        print(f"prepared state recorded: {state.record_path} (commit attests exactly this; drift is refused)")
    print("approval marker — after the human's explicit approval, emit this line verbatim as its own paragraph:")
    print(state.marker)
    for w in state.warnings:
        print(f"warning: {w}", file=sys.stderr)


def _print_learning(state: PrepareState) -> None:
    data = state.to_json()
    identity = "target commit" if state.target else "context HEAD"
    print(f"{state.mode}: {data['state_kind']} ({identity} {state.reviewed_commit_sha[:12]})")
    print(f"base: {state.base_sha} ({state.reference})")
    print(f"snapshot: {state.snapshot_id}")
    print(f"profile: {state.profile.profile_id} ({state.profile.source})")
    print(f"files: {state.shortstat or 'no differences in this scope'}")
    print(f"science signals: {', '.join(state.science_signals) or 'none'}")
    print("No attestation record, approval marker, commit, or notes were written.")
    print("Captured diff (use --json redirected to a scratch file for large diffs):")
    print(state.diff, end="" if state.diff.endswith("\n") else "\n")
    if state.mode == "practice":
        print("Before the first practice probe, run `attest.py practice-start --json`, then emit its practice_marker as a separate assistant message containing only that line.")
    for warning in state.warnings:
        print(f"warning: {warning}", file=sys.stderr)


def _print_targets(listing: dict) -> None:
    base = listing["base"]
    if not listing["candidates"]:
        sk = listing["skipped"]
        print(
            f"no branches awaiting review against {base}: every fetched remote branch is merged ({sk['merged']}), "
            f"already ends in an attestation ({sk['attested']}), or is the base itself. Name a branch explicitly "
            "with `prepare --target <branch>` if one is missing here."
        )
        return
    print(f"branches awaiting review against {base} (most recent first):")
    for c in listing["candidates"]:
        ahead = f"{c['ahead']} ahead" if c["ahead"] is not None else "? ahead"
        print(f"  {c['branch']}  {c['short_sha']}  {c['date']}  {ahead}  {c['subject'][:60]}")
    if listing["truncated"]:
        print(f"  … {listing['total'] - len(listing['candidates'])} more; `targets --all` lists every candidate")
    print("next: `attest.py prepare --target <branch>`")


def _print_commit(result: CommitResult) -> None:
    if result.dry_run:
        print(result.message)
        print()
        print("dry run: nothing committed. Proposed trailers above.")
    else:
        print(f"attestation commit: {result.attestation_sha}")
        if result.target:
            print(f"pushed to: {TARGET_REMOTE}/{result.target} (lease on the reviewed tip held; no local ref moved)")
    print(f"status: {result.status}")
    print(f"transcript digest: {result.transcript_digest} ({result.transcript_bytes} bytes)")
    if result.transcript_path:
        print(f"transcript: {result.transcript_path}")
    if result.transcript_digest == UNAVAILABLE:
        marker = "not applicable (no transcript)"
    elif result.marker_found:
        marker = "found"
    else:
        marker = "not yet in the transcript (dry run; required at commit)"
    print(f"approval marker: {marker}")
    print(f"signed: {'yes' if result.signed else 'no'}")
    if not result.dry_run:
        print(f"notes: {NOTES_REF} on {result.noted_shas[0][:7]} (commit) and {result.noted_shas[1][:7]} (tree)")
        pushed = "yes" if result.notes_pushed else f"no ({result.notes_push_reason})"
        print(f"notes pushed: {pushed}")
        for line in result.verifier:
            print(f"verifier: {line}")
    for w in result.warnings:
        print(f"warning: {w}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="attest.py", description="GSA producer mechanics for /git-signoff.")
    p.add_argument("--version", action="version", version=f"attest.py {VERSION} (GSA {SPEC_VERSION})")
    sub = p.add_subparsers(dest="command", required=True)

    prep = sub.add_parser("prepare", help="resolve SHAs, diff summary, profile, signals, hints, marker")
    prep.add_argument("--target", help="attest origin/BRANCH's tip instead of HEAD (target mode; the checkout is not consulted)")
    prep.add_argument("--reference", help="base branch or commit (default: upstream, config integration_branch, origin/HEAD, main/master)")
    prep.add_argument("--json", action="store_true", help="print one JSON object on stdout")
    learning = prep.add_mutually_exclusive_group()
    learning.add_argument("--practice", action="store_true", help="inspect a learning diff for rehearsal; never write attestation state")
    learning.add_argument("--explain", action="store_true", help="inspect a learning diff for a walkthrough; never write attestation state")
    prep.add_argument("--check-snapshot", metavar="SHA256", help="learning only: refuse if the inspected scope differs from this fingerprint")

    practice = sub.add_parser("practice-start", help="record an actual practice start locally; blocks this session from real signoff")
    practice.add_argument("--json", action="store_true", help="print one JSON object on stdout")

    tg = sub.add_parser("targets", help="list remote branches awaiting review, most recent first")
    tg.add_argument("--reference", help="base to list against (default: the integration branch)")
    tg.add_argument("--limit", type=int, default=TARGETS_DEFAULT_LIMIT, help=f"how many to show (default {TARGETS_DEFAULT_LIMIT})")
    tg.add_argument("--all", action="store_true", help="show every candidate")
    tg.add_argument("--json", action="store_true", help="print one JSON object on stdout")

    mark = sub.add_parser("marker", help="reprint the recorded approval marker (read-only; stale or missing record is exit 3)")
    mark.add_argument("--reference", help=argparse.SUPPRESS)

    com = sub.add_parser("commit", help="write the attestation commit and notes")
    com.add_argument("--email", required=True, help="Signoff-Verified-By, confirmed by the human")
    com.add_argument("--level", required=True, choices=LEVELS, help="interview level actually run")
    com.add_argument("--tradeoff", action="append", default=[], help="acknowledged trade-off (repeatable)")
    com.add_argument("--risk", action="append", default=[], help="acknowledged risk (repeatable)")
    com.add_argument("--summary", help="optional review summary paragraph")
    com.add_argument("--model", help="self-reported model id, used only when no deterministic source has one")
    com.add_argument("--reference", help="must agree with the prepared reference (default: the recorded one)")
    com.add_argument("--ack-no-transcript", action="store_true", help="human confirmed the downgraded status")
    com.add_argument("--no-sign", action="store_true", help="do not pass -S even if user.signingkey is set")
    com.add_argument("--dry-run", action="store_true", help="print the message; commit nothing")
    com.add_argument("--no-push", action="store_true", help="do not push refs/notes/signoff")
    com.add_argument("--json", action="store_true", help="print one JSON object on stdout")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    as_json = getattr(args, "json", False)
    try:
        root = repo_root()
        if args.command == "practice-start":
            result = start_practice(root)
            if as_json:
                print(json.dumps(result, indent=2))
            else:
                print(f"practice guard: {result['guard']}")
                if result["practice_record"]:
                    print(f"local session record: {result['practice_record']}")
                if result["practice_marker"]:
                    print("Emit this as a separate assistant message containing only this line before the first practice probe:")
                    print(result["practice_marker"])
            for warning in result["warnings"]:
                print(f"warning: {warning}", file=sys.stderr)
            return EXIT_OK
        if args.command == "targets":
            listing = list_targets(root, args.reference, None if args.all else args.limit)
            if as_json:
                print(json.dumps(listing, indent=2))
            else:
                _print_targets(listing)
            return EXIT_OK
        if args.command == "prepare":
            mode = "practice" if args.practice else "explain" if args.explain else "attest"
            state = prepare(root, args.reference, target=args.target, mode=mode, check_snapshot=args.check_snapshot)
            if as_json:
                print(json.dumps(state.to_json(), indent=2))
                for w in state.warnings:
                    print(f"warning: {w}", file=sys.stderr)
            else:
                _print_prepare(state)
            return EXIT_OK
        if args.command == "marker":
            _check_practice_record(GitRepo(root), resolve_adapter(os.environ, cwd=root))
            # Read-only on purpose: a stale or missing record is a refusal, never
            # a silent re-prepare. Otherwise `marker` would be the one command
            # that restarts a review without an interview: prepare A, add B,
            # commit refuses B, `marker` re-prepares for B, commit attests B.
            try:
                state = load_prepared(root, args.reference)
            except AttestError as exc:
                raise AttestError(
                    exc.code,
                    f"{exc} `marker` only reprints the recorded marker; run `attest.py prepare` to start a new "
                    "review of the current state, and cover it in the interview.",
                ) from exc
            print(state.marker)
            return EXIT_OK
        opts = CommitOptions(
            email=args.email,
            level=args.level,
            tradeoffs=args.tradeoff,
            risks=args.risk,
            summary=args.summary,
            model=args.model,
            reference=args.reference,
            ack_no_transcript=args.ack_no_transcript,
            sign=not args.no_sign,
            dry_run=args.dry_run,
            push=not args.no_push,
        )
        result = commit(root, opts)
        if as_json:
            print(json.dumps(result.to_json(), indent=2))
            for w in result.warnings:
                print(f"warning: {w}", file=sys.stderr)
        else:
            _print_commit(result)
        return EXIT_OK
    except AttestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        if as_json:
            print(json.dumps({"ok": False, "command": args.command, "exit_code": exc.code, "error": str(exc)}, indent=2))
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
