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


def test_skill_frontmatter_and_metadata(skill_content):
    assert skill_content.startswith("---")
    assert "name: explain-diff" in skill_content
    # Description should mention topic and commit walkthrough capabilities
    assert re.search(r"description:.*topic", skill_content, re.IGNORECASE), "Description must mention topic support"
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


def test_root_commit_diff_command_safety(skill_content):
    # Root commits with empty tree must use two-argument git diff and avoid three-dot syntax
    assert 'git diff "<reference_commit_hash>" "<commit_hash>"' in skill_content, (
        "SKILL.md must provide two-argument git diff command for root commit empty tree"
    )
    assert "never use three-dot" in skill_content.lower() or "avoid three-dot" in skill_content.lower()


def test_katex_rendering(skill_content):
    # KaTeX inline math must use single backslash for <= to render properly
    assert r"$K \le 1$" in skill_content
    assert r"$K \\le 1$" not in skill_content


def test_tri_lens_navigation_menu_contract(skill_content):
    # Must specify tri-lens menu tokens: [t] topic-by-topic, [c] commit-by-commit, and [f] file-by-file
    assert "[t]" in skill_content, "Missing [t] Topic walkthrough option"
    assert "[c]" in skill_content, "Missing [c] Commit walkthrough option"
    assert "[f]" in skill_content, "Missing [f] File walkthrough option"
    content_lower = skill_content.lower()
    assert "topic-by-topic" in content_lower or "topic mode" in content_lower
    assert "commit-by-commit" in content_lower or "commit narrative" in content_lower
    assert "file-by-file" in content_lower or "cumulative" in content_lower
    # Navigation controls across flows
    assert "[a]" in skill_content  # walk all files
    assert "[s]" in skill_content  # expand summary
    assert "[q]" in skill_content  # finish


def test_topic_clustering_rules(skill_content):
    # Empty diff early exit with fail-closed error check
    assert "No differences detected" in skill_content, "Missing empty diff early exit message"
    assert "status 0" in skill_content or "exit status" in skill_content.lower()
    assert "error" in skill_content.lower()
    # Topic clustering size rules: 2-5 topics for multi-file, collapse for small changesets
    assert "2–5" in skill_content or "2-5" in skill_content, "Missing 2-5 topics guideline"
    assert "3 hunks" in skill_content or "3 total hunks" in skill_content or "<= 3" in skill_content or r"\le 3" in skill_content, "Missing small changeset collapse rule"
    # Deterministic dependency ordering
    assert "dependency" in skill_content.lower() or "data-flow" in skill_content.lower()
    # Coverage & reconciliation invariant
    assert "exactly one topic" in skill_content.lower(), "Missing requirement assigning each hunk to exactly one topic"
    assert "reconcile" in skill_content.lower(), "Missing stat reconciliation requirement"
    # Miscellaneous / Tooling topic for orphan changes
    assert "Miscellaneous" in skill_content or "Tooling" in skill_content, "Missing Miscellaneous/Tooling topic handling"
    # Large diff scaling via stat-first ingestion
    assert "temp_diff_stat.txt" in skill_content
    assert "temp_diff_paths.txt" in skill_content


def test_cross_file_synthesis_protocol(skill_content):
    # Topic narrative requirement
    assert "Topic Narrative" in skill_content, "Missing literal 'Topic Narrative' protocol header"
    # Tagged verbatim hunks with file headers matching convention [path:Lxx-Lyy]
    assert re.search(r"\[.+?:\s*L\d+-L?\d*\]", skill_content), "Missing literal file-header tag pattern [path:Lxx-Lyy]"
    # Binary file metadata tag and deleted file tag formats
    assert "[binary file:" in skill_content, "Missing literal '[binary file:' tag format"
    assert "[deleted file:" in skill_content, "Missing literal '[deleted file:' tag format"
    # Cross-file interaction commentary
    assert "Cross-File Interaction Commentary" in skill_content, "Missing literal 'Cross-File Interaction Commentary'"


