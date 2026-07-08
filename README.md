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
