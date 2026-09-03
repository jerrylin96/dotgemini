---
name: make-feature
description: Creates a feature branch (always prefixed with gemini/) and isolated git worktree. Mandatory entry point for ALL codebase changes — use whenever developing features, fixing bugs, or editing files.
---

# Isolated Feature Branch Development via Git Worktree

Use this skill for **all codebase changes** — features, bug fixes, config edits, skill modifications. Changes are developed in an isolated worktree, synchronized to a remote feature branch for multi-agent review, and cleaned up prior to final merge without mutating the user's active branch checkout.

## When to Use & Invocation Variants

- **Always.** Mandatory entry point for any file modification in a repository.
- **Standard Invocation**: Trigger with `/make-feature` (or automatically whenever preparing to write or edit codebase files).
- **Heavy Mode (`/make-feature heavy`)**: Use for complex multi-slice features. In Phase 1b (`/plan`), the agent proactively selects `Sequential Subagents` execution strategy across task slices. In Phase 2, each task slice executes a strict 2-stage commit cadence: commit and push slice RED tests (`test(slice-N): add RED test suite (failing)`), write GREEN code, pass slice code review (`Adversarial Code Reviewer`), and commit/push GREEN code (`feat(slice-N): implement slice N (GREEN)`) before advancing to the next slice.
- The only exception: changes to Antigravity artifacts, scratch files, or non-repo files.

## Core Rules
> [!IMPORTANT]
> - **Branch Naming**: Always prefix the feature branch with `gemini/` and append a deterministic 6-character hex suffix: `gemini/<feature-name>-<hash>` (e.g., `gemini/user-auth-e4a9b2`).
> - **Ephemeral Review Folder**: Store active feature specs and plans in `<feature-name>-<hash>/` at the root of the isolated worktree. This folder is synchronized to remote origin for third-party agent review and strictly purged before merge.
> - **Strict Ephemerality (No Obsidian Clutter)**: All feature lifecycle artifacts (`spec.md`, `plan.md`, `review_manifest.md`, `review_report.md`, `scratchpad.md`) are 100% ephemeral. Do NOT write review reports, specs, or plans to Obsidian vaults or the git workspace tree.
> - **No Primary Branch Pollution**: Never run `git checkout -b` or modify files directly in the user's primary repository working directory. Always use a worktree.
> - **Worktree Cleanup**: Once the branch has been successfully pushed to the remote repository and signed off, prune/delete the worktree to save disk space and keep the workspace clean.

## Milestone Phase Goals & Gate Enforcement

> [!CAUTION]
> **Pre-Execution Worktree Circuit Breaker (Hard Stop)**:
> Before calling any file edit tool (`replace_file_content`, `write_to_file`, etc.) on a repository file, verify `TargetFile` is under `~/.gemini/tmp/worktrees/`. Modifying files directly in the primary workspace is **STRICTLY PROHIBITED**. If target is in the primary workspace, HALT immediately and initiate Stage 0 (`/grill-me`) and Phase 1 (`/spec` & `/plan`).

0. **Stage 0 (Interactive Alignment Gate - `/grill-me`)**:
   - **Goal**: Clarify scope boundaries, non-negotiables, technical constraints, and edge cases through interactive Q&A alignment before drafting `/spec`. Transition proactively to `/spec` once ~95% confidence is reached. (If `/grill-me` is unavailable or for trivial typo fixes, embed clarifying Q&A directly into `/spec` drafting).

