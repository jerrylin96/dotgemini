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
   After recording user confirmation in transcript, compute SHA-256 digest using Python heredoc:
   ```bash
   DIGEST=$(python3 - <<'PY'
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
   )
   ```

4. **Construct Flat Git Trailers & Determine Status:**
   - If `$DIGEST` is a valid 64-char hex:
     - Set `Signoff-Status: VERIFIED_BY_HUMAN`
     - Set `Signoff-Transcript-Digest: sha256:<hex-digest>`
   - If `$DIGEST` is `unavailable`:
     - Set `Signoff-Status: VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST`
     - Set `Signoff-Transcript-Digest: unavailable`
     - **Required Action:** Present downgraded trailers and request a second explicit user confirmation before committing.
     - **Re-verify Clean State:** Immediately after second approval, re-run clean-state checks (`HEAD == Reviewed-Commit-SHA`, `git diff --quiet`, `git diff --cached --quiet`). Stop if dirty or stale.
   - If `$DIGEST` is neither 64-char hex nor `unavailable`, or command exits non-zero: **ABORT signoff immediately** without creating trailers or committing.
   - If `ANTIGRAVITY_CONVERSATION_ID` is unset or empty, write `Signoff-Conversation-ID: unavailable`; otherwise write `$ANTIGRAVITY_CONVERSATION_ID`.

```text
Signoff-Status: VERIFIED_BY_HUMAN
Signoff-Timestamp: <ISO-8601 UTC timestamp, e.g. date -u +%Y-%m-%dT%H:%M:%SZ>
Signoff-Base-SHA: <merge-base-sha>
Signoff-Reviewed-Commit-SHA: <reviewed-commit-sha>
Signoff-Reviewed-Tree-SHA: <reviewed-tree-sha>
Signoff-Conversation-ID: <conversation-id-or-unavailable>
Signoff-Transcript-Digest: sha256:<hex-digest>
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

## Modifiers
- `/signoff`: Standard audit (4 axes).
- `/signoff --quick`: Streamlined 2-probe audit for small diffs.
- `/signoff --deep`: Intensive boundary & trade-off audit.
