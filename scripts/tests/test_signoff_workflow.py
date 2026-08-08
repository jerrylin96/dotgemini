import os
import shutil
import subprocess
import sys

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
                    return step.get("run", "")
        except Exception:
            pass

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
                unindented = line[base_indent:] if len(line) >= base_indent else line.lstrip()
                script_lines.append(unindented)

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
    os.makedirs(os.path.join(repo_dir, "scripts"), exist_ok=True)
    src_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "validate_gsa_note.py"))
    dst_script = os.path.join(repo_dir, "scripts", "validate_gsa_note.py")
    if os.path.exists(src_script):
        shutil.copy2(src_script, dst_script)


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


def test_malformed_tree_sha_in_note_fails(tmp_path):
    """Verify that a note payload containing a non-40-hex Signoff-Reviewed-Tree-SHA fails verification."""
    repo = str(tmp_path)
    setup_git_repo(repo)

    subprocess.run(["git", "commit", "--allow-empty", "-m", "Base commit"], cwd=repo, check=True)
    head_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()

    note_content = (
        f"Signoff-Spec-Version: 1.0\n"
        f"Signoff-Status: VERIFIED_BY_HUMAN\n"
        f"Signoff-Reviewed-Commit-SHA: {head_sha}\n"
        f"Signoff-Reviewed-Tree-SHA: not-a-valid-40-hex-tree-sha"
    )
    subprocess.run(["git", "notes", "--ref=signoff", "add", "-m", note_content], cwd=repo, check=True)

    res = run_verification_in_repo(repo)
    assert res.returncode == 1
    assert "::error::Missing, incomplete, or mismatched" in res.stdout or "::error::Missing, incomplete, or mismatched" in res.stderr


def test_appended_valid_notes_pass(tmp_path):
    """Verify that a note built by appending two valid attestations passes verification (Task 1)."""
    repo = str(tmp_path)
    setup_git_repo(repo)

    subprocess.run(["git", "commit", "--allow-empty", "-m", "Base commit"], cwd=repo, check=True)
    head_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    tree_sha = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()

    attestation1 = (
        f"[SIGNOFF {head_sha[:7]}]: first attestation\n\n"
        f"Signoff-Spec-Version: 1.0\n"
        f"Signoff-Status: VERIFIED_BY_HUMAN\n"
        f"Signoff-Reviewed-Commit-SHA: {head_sha}\n"
        f"Signoff-Reviewed-Tree-SHA: {tree_sha}\n"
        f"Signoff-Verified-By: alice@example.com"
    )
    attestation2 = (
        f"[SIGNOFF {head_sha[:7]}]: second attestation\n\n"
        f"Signoff-Spec-Version: 1.0\n"
        f"Signoff-Status: VERIFIED_BY_HUMAN\n"
        f"Signoff-Reviewed-Commit-SHA: {head_sha}\n"
        f"Signoff-Reviewed-Tree-SHA: {tree_sha}\n"
        f"Signoff-Verified-By: bob@example.com"
    )

    subprocess.run(["git", "notes", "--ref=signoff", "add", "-m", attestation1], cwd=repo, check=True)
    subprocess.run(["git", "notes", "--ref=signoff", "append", "-m", attestation2], cwd=repo, check=True)

    res = run_verification_in_repo(repo)
    assert res.returncode == 0
    assert "verified via commit note" in res.stdout.lower() or "verified" in res.stdout.lower()


def test_individually_malformed_notes_fail(tmp_path):
    """Verify that a note payload with two attestations that are individually malformed fails verification."""
    repo = str(tmp_path)
    setup_git_repo(repo)

    subprocess.run(["git", "commit", "--allow-empty", "-m", "Base commit"], cwd=repo, check=True)
    head_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    tree_sha = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()

    bad_attestation1 = (
        f"[SIGNOFF {head_sha[:7]}]: bad status\n\n"
        f"Signoff-Spec-Version: 1.0\n"
        f"Signoff-Status: REJECTED\n"
        f"Signoff-Reviewed-Commit-SHA: {head_sha}\n"
        f"Signoff-Reviewed-Tree-SHA: {tree_sha}"
    )
    bad_attestation2 = (
        f"[SIGNOFF {head_sha[:7]}]: bad tree sha\n\n"
        f"Signoff-Spec-Version: 1.0\n"
        f"Signoff-Status: VERIFIED_BY_HUMAN\n"
        f"Signoff-Reviewed-Commit-SHA: {head_sha}\n"
        f"Signoff-Reviewed-Tree-SHA: not-a-sha"
    )

    subprocess.run(["git", "notes", "--ref=signoff", "add", "-m", bad_attestation1], cwd=repo, check=True)
    subprocess.run(["git", "notes", "--ref=signoff", "append", "-m", bad_attestation2], cwd=repo, check=True)

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


def test_note_missing_verified_by_fails(tmp_path):
    """Verify that a note missing Signoff-Verified-By fails validation (GSA §2.1 accountability field)."""
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
    )
    subprocess.run(["git", "notes", "--ref=signoff", "add", "-m", note_content], cwd=repo, check=True)

    res = run_verification_in_repo(repo)
    assert res.returncode == 1


def test_lowercase_trailer_keys_fail(tmp_path):
    """Verify that a note with lowercase trailer keys is rejected (GSA §2.1 & §2.3 case-sensitivity)."""
    repo = str(tmp_path)
    setup_git_repo(repo)

    subprocess.run(["git", "commit", "--allow-empty", "-m", "Feature commit"], cwd=repo, check=True)
    head_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    tree_sha = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()

    note_content = (
        f"signoff-spec-version: 1.0\n"
        f"signoff-status: VERIFIED_BY_HUMAN\n"
        f"signoff-reviewed-commit-sha: {head_sha}\n"
        f"signoff-reviewed-tree-sha: {tree_sha}\n"
        f"signoff-verified-by: alice@example.com"
    )
    subprocess.run(["git", "notes", "--ref=signoff", "add", "-m", note_content], cwd=repo, check=True)

    res = run_verification_in_repo(repo)
    assert res.returncode == 1


def test_conformance_vectors(tmp_path):
    """Pin the gate against the shared GSA v1.0 conformance suite (Task 2)."""
    import json
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from validate_gsa_note import validate_payload

    conformance_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "conformance"))
    expected_file = os.path.join(conformance_dir, "expected.json")

    assert os.path.exists(expected_file), f"conformance/expected.json missing at {expected_file}"

    with open(expected_file, "r", encoding="utf-8") as f:
        expected_data = json.load(f)

    for vector_rel_path, spec in expected_data.items():
        if vector_rel_path.startswith("_"):
            continue

        vector_full_path = os.path.join(conformance_dir, vector_rel_path)
        assert os.path.exists(vector_full_path), f"Vector file missing at {vector_full_path}"

        with open(vector_full_path, "r", encoding="utf-8") as f:
            vector_payload = f.read()

        is_valid_expected = spec["valid"]

        passed = validate_payload(vector_payload)

        if is_valid_expected:
            assert passed, f"Expected vector {vector_rel_path} to pass, but failed"
        else:
            assert not passed, f"Expected vector {vector_rel_path} to fail, but passed"


