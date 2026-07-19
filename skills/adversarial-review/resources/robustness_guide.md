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
- **No Repo Deletions**: Never run deletion commands (e.g. `rm`) inside the repository, index, or worktree.
- **Avoid `rm -rf`**: If a temporary directory was created via `TEMP_DIR=$(mktemp -d)`, do not use recursive deletion (`rm -rf`). Instead, delete the specific temporary files created (`rm -- "$TEMP_DIR/file.txt"`) and then safely remove the empty directory using `rmdir -- "$TEMP_DIR"`.
- Cleanly delete only the generated temporary files and directories under the scratch directory when the review ends using `rm -- "<file_path>"`.
