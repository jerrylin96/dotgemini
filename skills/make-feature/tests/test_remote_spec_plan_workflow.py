import re
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
MAKE_FEATURE_PATH = REPO_ROOT / "skills" / "make-feature" / "SKILL.md"
SPEC_SKILL_PATH = REPO_ROOT / "skills" / "spec-driven-development" / "SKILL.md"
PLAN_SKILL_PATH = REPO_ROOT / "skills" / "planning-and-task-breakdown" / "SKILL.md"
AGENTS_MD_PATH = REPO_ROOT / "AGENTS.md"


def test_make_feature_skill_lifecycle():
    content = MAKE_FEATURE_PATH.read_text(encoding="utf-8")

    # 1. Deterministic 6-char hex derivation
    assert "tr -dc 'a-f0-9' < /dev/urandom | head -c 6" in content, (
        "make-feature/SKILL.md must specify 6-character hex hash derivation"
    )

    # 2. Remote check and fallback
    assert "git remote get-url origin" in content, (
        "make-feature/SKILL.md must include remote pre-flight check"
    )
    assert "REMOTE_ENABLED" in content, (
        "make-feature/SKILL.md must define REMOTE_ENABLED flag"
    )

    # 3. Early worktree initialization in Phase 1a
    phase1a_match = re.search(r"Phase 1a.*?Phase 1b", content, re.DOTALL)
    assert phase1a_match is not None, "Phase 1a section missing"
    assert "git worktree add" in phase1a_match.group(0), (
        "make-feature/SKILL.md must relocate worktree creation to Phase 1a"
    )

    # 4. In-tree spec and plan commits and pushes
    assert "spec.md" in content and "spec: add initial feature spec for external review" in content, (
        "make-feature/SKILL.md must include in-tree spec commit message"
    )
    assert "plan.md" in content and "plan: add implementation plan for external review" in content, (
        "make-feature/SKILL.md must include in-tree plan commit message"
    )

    # 5. Step 2b & 3b revision push sync
    assert "spec: address review feedback" in content, (
        "make-feature/SKILL.md must include Step 2b revision commit message"
    )
    assert "plan: address review feedback" in content, (
        "make-feature/SKILL.md must include Step 3b revision commit message"
    )

    # 6. Early abort teardown routines for Step 2c and 3c
    assert "git branch -D" in content, "make-feature/SKILL.md must include branch deletion in abort routine"
    assert "git push origin --delete" in content, (
        "make-feature/SKILL.md must include remote branch deletion in abort teardown routine"
    )

    # 7. Phase 2 Step 4: Redundant git worktree add removed from Phase 2 Step 4
    phase2_match = re.search(r"Phase 2.*?Phase 3", content, re.DOTALL)
    assert phase2_match is not None, "Phase 2 section not found"
    phase2_text = phase2_match.group(0)
    assert "git worktree add" not in phase2_text, (
        "Phase 2 Step 4 must not contain redundant 'git worktree add'"
    )

    # 8. Step 4d RED test remote push gate
    assert "test: add RED test suite (failing)" in phase2_text, (
        "make-feature/SKILL.md Phase 2 must define Step 4d RED test remote push gate"
    )

    # 9. Step 5 GREEN implementation commit
    assert "feat: implement feature to make tests pass (GREEN)" in phase2_text, (
        "make-feature/SKILL.md Phase 2 must define Step 5 GREEN commit message"
    )

    # 10. Heavy Mode per-slice 2-stage commit cadence
    assert "test(slice-N): add RED test suite (failing)" in content, (
        "make-feature/SKILL.md must specify Heavy Mode slice RED commit format"
    )
    assert "feat(slice-N): implement slice N (GREEN)" in content, (
        "make-feature/SKILL.md must specify Heavy Mode slice GREEN commit format"
    )

    # 11. Idempotent Step 7c cleanup with --ignore-unmatch in Phase 3
    phase3_match = re.search(r"Phase 3.*?Phase 4", content, re.DOTALL)
    assert phase3_match is not None, "Phase 3 section not found"
    phase3_text = phase3_match.group(0)
    assert "git rm -rf --ignore-unmatch" in phase3_text, (
        "make-feature/SKILL.md Phase 3 must specify idempotent cleanup with --ignore-unmatch"
    )
    assert "chore: remove ephemeral spec and plan before signoff" in phase3_text, (
        "make-feature/SKILL.md Phase 3 must specify cleanup commit message"
    )

    # 12. Ephemeral review report rule (prohibiting Obsidian)
    assert "Obsidian" in phase3_text and ("Do NOT write" in phase3_text or "prohibit" in phase3_text.lower()), (
        "make-feature/SKILL.md Phase 3 must forbid saving review reports to Obsidian"
    )


