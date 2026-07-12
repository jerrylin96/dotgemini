# Antigravity & Gemini CLI Config (`dotgemini`)

Personal global configuration and custom skills for Google Antigravity and Gemini CLI.

## Platform Support

This configuration is developed and tested on macOS and Linux (validated in CI). It is not supported on Windows — the branch resolver script used by the adversarial-review and explain-diff skills will exit with an error on platforms without fcntl, and several paths assume POSIX semantics.

## Setup on a New Machine

1. **Backup existing config (if any):**
   > [!WARNING]
   > Running `mv ~/.gemini ~/.gemini.bak` will overwrite any pre-existing backup at `~/.gemini.bak`. Make sure to check or rename any existing backup directory first.
   
   ```bash
   mv ~/.gemini ~/.gemini.bak
   ```

2. **Clone this repository:**
   ```bash
   git clone https://github.com/jerrylin96/dotgemini.git ~/.gemini
   # Or via SSH: git clone git@github.com:jerrylin96/dotgemini.git ~/.gemini
   ```

3. **Restore local settings and credentials (if applicable):**
   ```bash
   # Restore settings and credentials safely if backup exists
   if [ -d ~/.gemini.bak ]; then
     mkdir -p ~/.gemini/antigravity-cli
     [ -f ~/.gemini.bak/antigravity-cli/settings.json ] && cp ~/.gemini.bak/antigravity-cli/settings.json ~/.gemini/antigravity-cli/settings.json
     
     # Restore credentials (to avoid re-authenticating)
     [ -f ~/.gemini.bak/google_accounts.json ] && cp ~/.gemini.bak/google_accounts.json ~/.gemini/google_accounts.json
     [ -f ~/.gemini.bak/oauth_creds.json ] && cp ~/.gemini.bak/oauth_creds.json ~/.gemini/oauth_creds.json
   else
     echo "No backup directory found to restore settings."
   fi
   ```

*Note: Credentials, local settings (`settings.json`), terminal logs (`*.log`), subagent run data (`brain/`), and conversation logs (`conversations/`) are automatically excluded via `.gitignore` to prevent leaking secrets or tracking local session state.*

---

## What's Included

