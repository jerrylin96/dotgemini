### External Review Prompt (Plan Gate)

Review `harvest-pstack-skills-a4ef1c/plan.md` against `harvest-pstack-skills-a4ef1c/spec.md` (`218c002`) on branch `gemini/harvest-pstack-skills-a4ef1c`.

Focus on:
1. Closure of `S1`, `N1`, `N2`, `N3` from `reviews/arena-6cf52b3e.md`: clean Phase 2 RED→GREEN cadence, relative `[prose-editor](../prose-editor/SKILL.md)` link with inline `--unslop` application (`N1`), permanent guard vs. RED distinction (`N2`), and non-brittle `State transitions:` assertions (`N3`).
2. Line anchor accuracy, atomic task sizing, and worktree/env safety (`setup_review_env.py`, `run_in_env.py`, `test_parse_real_skill_md_without_crash`).

### Reviewer Identity & Session Continuity Directive
- If you already established your `REVIEWER_ID` in an earlier turn of this session, REUSE it.
- Print `### Reviewer Identification Proof` (`REVIEWER_ID`, `AUDITED_SHA`, `Review File: reviews/${REVIEWER_ID}.md`, `Push Commit SHA`) at the top of your chat response.
- Mode B isolation: edit ONLY `reviews/${REVIEWER_ID}.md`, stage ONLY `git add reviews/${REVIEWER_ID}.md`, pull `--rebase` if needed, never force-push.
