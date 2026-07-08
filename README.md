# Antigravity & Gemini CLI Config (`dotgemini`)

Personal global configuration and custom skills for Google Antigravity and Gemini CLI.

## Platform Support

This configuration is developed and tested on macOS only. It should work on Linux (POSIX fcntl file locking, shell/git assumptions), but has not been validated there. It is not supported on Windows — the adversarial-review skill's branch resolver script will exit with an error on platforms without fcntl, and several paths assume POSIX semantics.

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

### 1. Global Rules (`GEMINI.md`)
* Defines the **Ponytail (Lazy Senior Dev Mode)** YAGNI ladder.
* Enforces the **Caveman (Terse Style)** communication formatting to save ~65% output tokens.
* Enforces structured software development lifecycle gates.

### 2. Isolated Execution Environments
* Integrates with `setup_review_env.py` to automatically bootstrap CPU-compatible testing and linting virtual environments under `~/.gemini/tmp/<workspace-hash>` using `uv`.
  > [!WARNING]
  > This provides dependency/test isolation, NOT a security sandbox. Running setup scripts or installing dependencies (via uv/pip) on untrusted repositories can execute arbitrary build hooks or code under your user credentials.
* Isolates dynamic branch workspaces to prevent test collisions.

### 3. Custom Registered Skills (`skills/`)
* `adversarial-review` — Git worktree-based adversarial code review and diff inspection helper.
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

---

## Sharing and Collaborator Onboarding

> [!WARNING]
> This configuration repository (`dotgemini`) contains personal global settings, credentials, and custom preferences. Cloning it directly onto another collaborator's system using `git clone … ~/.gemini` will overwrite their own settings and force your personal styles/preferences.
> 
> Collaborators should only clone this as a reference or keep it isolated. For sharing rules/skills across team projects, **prefer Project-Level Integration** below to build a shared, repository-specific review workflow, or copy only the specific skill subset needed.

### Project-Level Integration (Recommended for Sharing)
If you want to bake this isolated environment setup directly into a specific project repository so that *any* agent working on it automatically uses it:
1. **Copy the Env Manager**: Place the [setup_review_env.py](scripts/setup_review_env.py) script in the project repository (e.g., `scripts/setup_review_env.py`).
2. **Add a Project-Level Guide**: Add a `GEMINI.md` to the project's root containing:
   ```markdown
   ## Isolated Testing & Execution Environment
   All testing and validation commands must run inside the CPU-isolated virtual environment:
   1. Initialize: `python3 scripts/setup_review_env.py`
   2. Run Tests: `~/.gemini/tmp/<your-workspace-hash>/bin/pytest`
   ```
   *(Note: The `<your-workspace-hash>` placeholder is a dynamic MD5 hash of your local workspace path, printed by setup_review_env.py upon completion.)*

