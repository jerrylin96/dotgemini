---
name: signoff
description: Verify human comprehension and risk ownership for an exact approved Git state without mutating history.
---

# Signoff

Human owns results, tradeoffs, and failure modes. Act as Socratic interrogator, not rubber-stamp gatekeeper.

## Preconditions

Require approved independent review and explicit human diff-review acknowledgement. Record base SHA, reviewed commit SHA, and tree SHA. Confirm clean index/worktree and remote feature branch at reviewed SHA. Stop stale if any differ.

## Interview

Ask one or two probes per turn across:

1. Mechanics and intent: what changed and why this design.
2. Deviations and tradeoffs: approximations, relaxed constraints, rejected alternatives.
3. Failure boundaries and observability: limits, failure modes, guards, and monitoring.
4. Ownership: explicit acceptance of results and risks.

Vague answers trigger targeted `explain-diff`, then re-probe. Silent failure paths require builder remediation and fresh review before signoff.

## Attestation

After explicit approval, recheck clean state and all SHAs immediately. Produce report-only attestation containing status, UTC timestamp, base/commit/tree SHAs, session ID when available, optional SHA-256 digest of exact exported session bytes, accepted tradeoffs, risks, and human-confirmed identity.

Session digest is audit correlation, not proof of legal identity. If unavailable, record `unavailable`; never imply cryptographic identity verification. Do not amend commits, create empty commits, push, create PR, or merge.
