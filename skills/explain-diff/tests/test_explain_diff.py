from pathlib import Path
import re
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SKILL_MD = REPO_ROOT / "skills" / "explain-diff" / "SKILL.md"
ROBUSTNESS_GUIDE = REPO_ROOT / "skills" / "explain-diff" / "resources" / "robustness_guide.md"
AGENTS_MD = REPO_ROOT / "AGENTS.md"


@pytest.fixture
def skill_content():
    assert SKILL_MD.exists(), f"SKILL.md not found at {SKILL_MD}"
    return SKILL_MD.read_text(encoding="utf-8")


@pytest.fixture
def robustness_guide_content():
    assert ROBUSTNESS_GUIDE.exists(), f"robustness_guide.md not found at {ROBUSTNESS_GUIDE}"
    return ROBUSTNESS_GUIDE.read_text(encoding="utf-8")


@pytest.fixture
def agents_content():
    assert AGENTS_MD.exists(), f"AGENTS.md not found at {AGENTS_MD}"
    return AGENTS_MD.read_text(encoding="utf-8")


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


def test_commit_mode_reference_hash(skill_content):
    # Single-commit mode defines reference hash as <sha>^ with root commit fallback
    assert "<sha>^" in skill_content
    assert "root" in skill_content.lower()
    assert "4b825dc642cb6eb9a060e54bf8d69288fbee4904" in skill_content
    assert "git show" in skill_content


def test_katex_rendering(skill_content):
    # KaTeX inline math must use single backslash for <= to render properly
    assert r"$K \le 1$" in skill_content
    assert r"$K \\le 1$" not in skill_content


def test_dual_lens_navigation_menu_contract(skill_content):
    # Must specify dual-lens menu tokens: [c] commit-by-commit and [f] file-by-file
    assert "[c]" in skill_content
    assert "[f]" in skill_content
    assert "commit-by-commit" in skill_content.lower() or "commit narrative" in skill_content.lower()
    assert "file-by-file" in skill_content.lower() or "cumulative" in skill_content.lower()
    # Navigation controls across flows
    assert "[a]" in skill_content  # walk all files
    assert "[s]" in skill_content  # expand summary
    assert "[q]" in skill_content  # finish


def test_commit_walkthrough_protocol(skill_content):
    # Must document commit-specific walkthrough commands (git show <sha>) and message extraction
    assert "git show" in skill_content
    assert "temp_commit_msg.txt" in skill_content
    assert "temp_commit_stat.txt" in skill_content
    assert "temp_commit_diff.txt" in skill_content
    # Intra-commit navigation tokens
    assert "[n]" in skill_content
    assert "[p]" in skill_content
    assert "[s]" in skill_content


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
    assert "temp_commit_msg.txt" in robustness_guide_content
    assert "temp_commits.txt" in robustness_guide_content
    assert "scratch" in content_lower


def test_agents_md_sync(agents_content):
    # AGENTS.md must describe explain-diff with commit walkthrough capabilities
    explain_diff_lines = [line for line in agents_content.splitlines() if "[explain-diff/SKILL.md]" in line]
    assert explain_diff_lines, "explain-diff entry not found in AGENTS.md"
    assert "commit-by-commit" in explain_diff_lines[0], f"Expected 'commit-by-commit' in line: {explain_diff_lines[0]}"
