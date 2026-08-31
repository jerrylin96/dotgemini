---
name: explain-diff
description: Interactive, neutral diff explanation walkthrough (overall summary, per-hunk and commit-by-commit walkthroughs, Q&A). Do not use to find bugs/quality issues.
---

# Diff Explanation Walkthrough

Resolve context, generate the diff, and interactively explain it: overall summary first (including commit series narrative for multi-commit changesets), then walkthroughs by commit or by file, with drill-down Q&A.

## Core Rules
> [!IMPORTANT]
> - **Read-only**: This skill never modifies the workspace or worktree and never runs tests, linters, or `setup_review_env.py`. Only read files (via the worktree or `git show`). Creating temporary, ephemeral scratch files under the conversation's scratch directory for diff reading does not violate this rule, provided cleanup only removes these generated scratch files.
> - **Neutral, not adversarial**: Describe what changed and why (inferred from code and commit messages). Do not critique or hunt for bugs. If the user asks for issues to be found, suggest switching to `/adversarial-review`.
> - **Exact hunks**: Quote diff hunks byte-for-byte in fenced `diff` blocks. Explanations may be terse (caveman), hunks may not be paraphrased.

## Context Resolution

Three modes, chosen by what the user provides:

* **Commit mode**: The user names a specific commit SHA or range. Skip the resolver and diff directly in the active workspace:
  - Single commit: `<commit_hash>` is `<sha>`, `<reference_commit_hash>` is `<sha>^`. For root/parentless commits (no parent), set `<reference_commit_hash>` to the Git empty tree `4b825dc642cb6eb9a060e54bf8d69288fbee4904` for the two-dot commit list step (1b), and use two-argument `git diff <empty-tree> <sha>` or `git show <sha>` directly for stats/diffs (steps 1c–1e, 5b); never use three-dot `...` with the empty tree as tree objects do not support merge-base resolution.
  - Range: `git diff <a>...<b>` where `<reference_commit_hash>` is `<a>` and `<commit_hash>` is `<b>`.
* **PR mode**: The user names a pull/merge request (number or web URL). Use the same resolver with the PR target — `--pr <N>`, or pass `#N`/the URL positionally. It fetches the PR head ref from the remote, so fork PRs work without a local branch; see [adversarial-review/SKILL.md](../adversarial-review/SKILL.md) for details, the extra `pr_number` JSON field, and the PR-baseline note (`--reference` override, optional best-effort `gh pr view` for the PR title/description — the description makes the "why" in the summary much better, but `gh` is never required).
* **Branch mode (default)**: The user names a branch or gives no target. Reuse the adversarial-review branch resolver — same script, same worktree cache, same protocol:
  ```bash
  python3 ~/.gemini/skills/adversarial-review/scripts/resolve_branches.py [optional_target_branch] [--reference <branch>]
  ```
  - The JSON response schema, ambiguity/ask-user rule, and no-branches handling are documented in [adversarial-review/SKILL.md](../adversarial-review/SKILL.md). Follow them identically: if `"ambiguous": true`, present the candidates and ask the user to pick the feature branch.
  - If `fetch_error` is set, mention that the explanation may be based on stale local tracking refs.
  - The resolver checks out the feature branch at `worktree_path`. Use it only for **reading** surrounding context; alternatively use `git show <feature_ref>:<path>`. Never run commands that write there.

## Execution Steps

> [!TIP]
> **Subagent Delegation**: If the changeset is exceptionally large (many files or large diffs), the main agent should delegate the task. Invoke the built-in `research` subagent (optimized for read-only exploration) to analyze the diff chunks in the background and draft the overall summary and file-by-file gists; wait for its report before presenting the summary/menu.

