---
name: adversarial-review
description: Multi-stage adversarial review of specifications, plans, RED tests, and code worktrees to catch edge cases, non-negotiables, and bugs across the software lifecycle.
---

# Adversarial Review

Automatically route review mode, perform artifact audits (Spec/Plan) or worktree diff audits (Test/Code) across 4 distinct lifecycle gates.

## Step 0: Select Review Mode and Route (Mandatory Dispatch)

The review subagent MUST first inspect its prompt inputs / Context Compaction Block to determine its target review mode and execution context:

### Mode Precedence Hierarchy:
1. **Explicit CLI Flag**: `--mode=external` or `--mode=pipeline` passed to `resolve_branches.py` or subagent (accepted aliases: `external-standalone`, `internal-pipeline`, `internal`).
2. **Compaction Block Marker**: `Review Mode Context: internal-pipeline` (set when invoked by `/make-feature`).
3. **Default Fallback**: **External Standalone Mode**.

> Note: Canonical mode names are `external` (External Standalone) and `pipeline` (Internal Pipeline). Long forms (`external-standalone`, `internal-pipeline`) are accepted as aliases everywhere; Compaction Blocks SHOULD use the long form for clarity, but short forms are also accepted.

### Mode Targets:
1. **Spec Reviewer Mode (`spec-review`, Role: Adversarial Spec Reviewer)** -> Execute **Artifact Review Path (Spec & Plan)**.
2. **Plan Reviewer Mode (`plan-review`, Role: Adversarial Plan Reviewer)** -> Execute **Artifact Review Path (Spec & Plan)**.
3. **RED Test Reviewer Mode (`test-review`, Role: Adversarial Test Reviewer)** -> Execute **Worktree RED Test Review Path**.
4. **Code Reviewer Mode (`code-review`, Role: Adversarial Code Reviewer)** -> Execute **Worktree Code Review Path** (using resolved External Standalone Mode or Internal Pipeline Mode rules).

> [!IMPORTANT]
> If the review mode is missing or ambiguous, the reviewer MUST stop immediately and ask the parent agent for explicit mode selection.

---

## Artifact Review Path (Spec & Plan)

Applicable **ONLY** to `spec-review` and `plan-review` modes.

> [!CAUTION]
> **Artifact Mode Bypass Rules**: When executing `spec-review` or `plan-review`, the review subagent MUST NOT:
> - Ask the user or parent agent to select a feature branch.
> - Invoke `resolve_branches.py`.
> - Create a separate git worktree or manage checkouts (the worktree is created and managed by the parent builder agent).
> - Generate or read a git diff.
> - Run test, linter, or environment setup scripts (`setup_review_env.py`, `run_in_env.py`).

### Execution Procedure for Spec & Plan Documents:
1. Read the target spec or plan directly via `view_file` using the file path provided under `Target Artifact Paths` in the Context Compaction Block. When executing under `/make-feature`, this path is the in-tree `${WORKTREE_PATH}/${FEATURE_SLUG}/spec.md` or `plan.md` in the feature worktree (which strictly supersedes `/artifact` and Obsidian). For standalone runs outside git worktrees, this may be an artifact path.
2. Apply mode-specific checklist:
   - **`spec-review` Checklist**: Scope completeness, unstated assumptions, missing edge cases, security/architectural risks, non-negotiables.
   - **`plan-review` Checklist**: Atomic task decomposition, explicit TDD RED/GREEN specs, executable verify commands, dependency ordering, worktree/env isolation safety.
3. Output verdict (`APPROVE` or `REJECT`) with required 3-5 line **Adversarial Audit Summary** (state clean compliance honestly if zero blocking issues found):
   ```markdown
   ### Adversarial Audit Summary (What Was Caught & Fixed)
   - **[Mode]**: <Concise bullet describing bug, missing edge case, weak assertion, or path issue resolved>
   - **[Mode]**: <If no blocking issues found: "No blocking issues found; verified clean compliance for [area/spec]">
   ```
4. **TERMINATE TURN**: Immediately stop calling tools upon posting the verdict report. Do NOT proceed to branch resolution or worktree review sections below.

