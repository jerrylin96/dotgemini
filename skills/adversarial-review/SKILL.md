---
name: adversarial-review
description: Adversarial review and diff explanation of two git worktrees.
---

# Adversarial Review and Diff Explanation

Compare active worktree/branch with target worktree/branch.

## Context Resolution
1. Read user input arguments for two branch/worktree references (e.g., `/adversarial-review branch-a branch-b`).
2. If arguments are missing:
   - Run `git worktree list` or `git branch -a` to discover active refs.
   - Ask user to specify refs to compare.

## Execution Steps
1. Run `git diff <ref_1>..<ref_2>` to extract change set.
2. Analyze diff from adversarial perspective:
   - Identify bugs, edge cases, regression risk, performance issues.
   - Explain logical differences.
3. Print the review report directly to the chat interface (to avoid cluttering the filesystem) unless the user explicitly requests saving it to a file.
