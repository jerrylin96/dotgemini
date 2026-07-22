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

---

## Workflow

### 1. Context & Range Resolution
1. Resolve reference commit (`<reference-commit>`) and target HEAD commit (`<reviewed-commit-sha>`) using the resolution protocol from **@skill:explain-diff**.
2. Compute explicit merge-base, tree, and parent SHAs:
   ```bash
   BASE_SHA=$(git merge-base "<reference-commit>" "<reviewed-commit-sha>")
   TREE_SHA=$(git rev-parse "<reviewed-commit-sha>^{tree}")
   PARENTS=$(git rev-parse "<reviewed-commit-sha>^@")
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
- **Vague / Hand-waving:** Switch to **@skill:explain-diff** to explain code mechanics, then re-probe with a targeted scenario until mastery is proven.
- **Silent Failures Found:** Instruct adding explicit runtime guards before signoff.

### 3. User Approval & Attestation

1. **Request Explicit User Approval & Commit Choice:**
   Present proposed trade-offs, risks, and `Signoff-Verified-By` email (propose value from `git config user.email`). Present the 3 commit options and require explicit selection:
   - Option 1: Report attestation only (no commit created).
   - Option 2: Amend unpushed commit `<reviewed-commit-sha>` (`git commit --amend`).
   - Option 3: Create a new empty attestation commit (`git commit --allow-empty`).

2. **Verify Clean & Stale-Free State:**
   After receiving initial user approval, re-verify state: current `HEAD` equals `<reviewed-commit-sha>`, no unstaged changes (`git diff --quiet`), and no staged changes (`git diff --cached --quiet`). If dirty or `HEAD` has moved, stop and declare signoff stale.

3. **Compute & Validate Transcript Digest:**
   After recording user confirmation in transcript, execute Python helper via temporary file to reliably capture stdout and exit status:
   ```bash
   TMP_DIGEST_FILE=$(mktemp)
   python3 - <<'PY' > "$TMP_DIGEST_FILE"
   import os, sys, hashlib, re
   cid = os.environ.get("ANTIGRAVITY_CONVERSATION_ID", "").strip()
   if not cid:
       print("unavailable"); sys.exit(0)
   p = os.path.expanduser(f"~/.gemini/antigravity-cli/brain/{cid}/.system_generated/logs/transcript.jsonl")
   try:
       with open(p, "rb") as f:
           h = hashlib.sha256(f.read()).hexdigest()
       print(h if re.match(r"^[a-f0-9]{64}$", h) else "unavailable")
   except OSError:
       print("unavailable")
   PY
   DIGEST_STATUS=$?
   DIGEST=$(tr -d '\r\n' < "$TMP_DIGEST_FILE")
   rm -f "$TMP_DIGEST_FILE"
   ```

4. **Construct Flat Git Trailers & Determine Status:**
   Evaluate helper exit status and normalized output strictly:
   ```bash
   if [ $DIGEST_STATUS -ne 0 ]; then
       # Helper failed non-zero: ABORT signoff immediately. Do not create trailers or commit.
       echo "Error: Digest helper exited non-zero ($DIGEST_STATUS). Aborting signoff."
   elif [[ "$DIGEST" =~ ^[a-f0-9]{64}$ ]]; then
       # Valid 64-char hex digest:
       STATUS="VERIFIED_BY_HUMAN"
       TRAILER_DIGEST="sha256:$DIGEST"
   elif [ "$DIGEST" = "unavailable" ]; then
       # Transcript unavailable/unreadable:
       STATUS="VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST"
       TRAILER_DIGEST="unavailable"
       # REQUIRED ACTION: Present downgraded trailers and request second explicit user confirmation.
       # RE-VERIFY CLEAN STATE: Immediately after second approval, re-run clean-state checks
       # (HEAD == Reviewed-Commit-SHA, git diff --quiet, git diff --cached --quiet). Stop if dirty/stale.
   else
       # Malformed, empty, or unexpected output: ABORT signoff immediately.
       echo "Error: Unexpected digest output '$DIGEST'. Aborting signoff."
   fi
   ```
   *If `ANTIGRAVITY_CONVERSATION_ID` is unset or empty, write `Signoff-Conversation-ID: unavailable`; otherwise write `$ANTIGRAVITY_CONVERSATION_ID`.*

```text
Signoff-Status: <STATUS>
Signoff-Timestamp: <ISO-8601 UTC timestamp, e.g. date -u +%Y-%m-%dT%H:%M:%SZ>
Signoff-Base-SHA: <merge-base-sha>
Signoff-Reviewed-Commit-SHA: <reviewed-commit-sha>
Signoff-Reviewed-Tree-SHA: <reviewed-tree-sha>
Signoff-Conversation-ID: <conversation-id-or-unavailable>
Signoff-Transcript-Digest: <TRAILER_DIGEST>
Signoff-Tradeoff: <Acknowledged Trade-off 1 or 'none'>
Signoff-Risk: <Acknowledged Risk 1 or 'none'>
Signoff-Verified-By: <Confirmed User Email>
Signoff-Agent: <Executing Agent Name> /signoff v1.0
```
*Note: For missing/unreadable transcripts, use `Signoff-Status: VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST` and `Signoff-Transcript-Digest: unavailable`. Repeat `Signoff-Tradeoff:` and `Signoff-Risk:` lines for each acknowledged item; use `none` if empty.*

### 4. Commit Execution & Integrity Verification

Execute the user's selected choice:
- **Option 1 (No Commit):** Present trailers in chat output. Report `Signoff-Attestation-Commit-SHA: none (trailers presented in chat only)`.

- **Option 2 (Amend Unpushed Commit):**
  *Just-in-time publication check:* Immediately before executing `--amend`, determine configured upstream remote:
  ```bash
  REMOTE=$(git config "branch.$(git rev-parse --abbrev-ref HEAD).remote" 2>/dev/null || echo "origin")
  ```
  Run `git fetch --prune "$REMOTE"`.
  - If `git fetch` fails (network/auth error), treat remote status as unverified, block Option 2, and require switching to Option 3 (`--allow-empty`) or Option 1.
  - Run `git branch -r --contains "<reviewed-commit-sha>"`. If `<reviewed-commit-sha>` appears on any remote branch, block `--amend` and require switching to Option 3 (`--allow-empty`) or Option 1.
  - If clean and unpublished, append flat trailer block via `git commit --amend`.
  - *Post-Operation Integrity Check:* Verify `git rev-parse HEAD^{tree}` equals `$TREE_SHA` and `git rev-parse HEAD^@` equals `$PARENTS`. If tree or parents changed, declare failure.

- **Option 3 (Empty Attestation Commit):** Append flat trailer block via `git commit --allow-empty -m "..."`.
  - *Post-Operation Integrity Check:* Verify `git rev-parse HEAD^{tree}` equals `$TREE_SHA` and `git rev-parse HEAD~1` equals `<reviewed-commit-sha>`. If tree or parent changed, declare failure.

After successful execution of Option 2 or Option 3, report the resulting `Signoff-Attestation-Commit-SHA` (`git rev-parse HEAD`).

---

## Verification & Debugging

To manually verify the transcript digest helper logic across all 3 outcome classes:

1. **Valid Readable Transcript:**
   `ANTIGRAVITY_CONVERSATION_ID="<valid-id>" python3 -c "..."`
   - Exit status: `0`
   - Output: 64-character lowercase hex digest. Status set to `VERIFIED_BY_HUMAN`.

2. **Absent / Unreadable Transcript:**
   `ANTIGRAVITY_CONVERSATION_ID="nonexistent" python3 -c "..."`
   - Exit status: `0`
   - Output: `unavailable`. Status set to `VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST` (requires second user confirmation).

3. **Helper / Runtime Failure:**
   `python3 -c "import sys; sys.exit(1)"`
   - Exit status: `1` (non-zero)
   - Status: Signoff aborts immediately. No trailers or commits created.

---

## Modifiers
- `/signoff`: Standard audit (4 axes).
- `/signoff --quick`: Streamlined 2-probe audit for small diffs.
- `/signoff --deep`: Intensive boundary & trade-off audit.
