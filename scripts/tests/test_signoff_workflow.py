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
    assert "::error::Missing, incomplete, or mismatched" in res.stdout or "::error::Missing, incomplete, or mismatched" in res.stderr


def test_status_only_trailer_fails(tmp_path):
    """Verify that a status-only trailer without Spec-Version, Commit-SHA, and Tree-SHA fails verification."""
    repo = str(tmp_path)
    setup_git_repo(repo)

    msg = "Status only commit\n\nSignoff-Status: VERIFIED_BY_HUMAN"
    subprocess.run(["git", "commit", "--allow-empty", "-m", msg], cwd=repo, check=True)

    res = run_verification_in_repo(repo)
    assert res.returncode == 1
    assert "::error::Missing, incomplete, or mismatched" in res.stdout or "::error::Missing, incomplete, or mismatched" in res.stderr


def test_valid_empty_attestation_commit_passes(tmp_path):
    """Verify that a valid empty attestation commit parented on HEAD~1 passes verification."""
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
    assert "verified via empty attestation commit on head" in res.stdout.lower()


def test_code_changing_non_empty_head_commit_fails(tmp_path):
    """Verify that a code-changing/non-empty HEAD commit with trailers fails empty attestation commit check."""
    repo = str(tmp_path)
    setup_git_repo(repo)

    # Base commit
    subprocess.run(["git", "commit", "--allow-empty", "-m", "Initial commit"], cwd=repo, check=True)

    # Create non-empty commit (modifying a file)
    test_file = os.path.join(repo, "foo.txt")
    with open(test_file, "w") as f:
        f.write("code change\n")
    subprocess.run(["git", "add", "foo.txt"], cwd=repo, check=True)

    rev_tree = subprocess.run(["git", "write-tree"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    rev_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()

    msg = (
        f"Code changing commit\n\n"
        f"Signoff-Spec-Version: 1.0\n"
        f"Signoff-Status: VERIFIED_BY_HUMAN\n"
        f"Signoff-Reviewed-Commit-SHA: {rev_commit}\n"
        f"Signoff-Reviewed-Tree-SHA: {rev_tree}"
    )
    subprocess.run(["git", "commit", "-m", msg], cwd=repo, check=True)

    res = run_verification_in_repo(repo)
    assert res.returncode == 1
    assert "::error::Missing, incomplete, or mismatched" in res.stdout or "::error::Missing, incomplete, or mismatched" in res.stderr


def test_empty_attestation_commit_wrong_reviewed_commit_fails(tmp_path):
    """Verify that an empty attestation commit whose Signoff-Reviewed-Commit-SHA is not HEAD~1 fails."""
    repo = str(tmp_path)
    setup_git_repo(repo)

    subprocess.run(["git", "commit", "--allow-empty", "-m", "Base commit"], cwd=repo, check=True)
    rev_tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()

    wrong_commit = "0000000000000000000000000000000000000000"
    msg = (
        f"[SIGNOFF]: attestation\n\n"
        f"Signoff-Spec-Version: 1.0\n"
        f"Signoff-Status: VERIFIED_BY_HUMAN\n"
        f"Signoff-Reviewed-Commit-SHA: {wrong_commit}\n"
        f"Signoff-Reviewed-Tree-SHA: {rev_tree}"
    )
    subprocess.run(["git", "commit", "--allow-empty", "-m", msg], cwd=repo, check=True)

    res = run_verification_in_repo(repo)
    assert res.returncode == 1
    assert "::error::Missing, incomplete, or mismatched" in res.stdout or "::error::Missing, incomplete, or mismatched" in res.stderr


def test_missing_reviewed_commit_sha_trailer_fails(tmp_path):
    """Verify that a HEAD trailer missing Signoff-Reviewed-Commit-SHA fails verification."""
    repo = str(tmp_path)
    setup_git_repo(repo)

    subprocess.run(["git", "commit", "--allow-empty", "-m", "Base commit"], cwd=repo, check=True)
    rev_tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()

    msg = (
        f"Missing commit SHA\n\n"
        f"Signoff-Spec-Version: 1.0\n"
        f"Signoff-Status: VERIFIED_BY_HUMAN\n"
        f"Signoff-Reviewed-Tree-SHA: {rev_tree}"
    )
    subprocess.run(["git", "commit", "--allow-empty", "-m", msg], cwd=repo, check=True)

    res = run_verification_in_repo(repo)
    assert res.returncode == 1
    assert "::error::Missing, incomplete, or mismatched" in res.stdout or "::error::Missing, incomplete, or mismatched" in res.stderr


def test_duplicate_status_fails(tmp_path):
    """Verify that a payload with duplicate Signoff-Status lines fails verification."""
    repo = str(tmp_path)
    setup_git_repo(repo)

    subprocess.run(["git", "commit", "--allow-empty", "-m", "Base commit"], cwd=repo, check=True)
    head_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    tree_sha = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()

    note_content = (
        f"Signoff-Spec-Version: 1.0\n"
        f"Signoff-Status: VERIFIED_BY_HUMAN\n"
        f"Signoff-Status: REJECTED\n"
        f"Signoff-Reviewed-Commit-SHA: {head_sha}\n"
        f"Signoff-Reviewed-Tree-SHA: {tree_sha}"
    )
    subprocess.run(["git", "notes", "--ref=signoff", "add", "-m", note_content], cwd=repo, check=True)

    res = run_verification_in_repo(repo)
    assert res.returncode == 1
    assert "::error::Missing, incomplete, or mismatched" in res.stdout or "::error::Missing, incomplete, or mismatched" in res.stderr


def test_duplicate_tree_sha_fails(tmp_path):
    """Verify that a payload with duplicate Signoff-Reviewed-Tree-SHA lines fails verification."""
    repo = str(tmp_path)
    setup_git_repo(repo)

    subprocess.run(["git", "commit", "--allow-empty", "-m", "Base commit"], cwd=repo, check=True)
    head_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    tree_sha = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()

    note_content = (
        f"Signoff-Spec-Version: 1.0\n"
        f"Signoff-Status: VERIFIED_BY_HUMAN\n"
        f"Signoff-Reviewed-Commit-SHA: {head_sha}\n"
        f"Signoff-Reviewed-Tree-SHA: {tree_sha}\n"
        f"Signoff-Reviewed-Tree-SHA: 0000000000000000000000000000000000000000"
    )
    subprocess.run(["git", "notes", "--ref=signoff", "add", "-m", note_content], cwd=repo, check=True)

    res = run_verification_in_repo(repo)
    assert res.returncode == 1
    assert "::error::Missing, incomplete, or mismatched" in res.stdout or "::error::Missing, incomplete, or mismatched" in res.stderr


def test_valid_head_note_passes(tmp_path):
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


def test_valid_tree_fallback_note_passes(tmp_path):
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


def test_tree_note_missing_reviewed_commit_sha_fails(tmp_path):
    """Verify that a tree note missing Signoff-Reviewed-Commit-SHA fails verification."""
    repo = str(tmp_path)
    setup_git_repo(repo)

    subprocess.run(["git", "commit", "--allow-empty", "-m", "Feature commit"], cwd=repo, check=True)
    tree_sha = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()

    note_content = (
        f"Signoff-Spec-Version: 1.0\n"
        f"Signoff-Status: VERIFIED_BY_HUMAN\n"
        f"Signoff-Reviewed-Tree-SHA: {tree_sha}"
    )
    subprocess.run(["git", "notes", "--ref=signoff", "add", "-m", note_content, tree_sha], cwd=repo, check=True)

    res = run_verification_in_repo(repo)
    assert res.returncode == 1
    assert "::error::Missing, incomplete, or mismatched" in res.stdout or "::error::Missing, incomplete, or mismatched" in res.stderr
