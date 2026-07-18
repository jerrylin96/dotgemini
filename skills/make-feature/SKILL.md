---
name: make-feature
description: Creates a new feature branch and checked-out git worktree in a temporary location, allowing the agent to safely edit files, test, and commit/push without touching or switching the user's primary checked-out branch. Always prefixes feature branches with `gemini/`.
---

# Isolated Feature Branch Development via Git Worktree

Use this skill when you need to make changes to a repository (such as adding a feature, modifying code, or editing configuration files like skills themselves) and push those changes to a remote feature branch, without mutating the user's active branch checkout in their working directory.

## Core Rules
> [!IMPORTANT]
> - **Branch Naming**: Always prefix the feature branch with `gemini/` (e.g., `gemini/feature-name`).
> - **No Primary Branch Pollution**: Never run `git checkout -b` or modify files directly in the user's primary repository working directory when developing a new feature. Always check out a worktree.
> - **Worktree Cleanup**: Once the branch has been successfully pushed to the remote repository, prune/delete the worktree to save disk space and keep the workspace clean.

## Execution Steps

1. **Resolve Repository Root**: Locate the root of the git repository you want to modify (e.g., `<repo_root>` for the active project or `~/.gemini` for global skills).
2. **Determine Branch and Base**: 
   * Identify a clear, concise name for the feature (e.g., `make-feature-skill`). Prefix it with `gemini/` to form `gemini/<feature-name>`.
   * Find the correct base integration branch (e.g., `main` or `master`).
3. **Fetch Latest Changes**: Sync with remote to ensure you branch off the latest commit:
   ```bash
   git fetch origin
   ```
4. **Add Git Worktree**:
   * **Sanitize Feature Name**: Construct `<sanitized-feature-name>` from `<feature-name>` by keeping only alphanumeric, `-`, `_`, and `.` characters, and replacing `/` or `\` with `_` to prevent directory traversal.
   * If creating a new branch, run:
     ```bash
     git worktree add -b gemini/<feature-name> ~/.gemini/tmp/worktrees/gemini_<sanitized-feature-name> origin/<base_branch>
     ```
   * If checking out an existing local or remote branch, run:
     ```bash
     git worktree add ~/.gemini/tmp/worktrees/gemini_<sanitized-feature-name> gemini/<feature-name>
     ```
5. **Modify & Develop**: Perform all file edits, writes, and local commands inside the isolated worktree directory (`~/.gemini/tmp/worktrees/gemini_<sanitized-feature-name>`). Do not make changes in the primary workspace.

   > [!TIP]
   > **Subagent Delegation (Antigravity Only)**: For complex changesets, instead of editing files directly, the main agent can change directories into the worktree path and invoke the built-in `self` subagent with `Workspace: inherit`. Tasks should explicitly instruct the subagent to use virtual environment wrappers (`setup_review_env.py` and `run_in_env.py`) for all runs/tests. This delegation contract is Antigravity-only; in other runtimes (e.g. Gemini CLI), the main agent performs these steps directly.

6. **Stage & Commit**: Run git staging and commit commands from within the worktree directory:
   ```bash
   git add <modified_files>
   git commit -m "<descriptive commit message>"
   ```
7. **Push Branch**: Push the feature branch to the remote origin:
   ```bash
   git push origin gemini/<feature-name>
   ```
8. **Clean Up**: Remove the worktree:
   ```bash
   git worktree remove ~/.gemini/tmp/worktrees/gemini_<sanitized-feature-name>
   ```
   *Note: If the worktree contains untracked or uncommitted changes and you want to discard them, add `--force` to the removal command.*
   
   Finally, prune git worktree metadata:
   ```bash
   git worktree prune
   ```
