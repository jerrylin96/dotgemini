"""Behavioral verification of scripts/sync_signoff_subtree.sh and subtree adoption state."""

import os
import shutil
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


def create_upstream_repo(
    repo_dir: str,
    skill_content: str = "---\nname: git-signoff\n---\n# git-signoff\n",
    conf_content: str = "conformance vector 1\n",
):
    """Initialize an upstream repo containing skills/git-signoff and conformance subtrees."""
    setup_fixture_repo(repo_dir)
    skill_dir = os.path.join(repo_dir, "skills/git-signoff")
    conf_dir = os.path.join(repo_dir, "conformance")
    os.makedirs(skill_dir, exist_ok=True)
    os.makedirs(conf_dir, exist_ok=True)
    with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(skill_content)
    with open(os.path.join(conf_dir, "vector.txt"), "w", encoding="utf-8") as f:
        f.write(conf_content)
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: add skill and conformance"], cwd=repo_dir, check=True, capture_output=True)


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
    assert "refusing to merge unrelated histories" in content, (
        "Script must strictly inspect unrelated-histories error before re-adopting"
    )

    # 4. Behavioral adoption in isolated fixture repos
    upstream_dir = str(tmp_path / "upstream")
    create_upstream_repo(upstream_dir)

    res_sync = subprocess.run(["bash", SYNC_SCRIPT, upstream_dir, "main"], cwd=downstream_dir, capture_output=True, text=True)
    assert res_sync.returncode == 0, f"Sync script failed: {res_sync.stderr}"
    assert os.path.isfile(os.path.join(downstream_dir, "skills/git-signoff/SKILL.md"))


def test_sync_subtree_repeat_sync(tmp_path):
    """Verify repeat sync succeeds cleanly when upstream has new commits."""
    downstream_dir = str(tmp_path / "downstream")
    upstream_dir = str(tmp_path / "upstream")
    setup_fixture_repo(downstream_dir)
    create_upstream_repo(upstream_dir)

    # Initial sync
    res1 = subprocess.run(["bash", SYNC_SCRIPT, upstream_dir, "main"], cwd=downstream_dir, capture_output=True, text=True)
    assert res1.returncode == 0, f"Initial sync failed: {res1.stderr}"

    # Upstream makes a second commit
    with open(os.path.join(upstream_dir, "skills/git-signoff/SKILL.md"), "a", encoding="utf-8") as f:
        f.write("\nUpdated in upstream\n")
    subprocess.run(["git", "add", "."], cwd=upstream_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: update skill"], cwd=upstream_dir, check=True, capture_output=True)

    # Repeat sync
    res2 = subprocess.run(["bash", SYNC_SCRIPT, upstream_dir, "main"], cwd=downstream_dir, capture_output=True, text=True)
    assert res2.returncode == 0, f"Repeat sync failed: {res2.stderr}\nstdout: {res2.stdout}"

    with open(os.path.join(downstream_dir, "skills/git-signoff/SKILL.md"), "r", encoding="utf-8") as f:
        downstream_content = f.read()
    assert "Updated in upstream" in downstream_content


def test_sync_subtree_unrelated_history_recovery(tmp_path):
    """Verify automatic fallback re-adoption succeeds when merge encounters unrelated histories."""
    downstream_dir = str(tmp_path / "downstream")
    upstream_dir = str(tmp_path / "upstream")
    setup_fixture_repo(downstream_dir)
    create_upstream_repo(upstream_dir)

    # Initial sync
    res1 = subprocess.run(["bash", SYNC_SCRIPT, upstream_dir, "main"], cwd=downstream_dir, capture_output=True, text=True)
    assert res1.returncode == 0, f"Initial sync failed: {res1.stderr}"

    # Upstream makes a new commit
    with open(os.path.join(upstream_dir, "skills/git-signoff/SKILL.md"), "a", encoding="utf-8") as f:
        f.write("\nupstream update\n")
    subprocess.run(["git", "add", "."], cwd=upstream_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "update"], cwd=upstream_dir, check=True, capture_output=True)

    # Simulate unrelated-history merge error during first subtree merge attempt
    bin_dir = str(tmp_path / "bin")
    os.makedirs(bin_dir, exist_ok=True)
    real_git = shutil.which("git")
    flag_file = str(tmp_path / "simulated_failure.flag")
    shim = os.path.join(bin_dir, "git")
    with open(shim, "w", encoding="utf-8") as f:
        f.write(f"""#!/usr/bin/env bash
if [ "$1" = "subtree" ] && [ "$2" = "merge" ] && [ ! -f "{flag_file}" ]; then
    touch "{flag_file}"
    echo "fatal: refusing to merge unrelated histories" >&2
    exit 1
fi
exec {real_git} "$@"
""")
    os.chmod(shim, 0o755)

    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}
    res2 = subprocess.run(["bash", SYNC_SCRIPT, upstream_dir, "main"], cwd=downstream_dir, capture_output=True, text=True, env=env)
    assert res2.returncode == 0, f"Recovery sync failed: {res2.stderr}\nstdout: {res2.stdout}"
    assert "Notice: squash merge failed with unrelated histories; re-adopting skills/git-signoff" in res2.stdout
    with open(os.path.join(downstream_dir, "skills/git-signoff/SKILL.md"), "r", encoding="utf-8") as f:
        downstream_content = f.read()
    assert "upstream update" in downstream_content


