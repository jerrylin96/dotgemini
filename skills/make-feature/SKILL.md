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

1. **Resolve Repository Root**: Locate the root of the git repository you want to modify (e.g., `/Users/jlin404/.gemini` or the user's workspace path).
2. **Determine Branch Name**: Identify a clear, concise name for the feature (e.g., `make-feature-skill`). Prefix it with `gemini/` to form `gemini/<feature-name>`.
3. **Add Git Worktree**: Run the `git worktree add` command to create a new branch and checkout its files into a temporary/isolated location under the `.gemini/tmp/worktrees/` directory:
   ```bash
   git worktree add -b gemini/<feature-name> /Users/jlin404/.gemini/tmp/worktrees/gemini_<feature-name> main
   ```
4. **Modify & Develop**: Perform all file edits, writes, and local commands inside the isolated worktree directory (e.g., `/Users/jlin404/.gemini/tmp/worktrees/gemini_<feature-name>`). Do not make changes in the primary workspace.
5. **Stage & Commit**: Run git staging and commit commands from within the worktree directory:
   ```bash
   git add <modified_files>
   git commit -m "<descriptive commit message>"
   ```
6. **Push Branch**: Push the feature branch to the remote origin:
   ```bash
   git push origin gemini/<feature-name>
   ```
7. **Clean Up**: Once the branch is pushed and the task is complete, remove the worktree from the primary repository directory:
   ```bash
   git worktree remove /Users/jlin404/.gemini/tmp/worktrees/gemini_<feature-name>
   ```
   If needed, also prune git worktrees:
   ```bash
   git worktree prune
   ```