1. **Phase 1a (Spec & Adversarial Spec Review Gate)**:
   - **Goal**: Worktree initialized, in-tree spec drafted in `<feature-name>-<hash>/spec.md`, committed and pushed to remote origin for external review, subagent spec review approved, and sequential human approval granted.
   - **Step 1 (Resolve Branch, Pre-flight Remote & Initialize Worktree)**:
     - Derive 6-character alphanumeric hex suffix and paths:
       ```bash
       HASH=$(LC_ALL=C tr -dc 'a-f0-9' < /dev/urandom | head -c 6)
       FEATURE_SLUG="<feature-name>-${HASH}"
       BRANCH_NAME="gemini/${FEATURE_SLUG}"
       WORKTREE_PATH="$HOME/.gemini/tmp/worktrees/gemini_${FEATURE_SLUG}"
       ```
     - Remote pre-flight check:
       ```bash
       if git remote get-url origin 2>/dev/null; then
         REMOTE_ENABLED=true
       else
         REMOTE_ENABLED=false
       fi
       ```
     - Create isolated git worktree off designated base branch (`<base_branch>`):
       ```bash
       git fetch origin 2>/dev/null || true
       git worktree add -b "${BRANCH_NAME}" "${WORKTREE_PATH}" "origin/${BASE_BRANCH}" 2>/dev/null || git worktree add -b "${BRANCH_NAME}" "${WORKTREE_PATH}" "${BASE_BRANCH}"
       ```
     - Initialize scratchpad:
       ```bash
       mkdir -p "<appDataDir>/brain/<conversation-id>/scratch"
       ```
       Create `<appDataDir>/brain/<conversation-id>/scratch/scratchpad.md` immediately recording `BRANCH_NAME`, `WORKTREE_PATH`, `FEATURE_SLUG`, and active base branch.
   - **Step 2 (Draft In-Tree `/spec` & Remote Push)**:
     - Create review folder: `mkdir -p "${WORKTREE_PATH}/${FEATURE_SLUG}"`.
     - Write spec to `${WORKTREE_PATH}/${FEATURE_SLUG}/spec.md` ([spec-driven-development](../spec-driven-development/SKILL.md)). *Note: This in-tree file strictly supersedes `/artifact` and Obsidian storage.*
     - Commit and push to remote origin for external agent inspection:
       ```bash
       cd "${WORKTREE_PATH}"
       git add "${FEATURE_SLUG}/spec.md"
       git commit -m "spec: add initial feature spec for external review"
       if [ "$REMOTE_ENABLED" = true ]; then
         git push origin "${BRANCH_NAME}"
       fi
       ```
   - **Step 2b (Subagent Adversarial Spec Review & Revision Sync)**:
     - Parent agent invokes `invoke_subagent` (`TypeName: self`, `Role: Adversarial Spec Reviewer`). Subagent audits `/spec` for missing edge cases, security/architectural risks, and unstated assumptions until `APPROVE`.
     - On any `REVISE` iteration, update `${FEATURE_SLUG}/spec.md`, commit (`git commit -m "spec: address review feedback"`), and push to `origin` if `REMOTE_ENABLED=true`.
   - **Step 2c (Human Approval Gate & Early Abort Routine)**:
     - **PAUSE** and wait for explicit human approval of `/spec`. Provide clickable links to GitHub remote file and local worktree file.
     - **Early Abort Teardown**: If the human engineer rejects or cancels the feature at Step 2c:
       ```bash
       git worktree remove "${WORKTREE_PATH}" --force
       git branch -D "${BRANCH_NAME}"
       if [ "$REMOTE_ENABLED" = true ]; then
         git push origin --delete "${BRANCH_NAME}" 2>/dev/null || true
       fi
       ```

2. **Phase 1b (Plan & Adversarial Plan Review Gate)**:
   - **Goal**: In-tree plan drafted in `<feature-name>-<hash>/plan.md` with explicit TDD targets, committed and pushed to remote origin, subagent plan review approved, and sequential human approval granted.
   - **Step 3 (Draft In-Tree `/plan` & Remote Push)**:
     - *Only after `/spec` is explicitly approved*, inspect codebase and write plan to `${WORKTREE_PATH}/${FEATURE_SLUG}/plan.md` ([planning-and-task-breakdown](../planning-and-task-breakdown/SKILL.md)). Every task item MUST include explicit TDD `RED Test Spec`, `GREEN Implementation Target`, and `Verify Command`. *Note: This in-tree file strictly supersedes `/artifact` and Obsidian storage.*
     - Commit and push to remote origin:
       ```bash
       cd "${WORKTREE_PATH}"
       git add "${FEATURE_SLUG}/plan.md"
       git commit -m "plan: add implementation plan for external review"
       if [ "$REMOTE_ENABLED" = true ]; then
         git push origin "${BRANCH_NAME}"
       fi
       ```
   - **Step 3b (Subagent Adversarial Plan Review & Revision Sync)**:
     - Parent agent invokes `invoke_subagent` (`TypeName: self`, `Role: Adversarial Plan Reviewer`). Subagent audits `/plan` for atomic task sizing, dependency ordering, TDD coverage, and worktree/env safety until `APPROVE`.
     - On any `REVISE` iteration, update `${FEATURE_SLUG}/plan.md`, commit (`git commit -m "plan: address review feedback"`), and push to `origin` if `REMOTE_ENABLED=true`.
   - **Step 3c (Human Approval Gate & Early Abort Routine)**:
     - **PAUSE** and wait for explicit human approval of `/plan`. Provide clickable links to GitHub remote file and local worktree file.
     - **Early Abort Teardown**: If rejected or cancelled, execute the same abort teardown routine as Step 2c.

