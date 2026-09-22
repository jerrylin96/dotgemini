#!/usr/bin/env python3
"""Git Signoff Attestation (GSA) verifier — stdlib-only, single file.

Verifies GSA v1.0 attestations (skills/git-signoff/specs/gsa-core.md) against a
repository's history using the §5.1 lookup order: git notes
(refs/notes/signoff) on the commit and its tree, then [SIGNOFF *]
attestation commits in the log, with the tree-SHA fallback for squash
merges and rebases.

Two modes:

  head     Verify that a specific commit (default HEAD) is attested — the
           PR-gate check. A commit that is itself an attestation commit
           passes when it is empty (same tree as its parent) and attests
           its own parent's commit and tree (the normal shape of a branch
           ending in /git-signoff); a non-empty attestation commit fails, so
           trailers cannot smuggle unreviewed changes past the gate.
           For 2-parent merge commits (e.g. GitHub standard PR merges),
           verifies that HEAD^{tree} cleanly matches git merge-tree HEAD^1 HEAD^2
           and that the merged PR head HEAD^2 is validly attested.
  history  Verify that a ref's history carries valid attestations — the
           repo-badge check. Passes when at least --require valid
           attestations (default 1) are found.

Evidence, not trailers (verify-v1.5). An attestation *commit* found by the
log lookup — in the target's own history or under --scan-refs — counts only
if the commit object corroborates its trailers: exactly one parent, empty
(its tree is the parent's), and that parent is the declared reviewed commit;
its declared tree anchors only when it is the parent's actual tree. Without
this, an empty [SIGNOFF] commit on an unrelated tree whose trailer named some
target's tree would pass that target. Notes are judged as before: they are
statements attached to the very object being verified.

  --scan-refs REF [REF ...]   head mode: also consider sound attestation
           commits reachable from these refs (pull-request head refs the
           composite action fetched for the merged PR associated with the
           target). A match by tree establishes that the same tracked code
           state was attested — not that this pull request, base, or
           interview context was reviewed (gsa-core §5.1). Which refs are
           eligible is the caller's decision (verify/action.yml: merged,
           same-repository PRs); the verifier trusts no ref it was not given.

Exit 0 on pass, 1 on fail. No dependencies beyond Python 3.10+ and git;
copy this file anywhere or run it via the companion composite action
(verify/action.yml in the git-signoff repository). The file is vendored into
adopter repositories as part of the skill folder, so `--audit` runs locally
without a download, and the producer helper (attest.py, same folder) imports
it to self-check every attestation it writes.

Environment:

  GIT_SIGNOFF_TRANSCRIPT_FILE   --audit: transcript file to hash instead of the
                                harness-resolved path.
  GIT_SIGNOFF_NO_UPDATE_CHECK   set to 1 to skip the stale-pin warning below.
  GIT_SIGNOFF_PIN_REMOTE        repository URL queried for verify-v* tags
                                (tests point it at a local bare repo).

Stale-pin warning: after fetching notes, the verifier lists the verify-v*
tags on the upstream repository and prints a one-line warning to stderr when
a newer pin than VERIFIER_PIN exists (stdout carries only the verdict). It
never changes the verdict and is skipped silently on any network failure.

Single-valued trailers appear exactly once per attestation (gsa-core §2.3):
a commit message or note block that repeats one — the way a line break
inside free text would smuggle a second Reviewed-Tree-SHA — is malformed
and never anchors anything. cat_sort_uniq-merged notes, whose blocks cannot
be separated, anchor only the object they are attached to.

Verification is non-destructive to your signoff notes: origin's notes are
fetched into an isolated mirror ref, never into refs/notes/signoff, so an
attestation you have not pushed yet survives a verifier run.
"""

import sys

if sys.version_info < (3, 10):  # loud, before anything that only parses on newer Pythons
    sys.exit(
        "verify_signoff.py needs Python 3.10 or newer; this is Python %d.%d. "
        "Run it with a newer interpreter (python3.10+)." % sys.version_info[:2]
    )

import argparse  # noqa: E402
import glob  # noqa: E402
import hashlib  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
from pathlib import Path  # noqa: E402

# The pin tag this file ships under. tag.yml's PINS list and the install
# snippets must carry the same value (pinned by tests); the stale-pin warning
# compares it against the tags published upstream.
VERIFIER_PIN = "verify-v1.7"
PIN_REMOTE = "https://github.com/jerrylin96/git-signoff"
PIN_TAG_RE = re.compile(r"refs/tags/verify-v(\d+)(?:\.(\d+))?$")

