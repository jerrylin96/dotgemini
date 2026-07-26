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

1. **Phase 1 (Spec & Plan - Two-Stage Sequential Gate)**:
   - **Goal**: Sequential user approval of `/spec` (Stage 1a) followed by `/plan` (Stage 1b).
   - **Step 1 (Resolve Branch)**: Identify target base branch (`<base_branch>`) and feature branch (`gemini/<feature-name>`).
   - **Step 2 (Stage 1a: Draft `/spec`)**: Automatically create/update `/spec` artifact ([spec-driven-development](../spec-driven-development/SKILL.md)). **PAUSE** and wait for explicit human approval of `/spec`.
   - **Step 3 (Stage 1b: Draft `/plan`)**: *Only after `/spec` is explicitly approved*, inspect codebase and create/update `/plan` artifact ([planning-and-task-breakdown](../planning-and-task-breakdown/SKILL.md)). Every task item MUST include explicit TDD `RED Test Spec`, `GREEN Implementation Target`, and `Verify Command`. **PAUSE** and wait for explicit human approval of `/plan`.
   - *Gate Enforcement*: Drafting `/plan` before `/spec` is approved is STRICTLY FORBIDDEN. Creating worktrees or editing code before `/plan` is approved is STRICTLY FORBIDDEN.


2. **Phase 2 (Build & Worktree)**:
   - **Goal**: Isolated worktree created, TDD cycle executed, code edited, tested, committed locally, and review manifest approved by user.
   - **Step 4 (Add Git Worktree & Develop via TDD)**: Sync latest changes (`git fetch origin`) and create git worktree off `origin/<base_branch>`:
     ```bash
     git worktree add -b gemini/<feature-name> ~/.gemini/tmp/worktrees/gemini_<sanitized-feature-name> origin/<base_branch>
     ```
     Perform all file edits inside isolated worktree directory following strict TDD order (write RED test first, then GREEN implementation). Verify using virtual environment wrappers (`run_in_env.py` for linters and tests).
     > [!IMPORTANT]
     > **Empirical Grounding Directive**: Prohibit declaring success, test passes, or schema validity without empirical execution output present in the context window.
   - **Step 4b (Builder Pre-Review Quality Check & Manifest Creation)**:
     - Run `python3 ~/.gemini/scripts/run_in_env.py <worktree_path> pytest` and `ruff check .` inside worktree and verify 100% pass rate.
     - Create local ephemeral `<worktree_path>/REVIEW_MANIFEST.md` detailing:
       - *Summary & Rationale*: Concise explanation of changes and Ponytail YAGNI justification.
       - *TDD Proof*: List of test cases added/modified and empirical pass log snippet.
       - *High-Risk Areas*: Key files or edge cases for reviewer focus.
     > [!IMPORTANT]
     > `REVIEW_MANIFEST.md` is an ephemeral hand-off file for the adversarial reviewer subagent only. It MUST NOT be staged, committed to Git, or pushed to the remote repository.
   - **Step 4c (HARD GATE: Human Approval of Review Manifest)**:
     - **PAUSE**. Present `<worktree_path>/REVIEW_MANIFEST.md` to user in chat.
     - *Gate Enforcement*: The agent MUST receive explicit user approval of the review manifest before pushing to remote origin or launching Phase 3 subagent review.
   - **Step 5 (Stage & Commit)**: Stage modified feature files (excluding `REVIEW_MANIFEST.md`) and commit on the feature branch inside the worktree:
     ```bash
     git add <modified_files>
     git commit -m "<descriptive commit message>"
     ```

3. **Phase 3 (Push & Adversarial Review)**:
   - **Goal**: Feature branch pushed to `origin`, subagent `/adversarial-review` executed using review manifest, and post-review report artifact created.
   - **Step 6 (Push to Remote)**: Push feature branch to remote origin:
     ```bash
     git push origin gemini/<feature-name>
     ```
   - **Step 7 (Subagent Adversarial Review Loop)**:
     - *Mandatory Subagent Delegation*: The parent agent MUST NOT run the review in its own context. The parent agent MUST execute `invoke_subagent` (`TypeName: self`, `Role: Adversarial Code Reviewer`, `Workspace: inherit`). Prompt MUST specify `<worktree_path>/REVIEW_MANIFEST.md` path.
     - The subagent runs isolated review on the worktree, reading `REVIEW_MANIFEST.md` first to target diff inspection. Repeat fix-commit-push loop until verdict is `APPROVE` with zero open `[CRITICAL]` findings. Post review report in chat.
     - *Subagent Lifecycle Cleanup*: Once the subagent finishes and posts its review report, the parent agent MUST kill the dangling subagent instance using `manage_subagents` (`Action: "kill"`, `ConversationIds: [<subagent_conversation_id>]`).
   - **Step 7b (Post-Review Audit Report Artifact)**:
     - Generate formal `review_report_<feature>.md` artifact detailing:
       - *What was checked* (empirical test runner logs, linter results, static diff analysis)
       - *What was changed* (file diff breakdown and architectural decisions)
       - *Human Review Attention Points* (edge cases, potential risks, or recommendations for signoff)

4. **Phase 4 (Human Signoff & Manual Merge)**:
   - **Goal**: Human engineer reviews artifact and manually merges branch to integration branch.
   - **Step 8 (Human Review & Manual Merge Gate)**: **PAUSE**. Present review report artifact, diff summary, and remote branch link to user.
   - **Strict Agent Merge Prohibition**:
     > [!CAUTION]
     > - **Human-Only Merge Ownership**: Merging code into the integration or production branch (`main`, `master`, etc.) is **ALWAYS performed manually by the human engineer** (e.g. via GitHub Pull Request UI or manual git merge).
     > - **Agent Merge Prohibited**: The AI agent is STRICTLY FORBIDDEN from executing `git merge`, `git rebase`, or performing automated branch integration. The agent's work concludes upon delivering the approved feature branch, passing adversarial review, and generating the post-review report artifact.
   - Recommended tools for user: [/explain-diff](../explain-diff/SKILL.md) and [/signoff](../signoff/SKILL.md).
   - Once merged manually by the user, remove the worktree:
     ```bash
     git worktree remove ~/.gemini/tmp/worktrees/gemini_<sanitized-feature-name> --force
     git worktree prune
     ```


