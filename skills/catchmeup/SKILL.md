---
name: catchmeup
description: Executive time-window activity summary for PIs, leads, and reviewers (presets: 1d, 1w, 2w, 1mo). Summarizes commits, authors, signoff attestations, and interactive diff drill-downs.
---

# Executive Repository Activity Summary (`/catchmeup`)

Designed for external reviewers, supervisors, team leads, and Principal Investigators (PIs) who need a clear, high-level summary of repository activity over a designated time window, with options to audit signoffs and drill down into specific commits.

## Preset Time Windows & Duration Grammar

When invoked (e.g. `/catchmeup` or `/catchmeup 2 weeks origin/main`), select or resolve the time window:

| Preset | Argument | Period Covered | Description |
|---|---|---|---|
| **1 Day** | `1d` or `1 day` | Past 24 hours | Daily standup / recent check-in |
| **1 Week** *(Default)* | `1w` or `1 week` | Past 7 days | Weekly milestone & sprint progress |
| **2 Weeks** | `2w` or `2 weeks` | Past 14 days | Bi-weekly review / sprint summary |
| **1 Month** | `1mo` or `1 month` | Past 30 days | Monthly release & project audit |

### Duration Grammar & Validation
- **Accepted Grammar**: `^[0-9]+\s*(d|w|mo|day|days|week|weeks|month|months)$`
- **Validation Rule**: Validate input duration against grammar before interpolating into git commands. If input fails validation, reject it, report invalid duration, and present preset menu (`[1] 1d`, `[2] 1w (default)`, `[3] 2w`, `[4] 1mo`). Trim surrounding whitespace before passing to `--since`.
- **Mapping Rule**:
  - `<N>d` / `<N> day(s)` -> `--since="<N> days ago"`
  - `<N>w` / `<N> week(s)` -> `--since="<N> weeks ago"`
  - `<N>mo` / `<N> month(s)` -> `--since="<N> months ago"`

## Core Rules

> [!IMPORTANT]
> - **Read-Only**: This skill is strictly read-only. It never modifies workspace or worktree files, creates commits, or alters repository state. Creating temporary, ephemeral scratch files under the conversation's scratch directory for log/diff reading does not violate this rule, provided cleanup only removes these generated scratch files.
> - **High-Level First**: Always open with an **Executive Summary** (themes, metrics, signoff attestations) before showing raw commits or line-by-line diffs.
> - **Real Attestation Parsing**: Parse exact `Signoff-Reviewed-Commit-SHA` and `Signoff-Status` trailers from attestation commits created by [/signoff](../signoff/SKILL.md) to audit feature commit coverage. Never use globbing in format strings.

## Execution Steps

### 1. Resolve Scope & Target Ref
- Syntax: `/catchmeup [duration] [target_ref]` (default ref: active checked-out HEAD).
- Verify git repository existence (`git rev-parse --is-inside-work-tree`). If not a git repo, display error and halt.
- Resolve stable target SHA:
  ```bash
  git rev-parse <target_ref>
  ```
- *Remote Tracking Warning*: Skill is read-only and does not run `git fetch` automatically. If using a remote tracking branch ref (e.g. `origin/main`), note that un-fetched remote commits will not be included.

### 2. Gather Git Activity & Parse Trailers
To prevent terminal truncation, save raw outputs to the conversation's scratch directory. Note that attestation commits carrying `Signoff-Reviewed-Commit-SHA` trailers are excluded via `--invert-grep --grep="^Signoff-Reviewed-Commit-SHA:"` so they do not pollute feature commit counts or churn metrics:

```bash
mkdir -p "<appDataDir>/brain/<conversation-id>/scratch"

# Feature commit log (excluding empty attestation commits and merge commits)
git log <target_ref> --since="<duration>" --no-merges --invert-grep --grep="^Signoff-Reviewed-Commit-SHA:" --pretty=format:"%h|%an|%ad|%s" > "<appDataDir>/brain/<conversation-id>/scratch/temp_catchmeup_log.txt"

# Shortstat summary (excluding attestation commits)
git log <target_ref> --since="<duration>" --no-merges --invert-grep --grep="^Signoff-Reviewed-Commit-SHA:" --shortstat > "<appDataDir>/brain/<conversation-id>/scratch/temp_catchmeup_stat.txt"

# Unique files touched (excluding attestation commits)
git log <target_ref> --since="<duration>" --no-merges --invert-grep --grep="^Signoff-Reviewed-Commit-SHA:" --name-only --format="" | sort -u > "<appDataDir>/brain/<conversation-id>/scratch/temp_catchmeup_files.txt"

# Attestation commits carrying explicit Signoff-* trailers
git log <target_ref> --since="<duration>" --grep="^Signoff-Reviewed-Commit-SHA:" --format="format:%H%n%(trailers:key=Signoff-Reviewed-Commit-SHA,only=true,valueonly=true)%(trailers:key=Signoff-Status,only=true,valueonly=true)---" > "<appDataDir>/brain/<conversation-id>/scratch/temp_catchmeup_attestations.txt"
```

Read generated scratch files using `view_file` in chunks of `<=800-line` max to guarantee untruncated access.

### 3. Generate Executive Report

#### Zero-Commit Handling
If no commits exist in the time window, display:
`"No commits found in the last <duration> on <target_ref> (resolved: <SHA>). Baseline commit: <SHA>."`

#### Report Structure
1. **Header & Context**:
   - **Target Ref**: `<target_ref>` (Resolved SHA: `<sha>`)
   - **Period Covered**: Past `<duration>`
2. **Activity Overview**:
   - Total substantive feature commits (excluding empty `Signoff-*` attestation commits).
   - Total active authors/contributors.
   - Unique files touched count (`temp_catchmeup_files.txt`).
   - Cumulative churn: total insertions (`+`) and deletions (`-`) aggregated across feature commits.
3. **Feature Themes & Milestones**:
   - Group commit subjects (`temp_catchmeup_log.txt`) into logical feature/fix/refactor themes (`--no-merges`).
4. **Attestation Audit**:
   - Map `Signoff-Reviewed-Commit-SHA` trailers back to feature commits:
     - **Verified (`VERIFIED_BY_HUMAN`)**: Fully signed off with transcript reference digest.
     - **Downgraded (`VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST`)**: Human approved without transcript digest attestation.
     - **Unsigned**: Substantive commits without matching attestation trailer.

### 4. Interactive Drill-Down & Cleanup
Present navigation menu:
- `[c]` **View Commit List**: Show chronological commit log with SHAs and signoff badges.
- `[f]` **View Changed Files**: Show list of unique touched files ranked by churn.
- `[d]` **Drill Into Specific Commit/File**: Delegate to @skill:explain-diff for hunk walkthroughs or view `git show <sha>`.
- `[q]` **Finish**.

#### Mandatory Cleanup Step
Upon completion or failure, clean up ephemeral scratch files:
```bash
rm -- "<appDataDir>/brain/<conversation-id>/scratch/temp_catchmeup_"*.txt
```
