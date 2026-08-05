---
name: signoff
description: Socratic reverse-interview to verify human comprehension, domain risk awareness, and explicit accountability for branch diffs before merging. Maps to /signoff. Use when the user asks to sign off, attest, or finalize a branch before merging.
---

# /signoff: Human Comprehension & Accountability Verification

## Core Philosophy
Audit human understanding and conscious risk acceptance. Prevent cognitive surrender (rubber-stamping AI diffs).
Human owns results, trade-offs, and failure modes.

Agent role: Socratic interrogator, not dogmatic gatekeeper.
Intentional trade-offs (e.g. surrogates violating exact domain laws for speed) pass if human explicitly understands boundaries and risks.

Attestations follow the **Git Signoff Attestation (GSA) Protocol v1.0** defined in [specs/gsa-core.md](specs/gsa-core.md): portable flat trailers, harness-agnostic transcript adapters, and dual persistence (empty commit + `refs/notes/signoff`).

Per-harness installation (Antigravity, Claude Code web/CLI, Codex, generic) and portability rules: [HARNESSES.md](HARNESSES.md). Outside Antigravity, `@skill:` references degrade gracefully — explain diff mechanics inline when the referenced skill is unavailable.

---

## Workflow

### 1. Context & Range Resolution
1. Resolve reference commit (`<reference-commit>`) and target HEAD commit (`<reviewed-commit-sha>`) using the resolution protocol from **@skill:explain-diff**.
2. Compute explicit merge-base and tree SHAs:
   ```bash
   BASE_SHA=$(git merge-base "<reference-commit>" "<reviewed-commit-sha>")
   TREE_SHA=$(git rev-parse "<reviewed-commit-sha>^{tree}")
   ```
3. Record `Base-SHA` (`$BASE_SHA`), `Reviewed-Commit-SHA` (`<reviewed-commit-sha>`), and `Reviewed-Tree-SHA` (`$TREE_SHA`) for the attestation record.
4. Inspect range diff `git diff "$BASE_SHA...<reviewed-commit-sha>"` to analyze core mechanisms, contract deviations, and silent failure paths prior to starting the interview.

### 2. Socratic Interview Loop

Pace: 1-2 probes per turn. Select the interview intensity level before the first probe; announce any guard-forced escalation to the user.

#### Universal Axes (fixed — applied to every reviewer)

1. **Mechanics & Intent:** Explain what changed and why this specific design was chosen.
2. **Deviations, Trade-offs & Edge Cases:** Identify approximations, relaxed constraints, and the edge cases the change handles specially (or fails to handle); verify if intentional and acceptable.
3. **Boundary Conditions & Failure Loudness:** Define input/operating limits where code fails/drifts. Ensure failures happen **loudly** (explicit assertions/guards) in dev/test, not silently in production.
4. **Ownership:** Confirm explicit accountability for results and risks.

#### Interview Intensity Levels

| Level | Modifier | Probes | Coverage | Pass criteria |
|---|---|---|---|---|
| **cursory** | `--quick` | 2 (one turn) | One merged Mechanics & Intent probe; one Ownership probe including the single riskiest consequence | User states in their own words what changed, why, and the riskiest consequence, and explicitly accepts ownership. Any uncertainty or vagueness escalates to standard. |
| **standard** | *(default)* | 4-6 | At least one probe per universal axis | No axis left with an unresolved vague or uncertain answer after the remediation loop; all silent-failure findings guarded before signoff. |
| **skeptical** | `--deep` | 8+ | At least two probes per universal axis, including at least two prediction challenges | User predicts concrete behavior (given input → expected output/failure) **before** the agent reveals it; a wrong prediction triggers explanation and a fresh scenario that must pass. Restating the diff does not pass — answers must demonstrate reasoning not present verbatim in the diff. |

Guards:
- **Cursory eligibility:** The agent MUST refuse cursory and run standard — stating the escalation — when the diff is large or high-risk: more than 5 files or 200 changed lines, schema/API/data-integrity changes, or areas flagged by the active interview profile.
- **One-way escalation:** Escalate whenever pass criteria are not met; never de-escalate within a session.
- Record the level actually run (post-escalation) in the `interview=` token of `Signoff-Agent`.