NOTES_REF = "refs/notes/signoff"
# The verifier's own isolated mirror of origin's notes. Fetching origin straight
# into NOTES_REF force-overwrites attestation notes that have not been pushed
# yet — gsa-core §5.1 forbids exactly that, and a reviewer who runs /git-signoff
# offline and verifies before pushing would silently lose the record. This ref
# is the only ref verification writes; NOTES_REF is read and never modified.
NOTES_FETCH_REF = "refs/notes/signoff-verify"
SUBJECT_RE = re.compile(r"^\[SIGNOFF [0-9a-f]{7,40}\]: ")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
TRAILER_RE = re.compile(r"^(Signoff-[A-Za-z0-9-]+):\s*(.*)$")
REQUIRED_TRAILERS = (
    "Signoff-Spec-Version",
    "Signoff-Status",
    "Signoff-Reviewed-Commit-SHA",
    "Signoff-Reviewed-Tree-SHA",
    "Signoff-Verified-By",
)
VALID_STATUSES = ("VERIFIED_BY_HUMAN", "VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST")
# Every trailer except Signoff-Tradeoff / Signoff-Risk carries exactly one value
# per attestation (gsa-core §2.3). A payload that is one attestation — a commit
# message, or one block of a note — is invalid if any of these repeats: the
# format is line-oriented, so a repeated key is how free text (a tradeoff, a
# summary) smuggles a second anchor past the gate.
SINGLE_VALUED_TRAILERS = (
    "Signoff-Spec-Version",
    "Signoff-Status",
    "Signoff-Timestamp",
    "Signoff-Base-SHA",
    "Signoff-Reviewed-Commit-SHA",
    "Signoff-Reviewed-Tree-SHA",
    "Signoff-Harness-ID",
    "Signoff-Conversation-ID",
    "Signoff-Transcript-Digest",
    "Signoff-Transcript-Bytes",
    "Signoff-Verified-By",
    "Signoff-Agent",
)


def git(repo, *args, check=True):
    proc = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc


def parse_trailers(payload):
    """Repeated-key-aware trailer parse; works on cat_sort_uniq note blobs."""
    trailers = {}
    for line in payload.splitlines():
        m = TRAILER_RE.match(line)
        if m:
            trailers.setdefault(m.group(1), []).append(m.group(2).strip())
    return trailers


DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def validate(trailers):
    """Structural validation of an attestation payload -> list of problems.

    Repeated-key-aware: every value of every key is checked, and the
    status/digest cross-field rule (§2.2) is applied to the payload as a
    whole. Use validate_single() for a payload that is one attestation and
    validate_merged() for a cat_sort_uniq-merged note blob.
    """
    return _structural_problems(trailers) + _cross_field_problems(trailers, merged=False)


def duplicate_problems(trailers):
    """Single-valued trailers (§2.3) that appear more than once."""
    return [
        f"duplicate {key} ({len(values)} values; one attestation carries exactly one)"
        for key in SINGLE_VALUED_TRAILERS
        for values in (trailers.get(key, []),)
        if len(values) > 1
    ]


def validate_single(trailers):
    """Validation of a payload that is exactly one attestation: a commit message,
    or one block of a note. Rejects repeated single-valued trailers."""
    return validate(trailers) + duplicate_problems(trailers)


def validate_merged(trailers):
    """Validation of a cat_sort_uniq-merged note blob (§2.5): the sorted union
    of several attestations' lines. Individual attestations cannot be recovered
    from it, so single-valued trailers legitimately repeat and the status/digest
    rule is applied per status rather than across the blob. Anchoring from such
    a blob is valid only for the object the note is attached to (§5.1)."""
    return _structural_problems(trailers) + _cross_field_problems(trailers, merged=True)


def _structural_problems(trailers):
    problems = []
    for key in REQUIRED_TRAILERS:
        if key not in trailers:
            problems.append(f"missing {key}")
    for version in trailers.get("Signoff-Spec-Version", []):
        if version != "1.0":
            problems.append(f"unsupported Signoff-Spec-Version {version!r}")
    for status in trailers.get("Signoff-Status", []):
        if status not in VALID_STATUSES:
            problems.append(f"invalid Signoff-Status {status!r}")
    for key in ("Signoff-Reviewed-Commit-SHA", "Signoff-Reviewed-Tree-SHA"):
        for sha in trailers.get(key, []):
            if not SHA_RE.match(sha):
                problems.append(f"malformed {key} {sha!r}")
    for email in trailers.get("Signoff-Verified-By", []):
        if "@" not in email:
            problems.append(f"implausible Signoff-Verified-By {email!r}")
    return problems


def _cross_field_problems(trailers, merged):
    # Cross-field status vs transcript digest check (GSA §2.2)
    problems = []
    statuses = trailers.get("Signoff-Status", [])
    digests = trailers.get("Signoff-Transcript-Digest", [])
    if "VERIFIED_BY_HUMAN" in statuses:
        if not digests:
            problems.append("status 'VERIFIED_BY_HUMAN' requires a Signoff-Transcript-Digest")
        elif merged:
            if not any(DIGEST_RE.match(d) for d in digests):
                problems.append("status 'VERIFIED_BY_HUMAN' requires sha256 transcript digest, got 'unavailable'")
        else:
            for d in digests:
                if d == "unavailable":
                    problems.append("status 'VERIFIED_BY_HUMAN' requires sha256 transcript digest, got 'unavailable'")
                elif not DIGEST_RE.match(d):
                    problems.append(f"malformed Signoff-Transcript-Digest {d!r}")
    if "VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST" in statuses:
        if not digests:
            problems.append("status 'VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST' requires 'unavailable' digest")
        elif merged:
            if "unavailable" not in digests:
                problems.append("status 'VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST' requires 'unavailable' digest")
        else:
            for d in digests:
                if d != "unavailable":
                    problems.append(
                        f"status 'VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST' requires 'unavailable' digest, got {d!r}"
                    )
    if merged:
        for d in digests:
            if d != "unavailable" and not DIGEST_RE.match(d):
                problems.append(f"malformed Signoff-Transcript-Digest {d!r}")
    return problems


def describe(trailers):
    who = ", ".join(trailers.get("Signoff-Verified-By", ["?"]))
    status = ", ".join(trailers.get("Signoff-Status", ["?"]))
    reviewed = ", ".join(s[:7] for s in trailers.get("Signoff-Reviewed-Commit-SHA", []))
    return f"reviewed={reviewed} status={status} by={who}"


