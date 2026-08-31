from pathlib import Path
import re
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SKILL_MD = REPO_ROOT / "skills" / "explain-diff" / "SKILL.md"
ROBUSTNESS_GUIDE = REPO_ROOT / "skills" / "explain-diff" / "resources" / "robustness_guide.md"


@pytest.fixture
def skill_content():
    assert SKILL_MD.exists(), f"SKILL.md not found at {SKILL_MD}"
    return SKILL_MD.read_text(encoding="utf-8")


@pytest.fixture
def robustness_guide_content():
    assert ROBUSTNESS_GUIDE.exists(), f"robustness_guide.md not found at {ROBUSTNESS_GUIDE}"
    return ROBUSTNESS_GUIDE.read_text(encoding="utf-8")


def test_skill_frontmatter_and_metadata(skill_content):
    assert skill_content.startswith("---")
    assert "name: explain-diff" in skill_content
    # Description should mention commits or commit walkthrough
    assert re.search(r"description:.*commit", skill_content, re.IGNORECASE), "Description must mention commit support"


def test_commit_extraction_directives(skill_content):
    # Must specify git log with --no-merges --reverse for deterministic chronological extraction
    assert "git log" in skill_content
    assert "--no-merges" in skill_content
    assert "--reverse" in skill_content
    assert "temp_commits.txt" in skill_content


def test_dual_lens_navigation_menu_contract(skill_content):
    # Must specify dual-lens menu tokens: [c] commit-by-commit and [f] file-by-file
    assert "[c]" in skill_content
    assert "[f]" in skill_content
    assert "commit-by-commit" in skill_content.lower() or "commit narrative" in skill_content.lower()
    assert "file-by-file" in skill_content.lower() or "cumulative" in skill_content.lower()


def test_commit_walkthrough_protocol(skill_content):
    # Must document commit-specific walkthrough commands (git show <sha>)
    assert "git show" in skill_content
    assert "temp_commit_stat.txt" in skill_content
    assert "temp_commit_diff.txt" in skill_content
    # Intra-commit navigation tokens
    assert "[n]" in skill_content or "Next commit" in skill_content


def test_single_vs_multi_commit_branching(skill_content):
    # Must distinguish between single commit (K=1) and multi-commit (K>1) flows
    content_lower = skill_content.lower()
    assert "single commit" in content_lower
    assert "multi-commit" in content_lower or "> 1" in skill_content or ">1" in skill_content


def test_read_only_and_neutral_invariants(skill_content):
    # Must retain strict read-only and neutral non-adversarial requirements
    assert "Read-only" in skill_content or "read-only" in skill_content
    assert "Neutral" in skill_content or "neutral" in skill_content
    assert "view_file" in skill_content


def test_robustness_guide_commit_safety(robustness_guide_content):
    # Robustness guide should include guidance on commit diff extraction safety
    content_lower = robustness_guide_content.lower()
    assert "commit" in content_lower
    assert "scratch" in content_lower
