# Git Diff Robustness Guide

This guide details best practices and compatibility standards for safely extracting, paging, and parsing git diffs.

## 1. Tooling Contract
- **Primary Viewer**: The `view_file` tool is the primary file viewer for human-readable text artifacts (`temp_commits.txt`, `temp_diff_stat.txt`, `temp_diff_all.txt`, `temp_commit_msg.txt`, `temp_commit_stat.txt`, `temp_diff.txt`). It supports 1-indexed, inclusive `StartLine` and `EndLine` parameters to read up to 800 lines of a file per turn.
- **NUL-Stream Parser (No `view_file`)**: Do NOT pass NUL-delimited streams (`temp_diff_numstat.txt` and `temp_diff_paths.txt`) through `view_file`. Parse them directly as raw bytes using Python `Path.read_bytes().split(b'\0')` or a streaming byte parser for exceptionally large changesets.
- **Fallback**: If `view_file` is unavailable, fall back to `read_file` (if available, noting it is best-effort) or shell commands like `sed -n '<start>,<end>p' "<file_path>"` or `head`/`tail`.
- Do not use `cat` or interactive pagers (e.g. `less`).

## 2. Directory Creation & Quoting
- Always ensure the target scratch directory exists before executing redirections: `mkdir -p "<appDataDir>/brain/<conversation-id>/scratch"`.
- Quote all shell paths and parameters in commands to handle paths containing spaces or special characters.

## 3. Temporary File Roles
- `temp_commits.txt`: Stores chronological commit history (`git log --no-merges --reverse --format="%h %s (%an)" ...`).
- `temp_commit_msg.txt`: Stores complete commit metadata and message body (`git log -1 --format="%H %an%n%B" <sha>`).
- `temp_commit_stat.txt`: Stores per-commit changed-file statistics (`git show --stat --format="" --find-renames --find-copies ...`).
- `temp_commit_diff.txt`: Stores per-commit per-file diff hunks (`git show --find-renames --find-copies <sha> -- <file>`).
- `temp_diff_stat.txt`: Stores cumulative changed-file statistics, used for topic-by-topic clustering and high-level changeset partitioning (`git diff ... --stat --find-renames --find-copies`).
- `temp_diff_numstat.txt`: Stores machine-readable line insertion/deletion totals (`git diff ... --numstat -z --find-renames --find-copies`), used for precise text line reconciliation.
- `temp_diff_all.txt`: Stores complete cumulative diff hunks and context (`git diff ... --find-renames --find-copies`).
- `temp_diff.txt`: Stores the per-file cumulative walkthrough diff. Dynamically extract each file's diff to a single stable location, overwriting it for each selected file (`git diff ... --find-renames --find-copies -- <file>`).
- `temp_diff_paths.txt`: Optional scratch file generated only for large changesets. Stores null-delimited name-status list (`git diff ... --name-status -z --find-renames --find-copies`), used for path/status enumeration and large diff topic clustering. Must only be read when generated.
- **Git Log Truncation**: Retrieve commit subjects via `git log --no-merges --reverse ...`. If history is long and risks stdout truncation, redirect to `temp_commits.txt` and read via `view_file`.
- **Commit Range Caveat & Root Exception**: Chronological commit narrative uses two-dot range with `--no-merges` (`<reference_commit_hash>..<commit_hash>`), excluding merge commits. Cumulative diff uses three-dot range (`<reference_commit_hash>...<commit_hash>`), which includes conflict resolutions and reflects branch tip divergence from merge-base. *Root-commit exception*: For root/parentless commits where `<reference_commit_hash>` is the empty tree `4b825dc642cb6eb9a060e54bf8d69288fbee4904`, two-argument direct diff `git diff "<empty-tree>" "<commit_hash>"` is used instead across all commands, as tree objects do not support three-dot merge-base resolution.
- **Explicit Rename and Copy Detection Flags (`--find-renames --find-copies`)**: Always specify explicit `--find-renames --find-copies` (equivalent to `-M -C`) across all diff artifact commands so rename and copy detection is deterministic and immune to differing local Git configurations (`diff.renames`). The `--find-copies-harder` flag is intentionally excluded because it checks all unmodified repository files as potential copy sources, which incurs an $O(N \times M)$ CPU cost and severe performance latency on large repositories.
- **Path-Limited File Diff Representation**: When diffing a single target path (`-- "<file>"`), Git pathspec filtering omits the source path if it is outside the pathspec. The agent must use the global status records from `temp_diff_paths.txt` or `temp_diff_numstat.txt` to display the source relationship metadata tag (e.g. `[rename: <old_path> -> <new_path>]` or `[copy: <source_path> -> <target_path>]`).

