# Harness Setup & Portability Guide

How to install and run `/git-signoff` on each agent harness. The skill is
one self-contained folder: the interview prompt (`SKILL.md`), the
deterministic producer (`attest.py`), and the verifier (`verify_signoff.py`).
Nothing is installed by name and no Python package is required — the
initializer, the producer, and the verifier are standard-library scripts
(Python 3.10+). Canonical protocol: [specs/gsa-core.md](specs/gsa-core.md).

## Portability Rules

1. **Copy the entire `git-signoff/` folder**, including `specs/`, `attest.py`,
   and `verify_signoff.py`, so relative links (e.g. `specs/gsa-core.md`) keep
   resolving and the helper finds its sibling verifier. Never copy `SKILL.md`
   alone. Licensing inside the folder: `attest.py`, `verify_signoff.py`, and
   the Markdown guidance are MIT like the rest of the repository's code
   (`LICENSE` in this folder); the documents under `specs/` are under the
   Apache License 2.0 (`specs/LICENSE`, stated in each file). Neither license
   covers the other's files.
2. **All links are relative** — enforced by `scripts/tests/test_skill_references.py`
   (no `file://` links).
3. **Cross-skill references degrade gracefully outside Antigravity.** On
   harnesses without `explain-diff`, the agent explains diff mechanics inline
   during remediation instead of delegating. The make-feature scratchpad step
   already self-skips when the scratchpad file does not exist.
4. **Transcript digests need the harness adapter env vars below.** When none
   apply, set `GIT_SIGNOFF_TRANSCRIPT_FILE` explicitly or accept the downgraded
   `VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST` status (second confirmation
   required).

## Cross-Harness Test Matrix & Agent Skills Conventions

### Explanation and practice

The same installed folder supports `/git-signoff --explain` for a guided
walkthrough and `/git-signoff --practice` for rehearsal. No second skill or
external `explain-diff` installation is required. Use the harness's normal
skill invocation spelling (for example `$git-signoff --explain` in Codex).
Practice retains the normal profiles, science guard, and tier clamps;
explanation has no grade. Both inspect current tracked working files unless
a remote branch is named, and leave preparation records, index, and notes
untouched. A named target fetches objects and a tracking ref.

Explanation can lead to a fresh real interview in the same conversation
after an explicit request. Practice requires a new conversation. Inspection
is read-only. Before its first probe, run `attest.py practice-start --json`:
it writes a small local record under
`<git-common-dir>/git-signoff/practice-sessions/<session-key>.json`.
All linked worktrees share it; it is not committed, pushed, or cloned.
The key uses the conversation id, or the canonical transcript path for a
generic file with no id. Generic files must represent one session; use a new
file for a new session. Transcript contents need not be available or parsable.

Real prepare, `marker`, and commit/dry-run reject the recorded session,
including `--ack-no-transcript`. A new conversation has a different key and
does not clear previous records. A failed write stops practice; unreadable
guard state stops signoff, and an empty/partial record still blocks it.
Never clear a guard to turn practice into real signoff.

For backup, emit practice-start's `practice_marker` as a separate assistant
message whose entire text is the line. It is a control event, not an
attestation or approval. Reading an example in docs or tool output does not
start practice.

The helper recognizes Claude assistant-message envelopes, Codex
`response_item` message envelopes, and normalized JSONL messages of the form
`{"role":"assistant","content":"<the exact practice_marker from this run>"}`.
Text content blocks are supported; user/tool records and quoted content are
not recursively parsed as messages. The marker is bound to the conversation
id, or the canonical transcript path for a generic file with no id.

Opaque/unrecognized or unavailable transcripts do not weaken an existing
local guard; they only prevent transcript-based backup detection. Without
any conversation identity or transcript path, the helper explicitly reports
`guard: instruction-only`. Records are repository-local, so another clone
must rely on the transcript backup or the skill instructions. Deliberately
deleting records, editing transcripts, or changing identity can bypass the
guards; they prevent accidental promotion, not forgery. No-transcript
acknowledgment and status remain available to fresh sessions. A recognized
practice event blocks both dry-run and real commit, even outside the approval
window or arriving on a snapshot retry.

The `init.py` zero-touch initializer installs `/git-signoff` as a committed repository skill. Git Signoff Attestation (GSA v1.0) is entirely protocol-neutral: the commit trailers, git notes mirror, and verification logic are implemented using standard library Python (stdlib) invoking the `git` CLI, requiring zero external dependencies.

