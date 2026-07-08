---
name: adversarial-review
description: Adversarial review and diff explanation of two git worktrees.
---

# Adversarial Review and Diff Explanation

Automatically resolve context, create/update feature branch worktree, and perform adversarial diff review.

## Context Resolution

1. Run the helper branch resolution script to discover branches and manage worktree.
   ```bash
   python3 ~/.gemini/skills/adversarial-review/scripts/resolve_branches.py [optional_target_branch] [--reference <branch>] [--prune]
   ```

### Script Flags
- `[optional_target_branch]`: Explicitly specify the feature branch name to review.
- `--reference <branch>`: Override the default integration branch to compare against.
- `--prune`: Prune all cached review worktrees and exit.

### JSON Response Schema
The script returns JSON on stdout. The schema depends on the outcome:

* **Success (Worktree Created/Updated)**
  ```json
  {
    "reference_branch": "main",
    "feature_branch": "feat/my-feature",
    "ambiguous": false,
    "worktree_path": "/Users/user/.gemini/tmp/worktrees/repo_feat_my-feature_a1b2c3",
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

2. If the script output contains `"ambiguous": true`:
   - Present the candidate list to the user.
   - Ask the user to clarify which branch is the intended feature branch.
3. If no candidate feature branch is found (e.g., `"feature_branch": null`):
   - Report that no feature branch is available to review, and ask the user to specify one.

## Execution Steps

1. Get the diff using the resolved branches:
   - Run `git diff <reference_branch>...<feature_branch>` to extract changes introduced by the feature branch. (The diff can be run from the primary repository).
2. Note on Worktree:
   - The review worktree is created at `worktree_path` to allow running tests or inspecting files without disrupting the user's active working tree. If you need to run tests, execute linters, or view/run code, `cd` into `worktree_path` first.
   - Note: Git fetches are best-effort. If network resolution fails, the review may run against stale local tracking references.
3. Perform adversarial review on the diff, emphasizing:
   - **Technical Bugs** (Unconditional): Logical errors, performance issues, security vulnerabilities, regression risks, and code design.
   - **Writing Quality** (Unconditional): Clarity and accuracy of documentation, comments, markdown, and precision of language.
   - **HPC / Scientific Check** (Conditional): If the diff touches HPC job scripts or scientific/numerical code, additionally check:
     - **HPC Constraints**: Do not expect intermediate compute files from HPC jobs or attempt running scripts requiring HPC-level resources.
     - **Scientific & Interpretation Errors**: Formula correctness, numerical stability, incorrect statistical assumptions, data leakage, and misinterpretation of data/metrics.
4. Output the final review report directly into the chat. Do not save to file unless requested.
