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


def test_root_commit_cross_reference_corrected(skill_content):
    # Root-commit guidance must reference steps 1c-1f and 6b to include path enumeration
    assert re.search(r"steps?\s+1c[–-]1f,\s*6b", skill_content), (
        "SKILL.md must reference 'steps 1c–1f, 6b' for root-commit empty-tree direct diff commands"
    )


def test_root_commit_diff_command_safety(skill_content):
    # Root commits with empty tree must use two-argument git diff and avoid three-dot syntax
    assert 'git diff "<reference_commit_hash>" "<commit_hash>"' in skill_content, (
        "SKILL.md must provide two-argument git diff command for root commit empty tree"
    )
    assert "never use three-dot" in skill_content.lower() or "avoid three-dot" in skill_content.lower()
    # Verify root two-argument variants exist across all command types:
    # 1. stats
    assert 'git diff "<reference_commit_hash>" "<commit_hash>" --stat --find-renames --find-copies' in skill_content
    # 2. numstat line totals
    assert 'git diff "<reference_commit_hash>" "<commit_hash>" --numstat -z --find-renames --find-copies' in skill_content
    # 3. complete diff
    assert 'git diff "<reference_commit_hash>" "<commit_hash>" --find-renames --find-copies >' in skill_content
    # 4. path enumeration
    assert 'git diff "<reference_commit_hash>" "<commit_hash>" --name-status -z --find-renames --find-copies' in skill_content
    # 5. per-file diff
    assert 'git diff "<reference_commit_hash>" "<commit_hash>" --find-renames --find-copies -- "<file>"' in skill_content


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


def test_topic_count_definition_and_menu_unique_files(skill_content):
    # T must be defined as total number of topics (1 <= T <= 6)
    content_lower = skill_content.lower()
    assert "total number of topics" in content_lower or "topic count" in content_lower or "count of topics" in content_lower
    assert "$1 \\le T \\le 6$" in skill_content or "1 <= T <= 6" in skill_content or "$T=6$" in skill_content
    # Menu example must explicitly distinguish unique files (U) without embedding raw KaTeX inside text code fence
    assert "Summary: 3 topics across 6 unique files (+112 / -28)" in skill_content
    assert "($T=3$)" not in skill_content, "KaTeX math syntax should not be embedded inside text code fences"
    assert "$U$" in skill_content, "Notation $U$ should be explained in prose where math renders"


def test_consistent_rename_copy_detection_flags(skill_content, robustness_guide_content):
    # Explicit rename and copy flags must be specified consistently across all diff artifact commands
    assert "--stat --find-renames --find-copies" in skill_content
    assert "--numstat -z --find-renames --find-copies" in skill_content
    assert "--name-status -z --find-renames --find-copies" in skill_content
    assert "--find-renames --find-copies >" in skill_content
    assert "--find-renames --find-copies --" in skill_content
    # Robustness guide must document explicit flags to avoid git config divergence and explain exclusion of --find-copies-harder
    assert "--find-renames" in robustness_guide_content
    assert "--find-copies" in robustness_guide_content
    assert "--find-copies-harder" in robustness_guide_content
    assert "performance" in robustness_guide_content.lower() or "cost" in robustness_guide_content.lower()
    # Path-limited diff representation explanation
    assert "path-limited" in skill_content.lower() or "outside the pathspec" in skill_content.lower()
    assert "path-limited" in robustness_guide_content.lower() or "outside the pathspec" in robustness_guide_content.lower()


def test_nul_stream_workflow_and_optional_paths(skill_content, robustness_guide_content):
    # Direct agent to parse NUL streams as raw bytes, NOT line-oriented view_file
    content_lower = skill_content.lower()
    assert "not pass nul" in content_lower or "not pipe nul" in content_lower or "raw bytes" in content_lower
    assert "raw bytes" in content_lower
    assert "optional" in content_lower and "temp_diff_paths.txt" in skill_content
    assert "only be read when generated" in content_lower or "only read when generated" in content_lower
    # Robustness guide specifies NUL parsing contract
    guide_lower = robustness_guide_content.lower()
    assert "read_bytes().split(b'\\0')" in robustness_guide_content or "split(b'\\0')" in robustness_guide_content
    assert "never pass nul" in guide_lower or "not pass nul" in guide_lower
    # C record parser handling in NUL stream
    assert "c<score>" in guide_lower or "c090" in guide_lower or "copy" in guide_lower


