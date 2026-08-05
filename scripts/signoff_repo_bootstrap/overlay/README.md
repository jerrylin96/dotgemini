# signoff — Git Signoff Attestation (GSA)

**Verify that a human actually understands an AI-assisted diff before it merges.**

`/signoff` runs a Socratic reverse-interview across four fixed axes — mechanics
& intent, trade-offs & edge cases, boundary conditions & failure loudness, and
ownership — then records the outcome as a machine-parsable **Git Signoff
Attestation**: an empty signed commit plus a mirrored git note
(`refs/notes/signoff`) that survives squash merges and branch deletion.

The protocol is harness-, model-, and vendor-neutral. The skill is
prompt-driven and self-contained; the optional `signoff-mcp` server adds
deterministic server-side enforcement (derived status, stale-state circuit
breakers, notes concurrency handling).

- **Protocol spec:** [`skills/signoff/specs/gsa-core.md`](skills/signoff/specs/gsa-core.md)
- **Per-harness install & portability guide:** [`skills/signoff/HARNESSES.md`](skills/signoff/HARNESSES.md)
- **Skill entry point:** [`skills/signoff/SKILL.md`](skills/signoff/SKILL.md)

## Install

### Claude Code — plugin (recommended, all surfaces)

This repository doubles as a Claude Code **plugin marketplace**
(`.claude-plugin/marketplace.json` at root; the repo root is the plugin).

- **claude.ai (web / cloud sessions):** Directory → Plugins → **Add from a
  repository** → `https://github.com/jerrylin96/signoff`, then install the
  `signoff` plugin. The install is account-scoped and follows you into cloud
  sessions on any project.
- **CLI / desktop:**
  ```text
  /plugin marketplace add jerrylin96/signoff
  /plugin install signoff@signoff
  ```

Then invoke with `/signoff` (modifiers: `--quick`, `--deep`).

### Claude Code — skill zip upload (web fallback)

`cd skills && zip -r signoff.zip signoff`, then claude.ai → Customize →
Skills → Add. See [HARNESSES.md](skills/signoff/HARNESSES.md).

### Other harnesses (Antigravity, Codex, Goose, …)

Copy the self-contained `skills/signoff/` folder into your harness's skill
location and set the transcript adapter env vars — full matrix in
[HARNESSES.md](skills/signoff/HARNESSES.md).

### MCP server (optional enforcement)

```bash
pip install "signoff-mcp @ git+https://github.com/jerrylin96/signoff"
claude mcp add signoff -- signoff-mcp   # server must run with cwd = target repo
```

Tools: `signoff_prepare`, `signoff_commit` (server-derived status,
`ack_no_transcript` circuit breaker), `signoff_push_notes`
(`cat_sort_uniq` notes merge). PyPI release pending.

## What an attestation looks like

```text
[SIGNOFF <short-sha>]: human comprehension and risk attestation

Signoff-Spec-Version: 1.0
Signoff-Status: VERIFIED_BY_HUMAN
Signoff-Base-SHA: ...
Signoff-Reviewed-Commit-SHA: ...
Signoff-Reviewed-Tree-SHA: ...
Signoff-Harness-ID: claude-code
Signoff-Transcript-Digest: sha256:...
Signoff-Tradeoff: ...
Signoff-Risk: ...
Signoff-Verified-By: you@example.com
Signoff-Agent: harness=claude-code/2.x model=... reasoning=... interview=standard/software-general
```

Verification survives squash merges via the reviewed **tree SHA** and the
notes mirror — lookup order in [gsa-core.md §5](skills/signoff/specs/gsa-core.md).

## Customization

Exactly one delimited `INTERVIEW-PROFILE` block in `SKILL.md` is the sole
customization point. Shipped profiles:
[`software-general`](skills/signoff/profiles/software-general.md) (default),
[`domain-science`](skills/signoff/profiles/domain-science.md). Universal
axes, intensity levels, and attestation mechanics are fixed.

## Development

```bash
pip install -e . pytest
pytest
```

Contract tests live in `scripts/tests/` (skill contracts), `tests/` (plugin
manifests), and `signoff_mcp/tests/` (server mechanics).

## Provenance

Extracted from [jerrylin96/dotgemini](https://github.com/jerrylin96/dotgemini)
with full history via `git filter-repo`; dotgemini now consumes this repo via
`git subtree`. MIT licensed.
