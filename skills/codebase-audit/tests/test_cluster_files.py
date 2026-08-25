import json
import os
import subprocess
import sys

import pytest

# Add scripts directory to sys.path to import cluster_files
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../scripts")))
import cluster_files


@pytest.fixture
def sample_repo(tmp_path):
    """Create a mock repository structure with multiple functional domains."""
    repo = tmp_path / "mock_repo"
    repo.mkdir()

    # Domain 1: Dynamics & Physics
    dynamics = repo / "src" / "dynamics"
    dynamics.mkdir(parents=True)
    (dynamics / "engine.py").write_text("# Dynamics engine\n" * 50)
    (dynamics / "integrator.py").write_text("# Integrator\n" * 40)

    # Domain 2: IO & Storage
    io_dir = repo / "src" / "io"
    io_dir.mkdir(parents=True)
    (io_dir / "loader.py").write_text("# Loader\n" * 30)
    (io_dir / "writer.py").write_text("# Writer\n" * 25)

    # Domain 3: Transforms & Preprocessing
    transforms = repo / "src" / "transforms"
    transforms.mkdir(parents=True)
    (transforms / "coordinates.py").write_text("# Coordinates\n" * 35)

    # Tests directory (top level)
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_dynamics.py").write_text("# Test dynamics\n" * 10)
    (tests / "test_io.py").write_text("# Test IO\n" * 10)

    # Nested tests directory
    nested_tests = repo / "src" / "transforms" / "tests"
    nested_tests.mkdir()
    (nested_tests / "test_coordinates.py").write_text("# Test coordinates\n" * 10)

    # Co-located test file
    (repo / "src" / "io" / "test_inline_io.py").write_text("# Inline test\n" * 10)

    return repo


@pytest.fixture
def real_git_repo(tmp_path):
    """Create a real git repository with initial commit and feature branch."""
    repo = tmp_path / "real_git_repo"
    repo.mkdir()

    def run_cmd(args):
        subprocess.run(["git"] + args, cwd=str(repo), check=True, capture_output=True, text=True)

    run_cmd(["init", "-b", "main"])
    run_cmd(["config", "user.name", "Test User"])
    run_cmd(["config", "user.email", "test@example.com"])

    # Initial structure on main
    src = repo / "src" / "core"
    src.mkdir(parents=True)
    (src / "base.py").write_text("# Base core\n" * 20)
    run_cmd(["add", "."])
    run_cmd(["commit", "-m", "Initial commit on main"])

    # Feature branch with multiple domains and a rename
    run_cmd(["checkout", "-b", "feature/audit-test"])

    dynamics = repo / "src" / "dynamics"
    dynamics.mkdir(parents=True)
    (dynamics / "sim.py").write_text("# Sim\n" * 60)

    io_dir = repo / "src" / "io"
    io_dir.mkdir(parents=True)
    (io_dir / "writer.py").write_text("# Writer\n" * 40)

    # Add a test file under tests/
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_dynamics.py").write_text("# Test dynamics\n" * 10)

    # Stage and commit new files
    run_cmd(["add", "."])
    run_cmd(["commit", "-m", "Add dynamics, io and tests"])

    # Rename base.py to core_base.py
    run_cmd(["mv", "src/core/base.py", "src/core/core_base.py"])
    (repo / "src" / "core" / "core_base.py").write_text("# Updated Core Base\n" * 25)
    run_cmd(["add", "."])
    run_cmd(["commit", "-m", "Rename base.py to core_base.py"])

    return repo


def test_repo_clustering_basic(sample_repo):
    """Test basic topological clustering on repo files."""
    clusters = cluster_files.cluster_repo(str(sample_repo), max_clusters=5, max_lines=3000)
    assert len(clusters) == 3
    cluster_names = [c["name"] for c in clusters]
    assert any("dynamics" in name.lower() for name in cluster_names)
    assert any("io" in name.lower() for name in cluster_names)
    assert any("transforms" in name.lower() for name in cluster_names)


def test_duplicate_cluster_id_uniqueness(tmp_path):
    """Test that same-named files in different packages get unique cluster IDs."""
    repo = tmp_path / "dup_repo"
    repo.mkdir()

    (repo / "pkgA").mkdir()
    (repo / "pkgA" / "model.py").write_text("# Giant A\n" * 3500)

    (repo / "pkgB").mkdir()
    (repo / "pkgB" / "model.py").write_text("# Giant B\n" * 3500)

    clusters = cluster_files.cluster_repo(str(repo), max_clusters=5, max_lines=3000)
    ids = [c["id"] for c in clusters]
    assert len(ids) == len(set(ids)), f"Duplicate cluster IDs found: {ids}"


def test_max_clusters_hard_bound(tmp_path):
    """Test that _consolidate_clusters strictly enforces max_clusters bound."""
    repo = tmp_path / "many_domains_repo"
    repo.mkdir()

    for i in range(6):
        d = repo / f"domain_{i}"
        d.mkdir()
        (d / "code.py").write_text(f"# Domain {i}\n" * 50)

    clusters = cluster_files.cluster_repo(str(repo), max_clusters=4, max_lines=3000)
    assert len(clusters) <= 4, f"Expected <= 4 clusters, got {len(clusters)}"


