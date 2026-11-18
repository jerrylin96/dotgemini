### External Review Prompt (GREEN Code Gate)

Review the complete feature implementation on branch `gemini/harvest-pstack-skills-a4ef1c` against `origin/main` (`harvest-pstack-skills-a4ef1c/spec.md` and `harvest-pstack-skills-a4ef1c/plan.md`).

Focus on:
1. Zero-dormancy wiring & trigger precision: `benchmark-checklist` 3-layer wiring + changeset scoping, auditable `State transitions:` gate in `spec-driven-development` + `adversarial-review`, `Downstream Consumer Trace` beyond `grep`, and inline `--unslop` wiring + `caveman` precedence.
2. Repo invariants & parser safety: `GEMINI.md -> AGENTS.md` symlink intact, no `disable-model-invocation: true`, no `file://` links in `skills/`, `prose-editor` `validator.py` Guard 1/2/3 compliance, and full `pytest` / `ruff check .` verification.

### Reviewer Identity & Session Continuity Directive
- If you already established your `REVIEWER_ID` in an earlier turn of this session, REUSE it.
- Print `### Reviewer Identification Proof` (`REVIEWER_ID`, `AUDITED_SHA`, `Review File: reviews/${REVIEWER_ID}.md`, `Push Commit SHA`) at the top of your chat response.
- Mode B isolation: edit ONLY `reviews/${REVIEWER_ID}.md`, stage ONLY `git add reviews/${REVIEWER_ID}.md`, pull `--rebase` if needed, never force-push.
