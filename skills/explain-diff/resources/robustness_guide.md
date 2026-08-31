# Git Diff Robustness Guide

This guide details best practices and compatibility standards for safely extracting, paging, and parsing git diffs.

## 1. Tooling Contract
- **Primary Viewer**: The `view_file` tool is the primary file viewer. It supports 1-indexed, inclusive `StartLine` and `EndLine` parameters to read up to 800 lines of a file per turn.
- **Fallback**: If `view_file` is unavailable, fall back to `read_file` (if available, noting it is best-effort) or shell commands like `sed -n '<start>,<end>p' "<file_path>"` or `head`/`tail`.
- Do not use `cat` or interactive pagers (e.g. `less`).

## 2. Directory Creation & Quoting
- Always ensure the target scratch directory exists before executing redirections: `mkdir -p "<appDataDir>/brain/<conversation-id>/scratch"`.
- Quote all shell paths and parameters in commands to handle paths containing spaces or special characters.

## 3. Temporary File Roles
- `temp_commits.txt`: Stores chronological commit history (`git log --no-merges --reverse --format="%h %s (%an)" ...`).
- `temp_commit_msg.txt`: Stores complete commit metadata and message body (`git log -1 --format="%H %an%n%B" <sha>`).
- `temp_commit_stat.txt`: Stores per-commit changed-file statistics (`git show --stat --format="" ...`).
- `temp_commit_diff.txt`: Stores per-commit per-file diff hunks (`git show <sha> -- <file>`).
- `temp_diff_stat.txt`: Stores cumulative changed-file statistics.
- `temp_diff_all.txt`: Stores complete cumulative diff hunks and context.
- `temp_diff.txt`: Stores the per-file cumulative walkthrough diff. Dynamically extract each file's diff to a single stable location, overwriting it for each selected file.
- `temp_diff_paths.txt`: Stores null-delimited name-status list.
- **Git Log Truncation**: Retrieve commit subjects via `git log --no-merges --reverse ...`. If history is long and risks stdout truncation, redirect to `temp_commits.txt` and read via `view_file`.
- **Commit Range Caveat**: Chronological commit narrative uses two-dot range with `--no-merges` (`<reference_commit_hash>..<commit_hash>`), excluding merge commits. Cumulative diff uses three-dot range (`<reference_commit_hash>...<commit_hash>`), which includes conflict resolutions and reflects branch tip divergence from merge-base.

## 4. Special Git Cases
- **Renames & Modes**: Explicitly check diff headers for renames (`rename from ...`), mode changes (`old mode ... new mode`), and binary files (`Binary files ... differ`).
- **Binary Files**: Report binary changes in the summary, but omit detailed text diffs.

## 5. Pagination & EOF Detection
- To prevent terminal truncation, read files in successive, chunked lines.
- Do not rely on receiving a short chunk as an EOF signal. Instead, calculate the total line count beforehand (e.g. check if the file lacks a trailing newline character and increment by 1). Read iteratively until `StartLine` exceeds this logical line count.

## 6. Cleanup
- **Prohibited Deletions**: Never delete repository-tracked files, worktree-tracked files, unknown paths, or perform broad recursive paths/deletions. Never run deletions inside the repository or worktree.
- **Allowed Deletions (Exception)**: Exact, agent-created temporary files and directories under the verified conversation scratch directory (e.g. `<appDataDir>/brain/<conversation-id>/scratch/`) are an explicit exception and can be safely deleted, even when `<appDataDir>` resides beneath the cloned configuration repository path.
- **Safe Commands**: Use `rm -- <known-file>` and `rmdir <known-empty-directory>` for cleanup (`rm -- <known-file>` remains the default for one-shot deletions, but signal/EXIT trap handlers MUST use `rm -f -- <known-file>` because they are re-entrant and must be idempotent). Never use `rm -rf` in any context. If an OS temporary directory was created via `TEMP_DIR=$(mktemp -d)`, delete only the specific temporary files inside it, then remove the empty directory with `rmdir -- "$TEMP_DIR"`.
