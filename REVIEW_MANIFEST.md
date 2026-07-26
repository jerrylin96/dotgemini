# Review Manifest: Lifecycle TDD Integration, Skill Bloat Reduction & Adversarial Review Optimization

## Summary & Rationale (Ponytail YAGNI Justified)

This feature upgrades the core software engineering lifecycle skills (`make-feature`, `planning-and-task-breakdown`, `adversarial-review`, `incremental-implementation`, and `AGENTS.md`) to:
1. **Streamline Bloat**: Deduplicate repeated simplicity checks across skill files, establishing single-source references to `ponytail/SKILL.md`.
2. **Integrate TDD into Phase 1 (`/plan`) & Phase 2 (`/build`)**: Require explicit `RED Test Spec`, `GREEN Implementation Target`, and `Verify Command` for every atomic task before worktree implementation starts.
3. **Enforce Empirical Anti-Hallucination Grounding**: Prohibit declaring success, test pass, or schema validity without empirical execution output or line-numbered `view_file` citations in context window.
4. **Optimize Adversarial Review Hand-off & Visibility**: Introduce builder pre-review quality checks, review manifest creation (`REVIEW_MANIFEST.md`), explicit user approval hard gate (Step 4c), manifest-driven reviewer subagent diff inspection, and post-review audit report artifact generation (Step 7b).

---

## TDD Proof & Verification

- **Task 1**: Deduplicated Rule 0 in `skills/incremental-implementation/SKILL.md` by replacing copy-pasted text with link to `ponytail/SKILL.md`.
- **Task 2**: Updated `skills/planning-and-task-breakdown/SKILL.md` with TDD Task Schema (RED spec, GREEN target, Verify Command) and updated verification checklist.
- **Task 3**: Added Empirical Anti-Hallucination Grounding Directives to `AGENTS.md`, `skills/make-feature/SKILL.md`, and `skills/adversarial-review/SKILL.md`.
- **Task 4**: Updated `skills/make-feature/SKILL.md` with Step 4b (Manifest creation), Step 4c (Hard human approval gate), Step 7 (Manifest-driven review subagent), and Step 7b (Post-review audit report artifact). Updated `skills/adversarial-review/SKILL.md` with manifest reading step.

---

## High-Risk Areas for Reviewer Focus

1. **Gate Sequence Continuity**: Check `make-feature/SKILL.md` to confirm Phase 1 through Phase 4 steps (Steps 1 through 8) are sequential, clear, and un-ambiguous.
2. **Grounding Directive Enforcement**: Confirm that anti-hallucination rules across `AGENTS.md`, `make-feature/SKILL.md`, and `adversarial-review/SKILL.md` are aligned without conflicting instructions.