def history_payloads(repo, ref):
    """(source, payload, sha) for every [SIGNOFF *] commit reachable from ref."""
    proc = git(repo, "log", ref, "--format=%H", r"--grep=^\[SIGNOFF ", check=False)
    out = []
    for sha in proc.stdout.split():
        payload = git(repo, "log", "-1", "--format=%B", sha).stdout
        if SUBJECT_RE.match(payload):
            out.append((f"commit {sha[:7]}", payload, sha))
    return out


def commit_evidence(repo, sha, trailers):
    """What an attestation *commit* has earned: (problems, commit_anchor, tree_anchor).

    The commit object must corroborate the trailers, in the shape the producer
    writes and head mode already demands of an attestation at the tip: exactly
    one parent, empty (its tree is the parent's), and the parent is the
    declared Signoff-Reviewed-Commit-SHA. Failing any of these, `problems` is
    non-empty and nothing is anchored. The declared Signoff-Reviewed-Tree-SHA
    anchors only when it is the parent's actual tree; otherwise the commit
    anchors its reviewed commit alone (this repository's own early history has
    eight such attestations, written by the first skill, that declare a tree no
    reviewed commit has). Notes are not judged here: a note is attached to the
    object it describes, which is its corroboration.
    """
    parents = git(repo, "log", "-1", "--format=%P", sha, check=False).stdout.split()
    if len(parents) != 1:
        return [f"{len(parents)} parents (an attestation commit has exactly one)"], None, None
    parent = parents[0]
    parent_tree = git(repo, "rev-parse", f"{parent}^{{tree}}", check=False).stdout.strip()
    own_tree = git(repo, "rev-parse", f"{sha}^{{tree}}", check=False).stdout.strip()
    if not parent_tree or own_tree != parent_tree:
        return ["not an empty commit (its tree differs from its parent's)"], None, None
    reviewed = trailers.get("Signoff-Reviewed-Commit-SHA", [None])[0]
    if reviewed != parent:
        return [f"parent {parent[:7]} is not the declared reviewed commit {(reviewed or 'none')[:7]}"], None, None
    declared_tree = trailers.get("Signoff-Reviewed-Tree-SHA", [None])[0]
    tree_anchor = declared_tree if declared_tree == parent_tree else None
    return [], reviewed, tree_anchor


def _earned_anchor(repo, sha, trailers, commit, tree):
    """The reason a sound attestation commit anchors `commit`/`tree`, or None."""
    problems, commit_anchor, tree_anchor = commit_evidence(repo, sha, trailers)
    if problems:
        return None
    if commit_anchor == commit:
        return "reviewed commit"
    if tree_anchor is not None and tree_anchor == tree:
        return "reviewed tree"
    return None


def scan_ref_payloads(repo, refs):
    """(source, payload, sha) for [SIGNOFF *] commits reachable from each of
    `refs` (patterns are expanded with for-each-ref; a plain ref is used as is).
    Deduplicated by sha."""
    out, seen = [], set()
    for pattern in refs:
        tips = git(repo, "for-each-ref", "--format=%(objectname)", pattern, check=False).stdout.split()
        if not tips:
            direct = git(repo, "rev-parse", "--verify", "-q", f"{pattern}^{{commit}}", check=False)
            tips = [direct.stdout.strip()] if direct.returncode == 0 else []
        for tip in tips:
            for source, payload, sha in history_payloads(repo, tip):
                if sha not in seen:
                    seen.add(sha)
                    out.append((f"{source} via {pattern}", payload, sha))
    return out


def note_payloads(repo, target):
    """Every payload attached to `target`, across the local notes ref and the
    fetched mirror. Local notes are read first so an un-pushed attestation
    verifies without ever being overwritten by origin."""
    out = []
    for ref in (NOTES_REF, NOTES_FETCH_REF):
        proc = git(repo, "notes", f"--ref={ref}", "show", target, check=False)
        if proc.returncode == 0 and proc.stdout.strip() and proc.stdout not in out:
            out.append(proc.stdout)
    return out


def _anchors(trailers, commit, tree):
    return commit in trailers.get("Signoff-Reviewed-Commit-SHA", []) or tree in trailers.get(
        "Signoff-Reviewed-Tree-SHA", []
    )


def _note_parts(payload):
    """(intact_blocks, merged_blob_or_None, leftover_blocks) of a note payload.

    A note is judged block by block (git notes append concatenates
    attestations). A cat_sort_uniq-merged blob is one sorted line set that the
    splitter cuts into fragments none of which is an attestation; when the
    blocks that are not intact attestations together parse as such a blob, they
    are that blob. Since `git notes append` puts a fresh attestation after an
    existing blob, one payload can hold both — judging the blob's fragments as
    attestations would report a legitimate merge as several invalid fragments
    and lose the evidence it carries (found in external review, verify-v1.6).
    Leftover blocks are the fragments that form neither."""
    blocks = split_attestation_blocks(payload)
    intact = [b for b in blocks if not validate_single(parse_trailers(b))]
    rest = [b for b in blocks if validate_single(parse_trailers(b))]
    # The blob is what remains of the payload once the intact blocks are cut
    # out — not the fragments joined back, since the splitter drops fragments
    # carrying no status, version or subject line (a sorted blob's leading
    # Reviewed-*-SHA lines are exactly such a fragment).
    remainder = payload
    for block in intact:
        remainder = remainder.replace(block, "", 1)
    if remainder.strip():
        trailers = parse_trailers(remainder)
        if duplicate_problems(trailers) and not validate_merged(trailers):
            return intact, remainder, []
    return intact, None, rest


