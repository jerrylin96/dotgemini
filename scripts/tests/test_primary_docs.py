"""Verify primary documentation (AGENTS.md, GEMINI.md, README.md) and relative links."""

import os
import re

WORKTREE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))


def test_primary_docs_consistency_and_links():
    agents_path = os.path.join(WORKTREE_ROOT, "AGENTS.md")
    gemini_path = os.path.join(WORKTREE_ROOT, "GEMINI.md")
    readme_path = os.path.join(WORKTREE_ROOT, "README.md")

    assert os.path.islink(gemini_path), "GEMINI.md must be a symbolic link"
    assert os.readlink(gemini_path) == "AGENTS.md", "GEMINI.md must point to AGENTS.md"

    with open(agents_path, "r", encoding="utf-8") as f:
        agents = f.read()
    with open(readme_path, "r", encoding="utf-8") as f:
        readme = f.read()

    # Obsolete bureaucratic skills and legacy /signoff alias must stay absent
    assert "make-feature" not in agents
    assert "make-feature" not in readme
    assert "`/signoff`" not in agents
    assert "`/signoff`" not in readme
    assert "[signoff/SKILL.md]" not in agents

    # Opt-in git-signoff remains discoverable
    assert "[git-signoff/SKILL.md](skills/git-signoff/SKILL.md)" in agents
    assert "`/git-signoff`" in readme
    assert "skills/git-signoff" in readme

    # Every relative markdown link in AGENTS.md and README.md must resolve on disk
    link_re = re.compile(r"\]\((?!https?://|#|mailto:)([^)#]+)(?:#[^)]*)?\)")
    for doc_name, doc_content in [("AGENTS.md", agents), ("README.md", readme)]:
        for rel_target in link_re.findall(doc_content):
            resolved = os.path.normpath(os.path.join(WORKTREE_ROOT, rel_target))
            assert os.path.exists(resolved), f"Broken link in {doc_name}: {rel_target} -> {resolved}"
