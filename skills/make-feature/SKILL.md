---
name: make-feature
description: Creates a feature branch (always prefixed with gemini/) and isolated git worktree. Mandatory entry point for ALL codebase changes — use whenever developing features, fixing bugs, or editing files.
---

# Isolated Feature Branch Development via Git Worktree

Use this skill for **all codebase changes** — features, bug fixes, config edits, skill modifications. Changes are pushed to a remote feature branch without mutating the user's active branch checkout.

## When to Use & Invocation Variants

- **Always.** Mandatory entry point for any file modification in a repository.
- **Standard Invocation**: Trigger with `/make-feature` (or automatically whenever preparing to write or edit codebase files).
- **Heavy Mode (`/make-feature heavy`)**: Use for complex multi-slice features. In Phase 1b (`/plan`), the agent proactively selects `Sequential Subagents` execution strategy across task slices. In Phase 2, each task slice undergoes per-slice RED test review (`Adversarial Test Reviewer`) and per-slice code review (`Adversarial Code Reviewer`) before advancing to the next slice.
- The only exception: changes to Antigravity artifacts, scratch files, or non-repo files.

## Core Rules
> [!IMPORTANT]
> - **Branch Naming**: Always prefix the feature branch with `gemini/` (e.g., `gemini/feature-name`).
> - **No Primary Branch Pollution**: Never run `git checkout -b` or modify files directly in the user's primary repository working directory. Always use a worktree.
> - **Worktree Cleanup**: Once the branch has been successfully pushed to the remote repository, prune/delete the worktree to save disk space and keep the workspace clean.

## Milestone Phase Goals & Gate Enforcement

> [!CAUTION]
> **Pre-Execution Worktree Circuit Breaker (Hard Stop)**:
> Before calling any file edit tool (`replace_file_content`, `write_to_file`, etc.) on a repository file, verify `TargetFile` is under `~/.gemini/tmp/worktrees/`. Modifying files directly in the primary workspace is **STRICTLY PROHIBITED**. If target is in the primary workspace, HALT immediately and initiate Stage 0 (`/grill-me`) and Phase 1 (`/spec` & `/plan`).

0. **Stage 0 (Interactive Alignment Gate - `/grill-me`)**:
   - **Goal**: Clarify scope boundaries, non-negotiables, technical constraints, and edge cases through interactive Q&A alignment before drafting `/spec`. Transition proactively to `/spec` once ~95% confidence is reached. (If `/grill-me` is unavailable or for trivial typo fixes, embed clarifying Q&A directly into `/spec` drafting).

1. **Phase 1a (Spec & Adversarial Spec Review Gate)**:
   - **Goal**: Sequential user approval of `/spec` after subagent adversarial spec audit.
   - **Step 1 (Resolve Branch)**: Identify target base branch (`<base_branch>`) and feature branch (`gemini/<feature-name>`).
   - **Step 2 (Draft `/spec`)**: Automatically create/update `/spec` artifact ([spec-driven-development](../spec-driven-development/SKILL.md)).
   - **Step 2b (Subagent Adversarial Spec Review)**: Parent agent invokes `invoke_subagent` (`TypeName: self`, `Role: Adversarial Spec Reviewer`). Subagent audits `/spec` for missing edge cases, security/architectural risks, and unstated assumptions until `APPROVE`.
   - **Step 2c (Human Approval Gate)**: **PAUSE** and wait for explicit human approval of `/spec`.

