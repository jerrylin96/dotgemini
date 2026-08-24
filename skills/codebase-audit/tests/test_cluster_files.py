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

    # Tests directory
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_dynamics.py").write_text("# Test dynamics\n" * 10)
    (tests / "test_io.py").write_text("# Test IO\n" * 10)

    return repo


def test_repo_clustering_basic(sample_repo):
    """Test basic topological clustering on repo files."""
    clusters = cluster_files.cluster_repo(str(sample_repo), max_clusters=5, max_lines=3000)
    assert len(clusters) == 3
    cluster_names = [c["name"] for c in clusters]
    assert any("dynamics" in name.lower() for name in cluster_names)
    assert any("io" in name.lower() for name in cluster_names)
    assert any("transforms" in name.lower() for name in cluster_names)


def test_line_count_splitting_and_merging(tmp_path):
    """Test merging of tiny folders and handling of line limits."""
    repo = tmp_path / "merge_repo"
    repo.mkdir()

    # Small folder 1
    (repo / "src" / "util1").mkdir(parents=True)
    (repo / "src" / "util1" / "u1.py").write_text("# u1\n" * 5)

    # Small folder 2
    (repo / "src" / "util2").mkdir(parents=True)
    (repo / "src" / "util2" / "u2.py").write_text("# u2\n" * 5)

    # Large folder
    (repo / "src" / "core").mkdir(parents=True)
    (repo / "src" / "core" / "core.py").write_text("# core\n" * 500)

    clusters = cluster_files.cluster_repo(str(repo), max_clusters=3, max_lines=1000)
    assert len(clusters) <= 2  # util1 and util2 should merge into shared/utils cluster


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
    """Test matching test files to clusters and graceful fallback when missing."""
    test_map = cluster_files.discover_associated_tests(str(sample_repo), ["src/dynamics/engine.py", "src/dynamics/integrator.py"])
    assert any("test_dynamics.py" in t for t in test_map)

    # Missing test directory fallback
    test_map_empty = cluster_files.discover_associated_tests(str(sample_repo), ["src/transforms/coordinates.py"])
    assert isinstance(test_map_empty, list)


def test_git_ref_fallback_cascade(monkeypatch):
    """Test fallback cascade when resolving git base ref."""
    def mock_run(cmd, *args, **kwargs):
        class MockResult:
            def __init__(self, stdout, returncode):
                self.stdout = stdout
                self.returncode = returncode
        if "origin/custom-base" in cmd:
            return MockResult("", 1)
        if "custom-base" in cmd:
            return MockResult("abc1234\n", 0)
        return MockResult("def5678\n", 0)

    monkeypatch.setattr(subprocess, "run", mock_run)
    resolved = cluster_files.resolve_git_base_ref("custom-base", cwd=".")
    assert resolved == "custom-base"


def test_small_diff_detection():
    """Test detection of small diffs (<300 lines) for fast-path fallback."""
    payload_small = cluster_files.format_cluster_payload([], total_lines=150, total_files=2)
    assert payload_small["is_small_diff"] is True
    assert payload_small["recommended_mode"] == "single-agent-adversarial-review"

    payload_large = cluster_files.format_cluster_payload([], total_lines=1200, total_files=12)
    assert payload_large["is_small_diff"] is False
    assert payload_large["recommended_mode"] == "multi-agent-audit"


def test_cli_json_output(sample_repo):
    """Test CLI execution and JSON payload structure."""
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../scripts/cluster_files.py"))
    cmd = [
        sys.executable,
        script_path,
        "--repo",
        str(sample_repo),
    ]
    res = subprocess.run(cmd, cwd=str(sample_repo), capture_output=True, text=True)
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert "clusters" in data
    assert "total_files" in data
    assert "total_lines" in data
    assert "is_small_diff" in data
    assert len(data["clusters"]) >= 2