def _anchoring_note_attestation(repo, commit, tree):
    """(source, trailers) of a valid attestation in a note on `commit` or `tree`
    that covers it, or None.

    Notes are evaluated block by block (git notes append concatenates
    attestations; a re-attestation without and then with a transcript is two
    blocks with two statuses, not one payload with a contradiction). The
    strongest valid block wins the report. A cat_sort_uniq-merged blob cannot
    be split into attestations; it is accepted only under the merge-aware
    rules and only because the note is attached to the object being verified —
    membership in a merged blob never anchors any other object (§5.1).
    """
    for note_target, how in ((commit, "note on commit"), (tree, "note on tree")):
        for payload in note_payloads(repo, note_target):
            intact, merged_blob, _ = _note_parts(payload)
            valid = [t for t in (parse_trailers(b) for b in intact) if _anchors(t, commit, tree)]
            if valid:
                valid.sort(key=lambda t: t.get("Signoff-Status", [""])[0] != "VERIFIED_BY_HUMAN")
                return how, valid[0]
            if merged_blob is not None:
                trailers = parse_trailers(merged_blob)
                if _anchors(trailers, commit, tree):
                    return f"{how} (cat_sort_uniq-merged)", trailers
    return None


def check_head(repo, target, scan_refs=()):
    """PR-gate check: is `target` (or, for an attestation commit, its parent,
    or for a 2-parent merge commit, its attested PR head) attested?
    `scan_refs`: additional refs whose sound attestation commits may anchor the
    target by tree (verify-v1.5; see the module docstring for what that means).
    Returns (passed, lines-to-print)."""
    commit = git(repo, "rev-parse", f"{target}^{{commit}}").stdout.strip()
    tree = git(repo, "rev-parse", f"{commit}^{{tree}}").stdout.strip()
    message = git(repo, "log", "-1", "--format=%B", commit).stdout

    if SUBJECT_RE.match(message):
        trailers = parse_trailers(message)
        problems = validate_single(trailers)
        parent = git(repo, "rev-parse", f"{commit}~1", check=False).stdout.strip()
        parent_tree = ""
        if parent:
            parent_tree = git(repo, "rev-parse", f"{parent}^{{tree}}", check=False).stdout.strip()
        if trailers.get("Signoff-Reviewed-Commit-SHA", [None])[0] != parent:
            problems.append("attestation commit does not attest its parent")
        if not parent_tree or tree != parent_tree:
            problems.append(
                "attestation commit is not empty (its tree differs from its parent's — "
                "it smuggles changes the attestation does not cover)"
            )
        if trailers.get("Signoff-Reviewed-Tree-SHA", [None])[0] != parent_tree:
            problems.append("attestation does not attest its parent's tree")
        if problems:
            return False, [f"FAIL: {target} is a malformed attestation commit: "
                           + "; ".join(problems)]
        return True, [
            f"PASS: {commit[:7]} is a valid attestation of its parent {parent[:7]}",
            f"  {describe(trailers)}",
        ]

    found = _anchoring_note_attestation(repo, commit, tree)
    if found:
        source, trailers = found
        return True, [
            f"PASS: {commit[:7]} attested via {source}",
            f"  {describe(trailers)}",
        ]

    parents = git(repo, "log", "-1", "--format=%P", commit, check=False).stdout.split()
    if len(parents) > 2:
        return False, [
            f"FAIL: merge commit {commit[:7]} is an octopus merge with {len(parents)} parents "
            "(only 2-parent merges supported for provenance verification)"
        ]
    if len(parents) == 2:
        p1, p2 = parents[0], parents[1]
        is_ancestor = git(repo, "merge-base", "--is-ancestor", p2, p1, check=False).returncode == 0
        if is_ancestor:
            return False, [
                f"FAIL: merge commit {commit[:7]} PR head {p2[:7]} is an ancestor of base {p1[:7]}"
            ]
        mproc = git(repo, "merge-tree", "--write-tree", p1, p2, check=False)
        if mproc.returncode != 0:
            return False, [
                f"FAIL: merge commit {commit[:7]} failed clean 3-way merge calculation between {p1[:7]} and {p2[:7]}"
            ]
        expected_tree = mproc.stdout.strip().splitlines()[0]
        if expected_tree != tree:
            return False, [
                f"FAIL: merge commit {commit[:7]} tree does not match clean 3-way merge of parents "
                f"{p1[:7]} and {p2[:7]} (manual conflict resolution or unreviewed changes introduced in merge)"
            ]
        ok2, lines2 = check_head(repo, p2, scan_refs)
        if ok2:
            return True, [
                f"PASS: merge commit {commit[:7]} verified via attested PR head {p2[:7]}",
                *[f"  {line}" for line in lines2],
            ]
        return False, [
            f"FAIL: merge commit {commit[:7]} PR head {p2[:7]} is not attested",
            *[f"  {line}" for line in lines2],
        ]

    # Log lookup (§5.1 steps 2–3): an attestation commit is evidence only when
    # its object corroborates its trailers — see commit_evidence.
    for source, payload, sha in history_payloads(repo, commit) + scan_ref_payloads(repo, scan_refs):
        trailers = parse_trailers(payload)
        if validate_single(trailers):
            continue
        how = _earned_anchor(repo, sha, trailers, commit, tree)
        if how:
            return True, [
                f"PASS: {commit[:7]} attested via {source} ({how})",
                f"  {describe(trailers)}",
            ]

    return False, [
        f"FAIL: no valid attestation covers commit {commit[:7]} (or tree {tree[:7]})",
        "  Run /git-signoff on this branch before merging.",
    ]