---

## Worktree RED Test Review Path

Applicable **ONLY** to `test-review` mode.

### 1. Required Inputs:
The review subagent MUST be provided with:
- **Target Worktree Path**: Absolute path under `~/.gemini/tmp/worktrees/`.
- **Designated RED Test Paths**: Specific test file path(s) or pytest node IDs.
- **Approved Spec Path**: Target in-tree `${FEATURE_SLUG}/spec.md` path (or `/spec` artifact path for standalone runs).
- **Task Slice Info**: (Optional) Relevant plan task item.

> [!IMPORTANT]
> If any required input (worktree path, test path, spec path) is missing or ambiguous, the reviewer MUST stop immediately and ask the parent agent for explicit input parameters.

### 2. Mandatory Source-Review & Assertion Rigor Audit:
Before running tests, the reviewer MUST view the test source code and spec artifact via `view_file` to evaluate:
- **Spec Parity**: Verify every relevant requirement and non-negotiable in the spec is represented by a substantive test case.
- **Assertion Rigor**: Reject weak assertions (e.g. trivial `assert result is not None` or generic type checks when value, state, or error semantics are required).
- **Edge, Boundary & Error Coverage**: Verify edge cases, boundary limits, and expected failure modes specified in the spec are tested (or explicitly explain why inapplicable).
- **Trivial-Implementation Resilience**: Reject tests that can pass after unrelated or minimal incorrect implementations.

### 3. Empirical Test Execution & Behavioral Failure Validation:
Run ONLY the designated RED test file(s) inside the worktree using the environment runner:
```bash
python3 ~/.gemini/scripts/run_in_env.py <worktree_path> pytest <designated_test_path>
```
- **Expected Behavioral Failure**: APPROVE only if tests fail for legitimate expected architectural or behavioral reasons.
- **Reject Syntax/Import/Env Errors**: REJECT if tests fail due to syntax errors, import bugs, collection failures, or environment issues.
- **Full Suite Exemption**: Do NOT require the full test suite to pass at this gate — RED tests should fail cleanly.

### 4. Verdict Report & Audit Summary:
Emit `APPROVE` or `REJECT` verdict detailing:
- Test command executed and observed failure traceback/reason.
- Spec requirements checked and assertion/coverage findings.
- Required 3-5 line **Adversarial Audit Summary**.
- **TERMINATE TURN**: Stop calling tools immediately after posting report. Max 3 REJECT cycles per gate before escalating to human engineer.

---

## Worktree Code Review Path

The following `Core Workflow Rules`, `Context Resolution`, and `Execution Steps` apply **ONLY** to `code-review` mode.

### Execution Context & Mode Rules

#### 1. External Standalone Mode (User-Triggered `/adversarial-review`)
- **Strict Read-Only Worktree Isolation**: The reviewer MUST NOT invoke file modification tools (`replace_file_content`, `write_to_file`) on repository or worktree files under `~/.gemini/tmp/worktrees/`. Writing temporary scratch files or report artifacts under conversation directories (`<appDataDir>/brain/<conversation-id>/`) remains permitted.
- **Mandatory Remote Fetch & SHA Guard**: Run `resolve_branches.py [target] [--last-sha=<sha>] [--force]`. If `resolve_branches.py` returns `"sha_changed": false` (and `--force` was not set), halt immediately and notify the user: `"Remote branch commit SHA has not changed since last review (<sha>). No new updates detected."`
- **Single-Pass Turn Termination**: Perform **exactly 1 audit pass**. Output must begin with a top-level `VERDICT: [APPROVE | NEEDS_REVISION | REJECT]` followed by a dedicated `### External PR Action Plan (Copy-Paste for PR Comments)` section with ready-to-copy code blocks/diffs:
  ```markdown
  ### External PR Action Plan (Copy-Paste for PR Comments)
  **Verdict:** NEEDS_REVISION — 2 issues
  **1. [file:line] Title** — explanation + ```suggestion diff```
  **2. [file:line] Title** — explanation
  **Tests to run:** `pytest path/to/test`
  ```
  Terminate turn immediately after posting.

