---
name: signoff
description: Socratic reverse-interview to verify human comprehension, domain risk awareness, and explicit accountability for branch diffs before merging.
---

# /signoff: Human Comprehension & Accountability Verification

## Core Philosophy
Audit human understanding and conscious risk acceptance. Prevent cognitive surrender (rubber-stamping AI diffs).
Human owns results, trade-offs, and failure modes.

Agent role: Socratic interrogator, not dogmatic gatekeeper.
Intentional trade-offs (e.g. surrogates violating exact domain laws for speed) pass if human explicitly understands boundaries and risks.

---

## Workflow

### 1. Diff Analysis
Inspect `git diff`. Identify:
- Core mechanisms, governing constraints, model assumptions, or approximations.
- Deviations from exact contracts, baseline laws, or standards.
- Unhandled silent failure paths (NaNs, un-checked boundaries).

### 2. Socratic Interview Loop (1-2 Probes / Turn)
Interrogate user across 4 core axes:
1. **Mechanics & Intent:** Explain what changed and why this specific design was chosen.
2. **Deviations & Trade-offs:** Identify approximations or relaxed constraints; verify if intentional and acceptable.
3. **Failure Boundaries & Observability:** Define input/operating limits where code fails/drifts. Ensure failures happen **loudly** (explicit assertions/guards) in dev/test, not silently in production.
4. **Ownership:** Confirm explicit accountability for results and risks.

**Evaluation & Remediation:**
- **Vague / Hand-waving:** Switch to `explain-diff` mode to explain code mechanics, then re-probe with a targeted scenario until mastery is proven.
- **Silent Failures Found:** Instruct adding explicit runtime guards before signoff.

### 3. Attestation Trailer
Once satisfied, offer to stage/commit with trailer:

```text
Signoff-Attestation:
  Status: VERIFIED_BY_HUMAN
  Timestamp: <ISO-8601>
  Acknowledged-Tradeoffs: ["<Tradeoff 1>"]
  Acknowledged-Risks: ["<Risk 1>"]
  Verified-By: <User Email>
  Agent: Antigravity /signoff v1.0
```

---

## Modifiers
- `/signoff`: Standard audit (4 axes).
- `/signoff --quick`: Streamlined 2-probe audit for small diffs.
- `/signoff --deep`: Intensive boundary & trade-off audit.
