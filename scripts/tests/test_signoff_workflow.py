import os
import subprocess


WORKFLOW_PATH = os.path.join(os.path.dirname(__file__), "..", "..", ".github", "workflows", "signoff.yml")



def get_verification_script() -> str:
    """Extract the Verify Git Signoff Attestation script directly from signoff.yml."""
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
    """Verify that .github/workflows/signoff.yml exists and adheres to Spec v1.1.0 security & trigger schema."""
    assert os.path.exists(WORKFLOW_PATH), f"Workflow file does not exist at {WORKFLOW_PATH}"
    
    with open(WORKFLOW_PATH, "r", encoding="utf-8") as f:
        content = f.read()
        
    assert "name: Signoff Verification Gate" in content
    assert "pull_request:" in content
    assert "permissions:" in content
    assert "contents: read" in content
    assert "concurrency:" in content
    assert "actions/checkout@v4" in content
    assert "ref: ${{ github.event.pull_request.head.sha }}" in content
    assert "fetch-depth: 0" in content
    assert "refs/notes/signoff" in content


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
    
    # Create plain commit without signoff
    subprocess.run(["git", "commit", "--allow-empty", "-m", "Un-attested commit"], cwd=repo, check=True)
    
    res = run_verification_in_repo(repo)
    assert res.returncode == 1
    assert "::error::Missing Git Signoff Attestation" in res.stdout or "::error::Missing Git Signoff Attestation" in res.stderr


def test_commit_trailer_attestation_passes(tmp_path):
    """Verify that a commit with Signoff-Status: VERIFIED_BY_HUMAN trailer exits 0 cleanly."""
    repo = str(tmp_path)
    setup_git_repo(repo)
    
    msg = "Attested commit\n\nSignoff-Status: VERIFIED_BY_HUMAN\nSignoff-Verified-By: test@example.com"
    subprocess.run(["git", "commit", "--allow-empty", "-m", msg], cwd=repo, check=True)
    
    res = run_verification_in_repo(repo)
    assert res.returncode == 0
    assert "verified" in res.stdout.lower()


def test_commit_trailer_no_digest_attestation_passes(tmp_path):
    """Verify that a commit with Signoff-Status: VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST trailer exits 0 cleanly."""
    repo = str(tmp_path)
    setup_git_repo(repo)
    
    msg = "Attested commit without transcript digest\n\nSignoff-Status: VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST\nSignoff-Verified-By: test@example.com"
    subprocess.run(["git", "commit", "--allow-empty", "-m", msg], cwd=repo, check=True)
    
    res = run_verification_in_repo(repo)
    assert res.returncode == 0
    assert "verified" in res.stdout.lower()


def test_commit_trailer_invalid_status_fails(tmp_path):
    """Verify that a commit with an invalid status (e.g. REJECTED) fails verification with exit 1."""
    repo = str(tmp_path)
    setup_git_repo(repo)
    
    msg = "Rejected commit\n\nSignoff-Status: REJECTED\nSignoff-Verified-By: test@example.com"
    subprocess.run(["git", "commit", "--allow-empty", "-m", msg], cwd=repo, check=True)
    
    res = run_verification_in_repo(repo)
    assert res.returncode == 1
    assert "::error::Missing Git Signoff Attestation" in res.stdout or "::error::Missing Git Signoff Attestation" in res.stderr


def test_git_note_attestation_passes(tmp_path):
    """Verify that a commit with attached refs/notes/signoff containing Signoff-Status exits 0 cleanly."""
    repo = str(tmp_path)
    setup_git_repo(repo)
    
    subprocess.run(["git", "commit", "--allow-empty", "-m", "Feature commit"], cwd=repo, check=True)
    
    note_content = "Signoff-Status: VERIFIED_BY_HUMAN\nSignoff-Verified-By: test@example.com"
    subprocess.run(["git", "notes", "--ref=signoff", "add", "-m", note_content], cwd=repo, check=True)
    
    res = run_verification_in_repo(repo)
    assert res.returncode == 0
    assert "verified" in res.stdout.lower()


def test_git_note_no_digest_attestation_passes(tmp_path):
    """Verify that a commit with attached refs/notes/signoff containing VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST exits 0."""
    repo = str(tmp_path)
    setup_git_repo(repo)
    
    subprocess.run(["git", "commit", "--allow-empty", "-m", "Feature commit"], cwd=repo, check=True)
    
    note_content = "Signoff-Status: VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST\nSignoff-Verified-By: test@example.com"
    subprocess.run(["git", "notes", "--ref=signoff", "add", "-m", note_content], cwd=repo, check=True)
    
    res = run_verification_in_repo(repo)
    assert res.returncode == 0
    assert "verified" in res.stdout.lower()


def test_git_note_invalid_status_fails(tmp_path):
    """Verify that a commit with attached refs/notes/signoff containing an invalid status fails verification."""
    repo = str(tmp_path)
    setup_git_repo(repo)
    
    subprocess.run(["git", "commit", "--allow-empty", "-m", "Feature commit"], cwd=repo, check=True)
    
    note_content = "Signoff-Status: REJECTED\nSignoff-Verified-By: test@example.com"
    subprocess.run(["git", "notes", "--ref=signoff", "add", "-m", note_content], cwd=repo, check=True)
    
    res = run_verification_in_repo(repo)
    assert res.returncode == 1
    assert "::error::Missing Git Signoff Attestation" in res.stdout or "::error::Missing Git Signoff Attestation" in res.stderr