def test_topic_drilldown_and_progression_tokens(skill_content):
    # Step 4e topic progression options: [n] next topic, [p] previous topic, [m] menu, [q] finish
    assert "[n]" in skill_content, "Missing [n] Next topic/commit option"
    assert "[p]" in skill_content, "Missing [p] Previous topic/commit option"
    assert "[m]" in skill_content, "Missing [m] Menu option in drilldown"
    assert "[q]" in skill_content, "Missing [q] Finish option"


def test_commit_walkthrough_protocol(skill_content):
    # Must document commit-specific walkthrough commands (git show <sha>) and message extraction
    assert "git show" in skill_content
    assert "temp_commit_msg.txt" in skill_content
    assert "temp_commit_stat.txt" in skill_content
    assert "temp_commit_diff.txt" in skill_content
    assert "[n]" in skill_content
    assert "[p]" in skill_content
    assert "[m]" in skill_content
    assert "[s]" in skill_content


def test_single_vs_multi_commit_branching(skill_content):
    # Must distinguish between single commit (K<=1) and multi-commit (K>1) flows deterministically
    content_lower = skill_content.lower()
    assert "single commit" in content_lower
    assert "multi-commit" in content_lower or "> 1" in skill_content or ">1" in skill_content
    assert "omit `[c]`" in skill_content or "omit [c]" in skill_content, "Deterministic rule omitting [c] for single commits missing"


def test_read_only_and_neutral_invariants(skill_content):
    # Must retain strict read-only and neutral non-adversarial requirements
    assert "Read-only" in skill_content or "read-only" in skill_content
    assert "Neutral" in skill_content or "neutral" in skill_content
    assert "view_file" in skill_content


def test_no_non_portable_file_links(skill_content, robustness_guide_content):
    # Prohibit non-portable file:// URLs in markdown files
    assert "file://" not in skill_content, "Non-portable file:// link found in SKILL.md"
    assert "file://" not in robustness_guide_content, "Non-portable file:// link found in robustness_guide.md"


def test_robustness_guide_topic_and_commit_safety(robustness_guide_content):
    # Preserves commit temporary file assertions while verifying topic clustering guidance
    assert "temp_commit_msg.txt" in robustness_guide_content, "Missing temp_commit_msg.txt in robustness guide"
    assert "temp_commits.txt" in robustness_guide_content, "Missing temp_commits.txt in robustness guide"
    assert "temp_diff_stat.txt" in robustness_guide_content, "Missing temp_diff_stat.txt in robustness guide"
    assert "temp_diff_paths.txt" in robustness_guide_content, "Missing temp_diff_paths.txt in robustness guide"
    content_lower = robustness_guide_content.lower()
    assert "commit" in content_lower
    assert "topic" in content_lower
    assert "scratch" in content_lower


def test_agents_md_sync(agents_content):
    # AGENTS.md must describe explain-diff with topic and commit-by-commit walkthrough capabilities
    explain_diff_lines = [line for line in agents_content.splitlines() if "[explain-diff/SKILL.md]" in line]
    assert explain_diff_lines, "explain-diff entry not found in AGENTS.md"
    line = explain_diff_lines[0]
    assert "topic-by-topic" in line or "topic" in line.lower(), f"Expected topic in AGENTS.md line: {line}"
    assert "commit-by-commit" in line, f"Expected strict 'commit-by-commit' in AGENTS.md line: {line}"


def test_readme_sync(readme_content):
    # README.md must describe explain-diff with topic-by-topic and tri-lens walkthrough options
    explain_diff_lines = [line for line in readme_content.splitlines() if "* `explain-diff`" in line]
    assert explain_diff_lines, "explain-diff entry not found in README.md"
    line = explain_diff_lines[0]
    assert "topic-by-topic" in line or "topic" in line.lower(), f"Expected topic walkthrough in README.md line: {line}"
    # Workflow paragraph must mention [t], [c], and [f]
    assert "`[t]`" in readme_content or "[t]" in readme_content
    assert "`[c]`" in readme_content or "[c]" in readme_content
    assert "`[f]`" in readme_content or "[f]" in readme_content