#### 2. Internal Pipeline Mode (Invoked by `/make-feature` Phase 3)
- **Review Mode Context**: Set to `internal-pipeline` in compaction block.
- **Builder-Reviewer Loop**: Parent builder agent handles code edits; reviewer subagent audits and emits `APPROVE` or `REJECT` up to max 3 cycles.

### Subagent Context Compaction Template
Parent agents MUST include a compacted context block (≤ 30 lines / ~400 words) when invoking review subagents:
```markdown
### Context Compaction Block
- **Feature Rationale**: <1-2 sentences>
- **Key Architectural Decisions**: <bulleted list>
- **Active Constraints**: <bulleted list>
- **Prior Step Findings**: <empirical summary>
- **Target Artifact Paths**: <file links>
- **Review Mode Context**: <external-standalone | internal-pipeline>
```

### Mandatory Terse Audit Summary Output
Every review subagent verdict MUST include a top-level `VERDICT:` line and a 3-5 line **Adversarial Audit Summary**. For **External Standalone code-review** the allowed verdicts are `APPROVE`, `NEEDS_REVISION`, or `REJECT`; for **Internal Pipeline code-review** and for spec-review/plan-review/test-review the allowed verdicts remain `APPROVE` or `REJECT` only:
```markdown
VERDICT: APPROVE

### Adversarial Audit Summary (What Was Caught & Fixed)
- **[Code]**: <Concise bullet describing bug, missing edge case, weak assertion, or path issue resolved>
- **[Code]**: <If no blocking issues found: "No blocking issues found; verified clean compliance for [area/spec]">
```


## Core Workflow Rules
> [!IMPORTANT]
> - **Reference Branch (Baseline)**: The branch currently checked out in the user's active workspace represents the baseline reference code. If the checked-out branch is itself the selected feature branch (or HEAD is detached), the script falls back to the default integration branch (e.g. `origin/main`) as the baseline instead.
> - **Feature Branch (Target)**: The branch containing the new changes to review. The agent must ALWAYS ask the user to select this branch.
> - **Worktree Checkout**: The resolver script creates/updates a managed worktree checked out to the selected **feature branch** at `worktree_path`.
> - **Testing/Inspecting**: All testing, linting, or inspection of the feature branch code must be run inside the resolved `worktree_path` (by executing `cd <worktree_path>` first), leaving the active workspace untouched on the reference branch.
> - **Subagent Delegation & Recursion Guardrail**: Subagent delegation is initiated by the main/parent agent (`invoke_subagent` using `TypeName: self` with `Workspace: inherit` on `worktree_path`). **If the current agent is ALREADY executing as a review subagent inside `worktree_path`, it must NOT spawn nested subagents**; it executes review checks directly. Max 3 REJECT cycles per gate before escalating to human engineer.
> - **Ephemeral Scratch files**: Creating temporary scratch files under the conversation's scratch directory for diff reading is permitted and does not violate repository/worktree read-only constraints, provided cleanup only removes those generated scratch files.

## Context Resolution

1. Run the helper branch resolution script to discover branches and manage worktree.
   ```bash
   python3 ~/.gemini/skills/adversarial-review/scripts/resolve_branches.py [optional_target] [--mode=external|pipeline] [--last-sha=<sha>] [--force] [--pr <N>] [--reference <branch>] [--prune] [--prune-all]
   ```

