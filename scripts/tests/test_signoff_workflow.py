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
            recording = "step"
            continue
        if recording == "step":
            if line.strip().startswith("run:"):
                recording = "script"
            continue
        if recording == "script":
            if base_indent is None:
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


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def test_workflow_yaml_structure():
    """Verify that .github/workflows/signoff.yml exists and adheres to hardened Spec schema."""
    import re
    assert os.path.exists(WORKFLOW_PATH), f"Workflow file does not exist at {WORKFLOW_PATH}"

    with open(WORKFLOW_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Structural trigger verification: ensure push explicitly scopes to main
    assert re.search(r"push:\s*\n\s*branches:\s*\[main\]", content), "push trigger must be explicitly scoped to [main]"
    assert re.search(r"pull_request:\s*\n\s*types:.*\[.*ready_for_review.*\]\s*\n\s*branches:\s*\[main\]", content), (
        "pull_request trigger must target [main]"
    )
    assert "name: Signoff Verification Gate" in content
    assert "permissions:" in content
    assert "contents: read" in content
    assert "concurrency:" in content
    assert "actions/checkout@" in content
    assert "ref: ${{ github.event.pull_request.head.sha || github.sha }}" in content
    assert "fetch-depth: 0" in content
    assert "persist-credentials: false" in content
    assert "cat_sort_uniq" in content
    assert "refs/notes/signoff" in content
    assert "SIGNOFF_EVENT_NAME" in content
    assert "SIGNOFF_REF" in content

    # Yaml integrity assertion
    script = get_verification_script()
    assert "HEAD_TREE" in script
    assert "validate_payload" in script
    assert "verify_target" in script
    assert "HEAD^2" in script
    assert "EVENT_NAME" in script

    # Verify README badge scopes to main and push
    readme_path = os.path.join(ROOT, "README.md")
    with open(readme_path, "r", encoding="utf-8") as f:
        readme_content = f.read()
    assert "actions/workflows/signoff.yml/badge.svg?branch=main&event=push" in readme_content


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


def run_verification_in_repo(
    repo_dir: str,
    event_name: str = "pull_request",
    ref: str = "refs/heads/main",
    before_sha: str = ""
) -> subprocess.CompletedProcess:
    """Helper to run the verification shell script inside a test git repository with realistic GitHub event context."""
    env = os.environ.copy()
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["SIGNOFF_EVENT_NAME"] = event_name
    env["SIGNOFF_REF"] = ref
    env["SIGNOFF_EVENT_BEFORE"] = before_sha
    env["GITHUB_EVENT_NAME"] = event_name
    env["GITHUB_REF"] = ref
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


def test_sequential_merge_with_attested_pr_head_passes(tmp_path):
    """Verify Scenario B: Sequential merge commits on main pass on push when merged PR head (HEAD^2) is attested."""
    repo = str(tmp_path)
    setup_git_repo(repo)

    # 1. Base commit on main
    subprocess.run(["git", "commit", "--allow-empty", "-m", "Base main commit"], cwd=repo, check=True)
    base_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()

    # 2. PR 1 branch created, attested, merged into main
    subprocess.run(["git", "checkout", "-b", "feature-1"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "Feature 1 work"], cwd=repo, check=True)
    f1_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    f1_tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    note_1 = f"Signoff-Spec-Version: 1.0\nSignoff-Status: VERIFIED_BY_HUMAN\nSignoff-Reviewed-Commit-SHA: {f1_sha}\nSignoff-Reviewed-Tree-SHA: {f1_tree}\nSignoff-Verified-By: dev1@example.com"
    subprocess.run(["git", "notes", "--ref=signoff", "add", "-m", note_1, f1_sha], cwd=repo, check=True)
    subprocess.run(["git", "notes", "--ref=signoff", "add", "-m", note_1, f1_tree], cwd=repo, check=True)

    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True)
    subprocess.run(["git", "merge", "--no-ff", "feature-1", "-m", "Merge PR 1"], cwd=repo, check=True)

    # 3. PR 2 branch created off original base (simulating concurrent PR), attested
    subprocess.run(["git", "checkout", "-b", "feature-2", base_sha], cwd=repo, check=True)
    with open(os.path.join(repo, "feature2.txt"), "w") as f:
        f.write("feature 2 content")
    subprocess.run(["git", "add", "feature2.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "Feature 2 work"], cwd=repo, check=True)
    f2_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    f2_tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    note_2 = f"Signoff-Spec-Version: 1.0\nSignoff-Status: VERIFIED_BY_HUMAN\nSignoff-Reviewed-Commit-SHA: {f2_sha}\nSignoff-Reviewed-Tree-SHA: {f2_tree}\nSignoff-Verified-By: dev2@example.com"
    subprocess.run(["git", "notes", "--ref=signoff", "add", "-m", note_2, f2_sha], cwd=repo, check=True)
    subprocess.run(["git", "notes", "--ref=signoff", "add", "-m", note_2, f2_tree], cwd=repo, check=True)

    # 4. Merge PR 2 into main sequentially (merge tree != feature 2 tree, no note on merge commit)
    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True)
    subprocess.run(["git", "merge", "--no-ff", "feature-2", "-m", "Merge PR 2"], cwd=repo, check=True)

    # 5. Run verification script on push to main
    res = run_verification_in_repo(repo, event_name="push", ref="refs/heads/main")
    assert res.returncode == 0
    assert "PASSED" in res.stdout


def test_pr_merge_commit_bypass_blocked(tmp_path):
    """Regression test (Hole A): PR HEAD is a merge commit with unattested P1 and attested P2.
    Must exit 1 on pull_request events because HEAD^2 fallback is strictly disabled for PRs."""
    repo = str(tmp_path)
    setup_git_repo(repo)

    # 1. Attested base on main
    subprocess.run(["git", "commit", "--allow-empty", "-m", "Attested main tip"], cwd=repo, check=True)
    main_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    main_tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    note_main = f"Signoff-Spec-Version: 1.0\nSignoff-Status: VERIFIED_BY_HUMAN\nSignoff-Reviewed-Commit-SHA: {main_sha}\nSignoff-Reviewed-Tree-SHA: {main_tree}\nSignoff-Verified-By: dev@example.com"
    subprocess.run(["git", "notes", "--ref=signoff", "add", "-m", note_main, main_sha], cwd=repo, check=True)
    subprocess.run(["git", "notes", "--ref=signoff", "add", "-m", note_main, main_tree], cwd=repo, check=True)

    # 2. Unattested branch with code changes
    subprocess.run(["git", "checkout", "-b", "unattested-branch", main_sha], cwd=repo, check=True)
    with open(os.path.join(repo, "evil.txt"), "w") as f:
        f.write("unattested code")
    subprocess.run(["git", "add", "evil.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "Unattested work"], cwd=repo, check=True)

    # 3. Branch merges main (so HEAD^2 is the attested main tip)
    subprocess.run(["git", "merge", "--no-ff", "main", "-m", "Merge main into feature"], cwd=repo, check=True)

    # 4. Run verification under pull_request event: MUST FAIL
    res = run_verification_in_repo(repo, event_name="pull_request", ref="refs/pull/123/merge")
    assert res.returncode == 1
    assert "::error::Missing, incomplete, or mismatched" in res.stdout or "::error::Missing, incomplete, or mismatched" in res.stderr


def test_push_crafted_merge_ancestor_blocked(tmp_path):
    """Regression test (Hole B): Merge commit on push whose HEAD^2 is an already-merged ancestor of HEAD^1.
    Must exit 1 because HEAD^2 does not bring new work."""
    repo = str(tmp_path)
    setup_git_repo(repo)

    # 1. Attested base on main
    subprocess.run(["git", "commit", "--allow-empty", "-m", "Initial main"], cwd=repo, check=True)
    base_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    base_tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    note_base = f"Signoff-Spec-Version: 1.0\nSignoff-Status: VERIFIED_BY_HUMAN\nSignoff-Reviewed-Commit-SHA: {base_sha}\nSignoff-Reviewed-Tree-SHA: {base_tree}\nSignoff-Verified-By: dev@example.com"
    subprocess.run(["git", "notes", "--ref=signoff", "add", "-m", note_base, base_sha], cwd=repo, check=True)
    subprocess.run(["git", "notes", "--ref=signoff", "add", "-m", note_base, base_tree], cwd=repo, check=True)

    # 2. Add an unattested commit on main
    with open(os.path.join(repo, "unattested.txt"), "w") as f:
        f.write("unattested direct work")
    subprocess.run(["git", "add", "unattested.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "Unattested work on main"], cwd=repo, check=True)
    p1_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()

    # 3. Create a crafted merge commit whose P1 is p1_sha and P2 is base_sha (already an ancestor)
    crafted_tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    crafted_commit = subprocess.run(
        ["git", "commit-tree", crafted_tree, "-p", p1_sha, "-p", base_sha, "-m", "Crafted merge with ancestor P2"],
        cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    subprocess.run(["git", "update-ref", "refs/heads/main", crafted_commit], cwd=repo, check=True)

    # 4. Run verification on push to main: MUST FAIL
    res = run_verification_in_repo(repo, event_name="push", ref="refs/heads/main")
    assert res.returncode == 1
    assert "::error::Missing, incomplete, or mismatched" in res.stdout or "::error::Missing, incomplete, or mismatched" in res.stderr


def test_head_2_fallback_disabled_on_non_main_push(tmp_path):
    """Verify that HEAD^2 fallback is disabled for push events on non-main branches."""
    repo = str(tmp_path)
    setup_git_repo(repo)

    # 1. Base commit
    subprocess.run(["git", "commit", "--allow-empty", "-m", "Base"], cwd=repo, check=True)
    base_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()

    # 2. Attested feature branch
    subprocess.run(["git", "checkout", "-b", "feature-attested", base_sha], cwd=repo, check=True)
    with open(os.path.join(repo, "feature.txt"), "w") as f:
        f.write("feature content")
    subprocess.run(["git", "add", "feature.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "Attested"], cwd=repo, check=True)
    f_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    f_tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    note = f"Signoff-Spec-Version: 1.0\nSignoff-Status: VERIFIED_BY_HUMAN\nSignoff-Reviewed-Commit-SHA: {f_sha}\nSignoff-Reviewed-Tree-SHA: {f_tree}\nSignoff-Verified-By: dev@example.com"
    subprocess.run(["git", "notes", "--ref=signoff", "add", "-m", note, f_sha], cwd=repo, check=True)
    subprocess.run(["git", "notes", "--ref=signoff", "add", "-m", note, f_tree], cwd=repo, check=True)

    # 3. Non-main branch merges feature-attested with distinct work
    subprocess.run(["git", "checkout", "-b", "staging", base_sha], cwd=repo, check=True)
    with open(os.path.join(repo, "staging.txt"), "w") as f:
        f.write("staging content")
    subprocess.run(["git", "add", "staging.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "Staging work"], cwd=repo, check=True)
    subprocess.run(["git", "merge", "--no-ff", "feature-attested", "-m", "Merge into staging"], cwd=repo, check=True)

    # 4. Push to staging: MUST FAIL because fallback is restricted to refs/heads/main
    res = run_verification_in_repo(repo, event_name="push", ref="refs/heads/staging")
    assert res.returncode == 1


def test_unattested_merge_commit_fails(tmp_path):
    """Verify that a merge commit where neither HEAD nor HEAD^2 is attested fails."""
    repo = str(tmp_path)
    setup_git_repo(repo)

    subprocess.run(["git", "commit", "--allow-empty", "-m", "Base main commit"], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "-b", "unattested-feature"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "Unattested work"], cwd=repo, check=True)

    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True)
    subprocess.run(["git", "merge", "--no-ff", "unattested-feature", "-m", "Merge unattested PR"], cwd=repo, check=True)

    res = run_verification_in_repo(repo)
    assert res.returncode == 1
    assert "::error::Missing, incomplete, or mismatched" in res.stdout or "::error::Missing, incomplete, or mismatched" in res.stderr
