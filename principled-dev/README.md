# principled-dev for goose

`principled-dev` is a model-neutral, human-gated development workflow packaged for goose. It provides eleven Agent Skills, four recipe entry points, a `PreToolUse` policy hook, and Python helpers for approval state, immutable Git resolution, durable feature worktrees, disposable review worktrees, review records, publication checks, and signoff attestations.

This directory is source code, not evidence of a published plugin or release. Replace documentation placeholders such as `<git-url>` with a trusted repository URL whose plugin root contains this directory's `plugin.json`.

## Workflow

1. Draft a specification; pause for explicit human approval.
2. Draft a plan; pause for separate explicit human approval.
3. Create an attached `agent/<feature>` branch in a durable feature worktree. Never edit the primary checkout.
4. Build and verify in that feature worktree, then bind the manifest to exact base, commit, tree, and artifact values.
5. Review the exact commit in a different, detached disposable worktree and fresh reviewer context.
6. Publish only the independently approved SHA to the feature branch.
7. Workflow policy assigns PR creation and integration to human. Hooks provide advisory checks, not complete enforcement.

Review and build locations are intentionally not interchangeable:

```text
${PRINCIPLED_DEV_WORKTREE_ROOT:-${XDG_CACHE_HOME:-$HOME/.cache}/principled-dev/worktrees}/
  <repository-id>/
    features/<branch-slug>-<branch-hash8>/   # attached, durable, writable
    reviews/<full-target-commit-sha>/        # detached, disposable, reviewer read-only
```

Dirty feature worktrees are preserved and never force-removed. A managed review worktree may be recreated or force-removed because it is an exact-SHA disposable cache. Neither is the primary checkout.

## Install

- [Global plugin installation](docs/installation.md): `goose plugin install <git-url>`, namespaced skills, recipes, slash commands, persistent guardrails, roots, and rollback.
- [Project-local installation](docs/project-local.md): copy skills to `.agents/skills/` and recipes to `.goose/recipes/`; includes the goose 1.44 project-plugin observation.
- [Capability parity](docs/capability-parity.md): `Equivalent`, `Adapted`, `Deferred`, and `Unavailable` status for each ported surface.
- [Known limitations](docs/known-limitations.md): hooks, subagents, POSIX locking, worktree boundaries, and other safety limits.
- [Development status and roadmap](docs/development-status.md): durable handoff, current evidence, bounded review policy, remaining gates, and multi-model orchestration roadmap.

## Installed skill names

Open Plugin installation namespaces the skills:

```text
principled-dev:adversarial-review
principled-dev:code-review-and-quality
principled-dev:debugging-and-error-recovery
principled-dev:explain-diff
principled-dev:incremental-implementation
principled-dev:make-feature
principled-dev:planning-and-task-breakdown
principled-dev:ponytail
principled-dev:signoff
principled-dev:spec-driven-development
principled-dev:test-driven-development
```

Project-local copied skills are unnamespaced because they are ordinary `.agents/skills/<name>/SKILL.md` directories.

## Runtime roots and environment

The helper defaults are:

- Worktree/cache root: `${XDG_CACHE_HOME:-$HOME/.cache}/principled-dev/worktrees`
- State root: `${XDG_STATE_HOME:-$HOME/.local/state}/principled-dev`
- State file: `<state-root>/lifecycle.json`

Override roots before starting goose when required:

```sh
export PRINCIPLED_DEV_WORKTREE_ROOT="/absolute/cache/path/principled-dev/worktrees"
export PRINCIPLED_DEV_STATE_ROOT="/absolute/state/path/principled-dev"
```

The hook uses these session values:

```sh
export PRINCIPLED_DEV_FEATURE_WORKTREE="/absolute/path/to/the/durable/feature/worktree"
export PRINCIPLED_DEV_BASE_BRANCH="main"
```

When hook executes successfully, matched `developer__write` and `developer__edit` calls are denied without resolved feature-worktree state. Shell calls are denied when launched outside resolved feature worktree, but wrappers and indirect mutations can evade command recognition. `GOOSE_MOIM_MESSAGE_FILE` should also point to `config/guardrails.md`; see installation docs. Hooks fail open and none of these controls is a security sandbox.

## Verify source checkout

From repository root:

```sh
python3 -m pytest principled-dev/tests
```

Run that command in the project's already-isolated test environment. The repository-level environment wrapper and its storage root are outside this plugin; see the global installation guide.

For an installed plugin, verify discovery in a new goose process:

```sh
goose skills list
```

Recipe files can be checked independently:

```sh
goose recipe validate /absolute/path/to/principled-dev/recipes/make-feature.yaml
goose recipe validate /absolute/path/to/principled-dev/recipes/adversarial-review.yaml
goose recipe validate /absolute/path/to/principled-dev/recipes/explain-diff.yaml
goose recipe validate /absolute/path/to/principled-dev/recipes/signoff.yaml
```

## Upstream goose references

Claims about plugin locations, namespacing, skill locations, recipe storage, slash-command mapping, hooks, persistent instructions, and subagent permission modes follow official goose documentation:

- [Plugins](https://github.com/aaif-goose/goose/blob/main/documentation/docs/guides/context-engineering/plugins.md)
- [Agent Skills](https://github.com/aaif-goose/goose/blob/main/documentation/docs/guides/context-engineering/using-skills.md)
- [Custom Slash Commands](https://github.com/aaif-goose/goose/blob/main/documentation/docs/guides/context-engineering/slash-commands.md)
- [Hooks](https://github.com/aaif-goose/goose/blob/main/documentation/docs/guides/context-engineering/hooks.md)
- [Subagents](https://goose-docs.ai/docs/guides/context-engineering/subagents)
- [Saving Recipes](https://github.com/aaif-goose/goose/blob/main/documentation/docs/guides/recipes/storing-recipes.md)
- [Environment Variables](https://github.com/aaif-goose/goose/blob/main/documentation/docs/guides/environment-variables.md)
