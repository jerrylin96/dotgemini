import os
import subprocess

try:
    import yaml
except ImportError:
    yaml = None


WORKFLOW_PATH = os.path.join(os.path.dirname(__file__), "..", "..", ".github", "workflows", "signoff.yml")


def get_verification_script() -> str:
    """Extract the Verify Git Signoff Attestation script directly from signoff.yml."""
    if os.path.exists(WORKFLOW_PATH) and yaml is not None:
        try:
            with open(WORKFLOW_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            steps = data.get("jobs", {}).get("verify-signoff", {}).get("steps", [])
            for step in steps:
                if step.get("name") == "Verify Git Signoff Attestation":
                    script = step.get("run", "")
                    if script:
                        return script
        except Exception:
            pass

    # Fallback un-indent parsing
    with open(WORKFLOW_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    script_lines = []
    recording = False
    base_indent = None

    for line in lines:
        if "Verify Git Signoff Attestation" in line:
            recording = True
            continue
        if recording:
            if base_indent is None:
                if line.strip().startswith("run:"):
                    continue
                if line.strip():
                    base_indent = len(line) - len(line.lstrip())

            if base_indent is not None:
                if line.strip() and (len(line) - len(line.lstrip())) < base_indent:
                    break
                script_lines.append(line[base_indent:] if len(line) >= base_indent else line)

    if not script_lines:
        raise RuntimeError("Verify Git Signoff Attestation step not found in workflow")

    return "".join(script_lines)


def test_workflow_yaml_structure():
    """Verify that .github/workflows/signoff.yml exists and adheres to hardened Spec schema."""
    assert os.path.exists(WORKFLOW_PATH), f"Workflow file does not exist at {WORKFLOW_PATH}"
    
    with open(WORKFLOW_PATH, "r", encoding="utf-8") as f:
        content = f.read()
        
    assert "name: Signoff Verification Gate" in content
    assert "pull_request:" in content
    assert "ready_for_review" in content
    assert "permissions:" in content
    assert "contents: read" in content
    assert "concurrency:" in content
    assert "actions/checkout@" in content
    assert "ref: ${{ github.event.pull_request.head.sha }}" in content
    assert "fetch-depth: 0" in content
    assert "persist-credentials: false" in content
    assert "cat_sort_uniq" in content
    assert "refs/notes/signoff" in content

    # Yaml integrity assertion
    script = get_verification_script()
    assert "HEAD_TREE" in script
    assert "validate_payload" in script


def setup_git_repo(repo_dir: str) -> None:
    """Initialize an isolated test git repository with standard configuration."""
    env = os.environ.copy()
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True, env=env)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, check=True, env=env)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True, env=env)


def run_verification_in_repo(repo_dir: str) -> subprocess.CompletedProcess:
    """Helper to run the verification shell script inside a test git repository."""
    env = os.environ.copy()
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return subprocess.run(
        ["bash", "-c", get_verification_script()],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        env=env
    )


def test_unattested_commit_fails(tmp_path):
    """Verify that an un-attested commit causes verification to output ::error:: and exit 1."""
    repo = str(tmp_path)
    setup_git_repo(repo)
    
    subprocess.run(["git", "commit", "--allow-empty", "-m", "Un-attested commit"], cwd=repo, check=True)
    
    res = run_verification_in_repo(repo)
    assert res.returncode == 1
    assert "::error::Missing, incomplete, or mismatched Git Signoff Attestation" in res.stdout or "::error::Missing, incomplete, or mismatched Git Signoff Attestation" in res.stderr


def test_status_only_trailer_fails(tmp_path):
    """Verify that a status-only trailer without Spec-Version and Tree-SHA fails verification."""
    repo = str(tmp_path)
    setup_git_repo(repo)
    
    msg = "Status only commit\n\nSignoff-Status: VERIFIED_BY_HUMAN"
    subprocess.run(["git", "commit", "--allow-empty", "-m", msg], cwd=repo, check=True)
    
    res = run_verification_in_repo(repo)
    assert res.returncode == 1
    assert "::error::Missing, incomplete, or mismatched" in res.stdout or "::error::Missing, incomplete, or mismatched" in res.stderr