### 1. Global Rules (`GEMINI.md`, aliased as `AGENTS.md`)
* Defines the **Ponytail (Lazy Senior Dev Mode)** YAGNI ladder.
* Enforces the **Caveman (Terse Style)** communication formatting to save ~65% output tokens.
* Enforces structured software development lifecycle gates.
* Also exposed as `AGENTS.md` (a symlink to `GEMINI.md`, so there's a single source of truth) so non-Gemini agents that follow the [AGENTS.md](https://agents.md) convention — Claude Code, Cursor, etc. — load the same rules. Gemini CLI and Antigravity keep reading `GEMINI.md` by default.

### 2. Isolated Execution Environments
* Integrates with `setup_review_env.py` to automatically bootstrap CPU-compatible testing and linting virtual environments under `~/.gemini/tmp/<workspace-hash>` using `uv`.
  > [!WARNING]
  > This provides dependency/test isolation, NOT a security sandbox. Running setup scripts or installing dependencies (via uv/pip) on untrusted repositories can execute arbitrary build hooks or code under your user credentials.
* Isolates dynamic branch workspaces to prevent test collisions.

### 3. Custom Registered Skills (`skills/`)
* `adversarial-review` — Git worktree-based adversarial code review helper.
  * **User Workflow**:
    1. **Prepare Baseline**: Prior to starting the review, checkout the intended **reference branch** (the baseline, e.g., `main` or a specific release branch) in your active workspace:
       ```bash
       git checkout <your-reference-branch>
       ```
    2. **Activate Review**: Trigger the review by typing `/adversarial-review` in the chat.
    3. **Select Feature Branch or PR**: Antigravity will automatically fetch the latest updates, detect your current checked-out branch as the reference branch, and present a list of all other local and remote branches. Select the **feature branch** (the target containing the new changes to review) when prompted. You can also name a pull request directly (e.g. "review PR #42" or paste the PR/MR URL) — the resolver fetches the PR head ref from the remote, so fork PRs work without a local branch (GitHub/GitLab/Gitea; not Bitbucket).
    4. **Under the Hood**: Antigravity checks out the selected feature branch to a clean, isolated worktree under `~/.gemini/tmp/worktrees/`, leaving your active workspace untouched on the reference branch. It then generates the diff between the two branches, runs tests/linters in the feature branch worktree, and performs the adversarial review.

* `explain-diff` — Interactive, read-only walkthrough explaining what changed between a feature branch, pull request, or specific commit/range and a reference branch.
  * **User Workflow**: Trigger with `/explain-diff`. Branch selection works exactly like `adversarial-review` (it reuses the same branch resolver and worktree cache). You then get an overall summary of the changeset and a numbered menu of changed files; pick one for a hunk-by-hunk explanation, ask follow-up questions, and return to the menu until done. Nothing is executed or modified — no tests, no linters.

* `make-feature` — Git worktree-based isolated feature branch development helper.
  * **User Workflow**: Trigger with `/make-feature` (or when preparing to write/contribute edits).
    1. **Initialize Feature**: Antigravity creates a new feature branch prefixed with `gemini/` and checks it out to a clean, isolated worktree under `<repo_root>/tmp/worktrees/`, keeping your primary working directory branch checkout completely untouched.
    2. **Isolated Edits**: Modify files, run tests, and execute git commit/push commands from inside the worktree directory.
    3. **Cleanup**: Once the branch is pushed to origin, Antigravity removes the worktree and prunes git metadata, keeping the environment clean.

* `/ponytail` — Lazy senior developer instructions.
* `/caveman` — Token-efficient caveman communication mode.
* `incremental-implementation` — Vertical slicing development guidelines.
* `test-driven-development` — Red-green-refactor testing patterns.
* `debugging-and-error-recovery` — Systematic triage and root-cause fix strategies.

## Running Tests

To run all unit tests for the configured skills and environment setup:
```bash
python3 scripts/run_tests.py
```
This script automatically ensures that the correct isolated virtual environment is initialized/up-to-date and runs all discoverable tests using `pytest` with `importlib` import mode.

If `uv` is available but the environment setup fails, `run_tests.py` will exit with a non-zero status by default to prevent masking issues. To bypass setup errors and fall back to testing on the host environment anyway, run with the `ALLOW_HOST_TEST_FALLBACK=1` environment variable set. If `uv` is entirely missing, host testing fallback occurs automatically.

---

## Sharing and Collaborator Onboarding

> [!WARNING]
> This configuration repository (`dotgemini`) contains personal global settings, credentials, and custom preferences. Cloning it directly onto another collaborator's system using `git clone … ~/.gemini` will overwrite their own settings and force your personal styles/preferences.
> 
> Collaborators should only clone this as a reference or keep it isolated. For sharing rules/skills across team projects, **prefer Project-Level Integration** below to build a shared, repository-specific review workflow, or copy only the specific skill subset needed.

### Project-Level Integration (Recommended for Sharing)
If you want to bake this isolated environment setup directly into a specific project repository so that *any* agent working on it automatically uses it:
1. **Copy the Env Manager**: Place the [setup_review_env.py](scripts/setup_review_env.py) script in the project repository (e.g., `scripts/setup_review_env.py`).
2. **Add a Project-Level Guide**: Add a `GEMINI.md` (or `AGENTS.md` for cross-tool portability) to the project's root containing:
   ```markdown
   ## Isolated Testing & Execution Environment
   All testing and validation commands must run inside the CPU-isolated virtual environment:
   1. Initialize: `python3 scripts/setup_review_env.py`
   2. Run Tests: `python3 ~/.gemini/scripts/run_in_env.py <workspace_path> pytest`
   *(Note: The setup_review_env.py script automatically manages and prints details of the isolated environment.)*
   ```
