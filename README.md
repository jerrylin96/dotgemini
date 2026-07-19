# Antigravity & Gemini CLI Config (`dotgemini`)

Personal global configuration and custom skills for Google Antigravity and Gemini CLI.

## Platform Support

This configuration is developed and tested on macOS and Linux (validated in CI). It is not supported on Windows — the branch resolver script used by the adversarial-review and explain-diff skills will exit with an error on platforms without fcntl, and several paths assume POSIX semantics.

## Setup on a New Machine

1. **Install Antigravity CLI (Required for full configuration):**
   Download and install the [Antigravity CLI](https://antigravity.google/product/antigravity-cli). This is required for executing custom skills (`skills/`), subagent delegation, and automated testing.
   
   Verify your installation:
   ```bash
   agy --version
   ```

   > [!NOTE]
   > **External/Multi-Agent CLIs:** If you are using Claude Code, Codex, or Cursor, the Antigravity CLI is not required to load the global rules. See [Cross-Agent Integration](#cross-agent-integration-claude-code-codex-cursor-etc) below.

   > [!NOTE]
   > **Installation Order:** If you clone the repository before installing the CLI, the CLI will safely initialize its state inside the existing `~/.gemini` folder without conflicts when you install it.

2. **Backup existing config (if any):**
   Ensure `$HOME/.gemini.bak` does not already exist before running the backup command to avoid nesting or losing pre-existing backups.

   ```bash
   if { [ -e "$HOME/.gemini" ] || [ -L "$HOME/.gemini" ]; } && { [ ! -e "$HOME/.gemini.bak" ] && [ ! -L "$HOME/.gemini.bak" ]; }; then
     mv "$HOME/.gemini" "$HOME/.gemini.bak"
   elif [ -e "$HOME/.gemini.bak" ] || [ -L "$HOME/.gemini.bak" ]; then
     echo "Warning: $HOME/.gemini.bak already exists. Please inspect, rename, or delete it before proceeding."
   fi
   ```

3. **Clone this repository:**
   ```bash
   git clone https://github.com/jerrylin96/dotgemini.git ~/.gemini
   # Or via SSH: git clone git@github.com:jerrylin96/dotgemini.git ~/.gemini
   ```

4. **Restore local settings and credentials (if applicable):**
   ```bash
   # Restore settings, credentials, and machine state safely if backup exists
   if [ -d "$HOME/.gemini.bak" ]; then
     mkdir -p "$HOME/.gemini/antigravity-cli"
     [ -f "$HOME/.gemini.bak/antigravity-cli/settings.json" ] && cp "$HOME/.gemini.bak/antigravity-cli/settings.json" "$HOME/.gemini/antigravity-cli/settings.json"
     
     # Restore credentials and machine IDs
     [ -f "$HOME/.gemini.bak/google_accounts.json" ] && cp "$HOME/.gemini.bak/google_accounts.json" "$HOME/.gemini/google_accounts.json"
     [ -f "$HOME/.gemini.bak/oauth_creds.json" ] && cp "$HOME/.gemini.bak/oauth_creds.json" "$HOME/.gemini/oauth_creds.json"
     [ -f "$HOME/.gemini.bak/antigravity-cli/installation_id" ] && cp "$HOME/.gemini.bak/antigravity-cli/installation_id" "$HOME/.gemini/antigravity-cli/installation_id"
   else
     echo "No backup directory found to restore settings."
   fi
   ```

*Note: Credentials, local settings (`antigravity-cli/settings.json`), terminal logs (`*.log`), subagent run data (`brain/`), and conversation logs (`conversations/`) are automatically excluded via `.gitignore` to prevent leaking secrets or tracking local session state.*

## Cross-Agent Integration (Claude Code, Codex, Cursor, etc.)

Since cloning this repository to `~/.gemini` only configures Google Antigravity CLI globally, you must link or copy the portable rules and skills for other AI coding assistants.

### 1. Project-Level Rules (`AGENTS.md` / `CLAUDE.md`)
To configure rules in a project repository:
- **Claude Code**: Copy or symlink `GEMINI.md` to `CLAUDE.md` at the project root:
  ```bash
  ln -s ~/.gemini/GEMINI.md CLAUDE.md
  ```
- **Codex CLI / Cursor / Other compliant agents**: Copy or symlink `GEMINI.md` to `AGENTS.md` at the project root:
  ```bash
  ln -s ~/.gemini/GEMINI.md AGENTS.md
  ```

### 2. Global Rules (Alternative)
- **Codex / Global agents.md**: Codex reads global rules from `~/.config/agents/AGENTS.md`. You can symlink it:
  ```bash
  mkdir -p ~/.config/agents
  ln -s ~/.gemini/GEMINI.md ~/.config/agents/AGENTS.md
  ```

### 3. Portable Skills
To reuse portable skills (e.g., `ponytail`, `caveman`, `test-driven-development`) with other agents:
- Place or symlink the specific skill folders into the configuration directory expected by your agent (e.g., Claude Code reads project-level instructions from `CLAUDE.md` and doesn't use the `.gemini/skills/` directory structure, but you can instruct Claude to read standard markdown files from `~/.gemini/skills/` in your `CLAUDE.md`).
- Note that Antigravity-specific skills (e.g., `adversarial-review`, `explain-diff`, `make-feature`, `session-sync`) require the Antigravity execution environment and will not run on external agents.

---

## What's Included

### 1. Global Rules (`GEMINI.md`, aliased as `AGENTS.md`)
* Defines the **Ponytail (Lazy Senior Dev Mode)** YAGNI ladder.
* Enforces the **Caveman (Terse Style)** communication formatting to save ~65% output tokens.
* Enforces structured software development lifecycle gates.
* Also exposed as `AGENTS.md` (a symlink to `GEMINI.md`, so there's a single source of truth) so other agents that follow the [AGENTS.md](https://agents.md) convention — Claude Code, Codex, Cursor, etc. — load the same rules. Antigravity keeps reading `GEMINI.md` by default.

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
> While this repository commits **no** credentials, local settings, or session history (they are automatically gitignored), replacing a collaborator's local `~/.gemini` directory with this repository will replace their own global rules, custom skills, and preferences with yours.
>
> Furthermore, collaborators will lose their local configurations and credentials unless they back up and restore:
> - `google_accounts.json`
> - `oauth_creds.json`
> - `antigravity-cli/settings.json`
> - `antigravity-cli/installation_id` (optional machine state ID)
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
