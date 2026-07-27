---
name: explain-diff
description: Interactively explain an exact Git changeset neutrally with verbatim hunk walkthroughs.
---

# Explain Diff

Explain what changed without judging quality or hunting bugs. If user requests review, switch to `adversarial-review`.

## Resolve

Accept branch, remote ref, PR/MR, commit, or range. Resolve immutable base and target SHAs. Ask user when target is ambiguous. Branch/PR mode may fetch refs and create a detached disposable context worktree; source files remain read-only. Surface stale-fetch warnings.

## Walkthrough

1. Capture complete diff safely using `adversarial-review/diff-safety.md`.
2. Present short overall summary: purpose inferred from code/history, logical themes, file count, insertions, and deletions.
3. Present numbered file menu with path, `+/-`, hunk count, and gist. Include `[a]` all, `[s]` expanded summary, `[q]` finish. Pause for selection.
4. For selected file, quote every hunk byte-for-byte in fenced `diff` blocks, then explain what changed, likely why, and connections to other hunks. Highlight precise inline text replacements.
5. Invite questions about callers, history, prior behavior, or related files. Re-present abbreviated menu and continue until user finishes.

Do not run tests or linters, edit source, or save a report unless requested. Scratch files and disposable context worktrees are allowed side effects.