def _describes_other_object(trailers, target):
    """Why a note that is attached to `target` does not attest it."""
    reviewed = ", ".join(v[:7] for v in trailers.get("Signoff-Reviewed-Commit-SHA", [])) or "none"
    declared_tree = ", ".join(v[:7] for v in trailers.get("Signoff-Reviewed-Tree-SHA", [])) or "none"
    return f"attests commit {reviewed} / tree {declared_tree}, not the object it is attached to ({target[:7]})"


def check_history(repo, ref, require):
    """Repo-badge check: does ref's history carry valid attestations? Evidence is
    attestation commits reachable from ref and notes on objects reachable from
    ref (a commit, or the tree of a commit); nothing outside that history."""
    lines, valid = [], 0
    seen = set()
    payloads = []
    # Enumerate the history first, and say so when it cannot be enumerated: a
    # ref this checkout does not have must not come back as "0 attestations"
    # plus a confident wrong reason on every note (verify-v1.6). A shallow
    # checkout enumerates only what it has, so history beyond its boundary —
    # and every note hanging there — looks absent; the warning names the cause.
    enumeration = git(repo, "log", ref, "--format=%H %T", check=False)
    if enumeration.returncode != 0:
        reason = (enumeration.stderr.strip().splitlines() or ["git log failed"])[0]
        return False, [
            f"FAIL: cannot enumerate {ref}: {reason}",
            "  history mode needs a ref this checkout has (a full clone: fetch-depth: 0 in Actions, "
            "git fetch --unshallow locally); nothing was judged",
        ]
    if git(repo, "rev-parse", "--is-shallow-repository", check=False).stdout.strip() == "true":
        lines.append(
            f"  warning: shallow checkout — history beyond the shallow boundary is not visible, so attestations "
            f"and notes there are reported as not in {ref} history (git fetch --unshallow, or fetch-depth: 0)"
        )
    for source, payload, sha in history_payloads(repo, ref):
        trailers = parse_trailers(payload)
        problems = validate_single(trailers)
        if not problems:
            problems, _, _ = commit_evidence(repo, sha, trailers)
        payloads.append((source, payload, problems or None, None))
    annotated = []
    for n_ref in (NOTES_REF, NOTES_FETCH_REF):
        listing = git(repo, "notes", f"--ref={n_ref}", "list", check=False)
        if listing.returncode != 0:
            continue
        for entry in listing.stdout.split("\n"):
            if entry and entry.split()[1] not in annotated:
                annotated.append(entry.split()[1])
    # A note is evidence for *this ref's* history only under head mode's own
    # rule, applied to every object in that history (verify-v1.6): the object it
    # hangs on must be reachable — a commit, or the tree some reachable commit
    # has — and the attestation must describe that object, naming it as the
    # reviewed commit or its tree as the reviewed tree. Attachment alone is not
    # enough: `notes.rewriteRef` copies a note onto a rebased commit whose
    # trailers still name the pre-rebase commit and tree, neither of which the
    # branch carries any more. Reachability alone is not enough either: notes
    # outlive branches by design, so notes published for a branch that was then
    # abandoned, or squash-merged onto an advanced base, would otherwise turn
    # the integration branch's badge green. A squash or rebase merge onto an
    # unchanged base keeps its evidence: the merged tip has the attested tree.
    commit_tree, history_trees = {}, set()  # reachable commit -> its tree; reachable trees
    for line in enumeration.stdout.split("\n"):
        if line:
            commit_sha, tree_sha = line.split()
            commit_tree[commit_sha] = tree_sha
            history_trees.add(tree_sha)
    for target in annotated:
        if target in commit_tree:
            commit, tree = target, commit_tree[target]
        elif target in history_trees:
            commit, tree = None, target
        else:
            lines.append(f"  skipped (note on {target[:7]}): object not in {ref} history")
            continue
        for payload in note_payloads(repo, target):
            intact, merged_blob, leftover = _note_parts(payload)
            if merged_blob is not None:
                merged = parse_trailers(merged_blob)
                problems = [] if _anchors(merged, commit, tree) else [_describes_other_object(merged, target)]
                payloads.append((f"note on {target[:7]} (cat_sort_uniq-merged)", merged_blob, problems or None, (commit, tree)))
            for block in intact + leftover:
                trailers = parse_trailers(block)
                problems = validate_single(trailers)
                if not problems and not _anchors(trailers, commit, tree):
                    problems = [_describes_other_object(trailers, target)]
                payloads.append((f"note on {target[:7]}", block, problems or None, (commit, tree)))
    # One rule throughout: count distinct reviewed commits, each independently
    # supported; copying or merging records never manufactures another. The
    # unit is the reviewed commit, never the payload, however many copies of
    # its attestation exist (commit in history, note on the commit, note on
    # the tree, a line set inside a cat_sort_uniq-merged blob). An intact
    # attestation — a commit, or one block of a note — supports its one
    # reviewed commit by its own claims, judged above. A merged blob is the
    # sorted union of several attestations' lines: which tree went with which
    # commit is gone, and a stale attestation merged in (a note git copied onto
    # a rebased commit) is indistinguishable from a live one. So a blob counts
    # a reviewed commit only when the support is unambiguous: either the blob
    # names exactly one reviewed tree and hangs on it (or on a commit that has
    # it) — then every attestation merged in declared that tree, and the blob
    # is squash or rebase evidence exactly as an intact tree note is — or the
    # commit is reachable and is the object the blob hangs on or has the tree
    # it hangs on. Once, whatever the line repeats, and it names what it could
    # not count. Blobs are judged after intact attestations so they never pre-empt
    # the sound commits behind them (verify-v1.6; before, a blob's whole SHA
    # tuple was the key, so (A, B) counted beside (A,) and (B,), a stale SHA
    # merged into a valid blob counted, and a repeated SHA counted twice).
    # Only a *valid* payload claims a commit: an invalid copy — a rebased or
    # cherry-picked attestation commit whose parent is no longer the commit it
    # names — is reported but must not shadow sound evidence for the same
    # reviewed commit listed after it.
    reported = set()

    def is_merged(entry):
        return entry[0].endswith("(cat_sort_uniq-merged)")

    for source, payload, precomputed, anchor in sorted(payloads, key=is_merged):
        trailers = parse_trailers(payload)
        merged = is_merged((source,))
        problems = precomputed if precomputed is not None else ([] if merged else validate_single(trailers))
        reviewed = list(dict.fromkeys(trailers.get("Signoff-Reviewed-Commit-SHA") or [source]))
        if problems:
            if any(sha not in seen for sha in reviewed) and (tuple(reviewed), tuple(problems)) not in reported:
                reported.add((tuple(reviewed), tuple(problems)))
                lines.append(f"  invalid ({source}): " + "; ".join(problems))
            continue
        if merged:
            note_commit, note_tree = anchor
            declared_trees = list(dict.fromkeys(trailers.get("Signoff-Reviewed-Tree-SHA", [])))
            if declared_trees == [note_tree]:
                supported = reviewed  # one tree, and the blob hangs on it: every merged attestation reviewed this tree
            else:
                supported = [
                    sha for sha in reviewed
                    if sha in commit_tree and (sha == note_commit or commit_tree[sha] == note_tree)
                ]
            unsupported = [sha for sha in reviewed if sha not in supported]
            if unsupported:
                lines.append(
                    f"  not counted ({source}): reviewed commit(s) {', '.join(sha[:7] for sha in unsupported)} "
                    f"are not in {ref} history at the object this note is attached to"
                )
            reviewed = supported
        unseen = [sha for sha in reviewed if sha not in seen]
        if not unseen:
            continue
        seen.update(reviewed)
        valid += len(unseen)
        counted = f" ({len(unseen)} reviewed commit(s) counted)" if merged else ""
        lines.append(f"  valid ({source}): {describe(trailers)}{counted}")
    verdict = "PASS" if valid >= require else "FAIL"
    lines.insert(
        0,
        f"{verdict}: {valid} valid attestation(s) in {ref} history"
        + (f" (required {require})" if verdict == "FAIL" else ""),
    )
    return valid >= require, lines


