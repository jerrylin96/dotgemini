### External Review Prompt (Spec Gate — Revision Round 2)

Re-review updated `harvest-pstack-skills-a4ef1c/spec.md` on branch `gemini/harvest-pstack-skills-a4ef1c` against `origin/main` (addressing `B1`–`B4`, `Y1`–`Y6`, `C1`–`C2`, `I5` from `reviews/arena-6cf52b3e.md`).

Focus on:
1. `B1`–`B4` closure: auditable `State transitions:` declaration + tie-break, `--unslop` Step 7c / `adversarial-review` wiring, `benchmark-checklist` scope + user-supplied methodology path, and `prose-editor` `validator.py` fence constraint.
2. `Y1`–`Y6` & `C1`–`C2`: non-duplicative RED assertions, 3-slice breakdown, single `AGENTS.md` placement in `## 1. Ponytail` (no `scratchpad.md` path drift), `Downstream Consumer Trace` naming, `@skill:benchmark-checklist` single source of truth, and `--unslop` vs `caveman` precedence.

### Reviewer Identity & Session Continuity Directive
- If you already established your `REVIEWER_ID` in an earlier turn of this session, REUSE it.
- Print `### Reviewer Identification Proof` (`REVIEWER_ID`, `AUDITED_SHA`, `Review File: reviews/${REVIEWER_ID}.md`, `Push Commit SHA`) at the top of your chat response.
- Mode B isolation: edit ONLY `reviews/${REVIEWER_ID}.md`, stage ONLY `git add reviews/${REVIEWER_ID}.md`, pull `--rebase` if needed, never force-push.