Repositories can vendor `/git-signoff` into one or both candidate locations using `--skill-target`:
- `.claude/skills/git-signoff`: Canonical destination for Claude Code (web, CLI, desktop).
- `.agents/skills/git-signoff`: Cross-client convention for Antigravity CLI, Codex CLI, Cursor, and OpenCode (the Agent Skills specification defines the skill format; `.agents/skills` is client convention and implementation guidance, not a normative location).

When invoked with `--skill-target auto` (the default), `init.py` inspects the repository for signals (`.claude` or `CLAUDE.md` for the Claude destination; `.agents`, `.cursor`, `.gemini`, `.codex`, `.opencode`, `AGENTS.md`, or `GEMINI.md` for the cross-client destination) and automatically selects the appropriate destination. Each cross-client directory marker is a canonical repository-local configuration path of its harness: `.opencode/` per OpenCode's configuration documentation, `.gemini/` for Antigravity CLI and `.codex/` for Codex CLI as confirmed by the maintainer against each product's documentation on 2026-09-09 (issue #16). In interactive greenfield setups without existing markers, it prompts the user; in non-interactive greenfield setups, it defaults to both destinations. Explicit choices (`--skill-target claude`, `--skill-target agents`, `--skill-target both`) are unioned with existing installations so re-running `init.py` always updates all configured harnesses together without version drift. A recognized existing install (a candidate path whose target contains `SKILL.md`, symlink or not) is always unioned into the destination set and cannot be excluded by any `--skill-target` value; a symlinked one is then refused by Policy A and must be replaced with a real copy first. A broken symlink is not recognized and is not unioned.

Re-running the initializer requires a clean working tree by default. `--allow-dirty` permits unrelated unstaged/untracked work only: pre-staged changes and any uncommitted or ignored state under managed scaffold paths are refused before branch creation, and the index is checked again before the scaffold commit.

### Cross-Harness Compatibility Matrix

| Harness | Skill Destination | Invocation Syntax | Transcript Discovery | Zero-Dependency stdlib |
|---|---|---|---|---|
| **Claude Code** | `.claude/skills/git-signoff` | `/git-signoff` | `CLAUDE_CODE_SESSION_ID` -> `~/.claude/projects/<slug>/<id>.jsonl` | Yes (standard library Python + git) |
| **Antigravity CLI** | `.agents/skills/git-signoff` | `/git-signoff` | `ANTIGRAVITY_CONVERSATION_ID` -> `~/.gemini/antigravity-cli/brain/<cid>/...` | Yes (standard library Python + git) |
| **Codex CLI** | `.agents/skills/git-signoff` | `$git-signoff` | `CODEX_SESSION_ID` -> `$CODEX_HOME/sessions/**/rollout-*-<id>.jsonl` | Yes (standard library Python + git) |
| **Cursor** | `.agents/skills/git-signoff` | `/git-signoff` (or auto) | `GIT_SIGNOFF_TRANSCRIPT_FILE` generic override | Yes (standard library Python + git) |
| **OpenCode** | `.agents/skills/git-signoff` | Automatic / tool-selected (native skill tool) | `GIT_SIGNOFF_TRANSCRIPT_FILE` generic override | Yes (standard library Python + git) |

## Antigravity CLI (native)

In the [dotgemini](https://github.com/jerrylin96/dotgemini) Antigravity global
config this skill is indexed natively in `AGENTS.md` and maps to `/git-signoff`;
on other Antigravity setups, copy the folder per the Portability Rules.

- Transcript env: `ANTIGRAVITY_CONVERSATION_ID`
- Transcript path: `~/.gemini/antigravity-cli/brain/<cid>/.system_generated/logs/transcript.jsonl`

## Claude Code — CLI, desktop, and web (claude.ai/code)

One mechanism covers every Claude Code surface: a **project skill** — the
self-contained folder committed to the repository under review at
`<repo>/.claude/skills/git-signoff/`. Local sessions load it from the working
tree; cloud sessions load it from the clone at session start. Vendor it with
the zero-touch initializer (README Quickstart) or copy the folder per the
Portability Rules. `git pull` is the whole update mechanism for
collaborators; updating the vendored copy means re-running the initializer
*from the current README snippet* (or re-copying the folder) — a previously
downloaded script re-vendors its own pinned version, never silently newer
content. Vendored copies never self-update or announce new releases; the
initializer vendors the skill at the same pinned tag the
install snippet serves the script from, and stamps source, ref, and commit
into a `VENDORED-FROM` file inside the copy — so any vendored folder tells
you exactly which version it holds. Offline installs pass
`--skill-source <path-to-skills/git-signoff>` (stamped `ref: local (--skill-source)`). Commit a
real copy, not a symlink — re-running the initializer over a destination
containing a symlink at the destination or in any parent path component aborts
per Policy A, refusing to mutate or traverse symlinked paths. This repository
dogfoods via symlinks at both `.claude/skills/git-signoff` and
`.agents/skills/git-signoff` to its own `skills/git-signoff/`; that symlink pattern is
for this repo only.

**Migration note (2026-09, `init-v9`):** re-running the initializer rewrites
`.github/workflows/git-signoff.yml` with a `permissions:` block (`contents:
read`, `pull-requests: read`) and pins `verify@verify-v1.6` and
`recover@verify-v1.6`. GitHub's restricted default token has no
`pull-requests` scope, and without it the verifier's `scan-refs: auto` lookup
scanned nothing. `verify-v1.6` also fixes history mode's deduplication (an
invalid rebased copy no longer hides valid evidence for the same commit) and
the 100-pull-request lookup window, and history mode no longer counts notes
on objects outside the ref's history, or notes that do not name the object
they hang on (an abandoned branch's published notes, or a note git copied onto
a rebased commit, made a badge green); branch names with `+`, `&` or `#` now
reach the pull-request lookup intact. Existing attestations verify as before; a history badge
that was green only on such notes turns red.

**Migration note (2026-09, `init-v8`):** re-running the initializer adds
`.git-signoff/config.json` (the integration branch, confirmed once), renders
the ruleset for that branch, and scaffolds the notes-recovery workflow; the
vendored `attest.py` gains target mode (`prepare --target <branch>`,
`targets`) and the preparation record; `verify@verify-v1.5` is the matching
verifier pin. Existing attestations verify as before.

**Migration note (2026-09, `init-v7`):** the skill folder, command, config
directory, workflow file, and environment variables were renamed from
`signoff` to `git-signoff` (`.claude/skills/git-signoff`,
`/git-signoff`, `.git-signoff/profile.md`, `.github/workflows/git-signoff.yml`,
`GIT_SIGNOFF_TRANSCRIPT_FILE`, `GIT_SIGNOFF_PROFILE_FILE`,
`GIT_SIGNOFF_VERIFIED_BY`). Protocol identifiers — `Signoff-*` trailers,
`refs/notes/signoff`, the `[SIGNOFF <sha>]` subject — did not change, so
existing attestations verify unchanged. The only install that existed under
the old names was this repository's own pair of symlinks, which were moved;
an adopter upgrading a hypothetical `.claude/skills/signoff` copy would re-run
the initializer (which vendors to the new path), delete the old folder,
rename `.signoff/` to `.git-signoff/`, and re-export any `SIGNOFF_*` variables
under the new names.

A machine-local install also works for local CLI/desktop sessions: copy the
folder to `~/.claude/skills/git-signoff` (user-level, all projects). Linked git
worktrees are handled by the `--git-common-dir` fallback: the transcript is
keyed to the primary repository root, and the adapter resolves it
automatically.

- Transcript env: `CLAUDE_CODE_SESSION_ID` (exported to Bash subprocesses;
  verified live in a web session on 2026-08-05, including full adapter
  resolution of the running session's transcript).
- Transcript path: `~/.claude/projects/<cwd-slug>/<session-id>.jsonl`

Web-specific caveats:
- **Ephemeral containers**: the transcript file is destroyed when the session
  container is reclaimed. The digest still proves what existed at commit time,
  but can never be re-hashed locally afterward — push the attestation commit
  and `refs/notes/signoff` before the session ends. (This is the primary
  motivation for transcript escrow in the cloud concept.)
- **Weaker append-only assumption** (GSA §2.3): web sessions sync and compact
  transcripts, so first-N-bytes re-verification is less reliable than on
  local CLI harnesses.
- **Target mode is for local harnesses.** `attest.py prepare --target <branch>`
  pushes the attestation to `origin/<branch>`; the web session's git proxy
  allows pushes only to the session's own working branch, so that push is
  refused there (exit 3, nothing on the branch, notes reported). From a web
  session, check the branch out and use HEAD mode as before.
- **`refs/notes/signoff` cannot be pushed from a web session** (verified
  2026-08-05): the cloud GitHub proxy restricts pushes to the session's
  working branch and returns HTTP 403 for notes refs (misreported by git as
  "Everything up-to-date" — verify with `git ls-remote`). `attest.py commit`
  reports this as `notes_pushed: false` with the reason and still exits 0:
  the attestation commit pushes with the branch, so verification falls back
  to the git-log lookup (GSA §5.1), and this repository's notes-recovery
  workflow rebuilds the ref on merge. Recover the notes mirror by hand from
  any unrestricted clone if needed — the note body is byte-identical to the
  attestation commit message:
  ```bash
  NOTE_BODY=$(git log -1 --format=%B <attestation-sha>)
  git notes --ref=signoff append -m "$NOTE_BODY" <reviewed-commit-sha>
  git notes --ref=signoff append -m "$NOTE_BODY" <reviewed-tree-sha>
  git fetch origin +refs/notes/signoff:refs/notes/signoff-remote &&
      git notes --ref=signoff merge -s cat_sort_uniq refs/notes/signoff-remote
  git push origin refs/notes/signoff
  ```

### Verified-By resolution (all harnesses)

`Signoff-Verified-By` is proposed deterministically, never inferred; the
human's explicit confirmation of the proposed value remains the
accountability step. Resolution order:

1. `GIT_SIGNOFF_VERIFIED_BY` env override — export once (e.g. shell profile) to
   pin a canonical identity across harnesses
2. Harness-authenticated account email (`CLAUDE_CODE_USER_EMAIL` on Claude
   Code web)
3. `git config user.email` (local harnesses; on web this is the session
   identity, not the human — never use it there)

Unifying multiple recorded emails to one human is the read side's job via
standard `.mailmap`, not the capture side's.

### Distribution to end users

One channel: the vendored project skill above, committed to each repository
that wants `/git-signoff`. Users never clone or link this repo, and there is
nothing account-scoped to install or keep updated. The earlier account-scoped
channels — a Claude Code plugin marketplace and a CI-built release-zip skill
upload — were retired in v0.4.0: both demanded per-account setup, and the
plugin's bundled skill never loaded in cloud sessions (platform gap, verified
2026-08-05); the per-repo folder covers every surface without either. Other
harnesses use the same folder in their own skill location (sections below).

## ChatGPT Codex CLI

Codex stores session rollouts under `$CODEX_HOME/sessions/` (default
`~/.codex/sessions/`) as date-partitioned
`rollout-<timestamp>-<session-id>.jsonl` files, but does **not** inject a
session-id env var. Two options:

1. Export the session id (from the rollout filename) so the `CodexAdapter`
   discovers the newest matching rollout:
   ```bash
   export CODEX_SESSION_ID=<session-uuid>
   ```
2. Or point the generic override at the rollout file directly:
   ```bash
   export GIT_SIGNOFF_TRANSCRIPT_FILE=~/.codex/sessions/<yyyy>/<mm>/<dd>/rollout-<ts>-<uuid>.jsonl
   ```

## Other harnesses (Goose, etc.)

Use the generic override — it takes precedence over every harness adapter:

```bash
export GIT_SIGNOFF_TRANSCRIPT_FILE=/path/to/transcript.log
```

Adapter resolution order (fixed): `GIT_SIGNOFF_TRANSCRIPT_FILE` →
`ANTIGRAVITY_CONVERSATION_ID` → `CLAUDE_CODE_SESSION_ID` → `CODEX_SESSION_ID`.

## Interviewer provenance (`Signoff-Agent`)

Attestations record who conducted the interview via the `Signoff-Agent`
trailer (grammar: [specs/gsa-core.md](specs/gsa-core.md) §2.3):

```text
Signoff-Agent: harness=<id>/<version|N/A> model=<model-id|N/A> reasoning=<level|N/A> interview=<intensity-level>/<profile-id>
```

Fields are deterministically sourced where the harness exposes them;
`attest.py` derives harness version, model, and reasoning from the environment
and from the same transcript snapshot bytes as the digest, and accepts the
agent's self-reported model (`--model`) only when no deterministic source has
one. Per-harness sources:

| Harness | harness version | model | reasoning |
|---|---|---|---|
| Claude Code (web + CLI) | `CLAUDE_CODE_VERSION` | `ANTHROPIC_MODEL` → transcript scan (last `"model"` field) → agent self-report | `CLAUDE_EFFORT` (set on web; CLI only if exported), else `N/A` |
| Antigravity CLI | `N/A` (not exposed) | transcript scan → self-report | `N/A` (not exposed) |
| Codex CLI | `N/A` (not exposed) | rollout scan → self-report | `N/A` at skill level (`model_reasoning_effort` lives in `$CODEX_HOME/config.toml` and is not auto-discovered) |
| Generic / other | `N/A` | transcript scan → self-report | `N/A` |

`interview=` records the intensity level actually run (cursory / standard /
skeptical, post-escalation) and the active profile's `Profile-ID`. When no
explicit modifier (`--quick` / `--deep`) is supplied, `/git-signoff` uses
**adaptive intensity by default** — dynamically evaluating range diff semantics
and blast radius per SKILL.md's classification precedence: Tier 0 (`cursory`
for tiny pure docs/types <50 LoC AND ≤2 files), Tier 1 (`standard` for default
feature work, with docs-only churn of any size capped at Tier 1), or Tier 2
(`skeptical` for high-impact content/path triggers or executable blast
radius >200 LoC / >5 files). Explicit `--quick` permits cursory opt-in on
small routine code (≤200 LoC, ≤5 files) or small docs (<50 LoC, ≤2 files), but
is subject to a 4-row safety clamp that strictly blocks cursory and
auto-escalates to Tier 1 for docs blast radius (≥50 LoC or >2 files), or Tier 2
for high-impact triggers / executable blast radius.
Self-reported model values are honest best-effort, not verifiable; where the
harness records model IDs in the transcript, the transcript digest lets
auditors re-derive the model from the same bytes.

