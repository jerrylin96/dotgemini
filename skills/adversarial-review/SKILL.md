---
name: adversarial-review
description: Adversarial review of two git worktrees. Use when the user requests an adversarial review of a branch or pull request, wants to find bugs or code quality issues in a feature branch before merging, or wants to compare the current branch with the main/reference branch. Do NOT use if the user only wants to list branches, run simple git diffs without review, wants a neutral explanation/walkthrough of changes (use explain-diff), or perform non-code reviews.
---

# Adversarial Review

Automatically resolve context, create/update feature branch worktree, and perform adversarial diff review.

## Core Workflow Rules
> [!IMPORTANT]
> - **Reference Branch (Baseline)**: The branch currently checked out in the user's active workspace represents the baseline reference code. If the checked-out branch is itself the selected feature branch (or HEAD is detached), the script falls back to the default integration branch (e.g. `origin/main`) as the baseline instead.
> - **Feature Branch (Target)**: The branch containing the new changes to review. The agent must ALWAYS ask the user to select this branch.
> - **Worktree Checkout**: The resolver script creates/updates a managed worktree checked out to the selected **feature branch** at `worktree_path`.
> - **Testing/Inspecting**: All testing, linting, or inspection of the feature branch code must be run inside the resolved `worktree_path` (by executing `cd <worktree_path>` first), leaving the active workspace untouched on the reference branch.

## Context Resolution

1. Run the helper branch resolution script to discover branches and manage worktree.
   ```bash
   python3 ~/.gemini/skills/adversarial-review/scripts/resolve_branches.py [optional_target] [--pr <N>] [--reference <branch>] [--prune] [--prune-all]
   ```

### Script Flags
- `[optional_target]`: Explicitly specify the feature branch to review. Accepts short names (`feat/x`), remote-qualified names (`origin/feat/x`), or fully qualified refs (`refs/heads/feat/x`); a remote-qualified name reviews that exact remote ref even when a same-named local branch exists. `#42` or a PR/MR web URL is treated as a pull request target (see `--pr`); a URL also selects the matching remote by comparing remote URLs.
- `--pr <N>`: Review a pull/merge request by number instead of a branch. The script fetches the PR head ref directly from the remote (`refs/pull/N/head` on GitHub/Gitea/Forgejo, `refs/merge-requests/N/head` on GitLab) into `refs/gemini-review/<remote>/pr/N`, so it works even for fork PRs whose head branch is not in any configured remote, and for merged/closed PRs. Unsupported on remotes that do not expose PR refs (e.g. Bitbucket). Unlike branch fetches, a failed PR fetch is a fatal error — there is no stale local fallback.
- `--reference <branch>`: Override the default integration branch to compare against.
- `--prune`: Prune cached review worktrees for this repository.
- `--prune-all`: Prune all cached review worktrees across all repositories.

### JSON Response Schema
The script returns JSON on stdout. The schema depends on the outcome:

* **Success (Worktree Created/Updated)**
   ```json
   {
     "reference_branch": "origin/main",
     "reference_ref": "origin/main",
     "reference_commit_hash": "b2c3d4e5...",
     "feature_branch": "feat/my-feature",
     "feature_ref": "origin/feat/my-feature",
     "ambiguous": false,
     "worktree_path": "/Users/user/.gemini/tmp/worktrees/a1b2c3d4_feat-my-feature_e5f6g7",
     "commit_hash": "a1b2c3d4...",
     "subject": "commit message subject",
     "fetch_error": null
   }
   ```
   - `reference_ref` currently always mirrors `reference_branch`.
   - `feature_ref` is the exact ref the review targets (local name, or remote-qualified like `origin/feat/my-feature`), so you can tell whether a local or remote branch was resolved.
   - `fetch_error` is `null` when the best-effort `git fetch` succeeded; otherwise it holds the fetch failure message and the results may be based on stale local tracking refs. Mention this in the review report if set.
   - **PR mode** returns the same success schema plus `"pr_number"`, with `feature_branch` like `"pr-42"` and `feature_ref` like `"origin/pull/42/head"`.
* **Ambiguous Candidates (Need user clarification)**
   ```json
   {
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

1. **Get the Diff**:
   - Run `git diff --merge-base <reference_commit_hash> <commit_hash>` (or `git diff <reference_commit_hash>...<commit_hash>`) using the resolved `reference_commit_hash` and the explicit feature branch `commit_hash` returned by the script. (This is more robust than using a branch name directly, as it avoids stale local tracking branch issues).
2. **Note on Worktree**:
   - The review worktree is created at `worktree_path` to allow running tests or inspecting files without disrupting the user's active working tree. Note that the worktree at `worktree_path` is checked out to the feature branch (the target being reviewed), while the active workspace's current branch is treated as the reference branch (baseline). If you need to run tests, execute linters, or view/run code, `cd` into `worktree_path` first.
   - Paths under `~/.gemini/tmp/worktrees/` are disposable cache and may be force-removed or recreated at any time; do not use them for long-lived uncommitted work.
   - The file lock only serializes concurrent `resolve_branches.py` runs. Do not run git worktree commands against `~/.gemini/tmp/worktrees/` manually while a review is in progress.
   - Note: Git fetches are best-effort. If network resolution fails, the review may run against stale local tracking references.
3. **Setup/Use Isolated Env**:
   - To run tests, execute linters, or run/view code:
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

4. **Perform Adversarial Review**:
   - Analyze the diff and perform an adversarial review focusing on:
     - **Technical Bugs** (Unconditional): Logical errors, performance issues, security vulnerabilities, regression risks, and code design.
     - **Writing Quality** (Unconditional): Clarity and accuracy of documentation, comments, markdown, and precision of language.
     - **HPC / Scientific Check** (Conditional): If the diff touches HPC job scripts or scientific/numerical code, additionally check:
       - **HPC Constraints**: Do not expect intermediate compute files from HPC jobs or attempt running scripts requiring HPC-level resources.
       - **Scientific & Interpretation Errors**: Formula correctness, numerical stability, incorrect statistical assumptions, data leakage, and misinterpretation of data/metrics.
5. Output the final review report directly into the chat. Do not save to file unless requested.
