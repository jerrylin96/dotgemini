# Capability parity

This document compares the source lifecycle represented by this repository's global agent configuration with the current `principled-dev` goose port. It does not claim publication, certification, or bit-for-bit behavioral identity.

## Status definitions

- **Equivalent** — same user-facing intent and gate can be expressed with current goose-native facilities.
- **Adapted** — intent is present, but implementation or invocation differs because goose exposes different primitives.
- **Deferred** — intentionally not included in this port; future work may add it.
- **Unavailable** — required source primitive has no usable current equivalent in the implemented port.

## Matrix

| Capability | Status | Current goose implementation |
|---|---|---|
| Spec before plan, with separate human approvals | Equivalent | `spec-driven-development`, `planning-and-task-breakdown`, and `make-feature` skills preserve sequential approval pauses. Approval state is digest-bound. |
| Minimal-code/YAGNI discipline | Equivalent | `principled-dev:ponytail`. |
| RED-GREEN-REFACTOR and static-validation distinction | Equivalent | `test-driven-development` and `incremental-implementation` preserve behavioral versus static evidence rules. |
| Stop-the-line debugging | Equivalent | `debugging-and-error-recovery` requires preserved evidence, root-cause localization, regression protection, and renewed verification. |
| Five-axis evidence-backed review | Equivalent | `code-review-and-quality` covers correctness, simplicity, architecture, security, performance, and empirical evidence. |
| `/make-feature` entry point | Adapted | A goose recipe/slash mapping loads the namespaced skill. Lifecycle state and Git helpers are Python modules rather than Antigravity lifecycle commands. |
| Primary-checkout isolation | Equivalent | Build instructions and hook policy require repository writes in one configured durable feature worktree, never the primary checkout. |
| Durable feature worktree | Adapted | Attached `agent/<feature>` branch under `<worktree-root>/<repository-id>/features/<slug>-<hash8>`. Source configuration used different branch/root naming. |
| Independent exact-SHA review worktree | Equivalent | Detached worktree under `<worktree-root>/<repository-id>/reviews/<full-target-sha>`, separate from builder and primary checkout. |
| Branch/commit/range/PR resolution | Adapted | Resolver fetches remotes, resolves immutable SHAs, uses merge-base semantics, supports provider PR head refs, and surfaces fetch freshness. Interface and provider integration differ. |
| Safe large/unusual-path diff handling | Equivalent | `adversarial-review/diff-safety.md` requires complete diff capture, null-delimited name status, rename handling, and session scratch. |
| Independent reviewer delegation | Adapted | Uses goose Summon internal subagents and must run in Auto permission mode. No independent capability means `BLOCKED`, never self-approval. |
| Review verdict bound to immutable Git state | Equivalent | Review record binds base SHA, target commit SHA, target tree SHA, findings, evidence, and freshness. New commits stale the verdict. |
| Approved-SHA publication check | Equivalent | Lifecycle publishes exact reviewed feature SHA, verifies remote SHA, and forbids PR creation/integration mutation. |
| Human-only PR creation and merge | Equivalent | Skills and hook policy reserve both for the human. |
| Socratic signoff | Adapted | `signoff` produces a report-only, stale-safe attestation. It deliberately does not append Git trailers or mutate history. |
| Session transcript correlation digest | Adapted | Optional SHA-256 of exact exported session bytes; records `unavailable` when export is unavailable and does not imply identity proof. |
| `/adversarial-review`, `/explain-diff`, `/signoff` | Adapted | Implemented as recipes plus absolute-path custom slash mappings. Recipes are not automatically registered by plugin installation. |
| Skill discovery | Adapted | Global Open Plugin skills are namespaced `principled-dev:<name>`; project fallback copies unnamespaced skills to `.agents/skills/`. |
| Persistent global guide/guardrails | Adapted | `GOOSE_MOIM_MESSAGE_FILE` injects `config/guardrails.md` each turn. This is model context, not a hard policy boundary. |
| Pre-write/integration guardrail | Adapted | `PreToolUse` hook denies direct developer write/edit paths outside resolved feature worktree, denies shell calls launched elsewhere, and recognizes selected direct integration commands. Wrappers/indirect mutations may evade checks; hook errors and timeouts fail open. |
| Per-workspace Python environment isolation | Adapted | Existing repository wrappers use path-hashed environments; they are not bundled as a goose plugin primitive and are not a security sandbox. |
| Fresh specialized subagent type/workspace selection | Adapted | goose internal subagents provide fresh context and extension selection, but do not reproduce Antigravity `TypeName` and `Workspace` controls exactly. |
| Agent-created PR | Unavailable | Intentionally prohibited by this lifecycle; human owns PR creation. |
| Agent merge into integration branch | Unavailable | Intentionally prohibited by this lifecycle; human owns integration. |
| Hard sandbox for hooks, helpers, tests, or dependencies | Unavailable | goose hooks execute local shell commands; worktrees and virtual environments isolate state/dependencies, not privileges. |
| Fail-closed enforcement when a policy hook crashes | Unavailable | goose's documented hook behavior is fail-open unless a valid block signal is emitted. |
| Internal subagents in Approve, Smart Approve, or Chat modes | Unavailable | goose documents internal subagents as disabled outside Auto mode. |
| Windows runtime support | Unavailable | Worktree/environment locking imports POSIX `fcntl`; current implementation supports macOS/Linux only. |
| `/btw` | Deferred | No recipe, skill, or command mapping in this port. |
| `/rewind` | Deferred | No recipe, skill, or command mapping in this port. |
| `/clear` | Deferred | No recipe, skill, or command mapping in this port. |

## Interpretation

`Equivalent` describes lifecycle intent and observable gate, not identical prompts, UI, tool names, branch prefixes, storage paths, or model behavior. `Adapted` surfaces must be verified on the exact goose version and operating environment. `Unavailable` safety properties must not be implied by documentation or by a successful test run.

See [known limitations](known-limitations.md) before relying on any guardrail.
