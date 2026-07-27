# Known limitations

Read this before using `principled-dev` as a control. Skills, recipes, persistent instructions, hooks, worktrees, and virtual environments reduce mistakes; together they still do not form a security sandbox or a complete authorization system.

## goose 1.44 project-plugin discovery mismatch

Official goose docs list `<project>/.agents/plugins/<plugin-name>/` as a project-plugin location. In an observed goose `1.44.0` CLI run, a complete `principled-dev` copy under `.agents/plugins/principled-dev/` was not shown by `goose skills list`. This observation is limited to that version and check.

Use the documented fallback in [project-local installation](project-local.md):

- copy `principled-dev/skills/<name>/` to `<project>/.agents/skills/<name>/`;
- copy `principled-dev/recipes/*.yaml` to `<project>/.goose/recipes/`;
- retain a complete plugin/source copy for hooks and Python helpers.

Do not infer that project hooks loaded because unnamespaced project skills loaded. Retest discovery after goose upgrades.

## Hooks fail open

The plugin's `PreToolUse` hook can block only when it executes and emits a valid goose deny signal. goose documents broken hooks as fail-open: spawn failures, timeouts, malformed/no output, and some internal errors are logged while the tool call proceeds. `path_policy.py` also catches unexpected exceptions and prints diagnostics without claiming a block.

Consequences:

- `hooks/hooks.json` is defense in depth, not a fail-closed policy engine.
- A successful plugin install or visible skill does not prove the hook ran.
- Test the hook with harmless operations in a disposable repository after install or update.
- Keep `GOOSE_MOIM_MESSAGE_FILE` guardrails active, but treat them as model instructions rather than enforcement.

## Hook coverage is deliberately narrow

The current matcher covers `developer__write`, `developer__edit`, and `developer__shell`. Other extensions, renamed tools, direct filesystem APIs, external agents, or commands that mutate files indirectly may fall outside path checks.

When hook state resolves successfully, shell calls launched outside the active feature worktree are denied. Inside it, policy recognizes directly parsed commands beginning with `git merge`, `gh pr ... create`, or short/fully-qualified/forced/deletion `git push` refspecs targeting the configured base branch. This working-directory boundary does not constrain absolute paths used by a command. Shell wrappers, compound scripts, aliases, redirections, scripts, alternative Git clients, push options without explicit refspecs, and indirect filesystem mutations can evade recognition. Never describe this as filesystem or Git enforcement.

## No sandbox

Plugin hooks run local commands with the goose process's user permissions. Python helpers and project-native tests do the same. Git worktrees isolate checkouts, and path-hashed virtual environments isolate dependencies and test executables; neither isolates credentials, network, processes, filesystem privileges, package build hooks, or malicious dependencies.

Install only trusted plugins. Do not install or execute untrusted project dependencies merely to complete review.

## Subagents require Auto mode

goose documents internal subagents as available only in Auto/autonomous permission mode and disabled in Manual Approval, Smart Approval, and Chat-only modes. Therefore independent reviewer delegation in this port works only in Auto mode.

Auto mode allows broad tool autonomy. Human lifecycle pauses are prompt/state gates layered on top; they are not goose permission prompts. Restrict inherited extensions where possible. If a fresh independent reviewer cannot be created, return `BLOCKED`; never substitute builder self-review and call it independent approval.

Subagents cannot spawn nested subagents or manage extensions. Failure or timeout may produce no reviewer result. Absence of findings is not an approval record.

## POSIX-only locking

`principled_dev.lock` imports `fcntl` and uses `flock` to serialize worktree operations. Current runtime support is macOS and Linux. Native Windows lacks this POSIX module and is unsupported. POSIX path and symlink semantics are also assumed.

A network or unusual filesystem may not provide the same advisory-lock guarantees as a local POSIX filesystem. Do not share one worktree root across machines.

## Exact worktree separation is mandatory

Three locations have different trust and durability:

1. **Primary checkout** — never modified by lifecycle build operations.
2. **Feature worktree** — attached durable `agent/<feature>` branch at `<worktree-root>/<repository-id>/features/<branch-slug>-<hash8>`; only builder location intended for edits. Dirty feature worktrees are preserved, and safe removal refuses dirtiness.
3. **Review worktree** — detached exact target commit at `<worktree-root>/<repository-id>/reviews/<full-target-sha>`; disposable cache and reviewer read-only by workflow. It may be force-recreated when stale, dirty, or invalid.

Builder and reviewer paths must differ. A detached review worktree is not a safe place for long-lived edits. A cache path is not automatically a feature path. `PRINCIPLED_DEV_FEATURE_WORKTREE` must point to the exact feature worktree, not its parent or the full cache root.

The default worktree root is `${XDG_CACHE_HOME:-$HOME/.cache}/principled-dev/worktrees`; `PRINCIPLED_DEV_WORKTREE_ROOT` overrides it. Repository IDs derive from canonical Git common-directory identity, reducing cross-repository collision but not replacing Git inspection.

## State and attestations are local records

Default state is `${XDG_STATE_HOME:-$HOME/.local/state}/principled-dev/lifecycle.json`, overridable with `PRINCIPLED_DEV_STATE_ROOT`. Approval digests and exact SHAs detect staleness in represented state; they do not authenticate the human, prevent manual file edits, or provide tamper-evident remote storage.

A session SHA-256 digest is correlation data only. `identity` in signoff is human-confirmed text, not cryptographic identity proof. Signoff is report-only and intentionally does not amend commits. It fails closed unless persisted publication state exists and a live `git ls-remote` query confirms the feature ref still equals reviewed local HEAD and persisted published SHA; network/auth failures therefore block signoff.

## Fetch and forge limitations

Resolver fetches Git refs and supports common GitHub/GitLab/Gitea-style pull-request head refs. Credentials, remote policies, provider-specific refs, deleted forks, or unavailable networks can prevent fresh resolution. Fetch failure is surfaced; stale/offline base use requires explicit human acceptance for feature creation, and PR-head fetch failure is fatal for PR resolution.

The implementation does not create PRs and does not merge. Human performs both.

## Recipe and slash-command limits

Plugin installation discovers plugin skills and hooks, not this repository's recipes as registered slash commands. Recipes must be copied or referenced separately. Custom slash mappings require absolute recipe paths and can accept only goose's supported slash-parameter shape. Missing or invalid recipe files may cause input to be treated as ordinary model text.

Global command mappings point to one absolute checkout. Multiple project checkouts cannot all own the same four command names simultaneously without reconfiguration.

## Names differ by installation mode

Global Open Plugin skills are `principled-dev:<name>`. Skills copied to `.agents/skills/` are unnamespaced `<name>`. Recipes include a fallback, but prompts, scripts, or users that refer to the wrong name may fail to load the intended instructions. Restart goose after installation or updates because skills are discovered at session startup.

## Environment helper limits

The repository's environment wrapper may install dependencies and run package build hooks with user credentials. GPU/platform dependency filtering is heuristic. Workspace-path hashing gives different worktree paths different environments, but does not guarantee dependency reproducibility without valid lock/config files. This helper is separate from plugin worktree/state roots.

## Deferred commands and publication status

`/btw`, `/rewind`, and `/clear` are deferred: no skills, recipes, or custom slash mappings for them are implemented here. No public plugin publication, registry listing, release, or stable download URL is claimed by these docs. Use `<git-url>` only after selecting and reviewing an actual trusted source.