## Customizing the interview (INTERVIEW PROFILE)

The interview profile — a single delimited text block — is the sole
customization point of the skill. Universal axes, intensity levels, workflow
steps, and attestation mechanics are fixed: profiles weight probes *within*
the universal axes and may add domain emphases; they cannot remove axes or
lower pass criteria.

The active profile is resolved per run, in fixed order:

1. **`GIT_SIGNOFF_PROFILE_FILE`** — explicit path to a profile file. Highest
   precedence; if set but unreadable, signoff aborts rather than silently
   falling back.
2. **`<repo>/.git-signoff/profile.md`** — repo-local profile. Commit one file to
   the repository under review and every `/git-signoff` run there uses it — for
   every collaborator, on every harness, surviving skill updates. This is
   the recommended path for labs and teams.
3. **Embedded block in `SKILL.md`** — the shipped default
   (`software-general`). Editing it in the vendored copy still works, but
   re-vendoring on update overwrites such edits — prefer the repo-local
   file.

A profile file must contain exactly one block of the form:

```text
<!-- INTERVIEW-PROFILE:BEGIN (sole customization point — replace only this block) -->
### Interview Profile: <your domain>
Profile-ID: <your-domain-id>

Domain emphases — weight probes within the universal axes; never remove axes
or lower pass criteria:
- **<Emphasis>:** <what to probe — e.g. grid-resolution sensitivity of any
  reported trend; conservation properties of a new parameterization>
<!-- INTERVIEW-PROFILE:END -->
```