#### Interview Profile (sole customization point)

The block below weights probes *within* the universal axes for the active domain. It is the only supported customization point of this skill — profiles may add domain emphases but cannot remove axes or lower pass criteria. Swap instructions and shipped profiles: [HARNESSES.md](HARNESSES.md), [profiles/](profiles/).

<!-- INTERVIEW-PROFILE:BEGIN (sole customization point — replace only this block) -->
### Interview Profile: software-general
Profile-ID: software-general

Domain emphases — weight probes within the universal axes; never remove axes
or lower pass criteria:
- **Efficiency:** algorithmic complexity and hot-path cost of the chosen
  design; what input scale breaks the current approach.
- **Data structures:** invariants of the chosen structures, which operations
  can corrupt them, and why this representation over alternatives.
- **API contracts:** caller-visible behavior changes, error contracts, and
  backward compatibility of interfaces the diff touches.
<!-- INTERVIEW-PROFILE:END -->

**Evaluation & Remediation:**
- **Uncertainty / Vague / Hand-waving:** If the user expresses uncertainty ("not sure", "don't know") OR gives vague/hand-waving answers, the agent MUST pause signoff, explain the mechanics and boundaries via **@skill:explain-diff**, and re-probe with a scenario before requesting approval.
- **Silent Failures Found:** Instruct adding explicit runtime guards before signoff.

### 3. User Approval & Attestation

> [!NOTE]
> **Scratchpad Lifecycle Sync (make-feature Phase 4, Step 8)**: If `<appDataDir>/brain/<conversation-id>/scratch/scratchpad.md` exists, ensure it is updated pre-signoff with final completion status, matching Step 8 of the make-feature skill (in harnesses that ship it). If the scratchpad file does not exist (e.g. post-Phase-4 cleanup or standalone `/signoff` execution), skip this step rather than recreating it.

1. **Request Explicit User Approval:**
   Present proposed trade-offs, risks, and `Signoff-Verified-By` email. Propose the email deterministically, in order: `SIGNOFF_VERIFIED_BY` env override → harness-authenticated account email (`CLAUDE_CODE_USER_EMAIL` on Claude Code) → `git config user.email` (local harnesses only — in cloud sessions git config holds the session identity, not the human; see [HARNESSES.md](HARNESSES.md)). The human's explicit confirmation of the proposed value is the accountability step. Confirm user readiness to proceed with empty attestation commit (`git commit --allow-empty`).

2. **Verify Clean & Stale-Free State:**
   After receiving initial user approval, re-verify state: current `HEAD` equals `<reviewed-commit-sha>`, no unstaged changes (`git diff --quiet`), and no staged changes (`git diff --cached --quiet`). If dirty or `HEAD` has moved, stop and declare signoff stale.

