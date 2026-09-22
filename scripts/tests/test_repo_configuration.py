"""Test pyproject.toml, pytest.ini, and CI workflow schema configurations."""

import os

WORKTREE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))


def test_pyproject_and_workflow_schema():
    """Verify dead MCP references are removed and CI workflow includes required permissions."""
    pyproject_path = os.path.join(WORKTREE_ROOT, "pyproject.toml")
    pytest_ini_path = os.path.join(WORKTREE_ROOT, "pytest.ini")
    workflow_path = os.path.join(WORKTREE_ROOT, ".github/workflows/signoff.yml")

    # 1. pyproject.toml
    with open(pyproject_path, "r", encoding="utf-8") as f:
        pyproject_content = f.read()

    assert "signoff-mcp" not in pyproject_content, "signoff-mcp script must be removed from pyproject.toml"
    assert "signoff_mcp" not in pyproject_content, "signoff_mcp packages include must be removed from pyproject.toml"
    assert 'mcp = ["mcp"]' not in pyproject_content, "mcp optional dependency must be removed from pyproject.toml"

    # 2. pytest.ini
    with open(pytest_ini_path, "r", encoding="utf-8") as f:
        pytest_content = f.read()

    assert "signoff_mcp/tests" not in pytest_content, "signoff_mcp/tests must be removed from pytest.ini testpaths"

    # 3. .github/workflows/signoff.yml
    with open(workflow_path, "r", encoding="utf-8") as f:
        workflow_content = f.read()

    assert "jerrylin96/git-signoff/verify@verify-v1.7" in workflow_content, (
        "Workflow must pin jerrylin96/git-signoff/verify@verify-v1.7"
    )
    assert "contents: read" in workflow_content, "Workflow must declare permissions: contents: read"
    assert "pull-requests: read" in workflow_content, "Workflow must declare permissions: pull-requests: read"