def test_sync_subtree_non_lineage_merge_failure(tmp_path):
    """Verify non-lineage merge failures do not trigger re-adoption and preserve diagnostics."""
    downstream_dir = str(tmp_path / "downstream")
    upstream_dir = str(tmp_path / "upstream")
    setup_fixture_repo(downstream_dir)
    create_upstream_repo(upstream_dir)

    # Initial sync
    res1 = subprocess.run(["bash", SYNC_SCRIPT, upstream_dir, "main"], cwd=downstream_dir, capture_output=True, text=True)
    assert res1.returncode == 0, f"Initial sync failed: {res1.stderr}"

    # Add commit to upstream
    with open(os.path.join(upstream_dir, "skills/git-signoff/SKILL.md"), "a", encoding="utf-8") as f:
        f.write("\nnew upstream change\n")
    subprocess.run(["git", "add", "."], cwd=upstream_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: new upstream change"], cwd=upstream_dir, check=True, capture_output=True)

    # Install rejecting commit-msg policy hook in downstream to simulate non-lineage failure
    hook_path = os.path.join(downstream_dir, ".git/hooks/commit-msg")
    os.makedirs(os.path.dirname(hook_path), exist_ok=True)
    with open(hook_path, "w", encoding="utf-8") as f:
        f.write("#!/bin/sh\necho 'policy hook rejected commit' >&2\nexit 1\n")
    os.chmod(hook_path, 0o755)

    # Sync should fail from hook without triggering unrelated history re-adoption
    res2 = subprocess.run(["bash", SYNC_SCRIPT, upstream_dir, "main"], cwd=downstream_dir, capture_output=True, text=True)
    assert res2.returncode != 0
    assert "Notice: squash merge failed with unrelated histories" not in res2.stdout
    assert "Notice: squash merge failed with unrelated histories" not in res2.stderr
    assert "policy hook rejected commit" in res2.stderr
    assert "error: subtree merge failed for skills/git-signoff" in res2.stderr


def test_sync_subtree_drift_enforcement(tmp_path):
    """Verify script loudly rejects local-only divergence (upstream_tree != local_tree)."""
    downstream_dir = str(tmp_path / "downstream")
    upstream_dir = str(tmp_path / "upstream")
    setup_fixture_repo(downstream_dir)
    create_upstream_repo(upstream_dir)

    # Initial sync
    res1 = subprocess.run(["bash", SYNC_SCRIPT, upstream_dir, "main"], cwd=downstream_dir, capture_output=True, text=True)
    assert res1.returncode == 0, f"Initial sync failed: {res1.stderr}"

    # Local modification inside skills/git-signoff in downstream
    with open(os.path.join(downstream_dir, "skills/git-signoff/local_untracked_drift.txt"), "w", encoding="utf-8") as f:
        f.write("local drift\n")
    subprocess.run(["git", "add", "."], cwd=downstream_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: local unauthorized divergence"], cwd=downstream_dir, check=True, capture_output=True)

    # Upstream makes a commit in conformance
    with open(os.path.join(upstream_dir, "conformance/vector.txt"), "a", encoding="utf-8") as f:
        f.write("upstream update\n")
    subprocess.run(["git", "add", "."], cwd=upstream_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: upstream update"], cwd=upstream_dir, check=True, capture_output=True)

    # Sync should fail with drift error
    res2 = subprocess.run(["bash", SYNC_SCRIPT, upstream_dir, "main"], cwd=downstream_dir, capture_output=True, text=True)
    assert res2.returncode != 0
    assert "diverges from upstream after sync" in res2.stderr
    assert "Vendored copies accept changes only via the git-signoff repo" in res2.stderr


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
