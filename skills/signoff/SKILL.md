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
1. Resolve baseline reference SHA (`<reference_commit>`) and target HEAD SHA (`<target_commit>`) using the branch/PR resolution protocol from **@skill:explain-diff**.
2. Inspect the explicit merge-base range: `git diff "<reference_commit>...<target_commit>"`.
3. Record `Base-SHA` and `Target-SHA` for the attestation record.

### 2. Socratic Interview Loop (1-2 Probes / Turn)
Interrogate user across 4 core axes:
1. **Mechanics & Intent:** Explain what changed and why this specific design was chosen.
2. **Deviations & Trade-offs:** Identify approximations or relaxed constraints; verify if intentional and acceptable.
3. **Failure Boundaries & Observability:** Define input/operating limits where code fails/drifts. Ensure failures happen **loudly** (explicit assertions/guards) in dev/test, not silently in production.
4. **Ownership:** Confirm explicit accountability for results and risks.

**Evaluation & Remediation:**
- **Vague / Hand-waving:** Switch to **@skill:explain-diff** to explain code mechanics, then re-probe with a targeted scenario until mastery is proven.
- **Silent Failures Found:** Instruct adding explicit runtime guards before signoff.

### 3. Attestation & Commit Execution

1. **Verify Unchanged State:** Ensure current `HEAD` matches `<target_commit>`. If diff changed, stop and declare signoff stale.
2. **Transcript Digest:** Compute transcript hash up to current turn using portable Python one-liner:
   ```bash
   CID="${ANTIGRAVITY_CONVERSATION_ID}"
   TPATH="$HOME/.gemini/antigravity-cli/brain/$CID/.system_generated/logs/transcript.jsonl"
   python3 -c "import os, sys, hashlib; p=sys.argv[1]; print('sha256:' + hashlib.sha256(open(p,'rb').read()).hexdigest() if os.path.exists(p) else 'unavailable')" "$TPATH"
   ```
   *If `ANTIGRAVITY_CONVERSATION_ID` is unset or file is missing, set digest to `unavailable` with explicit notice.*
3. **User Approval & Attestation:** Present completed trailers and request explicit user confirmation before committing:

```text
Signoff-Status: VERIFIED_BY_HUMAN
Signoff-Timestamp: <ISO-8601 UTC>
Signoff-Base-SHA: <reference_commit>
Signoff-Target-SHA: <target_commit>
Signoff-Conversation-ID: <conversation-id>
Signoff-Transcript-Digest: sha256:<hash>
Signoff-Tradeoff: <Acknowledged Trade-off>
Signoff-Risk: <Acknowledged Risk>
Signoff-Verified-By: <git config user.email>
Signoff-Agent: Antigravity /signoff v1.0
```
4. Append flat trailer block to the bottom of the commit message body.

---

## Modifiers
- `/signoff`: Standard audit (4 axes).
- `/signoff --quick`: Streamlined 2-probe audit for small diffs.
- `/signoff --deep`: Intensive boundary & trade-off audit.
