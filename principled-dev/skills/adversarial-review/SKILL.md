---
name: adversarial-review
description: Independently review an exact Git changeset for evidence-backed blocking defects before publication.
---

# Adversarial Review

Review branch, remote-qualified ref, PR/MR, commit, or range. Compare immutable SHAs with merge-base semantics.

## Resolve

1. Resolve base and target refs to exact commit SHAs. An explicit user target satisfies selection; otherwise present candidates and ask.
2. Surface fetch failures and stale-ref risk. PR head fetch failure is fatal.
3. Create or refresh a detached disposable review worktree at target SHA. Never use writable feature worktree for reviewer execution.
4. Read commit-bound manifest first when available.

## Inspect

- Save large diffs to session-specific scratch and read completely; use null-delimited name status for unusual paths and renames. See `diff-safety.md`.
- Run project-native tests, lint, and builds only when safe. Never install or execute untrusted dependencies without approval. Mark unavailable checks `unverified`.
- Review correctness, regressions, failure handling, tests, security, performance, architecture, docs, and project-specific risks.
- Every finding must include severity, exact path/line, exact evidence, consequence, and remediation. No speculative findings.
- Do not edit. Reviewer reports; builder fixes in durable feature worktree.

## Verdict

Return `APPROVE`, `REQUEST_CHANGES`, or `BLOCKED`, bound to base SHA, target commit SHA, and target tree SHA.

- Any `CRITICAL` or `IMPORTANT` finding requires `REQUEST_CHANGES`.
- `SUGGESTION` and `FYI` may remain with rationale.
- Missing independent reviewer capability requires `BLOCKED`.
- Any new commit makes verdict stale and requires a fresh reviewer context.

Report validation output, unverified checks, fetch freshness, and all findings. Stop after final report.