3. **Resolve Harness Adapter & Capture Transcript Snapshot:**
   After recording user confirmation in transcript, resolve the active harness adapter and capture the transcript snapshot (SHA256 digest + exact byte count) immediately before the commit, per GSA snapshot timing rules ([specs/gsa-core.md](specs/gsa-core.md) §2.3). Resolution order: `SIGNOFF_TRANSCRIPT_FILE` explicit override → `ANTIGRAVITY_CONVERSATION_ID` → `CLAUDE_CODE_SESSION_ID`. Execute the Python helper via temporary file with explicit trap cleanup:
   ```bash
   TMP_DIGEST_FILE=$(mktemp) || { echo "Error: mktemp failed. Aborting signoff." >&2; exit 1; }
   trap 'rm -f -- "$TMP_DIGEST_FILE"' EXIT INT TERM

   python3 - <<'PY' > "$TMP_DIGEST_FILE"
   import hashlib, os, re, subprocess

   TOKEN = re.compile(r"^[A-Za-z0-9._:/-]+$")

   def agent_fields(data):
       # Interviewer provenance (Signoff-Agent): deterministic where exposed.
       # Version/reasoning are Claude Code env vars; scope them to that harness.
       in_claude_code = bool(os.environ.get("CLAUDE_CODE_SESSION_ID", "").strip())
       hver = os.environ.get("CLAUDE_CODE_VERSION", "").strip() if in_claude_code else ""
       reasoning = os.environ.get("CLAUDE_EFFORT", "").strip() if in_claude_code else ""
       model = os.environ.get("ANTHROPIC_MODEL", "").strip()
       if not model and data:
           # Same snapshot bytes as the digest — never a second read.
           hits = re.findall(rb'"model"\s*:\s*"([^"]+)"', data)
           if hits:
               model = hits[-1].decode("utf-8", "replace")
       return [
           value if value and TOKEN.match(value) else missing
           for value, missing in ((hver, "N/A"), (model, "unavailable"), (reasoning, "N/A"))
       ]

   def emit(harness, cid, path):
       digest, nbytes, data = "unavailable", "unavailable", None
       if path:
           try:
               with open(os.path.expanduser(path), "rb") as f:
                   data = f.read()
               digest, nbytes = hashlib.sha256(data).hexdigest(), str(len(data))
           except OSError:
               pass
       print(harness)
       print(cid if cid else "unavailable")
       print(digest)
       print(nbytes)
       for line in agent_fields(data):
           print(line)

   def slug(p):
       return p.replace("/", "-")

   override = os.environ.get("SIGNOFF_TRANSCRIPT_FILE", "").strip()
   ag_cid = os.environ.get("ANTIGRAVITY_CONVERSATION_ID", "").strip()
   cc_cid = os.environ.get("CLAUDE_CODE_SESSION_ID", "").strip()

   if override:
       emit("generic-file", ag_cid or cc_cid or None, override)
   elif ag_cid:
       emit("antigravity-cli", ag_cid,
            f"~/.gemini/antigravity-cli/brain/{ag_cid}/.system_generated/logs/transcript.jsonl")
   elif cc_cid:
       path = f"~/.claude/projects/{slug(os.getcwd())}/{cc_cid}.jsonl"
       if not os.path.exists(os.path.expanduser(path)):
           # Worktree fallback: session transcripts are keyed to the primary repo root
           try:
               git_dir = subprocess.check_output(
                   ["git", "rev-parse", "--git-common-dir"],
                   text=True, stderr=subprocess.DEVNULL).strip()
               main_root = os.path.abspath(os.path.join(git_dir, os.pardir))
               path = f"~/.claude/projects/{slug(main_root)}/{cc_cid}.jsonl"
           except Exception:
               pass
       emit("claude-code", cc_cid, path)
   else:
       emit("unknown", None, None)
   PY
   DIGEST_STATUS=$?
   { read -r HARNESS_ID; read -r CONV_ID; read -r DIGEST; read -r T_BYTES; \
     read -r AGENT_HVER; read -r AGENT_MODEL; read -r AGENT_REASONING; } < "$TMP_DIGEST_FILE"
   rm -- "$TMP_DIGEST_FILE"
   trap - EXIT INT TERM
   ```
   *Harness storage paths are adapter-owned and non-normative (GSA §3.2); the `claude-code` path slug is the absolute working directory with `/` converted to `-`. When executed inside a linked worktree (per the Worktree Target Mandate), the cwd slug will not match the session's transcript directory, so the adapter falls back to the primary repository root resolved via `git rev-parse --git-common-dir`.*

4. **Construct Flat Git Trailers & Determine Status:**
   Evaluate helper exit status and exact output strictly. No subsequent trailer construction or commit occurs after an error abort:
   ```bash
   if [ $DIGEST_STATUS -ne 0 ]; then
       echo "Error: Digest helper exited non-zero ($DIGEST_STATUS). Aborting signoff." >&2
       exit 1
   elif [[ "$DIGEST" =~ ^[a-f0-9]{64}$ && "$T_BYTES" =~ ^[0-9]+$ ]]; then
       STATUS="VERIFIED_BY_HUMAN"
       TRAILER_DIGEST="sha256:$DIGEST"
   elif [ "$DIGEST" = "unavailable" ] && [ "$T_BYTES" = "unavailable" ]; then
       STATUS="VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST"
       TRAILER_DIGEST="unavailable"
       # REQUIRED ACTION: Present downgraded trailers and request second explicit user confirmation.
       # RE-VERIFY CLEAN STATE: Immediately after second approval, re-run clean-state checks
       # (HEAD == Reviewed-Commit-SHA, git diff --quiet, git diff --cached --quiet). Stop if dirty/stale.
   else
       echo "Error: Unexpected or malformed digest output. Aborting signoff." >&2
       exit 1
   fi
   for v in "$AGENT_HVER" "$AGENT_MODEL" "$AGENT_REASONING"; do
       if ! [[ "$v" =~ ^[A-Za-z0-9._:/-]+$ ]]; then
           echo "Error: Malformed Signoff-Agent provenance field '${v}'. Aborting signoff." >&2
           exit 1
       fi
   done
   ```
   *Status is derived strictly from transcript availability — never set it manually. Write `$HARNESS_ID`, `$CONV_ID`, `$TRAILER_DIGEST`, and `$T_BYTES` into the trailers exactly as emitted by the helper.*

