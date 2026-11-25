# Git Diff Robustness Guide

Best practices for extracting, paging, and quoting git diffs without truncation or hallucination.

## 1. Truncation Handling & Grounded Quotation Invariants
* **Terminal Truncation Risk**: Dumping raw `git diff` or ad-hoc `python3 -c` diff scripts directly to terminal stdout risks silent truncation (`<truncated ...>`, `observation too long`, `stdout_truncated: true`), causing models to hallucinate missing diff lines.
* **Scratch Redirection & Paged Reading**: Always `mkdir -p "<appDataDir>/brain/<conversation-id>/scratch"`, quote all shell arguments, redirect git output to scratch files (`temp_commits.txt`, `temp_diff_stat.txt`, `temp_diff_all.txt`, `temp_topic_diff.txt`, `temp_commit_diff.txt`, `temp_diff.txt`), check exit code `0` (fail closed on errors), and read through EOF in `<=800`-line chunks via `view_file` (or `read_file` fallback) before emitting any fenced `diff` block.

## 2. Git Range & Flag Conventions
* **Rename & Copy Detection**: Pass explicit `--find-renames --find-copies` across diff commands so behavior is independent of local `diff.renames` config (`--find-copies-harder` is omitted due to $O(N \times M)$ repository scan cost).
* **Commit Range Caveat & Root-Commit Exception**: Commit lists use two-dot `--no-merges` (`<a>..<b>`); cumulative branch diffs use three-dot merge-base syntax (`<a>...<b>`). For root commits compared against Git's empty tree `4b825dc642cb6eb9a060e54bf8d69288fbee4904`, always use two-argument `git diff "<empty-tree>" "<commit_hash>"` (tree objects do not support `...`).
* **Path-Limited Diffs & Non-Text Changes**: When diffing a single path (`-- "<file>"`) whose rename/copy source lies outside the pathspec, consult `temp_diff_stat.txt` or `temp_diff_all.txt` headers so `[rename: old -> new]` / `[copy: src -> dst]` context is preserved. Summarize binary files, submodules, symlinks, and mode-only changes via metadata tags rather than text diff blocks.

## 3. Cleanup
* Never delete repository or worktree files. Clean up only exact agent-created scratch files under `<appDataDir>/brain/<conversation-id>/scratch/` using `rm -f -- <known-file>`.
