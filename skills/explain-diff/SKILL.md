---
name: explain-diff
description: Interactive, neutral diff explanation walkthrough (overall summary, per-hunk walkthroughs, Q&A). Do not use to find bugs/quality issues.
---

# Diff Explanation Walkthrough

Resolve context, generate the diff, and interactively explain it: overall summary first, then per-hunk explanations of whichever changes the user picks, with drill-down Q&A.

## Core Rules
> [!IMPORTANT]
> - **Read-only**: This skill never modifies the workspace or worktree and never runs tests, linters, or `setup_review_env.py`. Only read files (via the worktree or `git show`). Creating temporary, ephemeral scratch files under the conversation's scratch directory for diff reading does not violate this rule, provided cleanup only removes these generated scratch files.
> - **Neutral, not adversarial**: Describe what changed and why (inferred from code and commit messages). Do not critique or hunt for bugs. If the user asks for issues to be found, suggest switching to `/adversarial-review`.
> - **Exact hunks**: Quote diff hunks byte-for-byte in fenced `diff` blocks. Explanations may be terse (caveman), hunks may not be paraphrased.

## Context Resolution

Two modes, chosen by what the user provides:

* **Commit mode**: The user names a specific commit SHA or range. Skip the resolver and diff directly in the active workspace:
  - Single commit: `git show <sha>` (diff vs. its parent).
  - Range: `git diff <a>...<b>`.
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
> **Subagent Delegation (Antigravity Only)**: If the changeset is exceptionally large (many files or large diffs), the main agent should delegate the task. Invoke the built-in `research` subagent (optimized for read-only exploration) to analyze the diff chunks in the background and draft the overall summary and file-by-file gists; wait for its report before presenting the summary/menu. This delegation contract is Antigravity-only; in other runtimes (e.g. Gemini CLI), the main agent performs these steps directly.

1. **Get the Diff Safely**: To prevent terminal command output truncation (which silently trims long diff outputs or lines), do NOT read the raw output of `git diff` directly from the terminal tool. Instead:
   a. Run `git diff "<reference_commit_hash>...<commit_hash>" --stat > "<appDataDir>/brain/<conversation-id>/scratch/temp_diff_stat.txt"` to see all changed files.
   b. Save the target diff to a temporary file under the conversation's scratch directory:
      `git diff "<reference_commit_hash>...<commit_hash>" -- "<file>" > "<appDataDir>/brain/<conversation-id>/scratch/temp_diff.txt"`
   c. Read the diff file using the `view_file` tool. This guarantees paginated, untruncated access to every hunk.

   *Execution & Robustness Directives:*
   - **Use `view_file`**: Read files in chunks of 800 lines max. *Reason: Prevents terminal truncation.*
   - **Create and Quote Paths**: Run `mkdir -p` first; quote all paths in commands. *Reason: Handles directories with special characters/spaces safely.*
   - **Manage Scratch Files**: Keep naming distinct (e.g. `temp_diff_stat.txt`, `temp_diff_all.txt`, `temp_diff.txt`, `temp_diff_paths.txt`). *Reason: Avoids concurrency name collisions.*
   - **Parse Large Diff Stats**: Run `git diff ... --name-status -z`. *Reason: Handles renames and non-standard characters safely.*
   - **Sequential Reading & EOF**: Read until file viewer lines exceed calculated count. *Reason: Avoids terminal cutoff.*
   - **Omit Binary Files**: Skip text diffs for binary files; report their changes in the summary. *Reason: Prevents binary content corruption.*
   - **Clean Up Safely**: Delete only temporary files when done. *Reason: Leaves repository and worktree untouched.*
   - **Reference Guide**: For full detail on tools compatibility, EOF edge cases, and path safety, see [robustness_guide.md](resources/robustness_guide.md).

2. **Overall Summary**: Open with a short summary of the whole changeset: what it does, why (inferred), and the changes grouped into logical themes (a theme may span files). Include scale (files touched, insertions/deletions).
3. **Navigation Menu**: Present a numbered menu of changed files — path, `+/-` stats, hunk count, one-line gist — plus:
   - `[a]` walk through every file in order,
   - `[s]` expand the overall summary,
   - `[q]` finish.
   Ask the user to pick. This mirrors the branch-selection interaction of adversarial-review.
4. **Explain a Selection**: For the chosen file, go **hunk by hunk**: quote each hunk verbatim in a fenced `diff` block, then explain in plain language what changed, why, and how it connects to the rest of the changeset. Pull surrounding context from `worktree_path` or `git show` when a hunk is unclear in isolation.
   - **Targeted Prose/Text Highlights**: For text/markup formats (e.g., `.tex`, `.md`, `.txt`, `.rst`) or whenever a modified line is long, identify and explicitly highlight the precise inline edits (e.g., `word_A` -> `word_B`) so that subtle changes are not lost in long diff paragraphs.
5. **Drill-down**: After each file, invite follow-up questions (e.g. callers of a changed function, prior behavior via `git log`/`git blame`, related hunks elsewhere). Answer them, then re-present the menu abbreviated, marking already-explained files, until the user picks `[q]` or confirms they are done.
6. Output everything directly in chat. Do not save reports to files unless requested.