1. **Get the Diff Safely & Extract Commits**: To prevent terminal command output truncation (which silently trims long diff outputs or lines), do NOT read raw git outputs directly from the terminal. Instead:
   a. **Create Scratch Directory**: Run `mkdir -p "<appDataDir>/brain/<conversation-id>/scratch"` to ensure the path exists.
   b. **Extract Commit List**: Write chronological commit history to scratch file:
      `git log --no-merges --reverse --format="%h %s (%an)" "<reference_commit_hash>..<commit_hash>" > "<appDataDir>/brain/<conversation-id>/scratch/temp_commits.txt"`
      *(Note: `--no-merges` extracts linear commits for the chronological narrative; any changes from merge conflict resolutions are captured in the cumulative file-by-file diff).*
   c. **Write Statistics**: Save the changed-file statistics:
      `git diff "<reference_commit_hash>...<commit_hash>" --stat > "<appDataDir>/brain/<conversation-id>/scratch/temp_diff_stat.txt"`
   d. **Write Complete Diff**: Save the full diff output for overall analysis:
      `git diff "<reference_commit_hash>...<commit_hash>" > "<appDataDir>/brain/<conversation-id>/scratch/temp_diff_all.txt"`
   e. **Enumerate Paths**: For unusually large changesets, run null-delimited path/status enumeration:
      `git diff "<reference_commit_hash>...<commit_hash>" --name-status -z > "<appDataDir>/brain/<conversation-id>/scratch/temp_diff_paths.txt"`
   f. **Read via File Viewer**: Read `temp_commits.txt`, `temp_diff_stat.txt`, and `temp_diff_all.txt` using `view_file` to determine total commit count ($K$, where $K$ is the number of commits in `temp_commits.txt`) and file count.

   *Execution & Robustness Directives:*
   - **Use `view_file`**: Read files in chunks of 800 lines max. *Reason: Prevents terminal truncation.*
   - **Create and Quote Paths**: Run `mkdir -p` first; quote all paths in commands. *Reason: Handles directories with special characters/spaces safely.*
   - **Manage Scratch Files**: Keep naming distinct (`temp_commits.txt`, `temp_commit_msg.txt`, `temp_commit_stat.txt`, `temp_commit_diff.txt`, `temp_diff_stat.txt`, `temp_diff_all.txt`, `temp_diff.txt`, `temp_diff_paths.txt`). *Reason: Avoids concurrency name collisions.*
   - **Parse Large Diff Stats**: Run `git diff ... --name-status -z` strictly for path and status enumeration. *Reason: Handles renames and non-standard characters safely.*
   - **Sequential Reading & EOF**: Read until file viewer lines exceed calculated count. *Reason: Avoids terminal cutoff.*
   - **Omit Binary Files**: Skip text diffs for binary files; report their changes in the summary. *Reason: Prevents binary content corruption.*
   - **Clean Up Safely**: Delete only temporary scratch files when done. *Reason: Leaves repository and worktree untouched.*
   - **Reference Guide**: For full detail on tools compatibility, EOF edge cases, and path safety, see [robustness_guide.md](resources/robustness_guide.md).

2. **Overall Summary**:
   - Open with a concise summary of the whole changeset: purpose, inferred why, and logical themes. Include scale (files touched, insertions/deletions, and commit count $K$).
   - **Commit Series Timeline**: If multi-commit ($K > 1$), list the chronological commit sequence from `temp_commits.txt` with SHA, author, and commit subject.

3. **Dual-Lens Navigation Menu**:
   - **Single commit ($K \le 1$)**: Present standard file list directly:
     - `[1..N]` choose specific file,
     - `[a]` walk through every file in order,
     - `[s]` expand the overall summary,
     - `[q]` finish.
   - **Multi-commit ($K > 1$)**: Present dual-lens choice:
     ```text
     Select walkthrough lens:
       [c] Commit-by-commit walkthrough (chronological narrative: 1 → K)
       [f] File-by-file walkthrough (cumulative changeset across all commits)
       [c1..cK] Jump directly to a specific commit (e.g. c1, c2)
       [s] Expand overall summary
       [q] Finish
     ```

4. **Commit-by-Commit Walkthrough Flow (`[c]`)**:
   For the selected commit (or iterating sequentially from commit 1 to $K$):
   a. **Commit Header**: Extract full commit message and metadata:
      `git log -1 --format="%H %an%n%B" "<sha>" > "<appDataDir>/brain/<conversation-id>/scratch/temp_commit_msg.txt"`
      Read with `view_file` and display commit SHA, author, and complete commit message.
   b. **Commit File Stat**: Extract commit-specific file statistics:
      `git show --stat --format="" "<sha>" > "<appDataDir>/brain/<conversation-id>/scratch/temp_commit_stat.txt"`
   c. **Hunk Inspection**: For each modified file in the commit, extract diff:
      `git show "<sha>" -- "<file>" > "<appDataDir>/brain/<conversation-id>/scratch/temp_commit_diff.txt"`
      Read with `view_file` and quote diff hunks verbatim in fenced `diff` blocks. Explain what changed, why, and how it fits into the commit sequence.
   d. **Intra-Commit Transition**:
      - `[n]` Next commit in series
      - `[p]` Previous commit
      - `[s]` Expand overall summary
      - `[f]` Switch to cumulative file-by-file view
      - `[q]` Finish

5. **File-by-File Walkthrough Flow (`[f]`)**:
   For cumulative file walkthrough:
   a. Present numbered menu of changed files (path, `+/-` stats, hunk count, one-line gist) plus:
      - `[1..N]` choose specific file,
      - `[a]` walk through every file in order,
      - `[c]` switch back to commit-by-commit walkthrough (if $K > 1$),
      - `[s]` expand the overall summary,
      - `[q]` finish.
   b. For the chosen file, write target diff to `temp_diff.txt` (`git diff "<reference_commit_hash>...<commit_hash>" -- "<file>" > "<appDataDir>/brain/<conversation-id>/scratch/temp_diff.txt"`).
   c. Go hunk by hunk: quote each hunk verbatim in fenced `diff` block, explain what changed and why.
   d. **Targeted Prose/Text Highlights**: For text/markup formats (`.tex`, `.md`, `.txt`, `.rst`), highlight precise inline edits (`word_A` -> `word_B`).

6. **Drill-down & Q&A**:
   After each commit or file, invite follow-up questions (callers of changed functions, prior behavior via `git log`/`git blame`, related hunks). Output everything directly in chat. Do not save reports to files unless requested.