def test_valid_gsa_commit_trailer_passes(tmp_path):
    """Verify that a commit with complete structured GSA payload exits 0 cleanly."""
    repo = str(tmp_path)
    setup_git_repo(repo)
    
    # Create reviewed commit
    subprocess.run(["git", "commit", "--allow-empty", "-m", "Substantive change"], cwd=repo, check=True)
    rev_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    rev_tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    
    msg = (
        f"[SIGNOFF {rev_commit[:7]}]: human comprehension and risk attestation\n\n"
        f"Signoff-Spec-Version: 1.0\n"
        f"Signoff-Status: VERIFIED_BY_HUMAN\n"
        f"Signoff-Reviewed-Commit-SHA: {rev_commit}\n"
        f"Signoff-Reviewed-Tree-SHA: {rev_tree}\n"
        f"Signoff-Verified-By: test@example.com"
    )
    subprocess.run(["git", "commit", "--allow-empty", "-m", msg], cwd=repo, check=True)
    
    res = run_verification_in_repo(repo)
    assert res.returncode == 0
    assert "verified via commit trailer payload" in res.stdout.lower()


def test_valid_gsa_commit_trailer_no_digest_passes(tmp_path):
    """Verify complete GSA payload with VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST passes."""
    repo = str(tmp_path)
    setup_git_repo(repo)
    
    subprocess.run(["git", "commit", "--allow-empty", "-m", "Substantive change"], cwd=repo, check=True)
    rev_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    rev_tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    
    msg = (
        f"[SIGNOFF {rev_commit[:7]}]: human comprehension attestation\n\n"
        f"Signoff-Spec-Version: 1.0\n"
        f"Signoff-Status: VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST\n"
        f"Signoff-Reviewed-Commit-SHA: {rev_commit}\n"
        f"Signoff-Reviewed-Tree-SHA: {rev_tree}\n"
        f"Signoff-Verified-By: test@example.com"
    )
    subprocess.run(["git", "commit", "--allow-empty", "-m", msg], cwd=repo, check=True)
    
    res = run_verification_in_repo(repo)
    assert res.returncode == 0
    assert "verified via commit trailer payload" in res.stdout.lower()


def test_commit_trailer_prefix_bypass_fails(tmp_path):
    """Verify that a commit with a fake status prefix (VERIFIED_BY_HUMAN_FAKE) fails with exit 1."""
    repo = str(tmp_path)
    setup_git_repo(repo)
    
    subprocess.run(["git", "commit", "--allow-empty", "-m", "Base commit"], cwd=repo, check=True)
    rev_tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    msg = f"Bypass commit\n\nSignoff-Spec-Version: 1.0\nSignoff-Status: VERIFIED_BY_HUMAN_FAKE\nSignoff-Reviewed-Tree-SHA: {rev_tree}"
    subprocess.run(["git", "commit", "--allow-empty", "-m", msg], cwd=repo, check=True)
    
    res = run_verification_in_repo(repo)
    assert res.returncode == 1
    assert "::error::Missing, incomplete, or mismatched" in res.stdout or "::error::Missing, incomplete, or mismatched" in res.stderr


def test_commit_trailer_rejected_fails(tmp_path):
    """Verify that a commit trailer with Signoff-Status: REJECTED fails verification."""
    repo = str(tmp_path)
    setup_git_repo(repo)
    
    subprocess.run(["git", "commit", "--allow-empty", "-m", "Base commit"], cwd=repo, check=True)
    rev_tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    msg = f"Rejected commit\n\nSignoff-Spec-Version: 1.0\nSignoff-Status: REJECTED\nSignoff-Reviewed-Tree-SHA: {rev_tree}"
    subprocess.run(["git", "commit", "--allow-empty", "-m", msg], cwd=repo, check=True)
    
    res = run_verification_in_repo(repo)
    assert res.returncode == 1
    assert "::error::Missing, incomplete, or mismatched" in res.stdout or "::error::Missing, incomplete, or mismatched" in res.stderr


def test_commit_trailer_mismatched_tree_fails(tmp_path):
    """Verify that a commit trailer referencing a mismatched tree SHA fails verification."""
    repo = str(tmp_path)
    setup_git_repo(repo)
    
    msg = "Mismatched tree commit\n\nSignoff-Spec-Version: 1.0\nSignoff-Status: VERIFIED_BY_HUMAN\nSignoff-Reviewed-Tree-SHA: 0000000000000000000000000000000000000000"
    subprocess.run(["git", "commit", "--allow-empty", "-m", msg], cwd=repo, check=True)
    
    res = run_verification_in_repo(repo)
    assert res.returncode == 1
    assert "::error::Missing, incomplete, or mismatched" in res.stdout or "::error::Missing, incomplete, or mismatched" in res.stderr


