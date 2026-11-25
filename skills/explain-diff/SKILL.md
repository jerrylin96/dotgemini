---
name: explain-diff
description: Interactive, neutral diff explanation walkthrough across topic-by-topic, commit-by-commit, and file-by-file lenses with Q&A. Do not use to find bugs/quality issues.
---

# Diff Explanation Walkthrough (`/explain-diff`)

Resolve the target changeset, extract diffs without truncation, and interactively explain what changed and why across topic, commit, or file walkthrough lenses.

## Core Rules
* **Strictly read-only**: Never modify repository or worktree files and never run tests, linters, or `setup_review_env.py`. Only read files and write/remove temporary diff files under `<appDataDir>/brain/<conversation-id>/scratch/`.
* **Neutral, not adversarial**: Explain mechanics, intent, and cross-file data flow. Do not hunt for bugs or nitpick style (point to `/adversarial-review` if asked for bug finding).
* **Grounded verbatim hunks**: Never dump bulk `git diff` or `python3 -c` diff scripts directly to terminal stdout where truncation causes hallucination. Always redirect diffs to scratch files, read through EOF via `view_file` / `read_file` (`<=800` lines per read), verify command exit code `0` (fail closed on errors), and quote hunks byte-for-byte in fenced `diff` blocks.

## 1. Context Resolution

* **Commit / Range mode**:
  * Single commit `<sha>`: `<commit_hash>` is `<sha>`, `<reference_commit_hash>` is `<sha>^`. For a root commit (no parent), use Git's empty tree `4b825dc642cb6eb9a060e54bf8d69288fbee4904` with two-argument `git diff "<empty-tree>" "<sha>"` (never three-dot `...` on a tree object).
  * Commit range `<a>..<b>` / `<a>...<b>`: `<reference_commit_hash>` is `<a>`, `<commit_hash>` is `<b>`.
* **Branch or PR mode (default)**: Reuse the shared resolver (supports branch names, `#N`, or PR/MR URLs):
  ```bash
  python3 ~/.gemini/skills/adversarial-review/scripts/resolve_branches.py [optional_target] [--reference <branch>]
  ```
  If `"ambiguous": true`, present candidates and ask the user to pick. Mention `fetch_error` if non-null.

## 2. Extract Overview & Diff Safely

For very large diffs, consider delegating initial clustering to a `research` subagent. Save overview and full diff with explicit `--find-renames --find-copies` (see [robustness_guide.md](resources/robustness_guide.md)):

```bash
mkdir -p "<appDataDir>/brain/<conversation-id>/scratch"
git log --no-merges --reverse --format="%h %s (%an)" "<reference_commit_hash>..<commit_hash>" > "<appDataDir>/brain/<conversation-id>/scratch/temp_commits.txt"
git diff "<reference_commit_hash>...<commit_hash>" --stat --find-renames --find-copies > "<appDataDir>/brain/<conversation-id>/scratch/temp_diff_stat.txt"
git diff "<reference_commit_hash>...<commit_hash>" --find-renames --find-copies > "<appDataDir>/brain/<conversation-id>/scratch/temp_diff_all.txt"
```
*(For root commits, replace `"<a>...<b>"` with two-argument `"<empty-tree>" "<commit_hash>"`.)*

If all commands exit `0` and `temp_diff_all.txt` is empty, output `No differences detected between <reference> and <target>.` and stop.

## 3. Summary & Tri-Lens Navigation Menu

1. Give a concise summary of purpose, inferred rationale, scale (files changed, `+/-` lines, commit count $K$), and chronological commit list when $K > 1$.
2. Group changes into 2–5 cohesive functional topics (plus optional `[Miscellaneous / Tooling]`, max 6; collapse into 1 topic `[t1]` for single-concern or `<=3`-hunk diffs) ordered by architectural/data-flow dependency. Note non-text changes cleanly (`[binary file: ...]`, `[rename: a -> b]`, `[deleted file: ...]`, `[mode change: ...]`).
3. Present the Tri-Lens menu (omit `[c]` for single commit $K \le 1$):

```text
Summary: 3 topics across 6 files (+112 / -28)

Topics:
  [t1] Domain Models & Migrations (models.py, migrations/...)
  [t2] API Handlers & Serialization (routes.py, schemas.py)
  [t3] Test Suite (tests/test_routes.py)

Walkthrough Lenses:
  [t] Topic-by-topic walkthrough (cross-file synthesis; recommended)
  [f] File-by-file walkthrough (cumulative per-file diffs)
  [c] Commit-by-commit walkthrough (chronological 1 -> K)
  [t1..tN] Jump to topic | [c1..cK] Jump to commit | [s] Summary | [q] Finish
```

## 4. Walkthrough Flows & Q&A

* **Topic-by-topic (`[t]`)**: State a 2–3 sentence **Topic Narrative**, extract path-scoped diff (`git diff "<reference_commit_hash>...<commit_hash>" --find-renames --find-copies -- "<file1>" "<file2>" > "<appDataDir>/brain/<conversation-id>/scratch/temp_topic_diff.txt"`), read through EOF via `view_file`, quote verbatim `diff` hunks tagged with `[path:Lstart-Lend]`, and add **Cross-File Interaction Commentary** explaining how the pieces connect.
* **Commit-by-commit (`[c]`)**: Extract commit message and hunks via `git show --find-renames --find-copies "<sha>" > "<appDataDir>/brain/<conversation-id>/scratch/temp_commit_diff.txt"`, read via `view_file`, quote verbatim hunks, and explain how the commit advances the series.
* **File-by-file (`[f]`)**: List numbered files (`[1..N]` pick file, `[a]` walk all), extract `"<file>"` diff to `temp_diff.txt`, read via `view_file`, and explain hunk by hunk.
* **Navigation & Cleanup**: Offer `[n]` next, `[p]` previous, `[m]` menu, `[t]`/`[f]`/`[c]` lens switch, `[s]` summary, `[q]` finish, plus open Q&A (`git log`/`git blame`/callers). Remove scratch `temp_*.txt` files with `rm -f --` when finished.