2. **Phase 1b (Plan & Adversarial Plan Review Gate)**:
   - **Goal**: Sequential user approval of `/plan` after subagent adversarial plan audit.
   - **Step 3 (Draft `/plan`)**: *Only after `/spec` is explicitly approved*, inspect codebase and create/update `/plan` artifact ([planning-and-task-breakdown](../planning-and-task-breakdown/SKILL.md)). Every task item MUST include explicit TDD `RED Test Spec`, `GREEN Implementation Target`, and `Verify Command`.
   - **Step 3b (Subagent Adversarial Plan Review)**: Parent agent invokes `invoke_subagent` (`TypeName: self`, `Role: Adversarial Plan Reviewer`). Subagent audits `/plan` for atomic task sizing, dependency ordering, TDD coverage, and worktree/env safety until `APPROVE`.
   - **Step 3c (Human Approval Gate)**: **PAUSE** and wait for explicit human approval of `/plan`.
   - **Step 3d (Scratchpad Initialization)**: Run `mkdir -p "<appDataDir>/brain/<conversation-id>/scratch"` and create `<appDataDir>/brain/<conversation-id>/scratch/scratchpad.md` summarizing spec/plan decisions and active constraints.

3. **Phase 2 (Build & Worktree - Adversarial RED Test Review Gate)**:
   - **Goal**: Isolated worktree created, TDD RED tests written, RED test subagent review passed, GREEN implementation written, 100% test pass verified.
   - **Step 4 (Add Git Worktree & Develop via TDD)**: Sync latest changes (`git fetch origin`) and create git worktree off `origin/<base_branch>`:
     ```bash
     git worktree add -b gemini/<feature-name> ~/.gemini/tmp/worktrees/gemini_<sanitized-feature-name> origin/<base_branch>
     ```
   - **Step 4b (Write RED Test Suite & Verify Failure)**: Write RED test suite and verify clean failure via `run_in_env.py`.
   - **Step 4c (Subagent Adversarial RED Test Review)**: Parent agent invokes `invoke_subagent` (`TypeName: self`, `Role: Adversarial Test Reviewer`). Subagent audits RED tests for assertion rigor, clean failure reason, boundary testing, and spec parity until `APPROVE`.
   - **Step 4d (Write GREEN Implementation & Verify Pass)**: Write minimal implementation code to make approved RED tests pass. Run `run_in_env.py` to confirm 100% GREEN pass rate and linter check.
     > [!IMPORTANT]
     > **Empirical Grounding Directive**: Prohibit declaring success, test passes, or schema validity without empirical execution output present in the context window.
     > [!TIP]
     > **Sequential Subagent Delegation**: If the approved `/plan` specifies `Sequential Subagents`, execution subagents MUST run sequentially using `Workspace: inherit` (or target worktree path) so all slice commits land on `gemini/<feature-name>`. In Heavy Mode (`/make-feature heavy`), each task slice builder writes RED tests, triggers `Adversarial Test Reviewer` subagent, writes GREEN implementation, triggers slice `Adversarial Code Reviewer` subagent, updates `scratchpad.md`, and commits the slice before advancing to the next slice. Parent agent MUST clean up review subagents via `manage_subagents` (`Action: "kill"`). Max 3 REJECT cycles per review gate before escalating to human engineer.
   - **Step 4e (Builder Pre-Review Quality Check & Manifest Creation)**:
     - Update `<appDataDir>/brain/<conversation-id>/scratch/scratchpad.md` with build step findings and empirical test logs.
     - Create review manifest artifact in conversation artifact directory (`<appDataDir>/brain/<conversation-id>/review_manifest_<feature>.md`).
   - **Step 4f (HARD GATE: Human Approval of Review Manifest)**:
     - **PAUSE**. Present `review_manifest_<feature>.md` artifact to user in chat and wait for explicit approval before pushing to remote origin or launching Phase 3 subagent review.
   - **Step 5 (Stage & Commit)**: Stage modified feature files in the worktree and commit:
     ```bash
     git add <modified_files>
     git commit -m "<descriptive commit message>"
     ```

