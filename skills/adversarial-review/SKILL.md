---
name: adversarial-review
description: Adversarial review and diff explanation of two git worktrees. Use when the user requests an adversarial review of a branch or pull request, wants to find bugs or code quality issues in a feature branch before merging, or wants to compare the current branch with the main/reference branch. Do NOT use if the user only wants to list branches, run simple git diffs without review, or perform non-code reviews.
---

# Adversarial Review and Diff Explanation

Automatically resolve context, create/update feature branch worktree, and perform adversarial diff review.

## Context Resolution

1. Run the helper branch resolution script to discover branches and manage worktree.
   ```bash
   python3 ~/.gemini/skills/adversarial-review/scripts/resolve_branches.py [optional_target_branch] [--reference <branch>] [--prune] [--prune-all]
   ```

### Script Flags
- `[optional_target_branch]`: Explicitly specify the feature branch name to review.
- `--reference <branch>`: Override the default integration branch to compare against.
- `--prune`: Prune cached review worktrees for this repository.
- `--prune-all`: Prune all cached review worktrees across all repositories.

### JSON Response Schema
The script returns JSON on stdout. The schema depends on the outcome:

* **Success (Worktree Created/Updated)**
   ```json
   {
     "reference_branch": "main",
     "feature_branch": "feat/my-feature",
     "ambiguous": false,
     "worktree_path": "/Users/user/.gemini/tmp/worktrees/a1b2c3d4_feat-my-feature_e5f6g7",
     "commit_hash": "a1b2c3d4...",
     "subject": "commit message subject"
   }
   ```
* **Ambiguous Candidates (Need user clarification)**
   ```json
   {
     "reference_branch": "main",
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
     ]
   }
   ```
* **No Branches Found**
   ```json
   {
     "reference_branch": "main",
     "feature_branch": null,
     "ambiguous": false,
     "candidates": [],
     "message": "No other branches found to compare."
   }
   ```
* **Prune Success**
   ```json
   {
     "success": true,
     "message": "Worktree cache pruned successfully."
   }
   ```
* **Error**
   ```json
   {
     "error": "Error message explanation"
   }
   ```

2. **Ambiguity & Auto-pick Rule**: The resolver only auto-picks a candidate branch if:
   - There is exactly one candidate feature branch in the repository.
   - Or the current branch of the working copy is one of the candidates (and not the integration branch).
   Otherwise, it flags `"ambiguous": true` and lists candidates. If the script output contains `"ambiguous": true`:
   - Present the candidate list to the user.
   - Ask the user to clarify which branch is the intended feature branch.
3. If no candidate feature branch is found (e.g., `"feature_branch": null`):
   - Report that no feature branch is available to review, and ask the user to specify one.

## Execution Steps

1. **Get the Diff**:
   - Run `git diff --merge-base <reference_branch> <commit_hash>` (or `git diff <reference_branch>...<commit_hash>`) using the resolved reference branch and the explicit `commit_hash` returned by the script. (This is more robust than using a branch name directly, as it avoids stale local tracking branch issues).
2. **Setup/Use Isolated Env**:
   - The review worktree is created at `worktree_path` to allow running tests or inspecting files without disrupting the user's active working tree.
   - To run tests, execute linters, or run/view code:
     1. Initialize the review environment for the worktree:
        ```bash
        python3 ~/.gemini/scripts/setup_review_env.py <worktree_path>
        ```
     2. Run tests using the environment's pytest binary:
        ```bash
        ~/.gemini/tmp/<workspace-hash>/bin/pytest
        ```
     3. Run ruff using the environment's ruff binary:
        ```bash
        ~/.gemini/tmp/<workspace-hash>/bin/ruff check .
        ```
   - The file lock only serializes concurrent `resolve_branches.py` runs. Do not run git worktree commands against `~/.gemini/tmp/worktrees/` manually while a review is in progress.
   - Note: Git fetches are best-effort. If network resolution fails, the review may run against stale local tracking references.
3. **Perform Adversarial Review**:
   - Analyze the diff and perform an adversarial review focusing on:
     - **Technical Bugs** (Unconditional): Logical errors, performance issues, security vulnerabilities, regression risks, and code design.
     - **Writing Quality** (Unconditional): Clarity and accuracy of documentation, comments, markdown, and precision of language.
     - **HPC / Scientific Check** (Conditional): If the diff touches HPC job scripts or scientific/numerical code, additionally check:
       - **HPC Constraints**: Do not expect intermediate compute files from HPC jobs or attempt running scripts requiring HPC-level resources.
       - **Scientific & Interpretation Errors**: Formula correctness, numerical stability, incorrect statistical assumptions, data leakage, and misinterpretation of data/metrics.
4. Output the final review report directly into the chat. Do not save to file unless requested.