3. **Phase 2 (Build, Worktree & RED Test Remote Push Gate)**:
   - **Goal**: TDD RED tests written, RED test subagent review passed, failing RED test suite committed and pushed to remote origin, GREEN implementation written, 100% test pass verified.
   - **Step 4 (Develop in Worktree via TDD)**: Operate directly within `${WORKTREE_PATH}`.
   - **Step 4b (Write RED Test Suite & Verify Failure)**: Write RED test suite and verify clean failure via `run_in_env.py`.
   - **Step 4c (Subagent Adversarial RED Test Review)**: Parent agent invokes `invoke_subagent` (`TypeName: self`, `Role: Adversarial Test Reviewer`). Subagent audits RED tests for assertion rigor, clean failure reason, boundary testing, and spec parity until `APPROVE`.
   - **Step 4d (Commit & Push RED Test Suite - Remote Test Review Gate)**:
     - *Before writing any implementation code*, stage and commit the failing RED test suite:
       ```bash
       cd "${WORKTREE_PATH}"
       git add <test_files>
       git commit -m "test: add RED test suite (failing)"
       if [ "$REMOTE_ENABLED" = true ]; then
         git push origin "${BRANCH_NAME}"
       fi
       ```
     - This establishes cryptographic proof of TDD rigor and allows external agents and CI bots on GitHub to inspect tests independently of implementation code.
   - **Step 4e (Write GREEN Implementation & Verify Pass)**: Write minimal implementation code to make approved RED tests pass. Run `run_in_env.py` to confirm 100% GREEN pass rate and linter check.
     > [!IMPORTANT]
     > **Empirical Grounding Directive**: Prohibit declaring success, test passes, or schema validity without empirical execution output present in the context window.
     > [!TIP]
     > **Sequential Subagent Delegation (Heavy Mode)**: If the approved `/plan` specifies `Sequential Subagents`, execution subagents MUST run sequentially using `Workspace: inherit` (or target worktree path) so all slice commits land on `${BRANCH_NAME}`. In Heavy Mode (`/make-feature heavy`), each task slice builder executes a strict 2-stage commit cycle:
     > 1. Write slice RED tests, trigger `Adversarial Test Reviewer` subagent, stage & commit `test(slice-N): add RED test suite (failing)`, and push to `origin` if `REMOTE_ENABLED=true`.
     > 2. Write slice GREEN implementation, confirm 100% pass, trigger slice `Adversarial Code Reviewer` subagent, stage & commit `feat(slice-N): implement slice N (GREEN)`, push to `origin` if `REMOTE_ENABLED=true`, update `scratchpad.md`, and advance to the next slice. Parent agent MUST clean up review subagents via `manage_subagents` (`Action: "kill"`). Max 3 REJECT cycles per review gate before escalating to human engineer.
   - **Step 4f (Builder Pre-Review Quality Check & Manifest Creation)**:
     - Update `<appDataDir>/brain/<conversation-id>/scratch/scratchpad.md` with build step findings and empirical test logs.
     - Create review manifest artifact in ephemeral conversation directory (`<appDataDir>/brain/<conversation-id>/review_manifest_<feature>.md`).
   - **Step 4g (HARD GATE: Human Approval of Review Manifest)**:
     - **PAUSE**. Present `review_manifest_<feature>.md` artifact to user in chat and wait for explicit approval before pushing to remote origin or launching Phase 3 subagent review.
   - **Step 5 (Stage & Commit GREEN Implementation)**:
     ```bash
     cd "${WORKTREE_PATH}"
     git add <modified_files>
     git commit -m "feat: implement feature to make tests pass (GREEN)"
     ```