def test_malformed_non_hex_tree_sha_fails(tmp_path):
    """Verify that a non-40-hex tree SHA fails verification."""
    repo = str(tmp_path)
    setup_git_repo(repo)
    
    msg = "Malformed tree SHA commit\n\nSignoff-Spec-Version: 1.0\nSignoff-Status: VERIFIED_BY_HUMAN\nSignoff-Reviewed-Tree-SHA: invalid-sha"
    subprocess.run(["git", "commit", "--allow-empty", "-m", msg], cwd=repo, check=True)
    
    res = run_verification_in_repo(repo)
    assert res.returncode == 1
    assert "::error::Missing, incomplete, or mismatched" in res.stdout or "::error::Missing, incomplete, or mismatched" in res.stderr


def test_valid_gsa_head_note_passes(tmp_path):
    """Verify that a commit with attached complete GSA note on HEAD SHA exits 0 cleanly."""
    repo = str(tmp_path)
    setup_git_repo(repo)
    
    subprocess.run(["git", "commit", "--allow-empty", "-m", "Feature commit"], cwd=repo, check=True)
    head_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    tree_sha = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    
    note_content = (
        f"Signoff-Spec-Version: 1.0\n"
        f"Signoff-Status: VERIFIED_BY_HUMAN\n"
        f"Signoff-Reviewed-Commit-SHA: {head_sha}\n"
        f"Signoff-Reviewed-Tree-SHA: {tree_sha}\n"
        f"Signoff-Verified-By: test@example.com"
    )
    subprocess.run(["git", "notes", "--ref=signoff", "add", "-m", note_content], cwd=repo, check=True)
    
    res = run_verification_in_repo(repo)
    assert res.returncode == 0
    assert "verified via commit note" in res.stdout.lower() or "verified" in res.stdout.lower()


def test_valid_gsa_tree_fallback_note_passes(tmp_path):
    """Verify GSA §5.1 tree-SHA note fallback: complete note attached directly to HEAD^{tree} passes."""
    repo = str(tmp_path)
    setup_git_repo(repo)
    
    subprocess.run(["git", "commit", "--allow-empty", "-m", "Feature commit"], cwd=repo, check=True)
    head_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    tree_sha = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    
    note_content = (
        f"Signoff-Spec-Version: 1.0\n"
        f"Signoff-Status: VERIFIED_BY_HUMAN\n"
        f"Signoff-Reviewed-Commit-SHA: {head_sha}\n"
        f"Signoff-Reviewed-Tree-SHA: {tree_sha}\n"
        f"Signoff-Verified-By: test@example.com"
    )
    subprocess.run(["git", "notes", "--ref=signoff", "add", "-m", note_content, tree_sha], cwd=repo, check=True)
    
    res = run_verification_in_repo(repo)
    assert res.returncode == 0
    assert "verified via tree note fallback" in res.stdout.lower() or "verified" in res.stdout.lower()


def test_git_note_mismatched_tree_fails(tmp_path):
    """Verify that a commit note referencing a mismatched tree SHA fails verification."""
    repo = str(tmp_path)
    setup_git_repo(repo)
    
    subprocess.run(["git", "commit", "--allow-empty", "-m", "Feature commit"], cwd=repo, check=True)
    head_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    
    note_content = (
        f"Signoff-Spec-Version: 1.0\n"
        f"Signoff-Status: VERIFIED_BY_HUMAN\n"
        f"Signoff-Reviewed-Commit-SHA: {head_sha}\n"
        f"Signoff-Reviewed-Tree-SHA: 1111111111111111111111111111111111111111"
    )
    subprocess.run(["git", "notes", "--ref=signoff", "add", "-m", note_content], cwd=repo, check=True)
    
    res = run_verification_in_repo(repo)
    assert res.returncode == 1
    assert "::error::Missing, incomplete, or mismatched" in res.stdout or "::error::Missing, incomplete, or mismatched" in res.stderr


def test_git_note_mismatched_commit_fails(tmp_path):
    """Verify that a commit note referencing a mismatched commit SHA fails verification."""
    repo = str(tmp_path)
    setup_git_repo(repo)
    
    subprocess.run(["git", "commit", "--allow-empty", "-m", "Feature commit"], cwd=repo, check=True)
    tree_sha = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    
    note_content = (
        f"Signoff-Spec-Version: 1.0\n"
        f"Signoff-Status: VERIFIED_BY_HUMAN\n"
        f"Signoff-Reviewed-Commit-SHA: 2222222222222222222222222222222222222222\n"
        f"Signoff-Reviewed-Tree-SHA: {tree_sha}"
    )
    subprocess.run(["git", "notes", "--ref=signoff", "add", "-m", note_content], cwd=repo, check=True)
    
    res = run_verification_in_repo(repo)
    assert res.returncode == 1
    assert "::error::Missing, incomplete, or mismatched" in res.stdout or "::error::Missing, incomplete, or mismatched" in res.stderr