```text
Signoff-Spec-Version: 1.0
Signoff-Status: <STATUS>
Signoff-Timestamp: <ISO-8601 UTC timestamp, e.g. date -u +%Y-%m-%dT%H:%M:%SZ>
Signoff-Base-SHA: <merge-base-sha>
Signoff-Reviewed-Commit-SHA: <reviewed-commit-sha>
Signoff-Reviewed-Tree-SHA: <reviewed-tree-sha>
Signoff-Harness-ID: <HARNESS_ID>
Signoff-Conversation-ID: <CONV_ID>
Signoff-Transcript-Digest: <TRAILER_DIGEST>
Signoff-Transcript-Bytes: <T_BYTES>
Signoff-Tradeoff: <Acknowledged Trade-off 1 or 'none'>
Signoff-Risk: <Acknowledged Risk 1 or 'none'>
Signoff-Verified-By: <Confirmed User Email>
Signoff-Agent: harness=<HARNESS_ID>/<AGENT_HVER> model=<AGENT_MODEL> reasoning=<AGENT_REASONING> interview=<intensity-level>/<profile-id>
```
*Note: For missing/unreadable transcripts, use `Signoff-Status: VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST` with `Signoff-Transcript-Digest: unavailable` and `Signoff-Transcript-Bytes: unavailable`. Repeat `Signoff-Tradeoff:` and `Signoff-Risk:` lines for each acknowledged item; use `none` if empty.*

*`Signoff-Agent` provenance (grammar: [specs/gsa-core.md](specs/gsa-core.md) §2.3): space-separated `key=value` tokens, values matching `[A-Za-z0-9._:/-]+`. When `<AGENT_MODEL>` is `unavailable`, substitute the agent's self-reported model identifier (use `N/A` only if genuinely unknown); keep `<AGENT_HVER>` and `<AGENT_REASONING>` exactly as emitted (`N/A` when the harness exposes none). `<intensity-level>` is the interview level actually run (post-escalation); `<profile-id>` is the `Profile-ID` of the active INTERVIEW PROFILE block.*

### 4. Commit Execution & Integrity Verification

> [!IMPORTANT]
> **Worktree Target Mandate:** If signoff is performed on a feature branch (e.g. via `resolve_branches.py` or `/make-feature`), the empty attestation commit MUST be executed inside `worktree_path` directly on the feature branch before pushing to `origin` and merging. Creating attestation commits on the primary workspace branch (e.g. `main`) is strictly prohibited.

Create an empty attestation commit (`git commit --allow-empty`) with the flat trailer block. Per GSA §2.4, the commit SHOULD be GPG/SSH-signed (`-S`) when a signing key is configured:
```bash
SHORT_SHA=$(git rev-parse --short=7 "<reviewed-commit-sha>")
SIGN_FLAG=""
[ -n "$(git config user.signingkey)" ] && SIGN_FLAG="-S"
git commit --allow-empty $SIGN_FLAG -m "[SIGNOFF ${SHORT_SHA}]: human comprehension and risk attestation

<trailers>"
```
- **Post-Operation Integrity Check:** Verify `git rev-parse HEAD^{tree}` equals `$TREE_SHA` and `git rev-parse HEAD~1` equals `<reviewed-commit-sha>`. If tree or parent changed, declare failure.

After successful execution, report the resulting `Signoff-Attestation-Commit-SHA` (`git rev-parse HEAD`).

