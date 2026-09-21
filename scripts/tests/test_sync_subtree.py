"""Behavioral verification of scripts/sync_signoff_subtree.sh and subtree adoption state."""

import os
import subprocess

WORKTREE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
SYNC_SCRIPT = os.path.join(WORKTREE_ROOT, "scripts/sync_signoff_subtree.sh")


def setup_fixture_repo(repo_dir: str):
    """Initialize a git repository with standard user credentials and initial commit."""
    os.makedirs(repo_dir, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True, capture_output=True)
    init_file = os.path.join(repo_dir, "README.md")
    with open(init_file, "w", encoding="utf-8") as f:
        f.write("# Fixture Repo\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True, capture_output=True)


def test_sync_subtree_script_behavior(tmp_path):
    """Verify scripts/sync_signoff_subtree.sh handles preconditions, adoption, and scoped fallback."""
    # 1. Clean worktree precondition check (executed in isolated fixture repo)
    downstream_dir = str(tmp_path / "downstream")
    setup_fixture_repo(downstream_dir)
    dirty_file = os.path.join(downstream_dir, "tmp_dirty_marker.txt")
    with open(dirty_file, "w") as f:
        f.write("dirty")
    res = subprocess.run(["bash", SYNC_SCRIPT], cwd=downstream_dir, capture_output=True, text=True)
    assert res.returncode != 0
    assert "error: working tree not clean" in res.stderr
    os.remove(dirty_file)

    # 2. Upstream URL assertion: verify script targets git-signoff
    with open(SYNC_SCRIPT, "r", encoding="utf-8") as f:
        content = f.read()
    assert "https://github.com/jerrylin96/git-signoff" in content, "Script must default to jerrylin96/git-signoff"
    assert "skills/git-signoff" in content, "Script must sync skills/git-signoff"
    assert "skills/signoff" not in content, "Script must not sync legacy skills/signoff"
    assert "signoff_mcp" not in content, "Script must not sync legacy signoff_mcp"

    # 3. Scoped unrelated-history fallback logic assertion
    assert "refusing to merge unrelated histories" in content or "unrelated" in content, (
        "Script must strictly inspect unrelated-histories error before re-adopting"
    )

    # 4. Behavioral adoption in isolated fixture repos
    upstream_dir = str(tmp_path / "upstream")
    setup_fixture_repo(upstream_dir)
    upstream_skill_dir = os.path.join(upstream_dir, "skills/git-signoff")
    upstream_conf_dir = os.path.join(upstream_dir, "conformance")
    os.makedirs(upstream_skill_dir, exist_ok=True)
    os.makedirs(upstream_conf_dir, exist_ok=True)
    with open(os.path.join(upstream_skill_dir, "SKILL.md"), "w") as f:
        f.write("---\nname: git-signoff\n---\n# git-signoff\n")
    with open(os.path.join(upstream_conf_dir, "vector.txt"), "w") as f:
        f.write("conformance vector 1\n")
    subprocess.run(["git", "add", "."], cwd=upstream_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: add skill and conformance"], cwd=upstream_dir, check=True, capture_output=True)

    res_sync = subprocess.run(["bash", SYNC_SCRIPT, upstream_dir, "main"], cwd=downstream_dir, capture_output=True, text=True)
    assert res_sync.returncode == 0, f"Sync script failed: {res_sync.stderr}"
    assert os.path.isfile(os.path.join(downstream_dir, "skills/git-signoff/SKILL.md"))


def test_subtree_adoption_state():
    """Verify that skills/git-signoff and conformance are adopted, and legacy paths removed."""
    # Must exist
    git_signoff_dir = os.path.join(WORKTREE_ROOT, "skills/git-signoff")
    skill_md = os.path.join(git_signoff_dir, "SKILL.md")
    attest_py = os.path.join(git_signoff_dir, "attest.py")
    conformance_dir = os.path.join(WORKTREE_ROOT, "conformance")
    claude_symlink = os.path.join(WORKTREE_ROOT, ".claude/skills/git-signoff")

    assert os.path.isdir(git_signoff_dir), "skills/git-signoff must exist"
    assert os.path.isfile(skill_md), "skills/git-signoff/SKILL.md must exist"
    assert os.path.isfile(attest_py), "skills/git-signoff/attest.py must exist"
    assert os.path.isdir(conformance_dir), "conformance/ must exist"
    assert os.path.isdir(os.path.join(conformance_dir, "vectors")), "conformance/vectors must exist"
    assert os.path.islink(claude_symlink), ".claude/skills/git-signoff must be a symlink"
    assert os.readlink(claude_symlink) == "../../skills/git-signoff"

    # Legacy paths must NOT be tracked
    res = subprocess.run(["git", "ls-files", "skills/signoff", "signoff_mcp", ".claude/skills/signoff"], cwd=WORKTREE_ROOT, capture_output=True, text=True, check=True)
    assert not res.stdout.strip(), f"Legacy files still tracked: {res.stdout}"