### Script Flags
- `[optional_target]`: Explicitly specify the feature branch to review. Accepts short names (`feat/x`), remote-qualified names (`origin/feat/x`), or fully qualified refs (`refs/heads/feat/x`); a remote-qualified name reviews that exact remote ref even when a same-named local branch exists. `#42` or a PR/MR web URL is treated as a pull request target (see `--pr`); a URL also selects the matching remote by comparing remote URLs.
- `--mode=<mode>`: Execution context. `external` (default) for user-triggered `/adversarial-review` (strict read-only, single-pass) or `pipeline` for `/make-feature` Phase 3 (builder-reviewer loop). Aliases `external-standalone`, `internal-pipeline`, and `internal` are accepted and normalized to canonical `external`/`pipeline`.
- `--last-sha=<sha>`: Full 40-char commit SHA (or 7-40 hex prefix) from previous review. When it matches the resolved `commit_hash` and `--force` is not set, the script returns `"sha_changed": false` and skips worktree creation.
- `--force`: Bypass the `--last-sha` unchanged guard. Forces a re-review even when SHA has not changed.
- `--pr <N>`: Review a pull/merge request by number instead of a branch. The script fetches the PR head ref directly from the remote (`refs/pull/N/head` on GitHub/Gitea/Forgejo, `refs/merge-requests/N/head` on GitLab) into `refs/gemini-review/<remote>/pr/N`, so it works even for fork PRs whose head branch is not in any configured remote, and for merged/closed PRs. Unsupported on remotes that do not expose PR refs (e.g. Bitbucket). Unlike branch fetches, a failed PR fetch is a fatal error — there is no stale local fallback.
- `--reference <branch>`: Override the default integration branch to compare against.
- `--prune`: Prune cached review worktrees for this repository.
- `--prune-all`: Prune all cached review worktrees across all repositories.

### JSON Response Schema
The script returns JSON on stdout. The schema depends on the outcome:

* **Success (Worktree Created/Updated)**
   ```json
   {
     "mode": "external",
     "reference_branch": "origin/main",
     "reference_ref": "origin/main",
     "reference_commit_hash": "b2c3d4e5...",
     "feature_branch": "feat/my-feature",
     "feature_ref": "origin/feat/my-feature",
     "ambiguous": false,
     "worktree_path": "/Users/user/.gemini/tmp/worktrees/a1b2c3d4_feat-my-feature_e5f6g7",
     "commit_hash": "a1b2c3d4...",
     "subject": "commit message subject",
     "sha_changed": true,
     "fetch_error": null
   }
   ```
   - `mode` — echoed, normalized `--mode` value (`external` default, or `pipeline`). Always present on success.
   - `sha_changed` — `true` if review should proceed; `false` when `--last-sha` matches `commit_hash` and `--force` not set.
   - `message` — present only when `sha_changed == false`, value: `"Remote branch commit SHA has not changed since last review (<sha>). No new updates detected."`
   - `worktree_path` — path to created worktree, or `null` when `sha_changed == false`.
   - `reference_ref` currently always mirrors `reference_branch`.
   - `feature_ref` is the exact ref the review targets (local name, or remote-qualified like `origin/feat/my-feature`), so you can tell whether a local or remote branch was resolved.
   - `fetch_error` is `null` when the best-effort `git fetch` succeeded; otherwise it holds the fetch failure message and the results may be based on stale local tracking refs. Mention this in the review report if set.
   - **PR mode** returns the same success schema plus `"pr_number"`, with `feature_branch` like `"pr-42"` and `feature_ref` like `"origin/pull/42/head"`.
   - Note: `mode` is now always present (even on ambiguous / no-branches responses, since it reflects the requested execution context); `sha_changed` is only present on success responses where a target was resolved (absent on ambiguous / no-branches).
* **Ambiguous Candidates (Need user clarification)**
   ```json
   {
     "mode": "external",
     "reference_branch": "origin/main",
     "reference_ref": "origin/main",
     "reference_commit_hash": "b2c3d4e5...",
     "feature_branch": null,
     "ambiguous": true,
     "candidates": [
       {
         "full_name": "feat/my-feature",
         "branch_name": "feat/my-feature",
         "timestamp": 1690000000,
         "commit_hash": "a1b2c3d4...",
         "subject": "commit subject"
       }
     ],
     "fetch_error": null
   }
   ```
* **No Branches Found**
   ```json
   {
     "mode": "external",
     "reference_branch": "origin/main",
     "reference_ref": "origin/main",
     "reference_commit_hash": "b2c3d4e5...",
     "feature_branch": null,
     "ambiguous": false,
     "candidates": [],
     "message": "No other branches found to compare.",
     "fetch_error": null
   }
   ```