### 5. Git Notes Persistence (`refs/notes/signoff`)

Per GSA §2.5, mirror the attestation payload into Git Notes so it survives squash merges and post-merge branch deletion. Attach the full attestation message to both the reviewed commit and its tree:
```bash
ATTESTATION_SHA=$(git rev-parse HEAD)
NOTE_BODY=$(git log -1 --format=%B "$ATTESTATION_SHA")
git notes --ref=signoff append -m "$NOTE_BODY" "<reviewed-commit-sha>"
git notes --ref=signoff append -m "$NOTE_BODY" "$TREE_SHA"
```

When pushing, fetch remote notes into a tracking ref and merge with `cat_sort_uniq` first — fetching directly into the local `refs/notes/signoff` is a non-fast-forward update whenever notes have diverged and is rejected:
```bash
if git fetch origin +refs/notes/signoff:refs/notes/signoff-remote 2>/dev/null; then
    git notes --ref=signoff merge -s cat_sort_uniq refs/notes/signoff-remote
fi
git push origin refs/notes/signoff
```
*The fetch guard tolerates remotes that have no `refs/notes/signoff` yet (first attestation ever pushed).*

---

## Verification & Debugging

To manually verify the harness adapter and transcript digest helper logic across all outcome classes (helper emits exactly 7 lines: harness ID, conversation ID, digest, byte count, harness version, model, reasoning level):

1. **Generic Override (any harness):**
   `SIGNOFF_TRANSCRIPT_FILE="/path/to/transcript" ...`
   - Output: `generic-file` / conversation ID (or `unavailable`) / 64-hex digest / byte count. Status set to `VERIFIED_BY_HUMAN`. Override takes precedence over all harness env vars.

2. **Antigravity CLI:**
   `ANTIGRAVITY_CONVERSATION_ID="<valid-id>" ...`
   - Output: `antigravity-cli` / conversation ID / 64-hex digest / byte count. Status set to `VERIFIED_BY_HUMAN`.

3. **Claude Code:**
   `CLAUDE_CODE_SESSION_ID="<valid-id>" ...`
   - Output: `claude-code` / session ID / 64-hex digest / byte count. Status set to `VERIFIED_BY_HUMAN`.
   - Provenance lines: harness version from `CLAUDE_CODE_VERSION`, model from `ANTHROPIC_MODEL` else the last `"model"` field of the transcript snapshot bytes, reasoning from `CLAUDE_EFFORT`. Unset sources degrade to `N/A` (version, reasoning) or `unavailable` (model).
   - From a linked worktree: the cwd-slug lookup misses, the `git rev-parse --git-common-dir` fallback resolves the primary repository root slug, and the digest still resolves. Outside any git repo, the fallback exception path degrades cleanly to `unavailable`.

4. **Absent / Unreadable Transcript (any adapter):**
   e.g. `ANTIGRAVITY_CONVERSATION_ID="nonexistent" ...`
   - Exit status: `0`
   - Output: harness ID / conversation ID / `unavailable` / `unavailable`. Status set to `VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST` (requires second user confirmation).

5. **No Harness Detected:**
   All adapter env vars unset -> Output: `unknown` / `unavailable` / `unavailable` / `unavailable` / `N/A` / `unavailable` / `N/A`. Downgraded status as in case 4.

6. **Helper / Runtime Failure:**
   Helper exits non-zero -> `exit 1` triggers immediate hard abort. No trailers or commits created.

7. **Malformed Output:**
   Digest fails `^[a-f0-9]{64}$` regex, byte count non-numeric, or any provenance field fails `^[A-Za-z0-9._:/-]+$` (empty output, truncated lines, mixed availability) -> `exit 1` triggers immediate hard abort.

8. **`mktemp` Failure:**
   `mktemp` exits non-zero -> `{ echo ... >&2; exit 1; }` triggers immediate hard abort.

---

## Modifiers
Modifiers select the named interview-intensity level (see Interview Intensity Levels):
- `/signoff`: **standard** intensity (default).
- `/signoff --quick`: **cursory** intensity — subject to the cursory-eligibility guard (auto-escalates to standard on large or high-risk diffs).
- `/signoff --deep`: **skeptical** intensity.
