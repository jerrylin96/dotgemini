### External Review Prompt (Spec Gate)

Review `harvest-pstack-skills-a4ef1c/spec.md` on branch `gemini/harvest-pstack-skills-a4ef1c` against `origin/main`.

Focus on:
1. Dormancy risk: verify trigger wiring (`AGENTS.md`, `SKILL.md` frontmatter, review/spec gates) cannot leave `benchmark-checklist` or conditional checks dormant.
2. Repo invariants: check `GEMINI.md -> AGENTS.md` symlink, `scripts/tests/test_skill_references.py` (`name` frontmatter, no `file://` links), and `skills/prose-editor/tests/test_prose_editor.py` compatibility.
3. YAGNI / Ponytail: flag any unnecessary abstraction, bloat, or conflict with `caveman` chat rules.
