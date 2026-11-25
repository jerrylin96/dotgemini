"""Test pyproject.toml, pytest.ini, and CI workflow configurations."""

import os

WORKTREE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))


def test_pyproject_and_ci_workflow_schema():
    """Verify dead MCP references and mandatory signoff CI gate are absent, and CI runs tests/lint."""
    pyproject_path = os.path.join(WORKTREE_ROOT, "pyproject.toml")
    pytest_ini_path = os.path.join(WORKTREE_ROOT, "pytest.ini")
    ci_workflow_path = os.path.join(WORKTREE_ROOT, ".github/workflows/ci.yml")
    signoff_workflow_path = os.path.join(WORKTREE_ROOT, ".github/workflows/signoff.yml")

    with open(pyproject_path, "r", encoding="utf-8") as f:
        pyproject_content = f.read()

    assert "signoff-mcp" not in pyproject_content
    assert "signoff_mcp" not in pyproject_content
    assert 'mcp = ["mcp"]' not in pyproject_content

    with open(pytest_ini_path, "r", encoding="utf-8") as f:
        pytest_content = f.read()

    assert "signoff_mcp/tests" not in pytest_content
    assert "scripts/tests" in pytest_content

    assert os.path.isfile(ci_workflow_path), ".github/workflows/ci.yml must exist"
    with open(ci_workflow_path, "r", encoding="utf-8") as f:
        ci_content = f.read()
    assert "pytest" in ci_content
    assert "ruff check" in ci_content

    assert not os.path.exists(signoff_workflow_path), (
        "Mandatory .github/workflows/signoff.yml should not be enforced on dotagent"
    )
