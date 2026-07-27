# Project-local installation

Use this path when a repository should carry its own reviewed workflow files. It avoids relying on user-global plugin state.

## goose 1.44 compatibility note

Official goose documentation lists `<project>/.agents/plugins/<plugin-name>/` as a project-plugin discovery location. In an observed goose `1.44.0` CLI check, placing this plugin at `.agents/plugins/principled-dev/` and running `goose skills list` from that project did **not** list its skills. This is a version-specific observed mismatch, not a claim about every goose release.

For goose 1.44 portability, copy skills as ordinary project skills and recipes as ordinary project recipes. This fallback does not install the plugin hook automatically.

## Layout

From project root, produce this structure:

```text
<project>/
├── .agents/
│   └── skills/
│       ├── adversarial-review/
│       ├── code-review-and-quality/
│       ├── debugging-and-error-recovery/
│       ├── explain-diff/
│       ├── incremental-implementation/
│       ├── make-feature/
│       ├── planning-and-task-breakdown/
│       ├── ponytail/
│       ├── signoff/
│       ├── spec-driven-development/
│       └── test-driven-development/
└── .goose/
    └── recipes/
        ├── adversarial-review.yaml
        ├── explain-diff.yaml
        ├── make-feature.yaml
        └── signoff.yaml
```

Copy **contents** of the source directories, not the `skills` or `recipes` parent as another nested level:

```text
principled-dev/skills/<skill>/...  ->  <project>/.agents/skills/<skill>/...
principled-dev/recipes/<name>.yaml ->  <project>/.goose/recipes/<name>.yaml
```

Before copying, inspect `.agents/skills/` and `.goose/recipes/`. If a destination name exists, stop and compare it; preserve the old directory or file under a backup name before replacing anything. Commit project-local workflow files only after normal review. Do not copy source `__pycache__` directories.

Copied project skills are unnamespaced: `make-feature`, `adversarial-review`, `explain-diff`, and `signoff`. The recipes first request `principled-dev:<name>` and then explicitly fall back to these project-local names.

Verify in a fresh goose process started from project root:

```sh
goose skills list
goose recipe list --verbose
goose recipe validate "$PWD/.goose/recipes/make-feature.yaml"
goose recipe validate "$PWD/.goose/recipes/adversarial-review.yaml"
goose recipe validate "$PWD/.goose/recipes/explain-diff.yaml"
goose recipe validate "$PWD/.goose/recipes/signoff.yaml"
```

## Slash commands

Custom slash mappings must point at literal absolute recipe paths. Add these entries to the goose configuration used to launch the project, replacing `/absolute/path/to/project` with `pwd -P` output for this checkout:

```yaml
slash_commands:
  - command: "make-feature"
    recipe_path: "/absolute/path/to/project/.goose/recipes/make-feature.yaml"
  - command: "adversarial-review"
    recipe_path: "/absolute/path/to/project/.goose/recipes/adversarial-review.yaml"
  - command: "explain-diff"
    recipe_path: "/absolute/path/to/project/.goose/recipes/explain-diff.yaml"
  - command: "signoff"
    recipe_path: "/absolute/path/to/project/.goose/recipes/signoff.yaml"
```

Merge entries into an existing `slash_commands` list. A relative path such as `.goose/recipes/make-feature.yaml` is not the approved fragment. If multiple checkouts need these command names, their global mappings cannot simultaneously point at every checkout; update the mappings or invoke recipes by explicit path.

## Persistent project guardrails

Project-local skill copying alone does not inject guardrails each turn. Keep a reviewed guardrail file in the project or use the source plugin's `config/guardrails.md`, then set an absolute path before starting goose:

```sh
export GOOSE_MOIM_MESSAGE_FILE="/absolute/path/to/project/.goose/principled-dev-guardrails.md"
goose session
```

If you copy `principled-dev/config/guardrails.md` to that destination, review it and track it like other policy. `GOOSE_MOIM_MESSAGE_FILE` is persistent model context, not hard enforcement.

## Hook availability

The `.agents/skills/` and `.goose/recipes/` fallback does **not** load `hooks/hooks.json`. To use the hook, either:

- install the trusted plugin globally with `goose plugin install <git-url>`, or
- retest project-plugin discovery on the exact goose version in use before placing the complete plugin below `.agents/plugins/`.

Do not claim the hook is active merely because project-local skills appear. Test a benign outside-worktree edit attempt in a disposable repository, and remember that goose hooks fail open on hook spawn errors, timeouts, or malformed output.

## Helper and roots

Skills and recipes do not relocate Python helpers. Run helpers from a separately retained complete plugin/source directory:

```sh
python3 /absolute/path/to/principled-dev/scripts/principled_dev.py --repo "$PWD" --help
```

Defaults and overrides are identical to global installation:

```text
Worktrees: ${PRINCIPLED_DEV_WORKTREE_ROOT:-${XDG_CACHE_HOME:-$HOME/.cache}/principled-dev/worktrees}
State:     ${PRINCIPLED_DEV_STATE_ROOT:-${XDG_STATE_HOME:-$HOME/.local/state}/principled-dev}
```

Set `PRINCIPLED_DEV_FEATURE_WORKTREE` to the exact durable feature worktree and `PRINCIPLED_DEV_BASE_BRANCH` to the human-selected integration branch when using the hook.

Worktree separation remains exact:

- primary checkout: never edited by the lifecycle;
- `<root>/<repository-id>/features/<branch-slug>-<hash8>`: attached branch, durable, writable builder location;
- `<root>/<repository-id>/reviews/<full-target-sha>`: detached exact commit, disposable, reviewer read-only by policy.

## Safe rollback

1. End project goose sessions.
2. Back up the slash-command configuration, then remove only this project's four mappings.
3. Remove the project-specific `GOOSE_MOIM_MESSAGE_FILE` export from the launcher; unset it in the current shell if needed.
4. Move copied `.agents/skills/<name>/` directories and `.goose/recipes/<name>.yaml` files into a project-adjacent dated backup directory. Do not recursively delete `.agents`, `.goose`, cache, state, or worktree roots.
5. Start goose from project root and inspect `goose skills list` and `goose recipe list --verbose`.

Restoration is the reverse move plus restoration of the backed-up configuration. Existing durable feature worktrees and lifecycle state are intentionally unaffected.
