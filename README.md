# Antigravity Global Agent Config (`dotagent`)

Personal global configuration and custom skills for Google Antigravity CLI.

> [!NOTE]
> **Repository Naming vs. Installation Paths:** The repository is named `dotagent` (formerly `dotgemini`; GitHub redirects old URLs automatically). Google Antigravity CLI loads global settings from `~/.gemini/` on disk.

## Platform Support

Developed and tested on macOS and Linux (validated in CI). Windows is unsupported (`fcntl` file locking and POSIX path semantics are required).

## Setup on a New Machine

1. **Install Antigravity CLI:**
   Download and install [Antigravity CLI](https://antigravity.google/product/antigravity-cli), then verify:
   ```bash
   agy --version
   ```

2. **Backup existing config (if any):**
   ```bash
   if [ -e "$HOME/.gemini" ] || [ -L "$HOME/.gemini" ]; then
     if [ -e "$HOME/.gemini.bak" ] || [ -L "$HOME/.gemini.bak" ]; then
       echo "Error: Both $HOME/.gemini and $HOME/.gemini.bak exist." >&2
       exit 1
     else
       mv "$HOME/.gemini" "$HOME/.gemini.bak"
     fi
   fi
   ```

3. **Clone to `~/.gemini`:**
   ```bash
   git clone https://github.com/jerrylin96/dotagent.git ~/.gemini
   ```

4. **Restore local settings and credentials (if applicable):**
   ```bash
   if [ -d "$HOME/.gemini.bak" ]; then
     mkdir -p "$HOME/.gemini/antigravity-cli"
     [ -f "$HOME/.gemini.bak/antigravity-cli/settings.json" ] && cp "$HOME/.gemini.bak/antigravity-cli/settings.json" "$HOME/.gemini/antigravity-cli/settings.json"
     [ -f "$HOME/.gemini.bak/google_accounts.json" ] && cp "$HOME/.gemini.bak/google_accounts.json" "$HOME/.gemini/google_accounts.json"
     [ -f "$HOME/.gemini.bak/oauth_creds.json" ] && cp "$HOME/.gemini.bak/oauth_creds.json" "$HOME/.gemini/oauth_creds.json"
     [ -f "$HOME/.gemini.bak/antigravity-cli/installation_id" ] && cp "$HOME/.gemini.bak/antigravity-cli/installation_id" "$HOME/.gemini/antigravity-cli/installation_id"
   fi
   ```

*Credentials, local CLI state (`antigravity-cli/`), logs (`*.log`), subagent artifacts (`brain/`), and auto-bundled Data Cloud skills are excluded via `.gitignore`.*

---

## What's Included

### 1. Lean Global Rules (`AGENTS.md`, symlinked as `GEMINI.md`)
* **Ponytail (Lazy Senior Dev Mode):** 7-rung YAGNI ladder, root-cause fixes + downstream consumer tracing, minimal diffs, and encoding recurring lessons in tests/linters.
* **Caveman (Terse Style):** Cuts conversational fluff (~65% fewer output tokens) while keeping technical artifacts exact.
* **Proportional Engineering Workflow:** Respects manual worktrees and feature branches in place (blocking direct edits only on protected branches), scales planning/TDD/review ceremony to task size, and enforces empirical grounding.

### 2. Isolated Execution Environments (`scripts/`)
* `setup_review_env.py` + `run_in_env.py` bootstrap CPU-compatible testing/linting virtual environments under `~/.gemini/tmp/<workspace-hash>` via `uv` (dependency isolation only, not a security sandbox).

### 3. Custom Skills (`skills/`)
* `adversarial-review` — Isolated worktree diff, test, linter, LaTeX, and scientific code review (`/adversarial-review`). Resolves local/remote branches or fork PRs (`#42` or PR URL) into `~/.gemini/tmp/worktrees/` without touching your active checkout.
* `explain-diff` — Interactive, read-only walkthrough explaining changes across topic-by-topic synthesis (`[t]`), chronological commit-by-commit narrative (`[c]`, shown for multi-commit changesets and omitted for single-commit changesets), and file-by-file diffs (`[f]`) (`/explain-diff`).
* `codebase-audit` — Multi-agent parallel cluster review and cross-boundary contract audit for large diffs (>300 LoC) and whole repositories (`/codebase-audit`).
* `codebase-map` — Multi-agent polyglot architecture discovery, entrypoint detection, and onboarding map generator (`/codebase-map`).
* `catchmeup` — Executive time-window repository summary (`1d`, `1w`, `2w`, `1mo`) with commit themes and interactive drill-downs (`/catchmeup`).
* `benchmark-checklist` — 7-question verification gate before running benchmarks or claiming speedups, latency/throughput gains, or perf regressions.
* `math-proof-audit` — Formal LaTeX derivation alignment and numerical edge-case red-teaming for mathematical/statistical code (`/showproof`).
* `prose-editor` — Advisory prose, paper, and documentation review using schema-validated Suggestion Cards and `--unslop` mode (`/edit-prose`, `/prose`).
* `google-workspace` & `timeline-postmortem` — Google Calendar/Tasks/Docs timeline scheduling, status rollups, and 5-Whys deadline retrospectives.
* `session-sync` — Sync and restore Antigravity CLI sessions across machines via hidden Git refs.
* [`git-signoff`](skills/git-signoff/SKILL.md) — Opt-in Socratic comprehension interview (`--explain`, `--practice`, or GSA trailer attestation via `/git-signoff`) for shared/high-stakes repositories.

## Running Tests

```bash
python3 scripts/run_tests.py
```
Initializes the isolated test environment via `uv` and runs all skill and helper test suites with `pytest` and `importlib` import mode.