CONV_ID_SAFE_RE = re.compile(r"^[a-zA-Z0-9._-]+$")


def split_attestation_blocks(payload):
    """Split a note payload into individual attestation blocks (handles cat_sort_uniq concatenation)."""
    blocks = []
    current = []
    has_reviewed_sha = False

    for line in payload.splitlines():
        is_new_block = False
        if SUBJECT_RE.match(line) and current:
            is_new_block = True
        elif line.startswith("Signoff-Spec-Version:") and has_reviewed_sha:
            is_new_block = True

        if is_new_block:
            block_text = "\n".join(current).strip()
            if block_text and (
                "Signoff-Spec-Version:" in block_text
                or "Signoff-Status:" in block_text
                or SUBJECT_RE.search(block_text)
            ):
                blocks.append(block_text)
            current = [line]
            has_reviewed_sha = False
        else:
            if "Signoff-Reviewed-Commit-SHA:" in line:
                has_reviewed_sha = True
            current.append(line)

    if current:
        block_text = "\n".join(current).strip()
        if block_text and (
            "Signoff-Spec-Version:" in block_text
            or "Signoff-Status:" in block_text
            or SUBJECT_RE.search(block_text)
        ):
            blocks.append(block_text)

    return blocks if blocks else ([payload.strip()] if payload.strip() else [])


def extract_attestation_trailers(repo, target, seen=None, depth=0):
    """Find and return trailers dict for target commit or tree."""
    if depth > 10:
        return None
    if seen is None:
        seen = set()

    commit_proc = git(repo, "rev-parse", f"{target}^{{commit}}", check=False)
    if commit_proc.returncode != 0:
        return None
    commit = commit_proc.stdout.strip()
    tree = git(repo, "rev-parse", f"{commit}^{{tree}}", check=False).stdout.strip()
    message = git(repo, "log", "-1", "--format=%B", commit, check=False).stdout

    # 1. Check target commit's own message
    if SUBJECT_RE.match(message) or "Signoff-Spec-Version:" in message:
        t = parse_trailers(message)
        if not validate_single(t):
            if commit in t.get("Signoff-Reviewed-Commit-SHA", []) or tree in t.get(
                "Signoff-Reviewed-Tree-SHA", []
            ):
                return t
            if SUBJECT_RE.match(message):
                parent = git(repo, "rev-parse", f"{commit}~1", check=False).stdout.strip()
                parent_tree = ""
                if parent:
                    parent_tree = git(repo, "rev-parse", f"{parent}^{{tree}}", check=False).stdout.strip()
                if (
                    parent
                    and parent_tree
                    and tree == parent_tree
                    and t.get("Signoff-Reviewed-Commit-SHA", [None])[0] == parent
                    and t.get("Signoff-Reviewed-Tree-SHA", [None])[0] == parent_tree
                ):
                    return t

    # 2. Check notes on commit and tree
    for note_target in (commit, tree):
        for payload in note_payloads(repo, note_target):
            for block in split_attestation_blocks(payload):
                t = parse_trailers(block)
                if not validate_single(t) and _anchors(t, commit, tree):
                    return t

    # 3. Check if target is a 2-parent merge commit
    parents = git(repo, "log", "-1", "--format=%P", commit, check=False).stdout.split()
    if len(parents) == 2 and parents[1] not in seen:
        seen.add(parents[1])
        p2_trailers = extract_attestation_trailers(repo, parents[1], seen=seen, depth=depth + 1)
        if p2_trailers:
            return p2_trailers

    # 4. Fall back to scanning commit history (same evidence rule as check_head)
    for _, payload, sha in history_payloads(repo, commit):
        t = parse_trailers(payload)
        if not validate_single(t) and _earned_anchor(repo, sha, t, commit, tree):
            return t

    return None


