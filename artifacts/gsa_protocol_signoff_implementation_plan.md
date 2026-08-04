# Implementation Plan: Git Signoff Attestation (GSA) Protocol Upgrade for `signoff`

## Goal Description
Upgrade the `signoff` skill (`skills/signoff/SKILL.md`) to comply with the **Git Signoff Attestation (GSA) Protocol v3.1.1** specification. This establishes a portable, harness-agnostic attestation format with v1.0 flat Git trailers, dual persistence across empty attestation commits and Git Notes (`refs/notes/signoff`), tracking-ref concurrency merge handling (`cat_sort_uniq`), synchronous transcript byte/digest snapshots, and automated reference test assertions.

## User Review Required

> [!IMPORTANT]
> **Dual Persistence & Concurrency Strategy:**
> Signoff attestations will be recorded as empty commits (`git commit --allow-empty [-S]`) AND attached to Git Notes (`refs/notes/signoff`) on both reviewed commit and tree SHAs. To prevent non-fast-forward push rejections in multi-developer environments, remote notes are fetched into a tracking ref (`refs/notes/signoff-remote`) before merging locally via `cat_sort_uniq`.

> [!NOTE]
> **Deterministic Status Enforcement:**
> `Signoff-Status` cannot be manually set; it is strictly derived based on transcript availability (`VERIFIED_BY_HUMAN` when digest is resolved, `VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST` when transcript is missing/unreadable and acknowledged by user).

## Scope Note: Phase 1 (Skill-Level Compliance)

This plan implements **Phase 1**: skill-level GSA trailer, adapter, and Git Notes compliance, enforced by agent instructions. The `signoff-mcp` server, programmatic `TranscriptProvider` implementations, and the server-side `ack_no_transcript` circuit breaker (GSA spec §4) are deferred to a later phase — a prompt-driven skill cannot host server-side status enforcement, so those guarantees are out of scope here.

## Open Questions

None at this time. The protocol spec (`v3.1.1`) defines all metadata fields, adapter interfaces, and error handling rules.

---

## Proposed Changes

### `signoff` Skill & Protocol Core

#### [EXISTING — NO CHANGES] `skills/signoff/specs/gsa-core.md`
- Canonical GSA Protocol Core v3.1.1 specification already exists on this branch (reviewed and approved); do not regenerate or modify it.
- Documents GSA metadata schema, status derivation logic, snapshot timing, harness adapter reference matrix (`AntigravityAdapter`, `ClaudeCodeAdapter`, `GenericFileAdapter`), and Git Notes persistence.

#### [MODIFY] `skills/signoff/SKILL.md`
- Update header to reference `specs/gsa-core.md`.
- Expand context & range resolution to record `Signoff-Spec-Version: 1.0`, `Signoff-Harness-ID`, `Signoff-Transcript-Bytes`, and exact base/reviewed commit/tree SHAs.
- Replace the Antigravity-only digest helper with portable harness adapter resolution (the core portability deliverable). Resolution order: `SIGNOFF_TRANSCRIPT_FILE` explicit override (`generic-file`) → `ANTIGRAVITY_CONVERSATION_ID` (`antigravity-cli`) → `CLAUDE_CODE_SESSION_ID` (`claude-code`, path slug = absolute cwd with `/` → `-`) → `unknown`. The helper emits harness ID, conversation ID, SHA256 digest, and exact byte count (`Signoff-Transcript-Bytes`) as a snapshot at commit time.
- Add signed attestation commit support per spec §2.4: `git commit -S --allow-empty` when `git config user.signingkey` is set.
- Update trailer schema to include all v1.0 standard fields:
  ```text
  Signoff-Spec-Version: 1.0
  Signoff-Status: <STATUS>
  Signoff-Timestamp: <ISO-8601 UTC timestamp>
  Signoff-Base-SHA: <merge-base-sha>
  Signoff-Reviewed-Commit-SHA: <reviewed-commit-sha>
  Signoff-Reviewed-Tree-SHA: <reviewed-tree-sha>
  Signoff-Harness-ID: <harness-id>
  Signoff-Conversation-ID: <conversation-id-or-unavailable>
  Signoff-Transcript-Digest: <transcript-digest-or-unavailable>
  Signoff-Transcript-Bytes: <byte-count-or-unavailable>
  Signoff-Tradeoff: <item-1>
  Signoff-Risk: <item-1>
  Signoff-Verified-By: <user-email>
  Signoff-Agent: <agent-name-and-model>
  ```
- Add Git Notes persistence commands (`git notes --ref=signoff add ...`) targeting both `<reviewed-commit-sha>` and `<reviewed-tree-sha>`.
- Add tracking-ref concurrency merge handling for pushing Git Notes:
  ```bash
  git fetch origin +refs/notes/signoff:refs/notes/signoff-remote
  git notes --ref=signoff merge -s cat_sort_uniq refs/notes/signoff-remote
  git push origin refs/notes/signoff
  ```

---

### Test Suite & Reference Validation

#### [MODIFY] `scripts/tests/test_skill_references.py`
- Add `test_signoff_gsa_protocol_spec_and_trailers()`:
  - Assert canonical spec file `skills/signoff/specs/gsa-core.md` exists.
  - Assert `skills/signoff/specs/gsa-core.md` contains `Protocol Specification`, `Cryptographic Developer Identity Binding`, `cat_sort_uniq`, and `ack_no_transcript`.
  - Assert `skills/signoff/SKILL.md` contains `Signoff-Spec-Version: 1.0`, `Signoff-Harness-ID`, `Signoff-Transcript-Bytes`, `refs/notes/signoff`, `refs/notes/signoff-remote`, and `cat_sort_uniq`.
  - Assert portable adapter resolution env vars (`SIGNOFF_TRANSCRIPT_FILE`, `ANTIGRAVITY_CONVERSATION_ID`, `CLAUDE_CODE_SESSION_ID`) and signed-commit support (`user.signingkey`) are present in `skills/signoff/SKILL.md`.

---

## Verification Plan

### Automated Tests
Run pytest via the isolated virtual environment test runner helper:
```bash
python3 ~/.gemini/scripts/run_in_env.py <workspace_path> pytest scripts/tests/test_skill_references.py
```

### Manual Verification
1. Inspect markdown formatting and links in `skills/signoff/specs/gsa-core.md` and `skills/signoff/SKILL.md`.
2. Verify all `@skill` cross-references resolve cleanly using `test_all_skill_references_resolve`.
