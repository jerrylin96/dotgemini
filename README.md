# Antigravity & Gemini CLI Config (`dotgemini`)

Personal global configuration and custom skills for Google Antigravity and Gemini CLI.

## Setup on a New Machine

1. **Backup existing config (if any):**
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
   # Restore settings
   mkdir -p ~/.gemini/antigravity-cli
   cp ~/.gemini.bak/antigravity-cli/settings.json ~/.gemini/antigravity-cli/settings.json
   
   # Restore credentials (to avoid re-authenticating)
   cp ~/.gemini.bak/google_accounts.json ~/.gemini/google_accounts.json 2>/dev/null || true
   cp ~/.gemini.bak/oauth_creds.json ~/.gemini/oauth_creds.json 2>/dev/null || true
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
* Isolates dynamic branch workspaces to prevent test collisions.

### 3. Custom Registered Skills (`skills/`)
* `/ponytail` — Lazy senior developer instructions.
* `/caveman` — Token-efficient caveman communication mode.
* `incremental-implementation` — Vertical slicing development guidelines.
* `test-driven-development` — Red-green-refactor testing patterns.
* `debugging-and-error-recovery` — Systematic triage and root-cause fix strategies.

---

## Generalizing & Collaborator Onboarding

To share this workflow with collaborators or scale it to new projects, you have two options:

### Option 1: Global Sync (Recommended for Collaborators)
Have your collaborators clone this configuration repository directly to their home folder. This instantly equips their local Antigravity/Gemini installation with the same rules and skills:
```bash
git clone https://github.com/jerrylin96/dotgemini.git ~/.gemini
```

### Option 2: Project-Level Integration (Recommended for Repository-Specific Setup)
If you want to bake this isolated environment setup directly into a specific project repository so that *any* agent working on it automatically uses it:
1. **Copy the Env Manager**: Place the [setup_review_env.py](file:///Users/jlin404/.gemini/antigravity-cli/scratch/setup_review_env.py) script in the project repository (e.g., `scripts/setup_review_env.py`).
2. **Add a Project-Level Guide**: Add a `GEMINI.md` to the project's root containing:
   ```markdown
   ## Isolated Testing & Execution Environment
   All testing and validation commands must run inside the CPU-isolated virtual environment:
   1. Initialize: `python3 scripts/setup_review_env.py`
   2. Run Tests: `~/.gemini/tmp/<workspace-hash>/bin/pytest`
   ```
   *(Note: The dynamic hashing logic in `setup_review_env.py` will still cleanly isolate the environment for each collaborator's machine and folder paths.)*

