---
name: catchmeup
description: Executive time-window activity summary for PIs, leads, and reviewers (presets: 1d, 1w, 2w, 1mo). Summarizes commits, authors, signoff attestations, and interactive diff drill-downs.
---

# Executive Repository Activity Summary (`/catchmeup`)

Designed for external reviewers, supervisors, team leads, and Principal Investigators (PIs) who need a clear, high-level summary of repository activity over a designated time window, with options to audit signoffs and drill down into specific commits.

## Preset Time Windows

When invoked (e.g. `/catchmeup` or `/catchmeup 2w`), select or resolve the time window:

| Preset | Argument | Period Covered | Description |
|---|---|---|---|
| **1 Day** | `1d` or `1 day` | Past 24 hours | Daily standup / recent check-in |
| **1 Week** *(Default)* | `1w` or `1 week` | Past 7 days | Weekly milestone & sprint progress |
| **2 Weeks** | `2w` or `2 weeks` | Past 14 days | Bi-weekly review / sprint summary |
| **1 Month** | `1mo` or `1 month` | Past 30 days | Monthly release & project audit |

*(Custom durations like `3d` or `6w` are also accepted).*

## Core Rules

> [!IMPORTANT]
> - **Read-Only**: This skill is strictly read-only. It never modifies workspace files, creates commits, or alters repository state.
> - **High-Level First**: Always open with an **Executive Summary** (themes, metrics, signoff attestations) before showing raw commits or line-by-line diffs.
> - **Attestation Transparency**: Parse and explicitly report `Signoff-*` git trailers from commit logs (`git log --grep="Signoff-"` or inspect commit bodies).

## Execution Steps

### 1. Resolve Time Window & Scope
- If user provides no argument (e.g. `/catchmeup`), present the non-linear preset menu (`[1] 1d`, `[2] 1w (default)`, `[3] 2w`, `[4] 1mo`) or default to `1w`.
- Map preset to git `--since` flag:
  - `1d` -> `--since="1 day ago"`
  - `1w` -> `--since="7 days ago"`
  - `2w` -> `--since="14 days ago"`
  - `1mo` -> `--since="30 days ago"`

### 2. Gather Git Activity
Save logs and stats to scratch files to prevent terminal output truncation:
```bash
mkdir -p "<appDataDir>/brain/<conversation-id>/scratch"

# Commit log with author, date, subject
git log --since="<duration>" --pretty=format:"%h|%an|%ad|%s" > "<appDataDir>/brain/<conversation-id>/scratch/temp_catchmeup_log.txt"

# Detailed log including bodies (for Signoff-* trailers)
git log --since="<duration>" > "<appDataDir>/brain/<conversation-id>/scratch/temp_catchmeup_full.txt"

# Shortstat summary
git log --since="<duration>" --shortstat > "<appDataDir>/brain/<conversation-id>/scratch/temp_catchmeup_stat.txt"
```

### 3. Generate Executive Summary
Present a high-level summary organized into 3 clear sections:
1. **Activity Overview**:
   - Time window covered (e.g., *Past 7 Days*).
   - Total commits, active authors/contributors.
   - Total files touched, net insertions/deletions.
2. **Key Feature Themes & Milestones**:
   - Group commit subjects into logical feature/refactor/fix categories.
3. **Signoff & Attestation Audit**:
   - List verified commits containing `Signoff-*` trailers (from [/signoff](../signoff/SKILL.md)).
   - Highlight any unsigned commits merged directly if auditing release candidates.

### 4. Interactive Drill-Down Menu
Present a numbered navigation menu for deeper inspection:
- `[c]` **View Commit List**: Show full chronological commit log with SHAs, authors, and signoff badges.
- `[f]` **View Changed Files**: Show list of touched files ranked by churn (+/- lines).
- `[d]` **Drill Into Specific Commit/File**: Reuse [`/explain-diff`](../explain-diff/SKILL.md) walkthrough engine to inspect hunks or view `git show <sha>`.
- `[q]` **Finish**.

Invite follow-up questions from the reviewer until they confirm completion.
