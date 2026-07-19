# Git Diff Robustness Guide

This guide details best practices and compatibility standards for safely extracting, paging, and parsing git diffs.

## 1. Tooling Contract
- **Antigravity CLI**: The `view_file` tool is the primary, guaranteed file viewer. It supports 1-indexed, inclusive `StartLine` and `EndLine` parameters to read up to 800 lines of a file per turn.
- **Gemini CLI (or other runtimes)**: If `view_file` is unavailable, fall back to `read_file` (if available, noting it is best-effort) or shell commands like `sed -n '<start>,<end>p' "<file_path>"` or `head`/`tail`.
- Do not use `cat` or interactive pagers (e.g. `less`).

## 2. Directory Creation & Quoting
- Always ensure the target scratch directory exists before executing redirections: `mkdir -p "<appDataDir>/brain/<conversation-id>/scratch"`.
- Quote all shell paths and parameters in commands to handle paths containing spaces or special characters.

## 3. Temporary File Roles
- `temp_diff_stat.txt`: Stores changed-file statistics.
- `temp_diff_all.txt`: Stores complete diff hunks and context.
- `temp_diff_paths.txt`: Stores null-delimited name-status list.

## 4. Special Git Cases
- **Renames & Modes**: Explicitly check diff headers for renames (`rename from ...`), mode changes (`old mode ... new mode`), and binary files (`Binary files ... differ`).
- **Binary Files**: Report binary changes in the summary, but omit detailed text diffs.

## 5. Pagination & EOF Detection
- To prevent terminal truncation, read files in successive, chunked lines.
- Do not rely on receiving a short chunk as an EOF signal. Instead, calculate the total line count beforehand (e.g. check if the file lacks a trailing newline character and increment by 1). Read iteratively until `StartLine` exceeds this logical line count.

## 6. Cleanup
- **Prohibited Deletions**: Do not delete repository-tracked files, worktree files, unknown paths, or perform broad recursive deletion (`rm -rf`). Never run deletions inside the repository or worktree.
- **Allowed Deletions**: Cleanly delete only the exact, agent-created temporary files and directories under the known conversation scratch directory (e.g., `<appDataDir>/brain/<conversation-id>/scratch/`).
- **Safe Commands**: Use `rm -- "<file_path>"` for files and `rmdir -- "<empty_dir_path>"` for directories. Never use `rm -rf` for cleanup. If an OS temporary directory was created via `TEMP_DIR=$(mktemp -d)`, delete only the specific temporary files inside it, then remove the empty directory with `rmdir -- "$TEMP_DIR"`.
