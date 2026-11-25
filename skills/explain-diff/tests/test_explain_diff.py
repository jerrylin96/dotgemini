from pathlib import Path
import re
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SKILL_MD = REPO_ROOT / "skills" / "explain-diff" / "SKILL.md"
ROBUSTNESS_GUIDE = REPO_ROOT / "skills" / "explain-diff" / "resources" / "robustness_guide.md"
AGENTS_MD = REPO_ROOT / "AGENTS.md"
README_MD = REPO_ROOT / "README.md"


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


@pytest.fixture
def readme_content():
    assert README_MD.exists(), f"README.md not found at {README_MD}"
    return README_MD.read_text(encoding="utf-8")


def test_skill_frontmatter_and_core_invariants(skill_content):
    assert skill_content.startswith("---")
    assert "name: explain-diff" in skill_content
    assert re.search(r"description:.*topic", skill_content, re.IGNORECASE)
    assert re.search(r"description:.*commit", skill_content, re.IGNORECASE)
    assert "read-only" in skill_content.lower()
    assert "neutral" in skill_content.lower()
    assert "view_file" in skill_content


def test_context_resolution_and_root_commit_safety(skill_content, robustness_guide_content):
    assert "<sha>^" in skill_content
    assert "4b825dc642cb6eb9a060e54bf8d69288fbee4904" in skill_content
    assert "4b825dc642cb6eb9a060e54bf8d69288fbee4904" in robustness_guide_content
    assert 'git diff "<empty-tree>"' in skill_content
    assert "never three-dot" in skill_content.lower()
    assert "resolve_branches.py" in skill_content


def test_scratch_diff_and_grounded_hunks(skill_content, robustness_guide_content):
    assert "git log --no-merges --reverse" in skill_content
    assert "--find-renames --find-copies" in skill_content
    assert "--find-copies-harder" in robustness_guide_content
    assert "temp_commits.txt" in skill_content
    assert "temp_diff_stat.txt" in skill_content
    assert "temp_diff_all.txt" in skill_content
    assert "temp_topic_diff.txt" in skill_content
    assert "temp_commit_diff.txt" in skill_content
    assert "python3 -c" in skill_content
    assert "No differences detected" in skill_content
    assert "Truncation Handling & Grounded Quotation Invariants" in robustness_guide_content


def test_tri_lens_navigation_and_walkthrough_flows(skill_content):
    for token in ["[t]", "[f]", "[c]", "[n]", "[p]", "[m]", "[s]", "[q]", "[a]"]:
        assert token in skill_content
    assert r"$K \le 1$" in skill_content
    assert "omit `[c]`" in skill_content
    assert "Topic Narrative" in skill_content
    assert "Cross-File Interaction Commentary" in skill_content
    assert re.search(r"\[.+?:\s*L\w+-L\w+\]", skill_content)


def test_no_non_portable_file_links(skill_content, robustness_guide_content):
    assert "file://" not in skill_content
    assert "file://" not in robustness_guide_content


def test_agents_and_readme_sync(agents_content, readme_content):
    explain_lines = [line for line in agents_content.splitlines() if "[explain-diff/SKILL.md]" in line]
    assert explain_lines
    assert "topic-by-topic" in explain_lines[0]
    assert "commit-by-commit" in explain_lines[0]

    readme_lines = [line for line in readme_content.splitlines() if "* `explain-diff`" in line]
    assert readme_lines
    assert "topic-by-topic" in readme_lines[0]
    for token in ["[t]", "[c]", "[f]", "multi-commit", "single-commit"]:
        assert token in readme_content


def test_truncation_circuit_breaker_in_agents_md(agents_content):
    assert "Truncation Circuit Breaker" in agents_content
    for marker in ["<truncated", "observation too long", "stdout_truncated", "view_file", "byte-for-byte"]:
        assert marker in agents_content
    content_lower = agents_content.lower()
    assert "unviewed" in content_lower
    assert "paraphras" in content_lower or "guess" in content_lower
