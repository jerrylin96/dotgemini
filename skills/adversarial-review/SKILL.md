---
name: adversarial-review
description: Adversarial review of two git worktrees to find bugs/quality issues before merge. Do not use for simple diffs or neutral walkthroughs.
---

# Adversarial Review

Automatically resolve context, create/update feature branch worktree, and perform adversarial diff review.

## Core Workflow Rules
> [!IMPORTANT]
> - **Reference Branch (Baseline)**: The branch currently checked out in the user's active workspace represents the baseline reference code. If the checked-out branch is itself the selected feature branch (or HEAD is detached), the script falls back to the default integration branch (e.g. `origin/main`) as the baseline instead.
> - **Feature Branch (Target)**: The branch containing the new changes to review. The agent must ALWAYS ask the user to select this branch.
> - **Worktree Checkout**: The resolver script creates/updates a managed worktree checked out to the selected **feature branch** at `worktree_path`.
> - **Testing/Inspecting**: All testing, linting, or inspection of the feature branch code must be run inside the resolved `worktree_path` (by executing `cd <worktree_path>` first), leaving the active workspace untouched on the reference branch.
> - **Ephemeral Scratch files**: Creating temporary scratch files under the conversation's scratch directory for diff reading is permitted and does not violate repository/worktree read-only constraints, provided cleanup only removes those generated scratch files.

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

1. **Get the Diff Safely**: To prevent terminal command output truncation (which silently trims long diff outputs or lines), do NOT read the raw output of `git diff` directly from the terminal tool. Instead, use the resolved `reference_commit_hash` and the explicit feature branch `commit_hash` returned by the branch resolution script (which is more robust than using a branch name directly, as it avoids stale local tracking branch issues).
   a. Run `git diff "<reference_commit_hash>...<commit_hash>" --stat > "<appDataDir>/brain/<conversation-id>/scratch/temp_diff_stat.txt"` (using `--merge-base` or `...` syntax) to see all changed files.
   b. Save the complete target diff to a temporary file under the conversation's scratch directory:
      `git diff "<reference_commit_hash>...<commit_hash>" > "<appDataDir>/brain/<conversation-id>/scratch/temp_diff_all.txt"`
   c. Read the diff file using the `view_file` tool. This guarantees paginated, untruncated access to the diff.

   *Execution and Robustness Guidelines:*
   - **Prerequisites & Tooling Contract**: The `view_file` tool is a guaranteed capability of the Antigravity CLI runtime, supporting 1-indexed, inclusive `StartLine` and `EndLine` parameters to read up to 800 lines of a file per invocation. In primitive runtimes (like Gemini CLI) where `view_file` is unavailable, fall back to using `read_file` (if available, noting that its pagination parameters are environment-dependent and best-effort) or a deterministic shell-based range reading procedure like `sed -n '<start_line>,<end_line>p' "<file_path>"` or `head`/`tail` after redirecting output to an OS temporary path (e.g. `$(mktemp -d)/temp_diff.txt`). Do not use `cat` or interactive pagers (such as `less`).
   - **Directory Creation & Quoting**: Always ensure the target scratch directory exists by running `mkdir -p "<appDataDir>/brain/<conversation-id>/scratch"` before executing any redirections. Quote all shell paths and parameters in commands to handle paths containing spaces or special characters.
   - **File Roles & Workflow**:
     - **temp_diff_stat.txt**: Stores changed-file statistics. Save via `git diff "<reference_commit_hash>...<commit_hash>" --stat > "<appDataDir>/brain/<conversation-id>/scratch/temp_diff_stat.txt"` once at the start. Use this to read stats.
     - **temp_diff_all.txt**: Stores complete diff hunks and context. Save via `git diff "<reference_commit_hash>...<commit_hash>" > "<appDataDir>/brain/<conversation-id>/scratch/temp_diff_all.txt"` once at the start. Use this to read full context.
     - **temp_diff_paths.txt**: Stores null-delimited name-status list. Save via `git diff "<reference_commit_hash>...<commit_hash>" --name-status -z > "<appDataDir>/brain/<conversation-id>/scratch/temp_diff_paths.txt"` once at the start if the branch history or changeset is exceptionally large.
     - For large files, use sequential chunked reading to consume the entire diff safely.
   - **Machine-Readable Path Enumeration**: To safely handle renames, whitespace, special characters, and newlines in filenames, run `git diff "<reference_commit_hash>...<commit_hash>" --name-status -z`. If the changeset is exceptionally large and risks stdout truncation, redirect it to a temp file: `git diff "<reference_commit_hash>...<commit_hash>" --name-status -z > "<appDataDir>/brain/<conversation-id>/scratch/temp_diff_paths.txt"` and parse it.
   - **Pagination & EOF Detection (Unterminated Final Lines)**: To prevent terminal output truncation on extremely large files, read files in successive, deterministic chunks. Do not rely on receiving a short chunk (fewer lines than requested) as an EOF signal. Instead, get the total logical line count of the file beforehand. Because `wc -l` counts newline characters rather than logical lines, verify if the file is non-empty and lacks a trailing newline character (e.g. check if the last byte of the file is not `\n`), and if so, increment the expected line count by 1 (or rely on file viewer metadata if it reports the exact logical line count). Read iteratively until the `StartLine` exceeds this logical line count.
   - **Special Git Cases & Binary Changes**: Explicitly check the diff headers for file renames, mode-only modifications (`old mode ... new mode`), and binary files (`Binary files ... differ`). Report binary changes in the overall summary, but omit detailed text hunks.
   - **Cleanup**: Once the review ends, cleanly delete only the temporary files and directories: run `rm -- "<file_path>"` for scratch files. If an OS temporary directory was created via `TEMP_DIR=$(mktemp -d)`, avoid recursive deletion (`rm -rf`); instead, delete the specific temporary files created inside the temp directory (`rm -- "$TEMP_DIR/temp_diff_stat.txt" "$TEMP_DIR/temp_diff_all.txt" "$TEMP_DIR/temp_diff_paths.txt"` etc.) and then safely remove the empty directory using `rmdir -- "$TEMP_DIR"`. Never run deletion commands inside the repository or worktree.
2. **Note on Worktree**:
   - The review worktree is created at `worktree_path` to allow running tests or inspecting files without disrupting the user's active working tree. Note that the worktree at `worktree_path` is checked out to the feature branch (the target being reviewed), while the active workspace's current branch is treated as the reference branch (baseline). If you need to run tests, execute linters, or view/run code, `cd` into `worktree_path` first.
   - Paths under `~/.gemini/tmp/worktrees/` are disposable cache and may be force-removed or recreated at any time; do not use them for long-lived uncommitted work.
   - The file lock only serializes concurrent `resolve_branches.py` runs. Do not run git worktree commands against `~/.gemini/tmp/worktrees/` manually while a review is in progress.
   - Note: Git fetches are best-effort. If network resolution fails, the review may run against stale local tracking references.
3. **Setup/Use Isolated Env**:
   - To run tests, execute linters, or run/view code:

     > [!TIP]
     > **Subagent Delegation (Antigravity Only)**: If the feature branch is large, has a massive diff, or has a complex test suite, the main agent can delegate this step. Invoke the built-in `research` subagent for read-only codebase exploration, or change directories into `<worktree_path>` and invoke the built-in `self` subagent with `Workspace: inherit` to set up the review environment and run tests. This delegation contract is Antigravity-only; in other runtimes (e.g. Gemini CLI), the main agent performs these steps directly.

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