def test_deterministic_submodule_symlink_typechange_accounting(skill_content, robustness_guide_content):
    # Submodules, symlinks, and typechanges must follow deterministic numstat line math or metadata tags
    content_lower = skill_content.lower()
    assert "submodule" in content_lower
    assert "symlink" in content_lower
    assert "typechange" in content_lower
    assert "temp_diff_numstat.txt" in content_lower
    assert "strictly follow" in content_lower or "follow" in content_lower
    assert "metadata" in content_lower
    # Tab alignment on numstat binary rows
    assert r"-\t-\t<path>" in skill_content or r"-\t-\t" in skill_content
    assert r"-\t-\t<path>" in robustness_guide_content or r"-\t-\t" in robustness_guide_content


def test_robustness_guide_root_commit_caveat(robustness_guide_content):
    # Robustness guide Commit Range Caveat must document the root-commit exception
    guide_lower = robustness_guide_content.lower()
    assert "commit range caveat" in guide_lower
    assert "root-commit exception" in guide_lower or "root" in guide_lower
    assert "4b825dc642cb6eb9a060e54bf8d69288fbee4904" in robustness_guide_content


def test_fail_closed_artifact_exit_status_checks(skill_content):
    # Every generated artifact must be verified for exit code 0; fail closed if any command fails
    assert "temp_diff_stat.txt" in skill_content
    assert "temp_diff_numstat.txt" in skill_content
    assert "temp_diff_all.txt" in skill_content
    assert "temp_diff_paths.txt" in skill_content
    content_lower = skill_content.lower()
    assert "exit status" in content_lower or "status 0" in content_lower
    assert "fail-closed" in content_lower or "fail closed" in content_lower or "never treat command errors as empty diffs" in content_lower
    assert "do not attempt to read partial" in content_lower or "do not perform reconciliation" in content_lower or "never treat" in content_lower


def test_changed_file_accounting_and_rename_semantics(skill_content, robustness_guide_content):
    content_lower = skill_content.lower()
    guide_lower = robustness_guide_content.lower()
    # Changed-file entity count U vs membership count M
    assert "unique changed-file" in content_lower or "unique changed-file entity count" in content_lower
    assert "file-topic membership count" in content_lower
    assert "m >= u" in content_lower or r"m \ge u" in content_lower or "m ≥ u" in content_lower or "membership" in content_lower
    # Renames count as 1 entity in U
    assert "pure rename" in content_lower or "rename" in content_lower
    assert "1 changed-file entity" in content_lower or "1 changed-file record" in guide_lower or "1 changed file" in guide_lower
    # Copies, submodules, and symlinks accounted for
    assert "copy" in content_lower
    assert "submodule" in content_lower
    assert "symlink" in content_lower or "typechange" in content_lower
    # Reconciliation against git diff --stat
    assert "git diff --stat" in content_lower
    assert "reconcile" in content_lower


def test_topic_clustering_rules(skill_content):
    # Empty diff early exit
    assert "No differences detected" in skill_content, "Missing empty diff early exit message"
    # Topic clustering size rules: 2-5 functional topics, optional Miscellaneous/Tooling (up to 6)
    assert "2–5" in skill_content or "2-5" in skill_content, "Missing 2-5 topics guideline"
    assert "Miscellaneous" in skill_content or "Tooling" in skill_content, "Missing Miscellaneous/Tooling topic handling"
    assert "maximum of 6" in skill_content or "max 6" in skill_content or "6 topics total" in skill_content or "t=6" in skill_content.lower()
    # Small changeset or single cohesive concern collapse
    assert "3 hunks" in skill_content or "3 total hunks" in skill_content or "<= 3" in skill_content or r"\le 3" in skill_content
    assert "cohesive concern" in skill_content.lower() or "single cohesive concern" in skill_content.lower()
    # Deterministic dependency ordering and stable tie-breaker
    assert "dependency" in skill_content.lower() or "data-flow" in skill_content.lower()
    assert "tie-breaker" in skill_content.lower()
    assert "alphabetical" in skill_content.lower()
    assert "lexical order" in skill_content.lower() or "posix" in skill_content.lower()
    # Coverage & reconciliation invariant distinguishing unique files vs membership, hunks, lines
    content_lower = skill_content.lower()
    assert "exactly one topic" in content_lower, "Missing requirement assigning each hunk to exactly one topic"
    assert "reconcile" in content_lower, "Missing stat reconciliation requirement"
    assert "temp_diff_numstat.txt" in skill_content
    assert "temp_diff_all.txt" in skill_content
    assert "temp_diff_stat.txt" in skill_content
    assert "temp_diff_paths.txt" in skill_content
    # Binary, deletion, rename & mode handling
    assert "binary file:" in content_lower
    assert "binary deletion" in content_lower
    assert "mode change" in content_lower
    assert "rename" in content_lower


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
    assert "temp_diff_numstat.txt" in robustness_guide_content, "Missing temp_diff_numstat.txt in robustness guide"
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
    # Single-commit [c] caveat
    assert "multi-commit" in readme_content and "single-commit" in readme_content, "Missing README single-commit [c] caveat"