## 4. Special Git Cases & Changed-File Accounting
- **Renames & Copies**:
  - In `git diff --stat --find-renames --find-copies`, a rename counts as **1 changed file** (e.g., `old => new | 0`), and a copy counts as **1 changed file** (the newly created copy target).
  - In `git diff --name-status -z --find-renames --find-copies`, a rename produces: `R<score>\0<old_path>\0<new_path>\0`, and a copy produces: `C<score>\0<source_path>\0<target_path>\0`.
  - In `git diff --numstat -z --find-renames --find-copies`, a rename produces: `<added>\t<deleted>\t\0<old_path>\0<new_path>\0`, and a copy produces: `<added>\t<deleted>\t\0<source_path>\0<target_path>\0`.
  - **Accounting Invariant**: A pure rename represents **1 changed-file logical entity ($U$)** matching `git diff --stat`'s file count. In topic file lists, it is displayed as `[rename: <old_path> -> <new_path>]` and contributes 1 to its topic's membership count ($M$). A copy (`C`) represents 1 changed-file entity (the new target file, noted as `[copy: <source> -> <target>]`) and contributes 1 to $U$ and 1 to $M$.
- **Submodules (gitlinks, mode `160000`)**: Submodule commit pointer changes count as 1 changed-file entity in $U$. For line accounting, submodules strictly follow `temp_diff_numstat.txt`: when numstat reports 0 or `-\t-\t` (non-text), they contribute 0 to text line additions/deletions and are reconciled under metadata tags: `[submodule: <path> (<old_sha> -> <new_sha>)]`.
- **Symlinks & Typechanges (`120000` / `T`)**: Symlink target updates or file-type changes count as 1 changed-file entity in $U$. They strictly follow `temp_diff_numstat.txt` line counts, and are displayed with explicit metadata tags: `[symlink: <path> -> <target>]` or `[typechange: <path> (<old_type> -> <new_type>)]`.
- **Binary Files**: Report binary changes in the summary using explicit old/new byte sizes (e.g., `[binary file: <path> (old: X bytes -> new: Y bytes)]`), keeping byte sizes separate from text line math, and omit detailed text diffs to prevent corrupted rendering.
- **Topic Clustering**: For topic-by-topic walkthroughs, cluster hunks semantically across files into cohesive functional themes. When changesets are exceptionally large, inspect `temp_diff_stat.txt`, `temp_diff_numstat.txt`, and (when generated) `temp_diff_paths.txt` first to partition files before reading full diff chunks.

## 5. NUL-Safe Path and Numstat Stream Parsing (`-z`)
Both `temp_diff_paths.txt` (`--name-status -z --find-renames --find-copies`) and `temp_diff_numstat.txt` (`--numstat -z --find-renames --find-copies`) emit NUL-byte (`\0`) delimited streams to guarantee safety against file paths containing spaces, quotes, newlines, or Unicode characters.
- **Parsing `--name-status -z --find-renames --find-copies`**:
  Read raw content as bytes and split by `b'\0'`. Consume tokens sequentially:
  - If status starts with `R` (rename) or `C` (copy): consume status (e.g. `R100` or `C090`), then next token is `<source_path>`, and subsequent token is `<target_path>`.
  - Otherwise: consume status (`M`, `A`, `D`, `T`), next token is `<path>`.
- **Parsing `--numstat -z --find-renames --find-copies`**:
  - For normal files: `<added>\t<deleted>\t<path>\0`.
  - For binary files: `-\t-\t<path>\0`.
  - For renames/copies: `<added>\t<deleted>\t\0<source_path>\0<target_path>\0`.
- To avoid line-oriented truncation or distortion, parse NUL streams via Python standard library `Path.read_bytes().split(b'\0')` or inline streaming byte parsers. Never pass NUL streams to `view_file`.

## 6. Pagination & EOF Detection
- To prevent terminal truncation, read files in successive, chunked lines.
- Do not rely on receiving a short chunk as an EOF signal. Instead, calculate the total line count beforehand (e.g. check if the file lacks a trailing newline character and increment by 1). Read iteratively until `StartLine` exceeds this logical line count.

## 7. Cleanup
- **Prohibited Deletions**: Never delete repository-tracked files, worktree-tracked files, unknown paths, or perform broad recursive paths/deletions. Never run deletions inside the repository or worktree.
- **Allowed Deletions (Exception)**: Exact, agent-created temporary files and directories under the verified conversation scratch directory (e.g. `<appDataDir>/brain/<conversation-id>/scratch/`) are an explicit exception and can be safely deleted, even when `<appDataDir>` resides beneath the cloned configuration repository path.
- **Safe Commands**: Use `rm -- <known-file>` and `rmdir <known-empty-directory>` for cleanup (`rm -- <known-file>` remains the default for one-shot deletions, but signal/EXIT trap handlers MUST use `rm -f -- <known-file>` because they are re-entrant and must be idempotent). Never use `rm -rf` in any context. If an OS temporary directory was created via `TEMP_DIR=$(mktemp -d)`, delete only the specific temporary files inside it, then remove the empty directory with `rmdir -- "$TEMP_DIR"`.
