---
name: adversarial-review
description: Isolated git worktree adversarial code review across technical correctness, tests, LaTeX builds, and scientific computing invariants. Maps to /adversarial-review.
---

# Adversarial Code Review (`/adversarial-review`)

Perform an empirical, fresh-context adversarial audit of a feature branch, pull request, or active worktree diff without mutating the user's reference checkout.

## Execution Modes

1. **Standalone Mode (`--mode=external`, Default)**:
   - User-triggered `/adversarial-review [branch_or_pr]`.
   - **Strictly read-only** with respect to repository and worktree source files (writing temporary diff files under `<appDataDir>/brain/<conversation-id>/scratch/` is permitted).
   - Performs **1 audit pass**, outputs a top-level `VERDICT: [APPROVE | NEEDS_REVISION | REJECT]`, an `### Adversarial Audit Summary`, and a copy-pasteable `### External PR Action Plan`, then terminates its turn immediately.
2. **Internal Pre-PR Mode (`--mode=pipeline`)**:
   - Invoked via `invoke_subagent` (`TypeName: self`, `Workspace: inherit`) by a parent builder agent to audit an active feature worktree before handoff.
   - If already inside the target feature worktree, inspect the diff against the base branch directly (`git diff <base>...HEAD`) without creating a nested worktree. Emits `APPROVE` or `REJECT` (max 3 fix-review cycles before escalating to human).

---

## Step 1: Resolve Target Branch or PR (Standalone Mode)

Run the branch/PR resolver to fetch updates and prepare a clean detached worktree under `~/.gemini/tmp/worktrees/`:

```bash
python3 ~/.gemini/skills/adversarial-review/scripts/resolve_branches.py [optional_target] [--mode=external|pipeline] [--last-sha=<sha>] [--force] [--pr <N>] [--reference <branch>] [--prune] [--prune-all]
```

* **Flags**:
  * `[optional_target]`: Branch (`feat/x`, `origin/feat/x`, `refs/heads/feat/x`), PR number (`#42`), or PR/MR URL. If omitted, `resolve_branches.py` returns `"ambiguous": true` with `candidates`—ask the user which branch to review.
  * `--last-sha=<sha>` / `--force`: Skips worktree setup (`"sha_changed": false`) when target SHA has not changed since last review unless `--force` is passed.
  * `--pr <N>`: Fetches `refs/pull/N/head` (GitHub/Gitea/Forgejo) or `refs/merge-requests/N/head` (GitLab) directly so fork PRs work without local branches. Optionally inspect PR metadata with `gh pr view <N> --json baseRefName,title,body` if `gh` is installed (never required).
  * `--reference <branch>`: Override baseline integration branch (defaults to active checkout or `origin/main`).
  * `--prune` / `--prune-all`: Clean cached review worktrees.
* If `fetch_error` is non-null in the JSON output, note in the report that results reflect local tracking refs.

---

## Step 2: Extract Diff Safely (No Terminal Truncation)

Never read raw `git diff` directly from terminal stdout where long lines/hunks truncate silently. Write diffs to scratch and read via `view_file` / `read_file` in `<=800`-line chunks through EOF (see [robustness_guide.md](resources/robustness_guide.md)):

```bash
mkdir -p "<appDataDir>/brain/<conversation-id>/scratch"
git diff "<reference_commit_hash>...<commit_hash>" --stat > "<appDataDir>/brain/<conversation-id>/scratch/temp_diff_stat.txt"
git diff "<reference_commit_hash>...<commit_hash>" > "<appDataDir>/brain/<conversation-id>/scratch/temp_diff_all.txt"
```

---

## Step 3: Run Empirical Verification in Worktree

Delegate execution to a fresh-context `self` subagent (`Workspace: inherit`) when invoked from a builder session to eliminate author bias; if already running as the review subagent, do NOT spawn nested subagents.

Inside `<worktree_path>`, run verification via the isolated environment wrappers:

```bash
python3 ~/.gemini/scripts/setup_review_env.py <worktree_path>
python3 ~/.gemini/scripts/run_in_env.py <worktree_path> pytest
python3 ~/.gemini/scripts/run_in_env.py <worktree_path> ruff check .
```

---

## Step 4: Adversarial Audit Checklist

Every finding MUST cite exact `file:line` locations, verbatim code snippets, or empirical test/linter output. Speculative or ungrounded claims are forbidden. Apply Ponytail triage: flag real correctness/security/design defects, not speculative YAGNI abstractions.

* **Correctness & Edge Cases**: Logic bugs, off-by-one errors, race conditions, silent failure paths, broken caller contracts, illegal/timeout/error state transitions on async/retry/lifecycle code, weak/missing test assertions.
* **Downstream Consumer Trace** *(unconditional for code diffs)*: Look beyond `grep` direct callers (inspect library source/pinned versions, JSON/DB/wire formats, config/feature flags, teardown/microtask ordering, and 3-hop callers). Identify the single safety fact the change relies on and prove it via real execution (small test or script), or explicitly mark it `unproven`.
* **Performance Claims Check** *(when perf/benchmark claims appear for the changeset)*: Require `@skill:benchmark-checklist` compliance—verify the limiter is named, all sides use tuned production settings, and >=5 alternating runs back the claim (or explicit single-run ballpark / user-supplied methodology verification); reject uncalibrated speedup claims as `inconclusive`.
* **Security & Simplicity**: Unvalidated inputs, injection/traversal risks, leaked secrets, dead code, duplicated helpers already in repo, unnecessary complexity.
* **Writing Quality**: Clarity and accuracy of docs, comments, and markdown; for external-facing docs, READMEs, or PR prose, apply `--unslop` rules inline from [prose-editor](../prose-editor/SKILL.md).
* **LaTeX / TeX Check** *(when `.tex`, `.cls`, `.sty`, `.bib` change)*: Compile root document(s) containing `\documentclass` with `latexmk -pdf -interaction=nonstopmode -halt-on-error -cd <root>.tex`. Non-zero exit is blocking; if TeX toolchain is absent, state compilation is **unverified**. Verify macro compatibility across `.cls` files.
* **Scientific / HPC Check** *(when numerical, ML, or job scripts change)*: Check dimensional/matrix alignment, normalization factors, numerical stability (`log1p`/log-sum-exp/epsilons), RNG seeding, data leakage, and units. Never run cluster-scale HPC jobs or expect missing HPC intermediate outputs locally.

---

## Step 5: Output Format & Cleanup

Clean up temporary scratch diff files (`rm -f -- "<appDataDir>/brain/<conversation-id>/scratch/temp_diff_stat.txt" "<appDataDir>/brain/<conversation-id>/scratch/temp_diff_all.txt"`), post the report in chat, and **stop calling tools immediately**:

```markdown
VERDICT: [APPROVE | NEEDS_REVISION | REJECT]

### Adversarial Audit Summary
- <Concise bullet per real defect, test/lint result, or verified area>

### External PR Action Plan
**1. [path/to/file:line] Short title** — concise root-cause explanation + exact fix/diff
**Tests verified:** `<exact command and pass/fail count>`
```
