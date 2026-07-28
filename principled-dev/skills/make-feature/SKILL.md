---
name: make-feature
description: Run a human-gated feature lifecycle using separate durable feature and disposable review Git worktrees.
---

# Make Feature

Use for every repository code or configuration change. Never modify the primary checkout.

## Gates

1. **Specification:** clarify requirements, write measurable acceptance criteria, and pause for explicit human approval. Do not plan first.
2. **Plan:** inspect code read-only, define small ordered tasks and verification. Behavioral tasks require RED/GREEN targets; static changes require fitting validation. Pause for separate approval.
3. **Build:** resolve exact base SHA and create an attached `agent/<feature>` branch in a durable managed worktree. Edit, test, and commit only there. Never reset or force-remove a dirty feature worktree.
4. **Manifest:** record summary, tests, risks, base SHA, commit SHA, tree SHA, and diff digest. Pause for approval. Any state change makes approval stale.
5. **Review:** create a separate detached disposable worktree at exact commit. Delegate to a fresh independent reviewer following `adversarial-review`. Reviewer is read-only; builder fixes findings in feature worktree, commits, and requests fresh review. `CRITICAL` and `IMPORTANT` block approval.
6. **Publish:** only after `APPROVE`, recheck clean state and exact reviewed SHA, push that SHA to configured upstream (fallback `origin`), then verify remote SHA. Never create a PR.
7. **Human review:** present branch, diff, evidence, risks, and non-blocking findings. Pause for explicit acknowledgement.
8. **Signoff:** follow `signoff`; do not mutate Git history.
9. **Integration:** human creates PR and merges. Remove clean feature worktree only after confirmed merge or explicit abandonment; prune disposable review cache separately.

## Bootstrap From Primary Checkout

Before the feature worktree exists, keep specification and plan files under the resolved `<state-root>/artifacts/` directory and use direct helper commands from the repository root to record and approve each gate, then create the worktree. Use absolute paths for the helper and artifact files. Global installations normally use `$HOME/.agents/plugins/principled-dev/scripts/principled_dev.py`; resolve `$HOME` before invoking the shell tool.

```sh
python3 /absolute/path/to/principled_dev.py --repo . --feature agent/<feature> record-artifact spec /absolute/state-root/artifacts/spec.md
python3 /absolute/path/to/principled_dev.py --repo . --feature agent/<feature> approve spec
python3 /absolute/path/to/principled_dev.py --repo . --feature agent/<feature> record-artifact plan /absolute/state-root/artifacts/plan.md
python3 /absolute/path/to/principled_dev.py --repo . --feature agent/<feature> approve plan
python3 /absolute/path/to/principled_dev.py --repo . feature agent/<feature> --base <base>
```

The hook denies primary-checkout edits, ordinary shell calls, wrappers, and compound commands during bootstrap. After feature creation, resume goose from the returned worktree path.

## Hard Rules

- If independent review cannot run, status is `BLOCKED`, never self-approved.
- Fetch failures block feature creation unless human explicitly accepts stale/offline base.
- Any moved HEAD, changed tree, dirty worktree, changed artifact digest, or remote mismatch invalidates dependent approvals.
- Agent may sync/rebase feature branch inside feature worktree, but this requires fresh manifest, review, publication, and signoff.
- Human alone owns PR creation and integration-branch merge.
