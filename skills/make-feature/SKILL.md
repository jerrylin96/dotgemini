---
name: make-feature
description: Creates a feature branch (always prefixed with gemini/) and isolated git worktree. Mandatory entry point for ALL codebase changes — use whenever developing features, fixing bugs, or editing files.
---

# Isolated Feature Branch Development via Git Worktree

Use this skill for **all codebase changes** — features, bug fixes, config edits, skill modifications. Changes are pushed to a remote feature branch without mutating the user's active branch checkout.

## When to Use & Invocation Variants

- **Always.** Mandatory entry point for any file modification in a repository.
- **Standard Invocation**: Trigger with `/make-feature` (or automatically whenever preparing to write or edit codebase files).
- **Heavy Mode (`/make-feature heavy`)**: Recommended for complex multi-slice features. Instructs Phase 1 (`/plan`) to proactively select `Sequential Subagents` execution strategy across task slices.
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
   - **Step 3b (Scratchpad Initialization)**: Run `mkdir -p "<appDataDir>/brain/<conversation-id>/scratch"` and create `<appDataDir>/brain/<conversation-id>/scratch/scratchpad.md` summarizing initial spec/plan decisions and active constraints.
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
     > [!TIP]
     > **Sequential Subagent Delegation**: If the approved `/plan` specifies `Sequential Subagents`, the parent agent (or slice-runner subagents) MUST execute subagents sequentially using `Workspace: inherit` (or target worktree path) so all slice commits land on `gemini/<feature-name>`. Each subagent must update `<appDataDir>/brain/<conversation-id>/scratch/scratchpad.md` (where `<conversation-id>` is the parent conversation ID) before exiting.
   - **Step 4b (Builder Pre-Review Quality Check & Manifest Creation)**:
     - Run `python3 ~/.gemini/scripts/run_in_env.py <worktree_path> pytest` and `ruff check .` inside worktree and verify 100% pass rate.
     - Update `<appDataDir>/brain/<conversation-id>/scratch/scratchpad.md` with build step findings and empirical test logs.
     - Create review manifest artifact in the conversation artifact directory (`<appDataDir>/brain/<conversation-id>/review_manifest_<feature>.md`) detailing:
       - *Summary & Rationale*: Concise explanation of changes and Ponytail YAGNI justification.
       - *TDD Proof*: List of test cases added/modified and empirical pass log snippet.
       - *High-Risk Areas*: Key files or edge cases for reviewer focus.
     > [!NOTE]
     > Storing the manifest in the external artifact directory ensures it never touches or pollutes the git repository working tree.
   - **Step 4c (HARD GATE: Human Approval of Review Manifest)**:
     - **PAUSE**. Present `review_manifest_<feature>.md` artifact to user in chat.
     - *Gate Enforcement*: The agent MUST receive explicit user approval of the review manifest before pushing to remote origin or launching Phase 3 subagent review.
   - **Step 5 (Stage & Commit)**: Stage modified feature files in the worktree and commit:
     ```bash
     git add <modified_files>
     git commit -m "<descriptive commit message>"
     ```

3. **Phase 3 (Push & Adversarial Review)**:
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
       - *Human Review Attention Points* (edge cases, potential risks, or recommendations for signoff)

4. **Phase 4 (Human Signoff, PR Creation & Manual Merge)**:
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




