# Harness Setup & Portability Guide

How to install and run `/signoff` on each agent harness. The skill is
prompt-driven and self-contained (GSA Phase 1); the `signoff-mcp` server
(GSA Phase 2) is an optional enforcement upgrade wherever MCP is supported.
Canonical protocol: [specs/gsa-core.md](specs/gsa-core.md).

## Portability Rules

1. **Copy the entire `signoff/` folder**, including `specs/`, so relative links
   (e.g. `specs/gsa-core.md`) keep resolving. Never copy `SKILL.md` alone.
2. **All links are relative** — enforced by `scripts/tests/test_skill_references.py`
   (no `file://` links).
3. **Cross-skill references degrade gracefully outside Antigravity.** On
   harnesses without `explain-diff`, the agent explains diff mechanics inline
   during remediation instead of delegating. The make-feature scratchpad step
   already self-skips when the scratchpad file does not exist.
4. **Transcript digests need the harness adapter env vars below.** When none
   apply, set `SIGNOFF_TRANSCRIPT_FILE` explicitly or accept the downgraded
   `VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST` status (second confirmation
   required).

## Antigravity CLI (native)

In the [dotgemini](https://github.com/jerrylin96/dotgemini) Antigravity global
config this skill is indexed natively in `AGENTS.md` and maps to `/signoff`;
on other Antigravity setups, copy the folder per the Portability Rules.

- Transcript env: `ANTIGRAVITY_CONVERSATION_ID`
- Transcript path: `~/.gemini/antigravity-cli/brain/<cid>/.system_generated/logs/transcript.jsonl`

## Claude Code — web (claude.ai/code)

The operative web channel is a **user-level skill** installed by zip upload
(the plugin channel registers in cloud sessions but does not load its skill
there yet — see "Distribution to end users" below):

1. Get `signoff.zip` — download the CI-built asset from the
   [latest release](https://github.com/jerrylin96/signoff/releases/latest/download/signoff.zip),
   or build it from a current checkout: `cd skills && zip -r signoff.zip signoff`
2. In the left panel: **Customize → Skills → Add**, upload the zip.
3. Invoke with `/signoff` in any session.

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
- **`refs/notes/signoff` cannot be pushed from a web session** (verified
  2026-08-05): the cloud GitHub proxy restricts pushes to the session's
  working branch and returns HTTP 403 for notes refs (misreported by git as
  "Everything up-to-date" — verify with `git ls-remote`). The attestation
  commit still pushes with the branch, so verification falls back to the
  git-log lookup (GSA §5.1). Recover the notes mirror afterward from any
  unrestricted clone — the note body is byte-identical to the attestation
  commit message:
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

1. `SIGNOFF_VERIFIED_BY` env override — export once (e.g. shell profile) to
   pin a canonical identity across harnesses
2. Harness-authenticated account email (`CLAUDE_CODE_USER_EMAIL` on Claude
   Code web)
3. `git config user.email` (local harnesses; on web this is the session
   identity, not the human — never use it there)

Unifying multiple recorded emails to one human is the read side's job via
standard `.mailmap`, not the capture side's.

### Updating the skill

Re-uploading a zip with the same skill name **replaces** the installed copy —
no delete needed. During active development, skip the upload loop entirely:
cloud sessions also load project skills committed to the cloned repo's
`.claude/skills/` (synced from git at session start), so this repo carries a
`.claude/skills/signoff` symlink and `git push` is the whole update mechanism
for sessions on this repo. Refresh the user-level (Customize) copy at stable
milestones only.

### Distribution to end users (no repo linking)

Users on unrelated projects never clone or link this repo. **Pick exactly
one channel for your surface** — none requires another:

- **Plugin marketplace (primary on CLI/desktop)**: claude.ai Customize →
  Plugins → Add → "Add marketplace" → "Add from a repository" →
  `jerrylin96/signoff`, then install the `signoff` plugin (path verified
  2026-08-05 — note it lives under Customize, not the Directory). CLI
  equivalent: `/plugin marketplace add jerrylin96/signoff` then
  `/plugin install signoff@signoff`. The repo root ships
  `.claude-plugin/marketplace.json` + `plugin.json`, so the repo itself is
  the marketplace. **Cloud-session caveat (verified 2026-08-05)**: the
  account-scoped install does sync — cloud sessions list the plugin as
  enabled — but its bundled skill does not currently load there, so
  `/signoff` stays unavailable in cloud sessions from this channel alone.
  Machine-local plugin installs (`~/.claude/settings.json`) do not transfer
  to cloud sessions either.
- **Web sessions (operative channel)**: claude.ai skill zip upload (this
  section) using the CI-built `signoff.zip` from the
  [latest release](https://github.com/jerrylin96/signoff/releases/latest/download/signoff.zip)
  — the proven user-scoped channel that reaches cloud sessions today. A zip
  is a snapshot: it updates only when re-uploaded, so re-download on new
  releases. This channel retires once cloud sessions load plugin skills.
- **Team repos (web + local)**: declare the plugin under
  [`enabledPlugins`](https://code.claude.com/docs/en/settings#enabledplugins)
  in *their* `.claude/settings.json` — installed at session start from the
  marketplace and auto-updating, per-repo rather than account-scoped.
- **Other harnesses**: self-contained folder copy (sections below).

## Claude Code — CLI

Copy the folder to `~/.claude/skills/signoff` (user-level, all projects) or
`<repo>/.claude/skills/signoff` (project-level). Same env and transcript path
as web. Linked git worktrees are handled by the `--git-common-dir` fallback:
the transcript is keyed to the primary repository root, and the adapter
resolves it automatically.

Optional MCP enforcement (server-derived status, `ack_no_transcript` circuit
breaker, stale-state checks — GSA §4):

```bash
pip install "signoff-mcp @ git+https://github.com/jerrylin96/signoff"
claude mcp add signoff -- signoff-mcp   # server must run with cwd = target repo
```

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
   export SIGNOFF_TRANSCRIPT_FILE=~/.codex/sessions/<yyyy>/<mm>/<dd>/rollout-<ts>-<uuid>.jsonl
   ```

## Other harnesses (Goose, etc.)

Use the generic override — it takes precedence over every harness adapter:

```bash
export SIGNOFF_TRANSCRIPT_FILE=/path/to/transcript.log
```

Adapter resolution order (fixed): `SIGNOFF_TRANSCRIPT_FILE` →
`ANTIGRAVITY_CONVERSATION_ID` → `CLAUDE_CODE_SESSION_ID` → `CODEX_SESSION_ID`.

## Interviewer provenance (`Signoff-Agent`)

Attestations record who conducted the interview via the `Signoff-Agent`
trailer (grammar: [specs/gsa-core.md](specs/gsa-core.md) §2.3):

```text
Signoff-Agent: harness=<id>/<version|N/A> model=<model-id|N/A> reasoning=<level|N/A> interview=<intensity-level>/<profile-id>
```

Fields are deterministically sourced where the harness exposes them; the
digest helper emits harness version, model, and reasoning from the same
transcript snapshot bytes as the digest. Per-harness sources:

| Harness | harness version | model | reasoning |
|---|---|---|---|
| Claude Code (web + CLI) | `CLAUDE_CODE_VERSION` | `ANTHROPIC_MODEL` → transcript scan (last `"model"` field) → agent self-report | `CLAUDE_EFFORT` (set on web; CLI only if exported), else `N/A` |
| Antigravity CLI | `N/A` (not exposed) | transcript scan → self-report | `N/A` (not exposed) |
| Codex CLI | `N/A` (not exposed) | rollout scan → self-report | `N/A` at skill level (`model_reasoning_effort` lives in `$CODEX_HOME/config.toml` and is not auto-discovered) |
| Generic / other | `N/A` | transcript scan → self-report | `N/A` |

`interview=` records the intensity level actually run (cursory / standard /
skeptical, post-escalation) and the active profile's `Profile-ID`.
Self-reported model values are honest best-effort, not verifiable; where the
harness records model IDs in the transcript, the transcript digest lets
auditors re-derive the model from the same bytes.

## Customizing the interview (INTERVIEW PROFILE)

`SKILL.md` contains exactly one delimited block:

```text
<!-- INTERVIEW-PROFILE:BEGIN (sole customization point — replace only this block) -->
...
<!-- INTERVIEW-PROFILE:END -->
```

This block — and only this block — is the sole customization point of the
skill. Universal axes, intensity levels, workflow steps, and attestation
mechanics are fixed: do not edit them. Profiles weight probes *within* the
universal axes and may add domain emphases; they cannot remove axes or lower
pass criteria.

To swap domains, replace everything between the markers (inclusive) with the
block from a shipped profile in [profiles/](profiles/):

- [profiles/software-general.md](profiles/software-general.md) — default:
  efficiency, data structures, API contracts.
- [profiles/domain-science.md](profiles/domain-science.md) — research code:
  unit/dimensional validity, surrogate-vs-ground-truth boundaries,
  statistical validity, reproducibility.

The `Profile-ID:` line inside the block feeds the `interview=` token of
`Signoff-Agent`, so every attestation records which profile interviewed the
human.