def check_audit(repo, target="HEAD", export_path=None):
    """Audit local transcript against signoff trailers on target."""
    trailers = extract_attestation_trailers(repo, target)
    if not trailers:
        return False, [f"FAIL: No signoff attestation found for {target}"]

    errs = validate_single(trailers)
    if errs:
        return False, [f"FAIL: Malformed signoff attestation on {target}: " + "; ".join(errs)]

    status = trailers.get("Signoff-Status", [""])[0]
    if status == "VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST":
        return True, [
            f"[NOTICE] Attestation for {target} verified without transcript digest (status: {status})."
        ]

    conv_id = trailers.get("Signoff-Conversation-ID", [""])[0]
    if (
        not conv_id
        or not CONV_ID_SAFE_RE.match(conv_id)
        or ".." in conv_id
        or conv_id.startswith(".")
    ):
        return False, [f"FAIL: Malformed or unsafe Signoff-Conversation-ID {conv_id!r}"]

    expected_digest = trailers.get("Signoff-Transcript-Digest", [""])[0]
    bytes_str = trailers.get("Signoff-Transcript-Bytes", [""])[0]
    harness_id = trailers.get("Signoff-Harness-ID", [""])[0]

    try:
        nbytes = int(bytes_str)
        if nbytes < 0:
            raise ValueError()
    except (ValueError, TypeError):
        return False, [f"FAIL: Malformed Signoff-Transcript-Bytes {bytes_str!r}"]

    # Resolve transcript path
    if os.environ.get("GIT_SIGNOFF_TRANSCRIPT_FILE"):
        transcript_path = Path(os.environ["GIT_SIGNOFF_TRANSCRIPT_FILE"])
    else:
        home_dir = Path(os.environ.get("HOME") or os.environ.get("USERPROFILE") or Path.home())
        if harness_id == "claude-code":
            proc = git(repo, "rev-parse", "--show-toplevel", check=False)
            if proc.returncode == 0 and proc.stdout.strip():
                root = proc.stdout.strip()
            else:
                proc_common = git(repo, "rev-parse", "--git-common-dir", check=False)
                if proc_common.returncode == 0 and proc_common.stdout.strip():
                    root = proc_common.stdout.strip()
                else:
                    root = os.path.abspath(repo)
            try:
                root = str(Path(root).resolve())
            except Exception:
                pass
            slug = root.replace("/", "-")
            transcript_path = home_dir / ".claude" / "projects" / slug / f"{conv_id}.jsonl"
            if not transcript_path.is_file():
                proc_common = git(repo, "rev-parse", "--git-common-dir", check=False)
                if proc_common.returncode == 0 and proc_common.stdout.strip():
                    common_dir = proc_common.stdout.strip()
                    main_root = os.path.abspath(os.path.join(root, common_dir, os.pardir))
                    try:
                        main_root = str(Path(main_root).resolve())
                    except Exception:
                        pass
                    fallback_slug = main_root.replace("/", "-")
                    fallback_path = home_dir / ".claude" / "projects" / fallback_slug / f"{conv_id}.jsonl"
                    if fallback_path.is_file():
                        transcript_path = fallback_path
        elif harness_id == "antigravity-cli":
            transcript_path = (
                home_dir
                / ".gemini"
                / "antigravity-cli"
                / "brain"
                / conv_id
                / ".system_generated"
                / "logs"
                / "transcript.jsonl"
            )
        elif harness_id == "codex-cli":
            base = os.environ.get("CODEX_HOME") or os.path.join(str(home_dir), ".codex")
            sessions_dir = os.path.join(base, "sessions")
            escaped_sid = glob.escape(conv_id)
            pattern = os.path.join(glob.escape(sessions_dir), "**", f"rollout-*-{escaped_sid}.jsonl")
            try:
                matches = glob.glob(pattern, recursive=True)
                if matches:
                    newest = max(matches, key=lambda p: (os.path.getmtime(p), p))
                    transcript_path = Path(newest)
                else:
                    transcript_path = Path(sessions_dir) / f"rollout-*-{conv_id}.jsonl"
            except OSError:
                transcript_path = Path(sessions_dir) / f"rollout-*-{conv_id}.jsonl"
        elif harness_id == "generic-file":
            candidate = Path(conv_id)
            if candidate.is_file():
                transcript_path = candidate
            else:
                return False, [
                    "FAIL: For generic-file harnesses, the conversation ID is not a local file path. "
                    "Please set GIT_SIGNOFF_TRANSCRIPT_FILE=<path/to/transcript.jsonl> to audit."
                ]
        else:
            return False, [f"FAIL: Unsupported or unknown harness {harness_id!r}"]

    if not transcript_path.is_file():
        return False, [f"FAIL: Transcript file not found at {transcript_path}"]

    raw_bytes = transcript_path.read_bytes()[:nbytes]
    actual_digest = f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}"

    if actual_digest != expected_digest:
        return False, [
            f"❌ MISMATCH: Transcript SHA-256 {actual_digest} does not match trailer {expected_digest}"
        ]

    if export_path:
        export_file = Path(export_path)
        export_file.parent.mkdir(parents=True, exist_ok=True)
        export_file.write_bytes(raw_bytes)

    lines = [
        f"✅ VALID MATCH: Transcript SHA-256 matches {expected_digest}",
        f"  Harness: {harness_id}",
        f"  Conversation ID: {conv_id}",
        f"  Bytes verified: {len(raw_bytes)}",
    ]
    if export_path:
        lines.append(f"  Exported snapshot to: {export_path}")
    return True, lines