def test_max_clusters_with_monolithic_and_overflow(tmp_path):
    """Test max_clusters budget when monolithic files and overflow coexist."""
    repo = tmp_path / "mono_overflow_repo"
    repo.mkdir()

    # 2 monolithic files
    (repo / "src" / "aa").mkdir(parents=True)
    (repo / "src" / "aa" / "a.py").write_text("# Mono A\n" * 3500)
    (repo / "src" / "huge.py").write_text("# Mono Huge\n" * 3500)

    # 2 normal domains
    (repo / "src" / "bb").mkdir(parents=True)
    (repo / "src" / "bb" / "b.py").write_text("# Domain B\n" * 100)
    (repo / "src" / "cc").mkdir(parents=True)
    (repo / "src" / "cc" / "c.py").write_text("# Domain C\n" * 100)

    # With max_clusters=2, the 2 monolithic files take both slots, remaining merged into 1 shared_utils
    clusters = cluster_files.cluster_repo(str(repo), max_clusters=2, max_lines=3000)
    # Total clusters should be 2 monolithic + at most 1 shared_utils = 3 (zero separate domain clusters)
    domain_clusters = [c for c in clusters if not c.get("is_monolithic")]
    assert len(domain_clusters) <= 1
    assert any(c["id"] == "cluster_shared_utils" for c in domain_clusters)


def test_small_domains_merge_into_shared_utils(tmp_path):
    """Test merging of tiny folders (<20 lines) into shared_utils."""
    repo = tmp_path / "small_merge_repo"
    repo.mkdir()

    (repo / "src" / "util1").mkdir(parents=True)
    (repo / "src" / "util1" / "u1.py").write_text("# u1\n" * 5)

    (repo / "src" / "util2").mkdir(parents=True)
    (repo / "src" / "util2" / "u2.py").write_text("# u2\n" * 5)

    (repo / "src" / "core").mkdir(parents=True)
    (repo / "src" / "core" / "core.py").write_text("# core\n" * 500)

    clusters = cluster_files.cluster_repo(str(repo), max_clusters=3, max_lines=1000)
    assert len(clusters) == 2
    assert any(c["id"] == "cluster_core" for c in clusters)
    assert any(c["id"] == "cluster_shared_utils" for c in clusters)


def test_monolithic_file_isolation(tmp_path):
    """Test that an oversized single file is isolated into a standalone cluster."""
    repo = tmp_path / "mono_repo"
    repo.mkdir()

    (repo / "src").mkdir(parents=True)
    (repo / "src" / "giant_model.py").write_text("# Giant\n" * 3500)
    (repo / "src" / "normal.py").write_text("# Normal\n" * 50)

    clusters = cluster_files.cluster_repo(str(repo), max_clusters=5, max_lines=3000)
    giant_cluster = next((c for c in clusters if any("giant_model.py" in str(f) for f in c["files"])), None)
    assert giant_cluster is not None
    assert len(giant_cluster["files"]) == 1
    assert giant_cluster.get("is_monolithic") is True


def test_associated_test_matching(sample_repo):
    """Test matching test files to clusters across top-level and nested tests with anchored stems."""
    test_map = cluster_files.discover_associated_tests(str(sample_repo), ["src/dynamics/engine.py", "src/dynamics/integrator.py"])
    assert any("test_dynamics.py" in t for t in test_map)

    # Test nested test discovery
    test_map_nested = cluster_files.discover_associated_tests(str(sample_repo), ["src/transforms/coordinates.py"])
    assert any("test_coordinates.py" in t for t in test_map_nested)

    # Ensure unanchored substrings like 'io.py' do not match 'test_monitor.py'
    (sample_repo / "tests" / "test_monitor.py").write_text("# Monitor\n" * 10)
    io_tests = cluster_files.discover_associated_tests(str(sample_repo), ["src/io/loader.py"])
    assert not any("test_monitor.py" in t for t in io_tests)


def test_associated_tests_no_absolute_path_false_positives(tmp_path):
    """Test that absolute path components (e.g. /home/user/) do not cause false-positive test matches."""
    # Create root directory with component 'user'
    root_dir = tmp_path / "repo_for_user"
    root_dir.mkdir()

    (root_dir / "src" / "user").mkdir(parents=True)
    (root_dir / "src" / "user" / "profile.py").write_text("# profile\n" * 20)

    (root_dir / "tests").mkdir()
    (root_dir / "tests" / "test_unrelated.py").write_text("# Unrelated\n" * 10)

    test_matches = cluster_files.discover_associated_tests(str(root_dir), ["src/user/profile.py"])
    # test_unrelated.py should NOT match
    assert not any("test_unrelated.py" in t for t in test_matches)


