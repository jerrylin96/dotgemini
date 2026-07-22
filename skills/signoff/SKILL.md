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
- **Vague / Hand-waving:** Switch to **@skill:explain-diff** to explain code mechanics, then re-probe with a targeted scenario until mastery is proven.
- **Silent Failures Found:** Instruct adding explicit runtime guards before signoff.

### 3. User Approval & Attestation

1. **Request Explicit User Approval & Commit Choice:**
   Present the proposed trade-offs, risks, and `Signoff-Verified-By` email (propose value from `git config user.email`). Present the 3 commit options and require explicit selection:
   - Option 1: Report attestation only (no commit).
   - Option 2: Amend unpushed commit `<reviewed-commit-sha>` (`git commit --amend`).
   - Option 3: Create a new empty attestation commit (`git commit --allow-empty`).

2. **Verify Clean & Stale-Free State:**
   After receiving user approval, re-verify state: current `HEAD` equals `<reviewed-commit-sha>`, no unstaged changes (`git diff --quiet`), and no staged changes (`git diff --cached --quiet`). If dirty or `HEAD` has moved, stop and declare signoff stale.

3. **Compute Transcript Digest:**
   After recording user confirmation in transcript, compute SHA-256 digest:
   ```bash
   CID="${ANTIGRAVITY_CONVERSATION_ID}"
   TPATH="$HOME/.gemini/antigravity-cli/brain/$CID/.system_generated/logs/transcript.jsonl"
   DIGEST=$(python3 -c "import os, sys, hashlib; p=sys.argv[1]; print(hashlib.sha256(open(p,'rb').read()).hexdigest() if os.path.isfile(p) and os.access(p, os.R_OK) else 'unavailable')" "$TPATH")
   ```

4. **Construct Flat Git Trailers:**
   - If `$DIGEST` is a valid 64-char hex, write `Signoff-Transcript-Digest: sha256:<hex-digest>`.
   - If `$DIGEST` is `unavailable` or `$CID` is unset, write `Signoff-Transcript-Digest: unavailable` (no `sha256:` prefix) and `Signoff-Conversation-ID: unavailable` (if `$CID` is unset).

```text
Signoff-Status: VERIFIED_BY_HUMAN
Signoff-Timestamp: <ISO-8601 UTC date -u +%Y-%m-%dT%H:%M:%SZ>
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
*Note: For an unavailable digest, use `Signoff-Transcript-Digest: unavailable`. Repeat `Signoff-Tradeoff:` and `Signoff-Risk:` lines for each acknowledged item; use `none` if empty.*

### 4. Commit Execution & Reporting

Execute the user's selected choice:
- **Option 1 (No Commit):** Display the attestation trailers in chat output.
- **Option 2 (Amend Unpushed Commit):** Append trailers to `<reviewed-commit-sha>` via `git commit --amend`. Require that tree SHA and parents remain unchanged.
- **Option 3 (Empty Attestation Commit):** Create a new commit via `git commit --allow-empty -m "..."` with trailers.

After execution, report the resulting `Signoff-Attestation-Commit-SHA` (`git rev-parse HEAD`).

---

## Modifiers
- `/signoff`: Standard audit (4 axes).
- `/signoff --quick`: Streamlined 2-probe audit for small diffs.
- `/signoff --deep`: Intensive boundary & trade-off audit.