def _pin_version(tag):
    """(major, minor) of a verify-v* tag name, or None."""
    m = PIN_TAG_RE.match(tag if tag.startswith("refs/tags/") else f"refs/tags/{tag}")
    if not m:
        return None
    return int(m.group(1)), int(m.group(2) or 0)


def newest_upstream_pin(remote=None, timeout=10):
    """Newest verify-v* pin published at `remote`, as a tag name, or None on any
    failure (offline, proxy refusal, timeout, unparseable output)."""
    remote = remote or os.environ.get("GIT_SIGNOFF_PIN_REMOTE") or PIN_REMOTE
    try:
        proc = subprocess.run(
            ["git", "ls-remote", "--tags", "--refs", remote, "refs/tags/verify-v*"],
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    best = None
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        version = _pin_version(parts[1])
        if version and (best is None or version > best[0]):
            best = (version, parts[1].rsplit("/", 1)[1])
    return best[1] if best else None


def stale_pin_warning(remote=None):
    """One warning line when a newer verify-v* pin than VERIFIER_PIN exists
    upstream, else None. Skipped when GIT_SIGNOFF_NO_UPDATE_CHECK=1."""
    if os.environ.get("GIT_SIGNOFF_NO_UPDATE_CHECK", "").strip() == "1":
        return None
    newest = newest_upstream_pin(remote)
    if newest is None:
        return None
    mine = _pin_version(VERIFIER_PIN)
    theirs = _pin_version(newest)
    if mine and theirs and theirs > mine:
        return f"warning: verifier pin {VERIFIER_PIN} is behind {newest}; see verify/README.md"
    return None


def main(argv=None):
    p = argparse.ArgumentParser(description="Verify Git Signoff Attestations (GSA v1.0)")
    p.add_argument("--repo", default=".", help="repository to verify")
    p.add_argument("--mode", choices=("head", "history"), default="head")
    p.add_argument("--target", default="HEAD", help="commit (head mode) or ref (history mode)")
    p.add_argument("--require", type=int, default=1, help="history mode: minimum valid attestations")
    p.add_argument(
        "--scan-refs",
        nargs="+",
        default=[],
        metavar="REF",
        help="head mode: also consider sound attestation commits reachable from these refs (e.g. the merged "
        "pull request's refs/remotes/pull/N/head); a tree match proves the same code state was attested",
    )
    p.add_argument("--version", action="version", version=f"verify_signoff.py {VERIFIER_PIN}")
    p.add_argument(
        "--audit",
        nargs="?",
        const="HEAD",
        default=None,
        metavar="COMMIT",
        help="audit local transcript against signoff trailers",
    )
    p.add_argument(
        "--export",
        default=None,
        metavar="PATH",
        help="export audited transcript snapshot to path (requires --audit)",
    )
    args = p.parse_args(argv)

    if args.export and args.audit is None:
        p.error("--export requires --audit")

    fetched = git(args.repo, "fetch", "origin", f"+{NOTES_REF}:{NOTES_FETCH_REF}", check=False)
    stale = stale_pin_warning()
    if stale:
        print(stale, file=sys.stderr)  # visible in CI logs; stdout stays the verdict

    if args.audit is not None:
        ok, lines = check_audit(args.repo, target=args.audit, export_path=args.export)
        if not ok and fetched.returncode != 0:
            err = fetched.stderr.strip()
            if err and "couldn't find remote ref" not in err:
                lines.append(f"  warning: origin notes fetch failed ({err.splitlines()[-1]})")
        print("\n".join(lines))
        return 0 if ok else 1

    if args.mode == "head":
        ok, lines = check_head(args.repo, args.target, tuple(args.scan_refs))
    else:
        ok, lines = check_history(args.repo, args.target, args.require)
    if not ok and fetched.returncode != 0:
        # A failed notes fetch turns "attested, note unreachable" into the same
        # message as "never attested", sending the reader to re-run an interview
        # instead of at the network. Name the real cause — but stay quiet about
        # a remote that simply has no notes ref yet, which is the normal state
        # for a first-time adopter and not a fault.
        err = fetched.stderr.strip()
        if err and "couldn't find remote ref" not in err:
            lines.append(f"  warning: origin notes fetch failed ({err.splitlines()[-1]})")
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