def test_spec_and_plan_skills():
    spec_content = SPEC_SKILL_PATH.read_text(encoding="utf-8")
    plan_content = PLAN_SKILL_PATH.read_text(encoding="utf-8")

    # Spec skill must document in-tree spec path (${FEATURE_SLUG}/spec.md) and superseding /artifact & Obsidian
    assert "${FEATURE_SLUG}/spec.md" in spec_content or "<feature-name>-<hash>/spec.md" in spec_content, (
        "spec skill must explicitly reference in-tree spec.md path under ${FEATURE_SLUG}"
    )
    assert "supersedes" in spec_content.lower(), (
        "spec skill must explicitly state in-tree spec supersedes Obsidian/artifact paths"
    )

    # Plan skill must document in-tree plan path (${FEATURE_SLUG}/plan.md) and superseding /artifact & Obsidian
    assert "${FEATURE_SLUG}/plan.md" in plan_content or "<feature-name>-<hash>/plan.md" in plan_content, (
        "plan skill must explicitly reference in-tree plan.md path under ${FEATURE_SLUG}"
    )
    assert "supersedes" in plan_content.lower(), (
        "plan skill must explicitly state in-tree plan supersedes Obsidian/artifact paths"
    )
    assert "Heavy Mode" in plan_content and "test(slice-N)" in plan_content and "feat(slice-N)" in plan_content, (
        "plan skill must document Heavy Mode per-slice 2-stage commit cadence (test(slice-N) and feat(slice-N))"
    )


def test_agents_guide_rules():
    content = AGENTS_MD_PATH.read_text(encoding="utf-8")

    # §3 Milestone Phase Goals updates
    sec3_match = re.search(r"## 3\.\s*Slash Commands.*?(?=## 4|\Z)", content, re.DOTALL)
    assert sec3_match is not None, "AGENTS.md must contain §3 Slash Commands & Lifecycle Discipline"
    sec3_text = sec3_match.group(0)
    assert "test: add RED test suite (failing)" in sec3_text, (
        "AGENTS.md §3 must mention RED test remote push gate"
    )
    assert "remove ephemeral" in sec3_text.lower() or "--ignore-unmatch" in sec3_text, (
        "AGENTS.md §3 must mention ephemeral cleanup"
    )

    # §9 Ephemerality and Obsidian boundaries
    sec9_match = re.search(r"## 9\.\s*User-Facing Artifacts.*?(?=## 10|\Z)", content, re.DOTALL)
    assert sec9_match is not None, "AGENTS.md must contain §9 User-Facing Artifacts"
    sec9_text = sec9_match.group(0)
    assert "ephemeral" in sec9_text.lower(), "AGENTS.md §9 must define feature artifact ephemerality"
    assert "review_report" in sec9_text or "review report" in sec9_text.lower(), (
        "AGENTS.md §9 must explicitly mention review reports"
    )
    assert "Obsidian" in sec9_text, "AGENTS.md §9 must enforce Obsidian boundaries"


def test_markdown_links_valid():
    skills_to_check = [MAKE_FEATURE_PATH, SPEC_SKILL_PATH, PLAN_SKILL_PATH]
    for skill_file in skills_to_check:
        content = skill_file.read_text(encoding="utf-8")
        links = re.findall(r"\[.*?\]\((?!https?://|#)(.*?)\)", content)
        for link in links:
            clean_link = link.split("#")[0]
            if clean_link:
                target_path = (skill_file.parent / clean_link).resolve()
                assert target_path.exists(), f"Broken relative link in {skill_file.name}: {link} -> {target_path}"
