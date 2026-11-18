### External Review Prompt (Plan Gate — Revision)

Re-review updated `harvest-pstack-skills-a4ef1c/plan.md` against `harvest-pstack-skills-a4ef1c/spec.md` (`218c002`) on branch `gemini/harvest-pstack-skills-a4ef1c`.

Focus on:
1. Parser Safety (`validator.py:294-306` Guard 1): Task 4 forbids concrete numeric `### Suggestion #<digits>` headers inside `prose-editor/SKILL.md` so `test_parse_real_skill_md_without_crash` passes.
2. Slice-decoupled verify gates: `test_agents_md_benchmark_wiring` (Slice 1) separated from `test_agents_md_encode_lessons_rule` (Slice 3), so Task 2's `-k "benchmark"` passes independently.
3. Closure of `S1`, `N1`, `N2`, `N3` from `reviews/arena-6cf52b3e.md`.

### Reviewer Identity & Session Continuity Directive
- If you already established your `REVIEWER_ID` in an earlier turn of this session, REUSE it.
- Print `### Reviewer Identification Proof` (`REVIEWER_ID`, `AUDITED_SHA`, `Review File: reviews/${REVIEWER_ID}.md`, `Push Commit SHA`) at the top of your chat response.
- Mode B isolation: edit ONLY `reviews/${REVIEWER_ID}.md`, stage ONLY `git add reviews/${REVIEWER_ID}.md`, pull `--rebase` if needed, never force-push.
