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

### 2. Socratic Interview Loop (1-2 Probes / Turn)
Interrogate user across 4 core axes:
1. **Mechanics & Intent:** Explain what changed and why this specific design was chosen.
2. **Deviations & Trade-offs:** Identify approximations or relaxed constraints; verify if intentional and acceptable.
3. **Failure Boundaries & Observability:** Define input/operating limits where code fails/drifts. Ensure failures happen **loudly** (explicit assertions/guards) in dev/test, not silently in production.
4. **Ownership:** Confirm explicit accountability for results and risks.

**Evaluation & Remediation:**
- **Uncertainty / Vague / Hand-waving:** If the user expresses uncertainty ("not sure", "don't know") OR gives vague/hand-waving answers, the agent MUST pause signoff, explain the mechanics and boundaries via **@skill:explain-diff**, and re-probe with a scenario before requesting approval.
- **Silent Failures Found:** Instruct adding explicit runtime guards before signoff.

### 3. User Approval & Attestation

> [!NOTE]
> **Scratchpad Lifecycle Sync (make-feature Phase 4, Step 8)**: If `<appDataDir>/brain/<conversation-id>/scratch/scratchpad.md` exists, ensure it is updated pre-signoff with final completion status, matching Step 8 in [make-feature](../make-feature/SKILL.md). If the scratchpad file does not exist (e.g. post-Phase-4 cleanup or standalone `/signoff` execution), skip this step rather than recreating it.

1. **Request Explicit User Approval:**
   Present proposed trade-offs, risks, and `Signoff-Verified-By` email (propose value from `git config user.email`). Confirm user readiness to proceed with empty attestation commit (`git commit --allow-empty`).

2. **Verify Clean & Stale-Free State:**
   After receiving initial user approval, re-verify state: current `HEAD` equals `<reviewed-commit-sha>`, no unstaged changes (`git diff --quiet`), and no staged changes (`git diff --cached --quiet`). If dirty or `HEAD` has moved, stop and declare signoff stale.

3. **Resolve Harness Adapter & Capture Transcript Snapshot:**
   After recording user confirmation in transcript, resolve the active harness adapter and capture the transcript snapshot (SHA256 digest + exact byte count) immediately before the commit, per GSA snapshot timing rules ([specs/gsa-core.md](specs/gsa-core.md) §2.3). Resolution order: `SIGNOFF_TRANSCRIPT_FILE` explicit override → `ANTIGRAVITY_CONVERSATION_ID` → `CLAUDE_CODE_SESSION_ID`. Execute the Python helper via temporary file with explicit trap cleanup:
   ```bash
   TMP_DIGEST_FILE=$(mktemp) || { echo "Error: mktemp failed. Aborting signoff." >&2; exit 1; }
   trap 'rm -f -- "$TMP_DIGEST_FILE"' EXIT INT TERM

   python3 - <<'PY' > "$TMP_DIGEST_FILE"
   import hashlib, os, subprocess

   def emit(harness, cid, path):
       digest, nbytes = "unavailable", "unavailable"
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
   { read -r HARNESS_ID; read -r CONV_ID; read -r DIGEST; read -r T_BYTES; } < "$TMP_DIGEST_FILE"
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
Signoff-Agent: <agent-name-and-model>
```
*Note: For missing/unreadable transcripts, use `Signoff-Status: VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST` with `Signoff-Transcript-Digest: unavailable` and `Signoff-Transcript-Bytes: unavailable`. Repeat `Signoff-Tradeoff:` and `Signoff-Risk:` lines for each acknowledged item; use `none` if empty.*

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

To manually verify the harness adapter and transcript digest helper logic across all outcome classes (helper emits exactly 4 lines: harness ID, conversation ID, digest, byte count):

1. **Generic Override (any harness):**
   `SIGNOFF_TRANSCRIPT_FILE="/path/to/transcript" ...`
   - Output: `generic-file` / conversation ID (or `unavailable`) / 64-hex digest / byte count. Status set to `VERIFIED_BY_HUMAN`. Override takes precedence over all harness env vars.

2. **Antigravity CLI:**
   `ANTIGRAVITY_CONVERSATION_ID="<valid-id>" ...`
   - Output: `antigravity-cli` / conversation ID / 64-hex digest / byte count. Status set to `VERIFIED_BY_HUMAN`.

3. **Claude Code:**
   `CLAUDE_CODE_SESSION_ID="<valid-id>" ...`
   - Output: `claude-code` / session ID / 64-hex digest / byte count. Status set to `VERIFIED_BY_HUMAN`.
   - From a linked worktree: the cwd-slug lookup misses, the `git rev-parse --git-common-dir` fallback resolves the primary repository root slug, and the digest still resolves. Outside any git repo, the fallback exception path degrades cleanly to `unavailable`.

4. **Absent / Unreadable Transcript (any adapter):**
   e.g. `ANTIGRAVITY_CONVERSATION_ID="nonexistent" ...`
   - Exit status: `0`
   - Output: harness ID / conversation ID / `unavailable` / `unavailable`. Status set to `VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST` (requires second user confirmation).

5. **No Harness Detected:**
   All adapter env vars unset -> Output: `unknown` / `unavailable` / `unavailable` / `unavailable`. Downgraded status as in case 4.

6. **Helper / Runtime Failure:**
   Helper exits non-zero -> `exit 1` triggers immediate hard abort. No trailers or commits created.

7. **Malformed Output:**
   Digest fails `^[a-f0-9]{64}$` regex or byte count non-numeric (empty output, truncated lines, mixed availability) -> `exit 1` triggers immediate hard abort.

8. **`mktemp` Failure:**
   `mktemp` exits non-zero -> `{ echo ... >&2; exit 1; }` triggers immediate hard abort.

---

## Modifiers
- `/signoff`: Standard audit (4 axes).
- `/signoff --quick`: Streamlined 2-probe audit for small diffs.
- `/signoff --deep`: Intensive boundary & trade-off audit.
