---
name: make-feature
description: Creates a feature branch (always prefixed with gemini/) and isolated git worktree. Mandatory entry point for ALL codebase changes — use whenever developing features, fixing bugs, or editing files.
---

# Isolated Feature Branch Development via Git Worktree

Use this skill for **all codebase changes** — features, bug fixes, config edits, skill modifications. Changes are pushed to a remote feature branch without mutating the user's active branch checkout.

## When to Use

- **Always.** This is the mandatory entry point for any file modification in a repository.
- The only exception: changes to Antigravity artifacts, scratch files, or non-repo files.

## Core Rules
> [!IMPORTANT]
> - **Branch Naming**: Always prefix the feature branch with `gemini/` (e.g., `gemini/feature-name`).
> - **No Primary Branch Pollution**: Never run `git checkout -b` or modify files directly in the user's primary repository working directory. Always use a worktree.
> - **Worktree Cleanup**: Once the branch has been successfully pushed to the remote repository, prune/delete the worktree to save disk space and keep the workspace clean.

## Execution Steps

1. **Resolve Repository Root & Target Base Branch**:
   - Locate the root of the git repository (`<repo_root>` or `~/.gemini`).
   - Identify feature branch name (`gemini/<feature-name>`) and target base integration branch (`<base_branch>`, e.g., `main`, `master`, `develop`, or active release branch).
2. **Draft `/spec` Artifact (PAUSE for Human Approval)**:
   - Automatically create/update the `/spec` artifact ([spec-driven-development](../spec-driven-development/SKILL.md)) outlining goals, requirements, and acceptance criteria.
   - **PAUSE**: Present the spec artifact to the human engineer and wait for explicit approval before proceeding.
3. **Draft `/plan` Artifact (PAUSE for Human Approval)**:
   - Upon spec approval, automatically create/update the `/plan` artifact ([planning-and-task-breakdown](../planning-and-task-breakdown/SKILL.md)) decomposing the spec into atomic tasks.
   - **PAUSE**: Present the plan artifact to the human engineer and wait for explicit approval before proceeding.
4. **Add Git Worktree & Develop (`/build` & `/test`)**:
   - Sync latest changes via `git fetch origin`.
   - Add git worktree off `origin/<base_branch>`:
     ```bash
     git worktree add -b gemini/<feature-name> ~/.gemini/tmp/worktrees/gemini_<sanitized-feature-name> origin/<base_branch>
     ```
   - Perform all file edits, writes, and local commands inside the isolated worktree directory (`~/.gemini/tmp/worktrees/gemini_<sanitized-feature-name>`). Do not make changes in the primary workspace.
   - Verify code using virtual environment wrappers (`run_in_env.py` for linters and tests).
5. **Stage, Commit & Push to Remote**:
   - Stage modified files and commit on the feature branch inside the worktree:
     ```bash
     git add <modified_files>
     git commit -m "<descriptive commit message>"
     ```
   - Push feature branch to remote origin so it is published for remote review:
     ```bash
     git push origin gemini/<feature-name>
     ```
6. **Adversarial Review Loop**:
   - Launch a background `self` subagent (`invoke_subagent` using `TypeName: self` with `Workspace: inherit` on `worktree_path`) to run an isolated [adversarial-review](../adversarial-review/SKILL.md) on the pushed feature branch.
   - If findings or open `[CRITICAL]` defects are reported: Fix issues in the worktree, run tests, commit, push to remote (`git push origin gemini/<feature-name>`), and re-trigger Step 6 in a loop.
   - Repeat until the review verdict is `APPROVE` with zero open `[CRITICAL]` findings.
7. **Human Review & Signoff Gate (PAUSE for Merge)**:
   - **PAUSE**: Present the adversarial review report, diff summary, and remote branch link to the human engineer.
   - **Recommended Commands**: Suggest using [/explain-diff](../explain-diff/SKILL.md) to inspect file-by-file diffs and [/signoff](../signoff/SKILL.md) to conduct Socratic reverse-interview signoff.
   - Do **not** initiate an automated merge. The human engineer retains full ownership of the decision to merge into `<base_branch>`.
   - Once merged by the user, remove the worktree:
     ```bash
     git worktree remove ~/.gemini/tmp/worktrees/gemini_<sanitized-feature-name>
     git worktree prune
     ```
     *Note: If the worktree contains untracked or uncommitted changes and you want to discard them, add `--force` to the removal command.*
