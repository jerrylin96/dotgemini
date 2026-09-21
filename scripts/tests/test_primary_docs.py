"""Verify primary documentation and lifecycle guides reference /git-signoff."""

import os

WORKTREE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))


def test_primary_docs_reference_git_signoff():
    agents_path = os.path.join(WORKTREE_ROOT, "AGENTS.md")
    readme_path = os.path.join(WORKTREE_ROOT, "README.md")
    make_feature_path = os.path.join(WORKTREE_ROOT, "skills/make-feature/SKILL.md")
    lifecycle_guide_path = os.path.join(WORKTREE_ROOT, "skills/make-feature/resources/lifecycle-guide.md")

    with open(agents_path, "r", encoding="utf-8") as f:
        agents = f.read()
    with open(readme_path, "r", encoding="utf-8") as f:
        readme = f.read()
    with open(make_feature_path, "r", encoding="utf-8") as f:
        mf = f.read()
    with open(lifecycle_guide_path, "r", encoding="utf-8") as f:
        lg = f.read()

    # 1. AGENTS.md
    assert "| **Ship** | `/git-signoff` | Human owns the merge | [git-signoff](skills/git-signoff/SKILL.md) |" in agents
    assert "| **Ship** | `/signoff` |" not in agents
    assert "[git-signoff/SKILL.md](skills/git-signoff/SKILL.md)" in agents
    assert "[signoff/SKILL.md](skills/signoff/SKILL.md)" not in agents

    # 2. README.md
    assert "`/git-signoff`" in readme
    assert "skills/git-signoff" in readme
    assert "`/signoff`" not in readme

    # 3. make-feature
    assert "[/git-signoff](../git-signoff/SKILL.md)" in mf
    assert "[/signoff](../signoff/SKILL.md)" not in mf
    assert "[git-signoff](../../git-signoff/SKILL.md)" in lg
    assert "[signoff](../../signoff/SKILL.md)" not in lg