Start from a shipped profile:

- [profiles/software-general.md](profiles/software-general.md) — default:
  efficiency, data structures, API contracts.
- [profiles/domain-science.md](profiles/domain-science.md) — research code:
  unit/dimensional validity, surrogate-vs-ground-truth boundaries, numerical
  stability, statistical validity, uncertainty quantification,
  reproducibility.
- [profiles/README.md](profiles/README.md) — complete guide to authoring
  scientific and domain-specific profiles with 4 discipline-specific templates
  (fluids/climate, genomics, AI surrogate models, numerical analysis).

Malformed or out-of-scope file-sourced profiles (missing markers or
`Profile-ID`, attempts to weaken axes or pass criteria, instructions
unrelated to interview emphasis) are announced and ignored — the run falls
back to the embedded default, so a broken profile can only restore stock
rigor, never lower it.

**Provenance:** the `Profile-ID:` line feeds the `interview=` token of
`Signoff-Agent`, and file-sourced profiles additionally record a 12-hex
SHA256 prefix of the block
(`interview=<level>/<profile-id>/sha256:<digest>`, GSA §2.3), so every
attestation shows exactly which question set interviewed the human — a
diluted profile is distinguishable from a shipped one.

**Science guard:** independent of the active profile, any diff that touches
scientific computation (scientific-stack imports, notebooks, RNG seeding,
unit-bearing constants, netCDF/GRIB/zarr datasets or model configs)
additively triggers the `domain-science` emphases — see the guard in
`SKILL.md`. A repo whose profile already carries those emphases sees no
change; the guard exists so science probes never depend on someone having
configured anything.
