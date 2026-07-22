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
1. Resolve reference commit (`<reference_commit>`) and target HEAD commit (`<target_commit>`) using the resolution protocol from **@skill:explain-diff**.
2. Compute the explicit merge-base:
   ```bash
   BASE_SHA=$(git merge-base "<reference_commit>" "<target_commit>")
   ```
3. Record `Base-SHA` (`$BASE_SHA`) and `Target-SHA` (`<target_commit>`) for the attestation record.
4. Inspect the range diff `git diff "$BASE_SHA...<target_commit>"` to analyze core mechanisms, contract deviations, and silent failure paths prior to starting the interview.

### 2. Socratic Interview Loop (1-2 Probes / Turn)
Interrogate user across 4 core axes:
1. **Mechanics & Intent:** Explain what changed and why this specific design was chosen.
2. **Deviations & Trade-offs:** Identify approximations or relaxed constraints; verify if intentional and acceptable.
3. **Failure Boundaries & Observability:** Define input/operating limits where code fails/drifts. Ensure failures happen **loudly** (explicit assertions/guards) in dev/test, not silently in production.
4. **Ownership:** Confirm explicit accountability for results and risks.

**Evaluation & Remediation:**
- **Vague / Hand-waving:** Switch to **@skill:explain-diff** to explain code mechanics, then re-probe with a targeted scenario until mastery is proven.
- **Silent Failures Found:** Instruct adding explicit runtime guards before signoff.

### 3. Attestation & Verification

1. **Verify Clean & Stale-Free State:**
   Ensure current `HEAD` equals `<target_commit>`, no unstaged changes exist (`git diff --quiet`), and no staged changes exist (`git diff --cached --quiet`). If dirty or `HEAD` has moved, stop and declare signoff stale.
2. **Transcript Digest:** Compute transcript hash up to current turn using portable Python one-liner:
   ```bash
   CID="${ANTIGRAVITY_CONVERSATION_ID}"
   TPATH="$HOME/.gemini/antigravity-cli/brain/$CID/.system_generated/logs/transcript.jsonl"
   DIGEST=$(python3 -c "import os, sys, hashlib; p=sys.argv[1]; print(hashlib.sha256(open(p,'rb').read()).hexdigest() if os.path.isfile(p) else 'unavailable')" "$TPATH")
   ```
   *If `$DIGEST` is `unavailable`, set `Signoff-Transcript-Digest: unavailable` (no `sha256:` prefix) and note why in the summary.*
3. **User Approval & Attestation:** Present completed trailers and request explicit user confirmation for `Signoff-Verified-By` and final commit:

```text
Signoff-Status: VERIFIED_BY_HUMAN
Signoff-Timestamp: <ISO-8601 UTC>
Signoff-Base-SHA: <merge_base_sha>
Signoff-Target-SHA: <target_commit_sha>
Signoff-Conversation-ID: <conversation-id>
Signoff-Transcript-Digest: sha256:<hex_digest_or_unavailable>
Signoff-Tradeoff: <Acknowledged Trade-off 1 or 'none'>
Signoff-Risk: <Acknowledged Risk 1 or 'none'>
Signoff-Verified-By: <Confirmed User Email>
Signoff-Agent: <Executing Agent Name> /signoff v1.0
```
*Note: Repeat `Signoff-Tradeoff:` and `Signoff-Risk:` lines for each acknowledged item. Use `none` if empty.*

### 4. Commit Execution
Present the execution choice to the user:
- **Unpushed Branch (Default):** Amend the target commit (`git commit --amend`).
- **Published / Pushed Branch:** Create an empty attestation commit (`git commit --allow-empty`) to avoid rewriting published history.

Append the flat block of `Signoff-*` trailers to the bottom of the commit message body.

---

## Modifiers
- `/signoff`: Standard audit (4 axes).
- `/signoff --quick`: Streamlined 2-probe audit for small diffs.
- `/signoff --deep`: Intensive boundary & trade-off audit.
