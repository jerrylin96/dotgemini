---
name: make-feature
description: Creates a feature branch (always prefixed with gemini/) and isolated git worktree. Mandatory entry point for ALL codebase changes — use whenever developing features, fixing bugs, or editing files.
---

# Isolated Feature Branch Development via Git Worktree

Use this skill for **all codebase changes** — features, bug fixes, config edits, skill modifications. Changes are pushed to a remote feature branch without mutating the user's active branch checkout.

## When to Use

- **Always.** This is the mandatory entry point for any file modification in a repository.
- The only exception: changes to Antigravity artifacts, scratch files, or non-repo files.

## Core Rules
> [!IMPORTANT]
> - **Branch Naming**: Always prefix the feature branch with `gemini/` (e.g., `gemini/feature-name`).
> - **No Primary Branch Pollution**: Never run `git checkout -b` or modify files directly in the user's primary repository working directory. Always use a worktree.
> - **Worktree Cleanup**: Once the branch has been successfully pushed to the remote repository, prune/delete the worktree to save disk space and keep the workspace clean.

## Milestone Phase Goals & Gate Enforcement

> [!CAUTION]
> **Pre-Execution Worktree Circuit Breaker (Hard Stop)**:
> Before calling any file edit tool (`replace_file_content`, `write_to_file`, etc.) on a repository file, verify `TargetFile` is under `~/.gemini/tmp/worktrees/`. Modifying files directly in the primary workspace is **STRICTLY PROHIBITED**. If target is in the primary workspace, HALT immediately and initiate Phase 1 (`/spec` & `/plan`).

1. **Phase 1 (Spec & Plan)**:
   - **Goal**: User-approved `/spec` and `/plan`.
   - **Step 1 (Resolve Branch)**: Identify target base branch (`<base_branch>`) and feature branch (`gemini/<feature-name>`).
   - **Step 2 (Draft `/spec`)**: Automatically create/update `/spec` artifact ([spec-driven-development](../spec-driven-development/SKILL.md)). **PAUSE** for explicit human approval.
   - **Step 3 (Draft `/plan`)**: Automatically create/update `/plan` artifact ([planning-and-task-breakdown](../planning-and-task-breakdown/SKILL.md)). **PAUSE** for explicit human approval.
   - *Gate Enforcement*: The agent MUST NOT create worktrees, edit code, or advance to Phase 2 until Phase 1 is fully user-approved.

2. **Phase 2 (Build & Worktree)**:
   - **Goal**: Isolated worktree created, code edited, tested, and committed locally.
   - **Step 4 (Add Git Worktree & Develop `/build` & `/test`)**: Sync latest changes (`git fetch origin`) and create git worktree off `origin/<base_branch>`:
     ```bash
     git worktree add -b gemini/<feature-name> ~/.gemini/tmp/worktrees/gemini_<sanitized-feature-name> origin/<base_branch>
     ```
     Perform all file edits inside isolated worktree directory and verify using virtual environment wrappers (`run_in_env.py` for linters and tests).
   - **Step 5 (Stage & Commit)**: Stage modified files and commit on the feature branch inside the worktree:
     ```bash
     git add <modified_files>
     git commit -m "<descriptive commit message>"
     ```

3. **Phase 3 (Push & Adversarial Review)**:
   - **Goal**: Feature branch pushed to `origin` AND `/adversarial-review` report posted by subagent in chat.
   - **Step 6 (Push to Remote)**: Push feature branch to remote origin:
     ```bash
     git push origin gemini/<feature-name>
     ```
   - **Step 7 (Subagent Adversarial Review Loop)**:
     - *Mandatory Subagent Delegation*: The parent agent MUST NOT run the review in its own context. The parent agent MUST execute `invoke_subagent` (`TypeName: self`, `Role: Adversarial Code Reviewer`, `Workspace: inherit`).
     - The subagent runs isolated review on the worktree. Repeat fix-commit-push loop until verdict is `APPROVE` with zero open `[CRITICAL]` findings. Post review report in chat.
     - *Subagent Lifecycle Cleanup*: Once the subagent finishes and posts its review report, the parent agent MUST kill the dangling subagent instance using `manage_subagents` (`Action: "kill"`, `ConversationIds: [<subagent_conversation_id>]`).

4. **Phase 4 (Human Signoff & Merge)**:
   - **Goal**: User confirms merge; branch merged to integration branch.
   - **Step 8 (Human Review & Signoff Gate)**: **PAUSE**. Present review report, diff summary, and remote branch link to user.
   - **Turn-Boundary & Merge Prohibition**:
     > [!CAUTION]
     > - Strictly forbid executing `git merge`, `git rebase`, or main-branch integration within the same turn as `/build` or `/adversarial-review`.
     > - The agent MUST pause after posting the `/adversarial-review` report in chat and wait for an explicit user merge confirmation prompt before attempting any merge.
   - Recommended commands for user: [/explain-diff](../explain-diff/SKILL.md) and [/signoff](../signoff/SKILL.md).
   - Once merged by the user, remove the worktree and ensure any remaining subagents are terminated:
     ```bash
     git worktree remove ~/.gemini/tmp/worktrees/gemini_<sanitized-feature-name>
     git worktree prune
     ```
     *Note: If the worktree contains untracked or uncommitted changes and you want to discard them, add `--force` to the removal command.*