* **Prune Success**
   ```json
   {
     "success": true,
     "message": "Worktree cache for repo hash a1b2c3d4 pruned successfully."
   }
   ```
* **Error**
   ```json
   {
     "error": "Error message explanation"
   }
   ```

2. **Ambiguity & Ask-User Rule**: If no target feature branch is specified as an argument to `resolve_branches.py`, it always flags `"ambiguous": true` and lists candidate branches (both local and remote) on stdout.
   - Present the candidate list to the user.
   - Ask the user to explicitly choose which feature branch is the intended target for review.
3. If no candidate feature branch is found (e.g., `"feature_branch": null`):
   - Report that no feature branch is available to review, and ask the user to specify one.
4. **PR baseline**: In PR mode the baseline is still the checked-out branch (or the default integration branch) — plain git cannot know a PR's true base branch. Since the diff is merge-base-anchored this is usually harmless, but if the PR targets a different base, pass `--reference <base>`. If the `gh` CLI happens to be installed, you may best-effort run `gh pr view <N> --json baseRefName,title,body` to discover the base branch and enrich context; never treat `gh` as required and never fail because it is absent.

## Execution Steps

1. **Read Review Manifest First (Fast Targeted Review)**:
   - Check if `<appDataDir>/brain/<conversation-id>/review_manifest_<feature>.md` exists. If present, view it using `view_file` to understand the builder's summary, TDD test proof, and identified high-risk areas.
   - Use the manifest to target diff inspection directly at changed logic and high-risk modules, cutting unnecessary exploratory turns.


2. **Get the Diff Safely**: To prevent terminal command output truncation (which silently trims long diff outputs or lines), do NOT read the raw output of `git diff` directly from the terminal tool. Instead, use the resolved `reference_commit_hash` and the explicit feature branch `commit_hash` returned by the branch resolution script (which is more robust than using a branch name directly, as it avoids stale local tracking branch issues).
   a. Run `git diff "<reference_commit_hash>...<commit_hash>" --stat > "<appDataDir>/brain/<conversation-id>/scratch/temp_diff_stat.txt"` (using `--merge-base` or `...` syntax) to see all changed files.
   b. Save the complete target diff to a temporary file under the conversation's scratch directory:
      `git diff "<reference_commit_hash>...<commit_hash>" > "<appDataDir>/brain/<conversation-id>/scratch/temp_diff_all.txt"`
   c. Read the diff file using the `view_file` tool. This guarantees paginated, untruncated access to the diff.

   *Execution & Robustness Directives:*
   - **Use `view_file`**: Read files in chunks of 800 lines max. *Reason: Prevents terminal truncation.*
   - **Create and Quote Paths**: Run `mkdir -p` first; quote all paths in commands. *Reason: Handles directories with special characters/spaces safely.*
   - **Manage Scratch Files**: Keep naming distinct (e.g. `temp_diff_stat.txt`, `temp_diff_all.txt`, `temp_diff_paths.txt`). *Reason: Avoids concurrency name collisions.*
   - **Parse Large Diff Stats**: Run `git diff ... --name-status -z`. *Reason: Handles renames and non-standard characters safely.*
   - **Sequential Reading & EOF**: Read until file viewer lines exceed calculated count. *Reason: Avoids terminal cutoff.*
   - **Omit Binary Files**: Skip text diffs for binary files; report their changes in the summary. *Reason: Prevents binary content corruption.*
   - **Clean Up Safely**: Delete only temporary files when done. *Reason: Leaves repository and worktree untouched.*
   - **Reference Guide**: For full detail on tools compatibility, EOF edge cases, and path safety, see [robustness_guide.md](resources/robustness_guide.md).
3. **Note on Worktree**:
   - The review worktree is created at `worktree_path` to allow running tests or inspecting files without disrupting the user's active working tree. Note that the worktree at `worktree_path` is checked out to the feature branch (the target being reviewed), while the active workspace's current branch is treated as the reference branch (baseline). If you need to run tests, execute linters, or view/run code, `cd` into `worktree_path` first.
   - Paths under `~/.gemini/tmp/worktrees/` are disposable cache and may be force-removed or recreated at any time; do not use them for long-lived uncommitted work.
   - The file lock only serializes concurrent `resolve_branches.py` runs. Do not run git worktree commands against `~/.gemini/tmp/worktrees/` manually while a review is in progress.
   - Note: Git fetches are best-effort. If network resolution fails, the review may run against stale local tracking references.
