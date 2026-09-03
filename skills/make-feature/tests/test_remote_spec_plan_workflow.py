import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MAKE_FEATURE_PATH = REPO_ROOT / "skills" / "make-feature" / "SKILL.md"
LIFECYCLE_GUIDE_PATH = REPO_ROOT / "skills" / "make-feature" / "resources" / "lifecycle-guide.md"
SPEC_SKILL_PATH = REPO_ROOT / "skills" / "spec-driven-development" / "SKILL.md"
PLAN_SKILL_PATH = REPO_ROOT / "skills" / "planning-and-task-breakdown" / "SKILL.md"
INCREMENTAL_SKILL_PATH = REPO_ROOT / "skills" / "incremental-implementation" / "SKILL.md"
TDD_SKILL_PATH = REPO_ROOT / "skills" / "test-driven-development" / "SKILL.md"
ADVERSARIAL_SKILL_PATH = REPO_ROOT / "skills" / "adversarial-review" / "SKILL.md"
AGENTS_MD_PATH = REPO_ROOT / "AGENTS.md"
README_PATH = REPO_ROOT / "README.md"


class TestRemoteSpecPlanWorkflow(unittest.TestCase):
    def test_make_feature_skill_lifecycle(self):
        content = MAKE_FEATURE_PATH.read_text(encoding="utf-8")

        # 1. 6-char hex derivation & BASE_BRANCH assignment & feature sanitization
        self.assertTrue(
            "tr -dc 'a-f0-9' < /dev/urandom | head -c 6" in content or "openssl rand -hex 3" in content,
            "make-feature/SKILL.md must specify 6-character hex hash derivation",
        )
        self.assertIn(
            'BASE_BRANCH="${1:-main}"',
            content,
            "make-feature/SKILL.md must assign BASE_BRANCH before use",
        )
        self.assertIn(
            "SANITIZED_FEATURE=",
            content,
            "make-feature/SKILL.md must sanitize feature name",
        )

        # 2. Remote check and fallback
        self.assertIn(
            "git remote get-url origin",
            content,
            "make-feature/SKILL.md must include remote pre-flight check",
        )
        self.assertIn(
            "REMOTE_ENABLED",
            content,
            "make-feature/SKILL.md must define REMOTE_ENABLED flag",
        )

        # 3. Early worktree initialization in Phase 1a
        phase1a_match = re.search(r"Phase 1a.*?Phase 1b", content, re.DOTALL)
        self.assertIsNotNone(phase1a_match, "Phase 1a section missing")
        self.assertIn(
            "git worktree add",
            phase1a_match.group(0),
            "make-feature/SKILL.md must relocate worktree creation to Phase 1a",
        )

        # 4. In-tree spec and plan commits and pushes
        self.assertIn("spec.md", content)
        self.assertIn("spec: add initial feature spec for external review", content)
        self.assertIn("plan.md", content)
        self.assertIn("plan: add implementation plan for external review", content)

        # 5. Step 2b & 3b revision push sync
        self.assertIn("spec: address review feedback", content)
        self.assertIn("plan: address review feedback", content)

        # 6. Early abort teardown routines for Step 2c and 3c (must cd out of worktree first)
        self.assertIn(
            "PRIMARY_REPO=",
            content,
            "make-feature/SKILL.md abort routine must resolve PRIMARY_REPO before worktree remove",
        )
        self.assertIn("git branch -D", content)
        self.assertIn("git push origin --delete", content)
        self.assertIn("git worktree prune", content)

        # 7. Phase 2 Step 4: Redundant git worktree add removed from Phase 2 Step 4
        phase2_match = re.search(r"3\.\s*\*\*Phase 2.*?4\.\s*\*\*Phase 3", content, re.DOTALL)
        self.assertIsNotNone(phase2_match, "Phase 2 section not found")
        phase2_text = phase2_match.group(0)
        self.assertNotIn(
            "git worktree add",
            phase2_text,
            "Phase 2 Step 4 must not contain redundant 'git worktree add'",
        )

        # 8. Step 4d RED test remote push gate
        self.assertIn(
            "test: add RED test suite (failing)",
            phase2_text,
            "make-feature/SKILL.md Phase 2 must define Step 4d RED test remote push gate",
        )

        # 9. Step 4g & Step 5 GREEN implementation commit
        self.assertIn(
            "feat: implement feature to make tests pass (GREEN)",
            phase2_text,
            "make-feature/SKILL.md Phase 2 must define Step 5 GREEN commit message",
        )

        # 10. Heavy Mode per-slice 2-stage commit cadence
        self.assertIn("test(slice-N): add RED test suite (failing)", content)
        self.assertIn("feat(slice-N): implement slice N (GREEN)", content)

        # 11. Idempotent Step 7b cleanup with --ignore-unmatch in Phase 3
        phase3_match = re.search(r"4\.\s*\*\*Phase 3.*?5\.\s*\*\*Phase 4", content, re.DOTALL)
        self.assertIsNotNone(phase3_match, "Phase 3 section not found")
        phase3_text = phase3_match.group(0)
        self.assertIn(
            "git rm -rf --ignore-unmatch",
            phase3_text,
            "make-feature/SKILL.md Phase 3 must specify idempotent cleanup with --ignore-unmatch",
        )
        self.assertIn(
            "chore: remove ephemeral spec and plan before signoff",
            phase3_text,
            "make-feature/SKILL.md Phase 3 must specify cleanup commit message",
        )
        self.assertIn(
            "git diff --cached --quiet",
            phase3_text,
            "make-feature/SKILL.md Phase 3 cleanup commit must be guarded against empty diff",
        )

        # 12. Ephemeral review report rule (prohibiting Obsidian)
        self.assertIn("Obsidian", phase3_text)
        self.assertTrue(
            "Do NOT write" in phase3_text or "prohibit" in phase3_text.lower(),
            "make-feature/SKILL.md Phase 3 must forbid saving review reports to Obsidian",
        )

    def test_spec_and_plan_skills(self):
        spec_content = SPEC_SKILL_PATH.read_text(encoding="utf-8")
        plan_content = PLAN_SKILL_PATH.read_text(encoding="utf-8")

        # Spec skill must document in-tree spec path (${FEATURE_SLUG}/spec.md) and superseding /artifact & Obsidian
        self.assertTrue(
            "${FEATURE_SLUG}/spec.md" in spec_content or "<feature-name>-<hash>/spec.md" in spec_content,
            "spec skill must explicitly reference in-tree spec.md path under ${FEATURE_SLUG}",
        )
        self.assertIn(
            "supersedes",
            spec_content.lower(),
            "spec skill must explicitly state in-tree spec supersedes Obsidian/artifact paths",
        )

        # Plan skill must document in-tree plan path (${FEATURE_SLUG}/plan.md) and superseding /artifact & Obsidian
        self.assertTrue(
            "${FEATURE_SLUG}/plan.md" in plan_content or "<feature-name>-<hash>/plan.md" in plan_content,
            "plan skill must explicitly reference in-tree plan.md path under ${FEATURE_SLUG}",
        )
        self.assertIn(
            "supersedes",
            plan_content.lower(),
            "plan skill must explicitly state in-tree plan supersedes Obsidian/artifact paths",
        )
        self.assertIn("Heavy Mode", plan_content)
        self.assertIn("test(slice-N)", plan_content)
        self.assertIn("feat(slice-N)", plan_content)

        # Overview in plan skill must not mention pause before creating worktrees
        self.assertNotIn("before creating worktrees", plan_content)

    def test_agents_guide_rules(self):
        content = AGENTS_MD_PATH.read_text(encoding="utf-8")

        # §3 Milestone Phase Goals updates
        sec3_match = re.search(r"## 3\.\s*Slash Commands.*?(?=## 4|\Z)", content, re.DOTALL)
        self.assertIsNotNone(sec3_match, "AGENTS.md must contain §3 Slash Commands & Lifecycle Discipline")
        sec3_text = sec3_match.group(0)
        self.assertIn(
            "test: add RED test suite (failing)",
            sec3_text,
            "AGENTS.md §3 must mention RED test remote push gate",
        )
        self.assertTrue(
            "remove ephemeral" in sec3_text.lower() or "--ignore-unmatch" in sec3_text,
            "AGENTS.md §3 must mention ephemeral cleanup",
        )

        # §9 Ephemerality and Obsidian boundaries
        sec9_match = re.search(r"## 9\.\s*User-Facing Artifacts.*?(?=## 10|\Z)", content, re.DOTALL)
        self.assertIsNotNone(sec9_match, "AGENTS.md must contain §9 User-Facing Artifacts")
        sec9_text = sec9_match.group(0)
        self.assertIn("ephemeral", sec9_text.lower())
        self.assertTrue("review_report" in sec9_text or "review report" in sec9_text.lower())
        self.assertIn("Obsidian", sec9_text)

    def test_companion_docs_and_sibling_skills(self):
        # 1. README.md
        readme_content = README_PATH.read_text(encoding="utf-8")
        self.assertIn("gemini/<feature-name>-<hash>", readme_content)
        self.assertNotIn(
            "before creating worktrees",
            readme_content,
            "README.md must not say 'before creating worktrees'",
        )
        self.assertIn("Phase 1a & 1b", readme_content)

        # 2. lifecycle-guide.md
        lifecycle_content = LIFECYCLE_GUIDE_PATH.read_text(encoding="utf-8")
        phase2_match = re.search(r"4\.\s*\*\*Phase 2.*?(?=5\.\s*\*\*Phase 3)", lifecycle_content, re.DOTALL)
        self.assertIsNotNone(phase2_match, "lifecycle-guide.md Phase 2 not found")
        self.assertNotIn(
            "Create isolated worktree",
            phase2_match.group(0),
            "lifecycle-guide.md Phase 2 must not create worktree (moved to Phase 1a)",
        )
        phase1a_match = re.search(r"2\.\s*\*\*Phase 1a.*?(?=3\.\s*\*\*Phase 1b)", lifecycle_content, re.DOTALL)
        self.assertIsNotNone(phase1a_match, "lifecycle-guide.md Phase 1a not found")
        self.assertIn("gemini/<feature-name>-<hash>", phase1a_match.group(0))
        self.assertIn("git rm -rf --ignore-unmatch", lifecycle_content)

        # 3. incremental-implementation/SKILL.md
        incremental_content = INCREMENTAL_SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("gemini/<feature-name>-<hash>", incremental_content)

        # 4. test-driven-development/SKILL.md
        tdd_content = TDD_SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "Phase 2 (Build, Worktree & RED Test Remote Push Gate)",
            tdd_content,
            "test-driven-development SKILL.md must align Phase 2 heading",
        )
        self.assertIn("${FEATURE_SLUG}/spec.md", tdd_content)

        # 5. adversarial-review/SKILL.md
        adversarial_content = ADVERSARIAL_SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("${FEATURE_SLUG}/spec.md", adversarial_content)
        self.assertNotIn(
            "Create or use a git worktree.",
            adversarial_content,
            "adversarial-review must not forbid using parent-managed worktrees",
        )

    def test_markdown_links_valid(self):
        skills_to_check = [
            MAKE_FEATURE_PATH,
            LIFECYCLE_GUIDE_PATH,
            SPEC_SKILL_PATH,
            PLAN_SKILL_PATH,
            INCREMENTAL_SKILL_PATH,
            TDD_SKILL_PATH,
            ADVERSARIAL_SKILL_PATH,
        ]
        for skill_file in skills_to_check:
            content = skill_file.read_text(encoding="utf-8")
            links = re.findall(r"\[.*?\]\((?!https?://|#)(.*?)\)", content)
            for link in links:
                clean_link = link.split("#")[0]
                if clean_link:
                    target_path = (skill_file.parent / clean_link).resolve()
                    self.assertTrue(
                        target_path.exists(),
                        f"Broken relative link in {skill_file.name}: {link} -> {target_path}",
                    )


if __name__ == "__main__":
    unittest.main()