4. **Phase 3 (Push & Adversarial Code Review Gate)**:
   - **Goal**: Feature branch pushed to `origin`, subagent `/adversarial-review` executed using review manifest artifact, and post-review report artifact created.
   - **Step 6 (Push to Remote)**: Push feature branch to remote origin:
     ```bash
     git push origin gemini/<feature-name>
     ```
   - **Step 7 (Subagent Adversarial Review Loop)**:
     - *Mandatory Subagent Delegation*: The parent agent MUST NOT run the review in its own context. The parent agent MUST execute `invoke_subagent` (`TypeName: self`, `Role: Adversarial Code Reviewer`, `Workspace: inherit`).
     - *Subagent Compaction Block*: The subagent prompt MUST include a compacted context block (≤ 30 lines) formatted as:
       ```markdown
       ### Context Compaction Block
       - **Feature Rationale**: <1-2 sentences>
       - **Key Architectural Decisions**: <bulleted list>
       - **Active Constraints**: <bulleted list>
       - **Prior Step Findings**: <empirical summary>
       - **Target Artifact Paths**: <file links>
       ```
       *(Prohibition: NEVER include secrets, tokens, credentials, or `.env` contents in the compaction block)*. Specify the `<appDataDir>/brain/<conversation-id>/review_manifest_<feature>.md` path to preserve reasoning state across context isolation.
     - The subagent runs isolated review on the worktree, reading `review_manifest_<feature>.md` first to target diff inspection. Repeat fix-commit-push loop until verdict is `APPROVE` with zero open `[CRITICAL]` findings. Post review report in chat.
     - *Subagent Lifecycle Cleanup*: Once the subagent finishes and posts its review report, the parent agent MUST kill the dangling subagent instance using `manage_subagents` (`Action: "kill"`, `ConversationIds: [<subagent_conversation_id>]`).
   - **Step 7b (Post-Review Audit Report Artifact & Scratchpad Update)**:
     - Update `<appDataDir>/brain/<conversation-id>/scratch/scratchpad.md` with post-review findings and subagent verdict.
     - Generate formal `review_report_<feature>.md` artifact detailing:
       - *What was checked* (empirical test runner logs, linter results, static diff analysis)
       - *What was changed* (file diff breakdown and architectural decisions)
       - *Full Audit Trail Preservation*: Include or link to the verdict and 3-5 line Adversarial Audit Summary for all four review gates (Spec Review, Plan Review, RED Test Review, Code Review) with empirical evidence references.
       - *Human Review Attention Points* (edge cases, potential risks, or recommendations for signoff)

5. **Phase 4 (Human Signoff, PR Creation & Manual Merge)**:
   - **Goal**: Human engineer reviews post-review audit report artifact, creates Pull Request, and manually merges feature branch to target integration branch (`<base_branch>`).
   - **Step 8 (Human Review, PR Creation & Integration Gate)**: **PAUSE**. Update `<appDataDir>/brain/<conversation-id>/scratch/scratchpad.md` pre-signoff with final completion status. Present review report artifact, diff summary, and remote feature branch link to user.
   - **Human Ownership of PR Creation & Integration**:
     > [!CAUTION]
     > - **Human PR & Merge Ownership**: Creating Pull Requests (PRs), reviewing PR diffs, and merging code *into* the target integration branch (`<base_branch>`, e.g., `main`, `develop`, `staging`, `release/*`, etc.) is **ALWAYS performed manually by the human engineer**. The AI agent is strictly forbidden from creating PRs or merging directly into the primary integration branch.
     > - **Agent Permitted Feature Sync**: Inside its isolated feature worktree (`~/.gemini/tmp/worktrees/gemini_<feature-name>`), the AI agent IS permitted to rebase or pull upstream changes from its designated base branch (`git fetch origin && git rebase origin/<base_branch>`) to resolve drift and keep its feature branch clean for human review and merge.
   - Recommended tools for user: [/explain-diff](../explain-diff/SKILL.md) and [/signoff](../signoff/SKILL.md).
   - Once merged manually by the user, clean up scratchpad and remove worktree:
     ```bash
     rm -- "<appDataDir>/brain/<conversation-id>/scratch/scratchpad.md"
     git worktree remove ~/.gemini/tmp/worktrees/gemini_<sanitized-feature-name> --force
     git worktree prune
     ```