4. **Phase 3 (Push, Adversarial Code Review Gate & Ephemeral Folder Cleanup)**:
   - **Goal**: Feature implementation pushed to `origin`, subagent `/adversarial-review` executed, ephemeral review folder purged from git tree, and post-review report artifact created in ephemeral conversation brain.
   - **Step 6 (Push GREEN Feature Code to Remote)**:
     ```bash
     if [ "$REMOTE_ENABLED" = true ]; then
       git push origin "${BRANCH_NAME}"
     fi
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
       - Review Mode Context: internal-pipeline
       ```
       *(Prohibition: NEVER include secrets, tokens, credentials, or `.env` contents in the compaction block)*. Specify the `<appDataDir>/brain/<conversation-id>/review_manifest_<feature>.md` path to preserve reasoning state across context isolation.
     - The subagent inspects both the code diff and `${FEATURE_SLUG}/spec.md` / `plan.md` to verify implementation-to-spec parity. Repeat fix-commit-push loop until verdict is `APPROVE` with zero open `[CRITICAL]` findings. Post review report in chat.
     - *Subagent Lifecycle Cleanup*: Once the subagent finishes and posts its review report, the parent agent MUST kill the dangling subagent instance using `manage_subagents` (`Action: "kill"`, `ConversationIds: [<subagent_conversation_id>]`).
   - **Step 7c (Idempotent Ephemeral Cleanup)**:
     - *Only after* `Adversarial Code Reviewer` issues verdict of `APPROVE`, purge the ephemeral review folder:
       ```bash
       cd "${WORKTREE_PATH}"
       if [ -d "${FEATURE_SLUG}" ]; then
         git rm -rf --ignore-unmatch "${FEATURE_SLUG}"
         git commit -m "chore: remove ephemeral spec and plan before signoff"
         if [ "$REMOTE_ENABLED" = true ]; then
           git push origin "${BRANCH_NAME}"
         fi
       fi
       ```
     - This guarantees that upon squash or rebase merge to `<base_branch>`, zero ephemeral files pollute the primary tree.
   - **Step 7b (Ephemeral Post-Review Audit Report Artifact & Scratchpad Update)**:
     - Update `<appDataDir>/brain/<conversation-id>/scratch/scratchpad.md` with post-review findings and subagent verdict.
     - Generate formal `review_report_<feature>.md` artifact strictly within the ephemeral conversation directory (`<appDataDir>/brain/<conversation-id>/`).
     - **Prohibition on Obsidian Dumping**: Do NOT write `review_report_<feature>.md` to Obsidian vaults or the git workspace tree. Its content is ephemeral audit evidence for chat review and GitHub PR description/comments only.
     - Report details:
       - *What was checked* (empirical test runner logs, linter results, static diff analysis)
       - *What was changed* (file diff breakdown and architectural decisions)
       - *Full Audit Trail Preservation*: Include or link to the verdict and 3-5 line Adversarial Audit Summary for all review gates (Spec Review, Plan Review, RED Test Review, Code Review) with empirical evidence references.
       - *Human Review Attention Points* (edge cases, potential risks, or recommendations for signoff)

5. **Phase 4 (Human Signoff, PR Creation & Manual Merge)**:
   - **Goal**: Human engineer reviews post-review audit report artifact, creates Pull Request, and manually merges feature branch to target integration branch (`<base_branch>`).
   - **Step 8 (Human Review, PR Creation & Integration Gate)**: **PAUSE**. Update `<appDataDir>/brain/<conversation-id>/scratch/scratchpad.md` pre-signoff with final completion status. Present review report, diff summary, and remote feature branch link to user.
   - **Human Ownership of PR Creation & Integration**:
     > [!CAUTION]
     > - **Human PR & Merge Ownership**: Creating Pull Requests (PRs), reviewing PR diffs, and merging code *into* the target integration branch (`<base_branch>`, e.g., `main`, `develop`, `staging`, `release/*`, etc.) is **ALWAYS performed manually by the human engineer**. The AI agent is strictly forbidden from creating PRs or merging directly into the primary integration branch.
     > - **Agent Permitted Feature Sync**: Inside its isolated feature worktree (`${WORKTREE_PATH}`), the AI agent IS permitted to rebase or pull upstream changes from its designated base branch (`git fetch origin && git rebase origin/<base_branch>`) to resolve drift and keep its feature branch clean for human review and merge.
   - Recommended tools for user: [/explain-diff](../explain-diff/SKILL.md) and [/signoff](../signoff/SKILL.md).
   - Once merged manually by the user, clean up scratchpad and remove worktree:
     ```bash
     rm -- "<appDataDir>/brain/<conversation-id>/scratch/scratchpad.md"
     git worktree remove "${WORKTREE_PATH}" --force
     git worktree prune
     ```