4. **Subagent Execution & Environment Setup**:
   - The main agent should delegate the review execution to a background subagent (`invoke_subagent`), supplying a compacted context summary block (per AGENTS.md §10 / make-feature SKILL.md Phase 3), to keep its context clean and eliminate author bias.
     - **Subagent Selection**: Use `TypeName: self` with `Workspace: inherit` inside `<worktree_path>` (since `self` possesses the necessary write/execution tools to run environment setup and tests). Use `research` subagent ONLY for read-only static analysis.
     - **Recursion Prevention**: If you are already running as the invoked review subagent, execute the steps below directly without spawning further subagents.
   - **Headless Execution Guardrail (No `ctrl+k` Prompts)**: All test, linter, compilation, and setup commands MUST be run using `python3 ~/.gemini/scripts/run_in_env.py <worktree_path> <cmd>` (or whitelisted file/git tools). Direct execution of bare un-wrapped terminal commands (`pytest`, `mkdir`, bare `python`, etc.) is strictly forbidden as it triggers interactive permission prompts.
   - **Sequential Execution Procedure**:
     1. Initialize the review environment for the worktree:
        ```bash
        python3 ~/.gemini/scripts/setup_review_env.py <worktree_path>
        ```
     2. Run tests using the environment runner:
        ```bash
        python3 ~/.gemini/scripts/run_in_env.py <worktree_path> pytest
        ```
     3. Run ruff using the environment runner:
        ```bash
        python3 ~/.gemini/scripts/run_in_env.py <worktree_path> ruff check .
        ```

5. **Perform Adversarial Review**:
   - **Empirical Anti-Hallucination Grounding**: All findings MUST quote byte-for-byte exact line numbers, code snippets, and actual test runner execution output. Hypothetical, speculative, or ungrounded bug claims are strictly forbidden.
   - Analyze the diff and perform an adversarial review focusing on:
     - **Technical Bugs** (Unconditional): Logical errors, performance issues, security vulnerabilities, regression risks, and code design.
     - **Writing Quality** (Unconditional): Clarity and accuracy of documentation, comments, markdown, and precision of language.
     - **LaTeX / TeX Check** (Conditional): If the diff touches any `.tex`, `.cls`, `.sty`, or `.bib` files, additionally check:
       - **Root Document Compilation**: Identify root document(s) containing `\documentclass` that include modified files (or compile all root `.tex` files if inclusion is unresolvable). Compile with `latexmk -pdf -interaction=nonstopmode -halt-on-error -cd <root>.tex`. Non-zero exit is a **blocking defect** (fix and recompile before commit). Warnings (overfull boxes, undefined references) are non-blocking.
       - **Toolchain Availability & Honesty**: If no TeX toolchain (`latexmk`/`pdflatex`) is installed in the environment, explicitly report in the summary that TeX compilation was **unverified**. Never claim a document compiles without empirical build logs.
       - **Class Macro Compatibility**: Never copy preamble macros between documents using different document classes without verifying macro definitions in the target class (e.g., checking `.cls` files).
     - **HPC / Scientific Check** (Conditional): If the diff touches HPC job scripts or scientific/numerical code, additionally check:
       - **HPC Constraints**: Do not expect intermediate compute files from HPC jobs or attempt running scripts requiring HPC-level resources.
       - **Scientific & Interpretation Errors**: Formula correctness, numerical stability, incorrect statistical assumptions, data leakage, and misinterpretation of data/metrics.
6. **Output Report & Terminate Turn**:
   - Output the final review report directly into the chat. Do not save to file unless requested.
   - **Turn Termination**: Immediately upon posting the review report, the subagent MUST stop calling tools to conclude its turn. Do not execute further steps or linger in an idle loop.