def test_git_diff_real_repo_clustering(real_git_repo):
    """Test git diff mode against a real git repository."""
    clusters, total_lines, total_files, warning = cluster_files.cluster_diff(
        base_ref="main",
        head_ref="HEAD",
        repo_path=str(real_git_repo),
        max_clusters=5,
        max_lines=3000,
    )
    assert total_files >= 2
    assert total_lines > 0
    assert warning is None

    for c in clusters:
        for f in c["files"]:
            assert not cluster_files.is_test_path(f), f"Test file clustered as source: {f}"

    all_files = [f for c in clusters for f in c["files"]]
    assert "src/core/core_base.py" in all_files
    assert not any("=>" in f for f in all_files)


def test_git_diff_shallow_clone_fallback(monkeypatch, real_git_repo):
    """Test that a failed three-dot diff (shallow clone) falls back to two-dot diff with a warning."""
    original_run_git = cluster_files.run_git

    def mock_run_git(args, cwd="."):
        # Simulate three-dot failure with 'no merge base'
        if any("..." in arg for arg in args):
            return 128, "", "fatal: refusing to merge unrelated histories / no merge base"
        return original_run_git(args, cwd=cwd)

    monkeypatch.setattr(cluster_files, "run_git", mock_run_git)

    clusters, total_lines, total_files, warning = cluster_files.cluster_diff(
        base_ref="main",
        head_ref="HEAD",
        repo_path=str(real_git_repo),
    )
    assert total_files >= 2
    assert warning is not None
    assert "shallow history" in warning


def test_git_diff_failure_raises_error():
    """Test that cluster_diff raises RuntimeError when both three-dot and two-dot diffs fail."""
    with pytest.raises(RuntimeError) as exc_info:
        cluster_files.cluster_diff(base_ref="nonexistent_base_ref_12345", repo_path=".")
    assert "Git diff failed" in str(exc_info.value)


def test_git_diff_empty_merge_base_stays_empty(real_git_repo):
    """Test that a diff against HEAD returns empty without failing or inverting."""
    clusters, total_lines, total_files, warning = cluster_files.cluster_diff(
        base_ref="HEAD",
        head_ref="HEAD",
        repo_path=str(real_git_repo),
    )
    assert clusters == []
    assert total_lines == 0
    assert total_files == 0
    assert warning is None


def test_get_domain_key():
    """Test domain key resolution for various directory depths."""
    assert cluster_files.get_domain_key("src/dynamics/engine.py") == "dynamics"
    assert cluster_files.get_domain_key("src/main.py") == "src"
    assert cluster_files.get_domain_key("lib/utils.py") == "lib"
    assert cluster_files.get_domain_key("scripts/run.py") == "scripts"
    assert cluster_files.get_domain_key("standalone.py") == "root"


def test_parse_numstat_path():
    """Test parsing of git numstat rename notations, quoted paths, and multiple arrows."""
    assert cluster_files.parse_numstat_path("src/core/{base.py => core_base.py}") == "src/core/core_base.py"
    assert cluster_files.parse_numstat_path("{old => new}/file.py") == "new/file.py"
    assert cluster_files.parse_numstat_path("old.py => new.py") == "new.py"
    assert cluster_files.parse_numstat_path('"src/{old => new}/file.py"') == "src/new/file.py"
    assert cluster_files.parse_numstat_path('"quoted filename with spaces.py"') == "quoted filename with spaces.py"
    assert cluster_files.parse_numstat_path("regular/file.py") == "regular/file.py"


def test_small_diff_detection():
    """Test detection of small diffs (<300 lines) for fast-path fallback in diff mode."""
    payload_small = cluster_files.format_cluster_payload([], total_lines=150, total_files=2, is_diff=True)
    assert payload_small["is_small_diff"] is True
    assert payload_small["recommended_mode"] == "single-agent-adversarial-review"

    payload_large = cluster_files.format_cluster_payload([], total_lines=1200, total_files=12, is_diff=True)
    assert payload_large["is_small_diff"] is False
    assert payload_large["recommended_mode"] == "multi-agent-audit"

    # Repo sweep mode should never flag is_small_diff
    payload_repo = cluster_files.format_cluster_payload([], total_lines=150, total_files=2, is_diff=False)
    assert payload_repo["is_small_diff"] is False
    assert payload_repo["recommended_mode"] == "multi-agent-audit"


def test_cli_diff_mode_real_git(real_git_repo):
    """Test CLI execution in diff mode against a real git repository."""
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../scripts/cluster_files.py"))
    cmd = [
        sys.executable,
        script_path,
        "--diff",
        "main",
    ]
    res = subprocess.run(cmd, cwd=str(real_git_repo), capture_output=True, text=True)
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert "clusters" in data
    assert "total_files" in data
    assert "total_lines" in data
    assert data["total_files"] >= 2


def test_cli_diff_failure_exits_nonzero(tmp_path):
    """Test that CLI exits with non-zero exit code and error JSON on git failure."""
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../scripts/cluster_files.py"))
    cmd = [
        sys.executable,
        script_path,
        "--diff",
        "nonexistent_ref_9999",
    ]
    res = subprocess.run(cmd, cwd=str(tmp_path), capture_output=True, text=True)
    assert res.returncode == 1
    err_data = json.loads(res.stderr)
    assert "error" in err_data
    assert "nonexistent_ref_9999" in err_data["error"]
    assert err_data["is_small_diff"] is False
