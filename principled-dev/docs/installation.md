# Global installation

This path installs `principled-dev` as a user Open Plugin. Install only from a trusted Git source: plugin hooks execute local commands, and skills supply instructions to the model. This repository does not claim that any particular public plugin URL or release has been published.

## Prerequisites

- goose CLI with Open Plugin, Agent Skills, hooks, recipes, custom slash commands, Top of Mind persistent instructions, and Summon support. The implementation was exercised against goose `1.44.0`; see [known limitations](known-limitations.md).
- Git and Python 3.10 or newer.
- macOS or Linux. Runtime locking imports POSIX-only `fcntl`; Windows is unsupported.
- Auto permission mode when independent subagents are required.

Check the local CLI:

```sh
goose --version
goose plugin install --help
```

## 1. Install the plugin

`<git-url>` must identify a trusted Git repository with `plugin.json`, `skills/`, `hooks/`, and `scripts/` at its supported plugin root. The `principled-dev/` directory in this source tree is that payload; do not infer a published URL from this documentation.

```sh
goose plugin install <git-url>
```

goose's documented user-plugin destination is:

```text
~/.agents/plugins/principled-dev/
```

Open Plugin skills are namespaced. Start a new goose process, then verify:

```sh
goose skills list
```

Expected names include:

```text
principled-dev:make-feature
principled-dev:adversarial-review
principled-dev:explain-diff
principled-dev:signoff
```

The other installed skills are also addressed as `principled-dev:<skill-name>`. `goose plugin update principled-dev` updates a git-backed installation, but review upstream changes before updating. Avoid `--auto-update` when reproducible, reviewed policy is more important than convenience.

## 2. Install recipes

Plugin discovery imports skills and hooks; it does not make this plugin's `recipes/` directory a custom slash-command registry. Copy the four reviewed recipe files to goose's global recipe library, or retain them under the installed plugin and reference them there. The global recipe location documented by goose is:

```text
~/.config/goose/recipes/
```

Before copying, inspect that destination and preserve any same-named files under a backup name. Do not overwrite them blindly. After placing the files, validate their actual absolute paths:

```sh
goose recipe validate "$HOME/.config/goose/recipes/make-feature.yaml"
goose recipe validate "$HOME/.config/goose/recipes/adversarial-review.yaml"
goose recipe validate "$HOME/.config/goose/recipes/explain-diff.yaml"
goose recipe validate "$HOME/.config/goose/recipes/signoff.yaml"
```

## 3. Add slash commands with absolute recipe paths

Merge this fragment into `~/.config/goose/config.yaml`. Replace `/absolute/...` with literal absolute paths. Do not use relative paths; do not copy the placeholder unchanged.

```yaml
slash_commands:
  - command: "make-feature"
    recipe_path: "/absolute/path/to/home/.config/goose/recipes/make-feature.yaml"
  - command: "adversarial-review"
    recipe_path: "/absolute/path/to/home/.config/goose/recipes/adversarial-review.yaml"
  - command: "explain-diff"
    recipe_path: "/absolute/path/to/home/.config/goose/recipes/explain-diff.yaml"
  - command: "signoff"
    recipe_path: "/absolute/path/to/home/.config/goose/recipes/signoff.yaml"
```

Do not add a second `slash_commands:` key if one already exists; append entries to the existing list. Restart goose after changing configuration. The recipes deliberately load namespaced plugin skills first and only then fall back to unnamespaced project-local skills.

## 4. Persist guardrails on every turn

A skill is loaded on demand. For persistent lifecycle reminders, point goose's Top of Mind file variable at the installed guardrail file **before launching goose**:

```sh
export GOOSE_MOIM_MESSAGE_FILE="$HOME/.agents/plugins/principled-dev/config/guardrails.md"
goose session
```

For persistence across terminal sessions, add the export to the shell startup file or service environment that launches goose. `GOOSE_MOIM_MESSAGE_FILE` supports `~/` and files up to 64 KB in goose's documented behavior. Confirm the path after installation rather than assuming it.

This injection is model context, not an authorization boundary. Keep the plugin hook enabled as defense in depth, and understand its fail-open limits.

## 5. Configure helper roots and hook context

The Python CLI resolves roots as follows:

```text
PRINCIPLED_DEV_WORKTREE_ROOT
  or ${XDG_CACHE_HOME:-$HOME/.cache}/principled-dev/worktrees

PRINCIPLED_DEV_STATE_ROOT
  or ${XDG_STATE_HOME:-$HOME/.local/state}/principled-dev
```

State is written to `<state-root>/lifecycle.json`. Each repository gets a canonical repository-ID directory below the worktree root.

Optional explicit roots:

```sh
export PRINCIPLED_DEV_WORKTREE_ROOT="/absolute/cache/path/principled-dev/worktrees"
export PRINCIPLED_DEV_STATE_ROOT="/absolute/state/path/principled-dev"
```

When a durable feature worktree has been created, launch or resume goose with the exact values used by the path-policy hook:

```sh
export PRINCIPLED_DEV_FEATURE_WORKTREE="/absolute/path/to/durable/feature/worktree"
export PRINCIPLED_DEV_BASE_BRANCH="main"
```

The feature variable is intentionally not a broad cache root. It must name the one writable durable feature worktree for that session. Symlink-resolved writes outside it are blocked. Shell checks also block directly parsed `git merge`, `gh pr create`, and pushes whose refspec targets the configured base branch; they are not a complete shell sandbox.

Helper entry point after global installation:

```sh
python3 "$HOME/.agents/plugins/principled-dev/scripts/principled_dev.py" --help
```

## 6. Use

Start a new Auto-mode session from the repository to be changed and invoke:

```text
/make-feature describe the requested change
```

Auto mode is required for goose's internal subagent delegation. Human approval gates inside the workflow remain required even though goose's tool permission mode is Auto. If an independent reviewer cannot run, review status is `BLOCKED`; the builder must not self-approve.

## Disable, uninstall, or roll back safely

Prefer reversible operations. goose 1.44 exposes plugin install/update commands but no plugin uninstall command.

1. End active goose sessions so no hook or helper is using the installation.
2. Remove or comment the `GOOSE_MOIM_MESSAGE_FILE` export from the launch environment; `unset GOOSE_MOIM_MESSAGE_FILE` affects only the current shell.
3. Remove the four `slash_commands` list entries from goose configuration after making a backup copy of that configuration.
4. Disable the plugin without deleting it by adding `principled-dev` to `disabledPlugins` in `~/.config/goose/settings.json`:

   ```json
   {
     "disabledPlugins": ["principled-dev"]
   }
   ```

   Merge with existing JSON rather than replacing unrelated settings.
5. Restart goose and verify the namespaced skills are absent with `goose skills list`.
6. If filesystem removal is still desired, move `~/.agents/plugins/principled-dev` to a dated backup outside `~/.agents/plugins/` instead of deleting it. Likewise move, rather than delete, same-named recipe files. Restore by moving the backups back and removing the disabled setting.

Do not delete managed worktree or state roots as part of plugin uninstall. They may contain durable feature work, approval state, or audit evidence. Inspect each repository's worktrees with Git and archive or clean them through the owning repository's normal human-reviewed process.
