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

Nothing to install: this repo is the Antigravity global config; the skill is
indexed in `AGENTS.md` and maps to `/signoff`.

- Transcript env: `ANTIGRAVITY_CONVERSATION_ID`
- Transcript path: `~/.gemini/antigravity-cli/brain/<cid>/.system_generated/logs/transcript.jsonl`

## Claude Code — web (claude.ai/code)

Claude Code does not read this repo's root `skills/` layout. Install signoff as
a **user-level skill** so it follows you across sessions and repositories:

1. Zip the folder: `cd skills && zip -r signoff.zip signoff`
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

### Updating the skill

Re-uploading a zip with the same skill name **replaces** the installed copy —
no delete needed. During active development, skip the upload loop entirely:
cloud sessions also load project skills committed to the cloned repo's
`.claude/skills/` (synced from git at session start), so this repo carries a
`.claude/skills/signoff` symlink and `git push` is the whole update mechanism
for sessions on this repo. Refresh the user-level (Customize) copy at stable
milestones only.

### Distribution to end users (no repo linking)

Users on unrelated projects never clone or link this repo:

- **Web sessions, all projects**: claude.ai skill upload (this section) — the
  only user-scoped channel that reaches cloud sessions; user-installed plugins
  do not transfer to them.
- **CLI/desktop, all projects**: Claude Code plugin, user scope (planned
  distribution channel once the dedicated signoff repo/marketplace exists).
- **Team repos (web + local)**: a repo-declared plugin line in *their*
  `.claude/settings.json` — installed at session start from the marketplace.
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
pip install "dotgemini[mcp] @ git+https://github.com/jerrylin96/dotgemini"
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
