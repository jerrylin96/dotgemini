### External Review Prompt (RED Test Gate)

Review the RED test commit (`test: add RED test suite (failing)`) on branch `gemini/harvest-pstack-skills-a4ef1c` (`scripts/tests/test_pstack_harvest.py` and `scripts/tests/test_skill_references.py`) against `harvest-pstack-skills-a4ef1c/spec.md` (`218c002`) and `harvest-pstack-skills-a4ef1c/plan.md` (`7e4dda5`).

Focus on:
1. Spec parity & assertion rigor: verify all 7 tests in `scripts/tests/test_pstack_harvest.py` fail cleanly on missing implementation without trivial-pass loopholes, and `test_no_skill_disables_model_invocation` in `scripts/tests/test_skill_references.py` stays GREEN as a permanent structural guard.
2. Zero duplication & slice decoupling (`P4`, `P5`, `P7`, `P8`, `N2`, `N3`).

### Reviewer Identity & Session Continuity Directive
- If you already established your `REVIEWER_ID` in an earlier turn of this session, REUSE it.
- Print `### Reviewer Identification Proof` (`REVIEWER_ID`, `AUDITED_SHA`, `Review File: reviews/${REVIEWER_ID}.md`, `Push Commit SHA`) at the top of your chat response.
- Mode B isolation: edit ONLY `reviews/${REVIEWER_ID}.md`, stage ONLY `git add reviews/${REVIEWER_ID}.md`, pull `--rebase` if needed, never force-push.
