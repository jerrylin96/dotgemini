import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def run(*args, cwd=None, env=None):
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def skill_paths():
    return sorted((PLUGIN_ROOT / "skills").glob("*/SKILL.md"))


def frontmatter_name(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "---"
    closing = lines.index("---", 1)
    fields = {}
    for line in lines[1:closing]:
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    assert set(fields) == {"name", "description"}
    return fields["name"]


def test_plugin_manifest_and_neutral_paths():
    manifest = json.loads((PLUGIN_ROOT / "plugin.json").read_text(encoding="utf-8"))
    assert manifest == {
        "name": "principled-dev",
        "version": "0.1.0",
        "description": "Model-neutral, human-gated software development lifecycle for goose",
    }

    forbidden = ("ANTIGRAVITY", "DOTGEMINI", "~/.gemini", "google_accounts.json")
    text_suffixes = {".json", ".md", ".py", ".sh", ".yaml"}
    for path in PLUGIN_ROOT.rglob("*"):
        if path.is_file() and "tests" not in path.parts and path.suffix in text_suffixes:
            content = path.read_text(encoding="utf-8")
            assert not any(token in content for token in forbidden), path


def test_all_expected_skills_have_portable_frontmatter():
    expected = {
        "adversarial-review",
        "code-review-and-quality",
        "debugging-and-error-recovery",
        "explain-diff",
        "incremental-implementation",
        "make-feature",
        "planning-and-task-breakdown",
        "ponytail",
        "signoff",
        "spec-driven-development",
        "test-driven-development",
    }
    actual = {frontmatter_name(path) for path in skill_paths()}
    assert actual == expected
    assert {path.parent.name for path in skill_paths()} == expected


def test_plugin_installs_and_namespaces_skills(tmp_path):
    goose = shutil.which("goose")
    assert goose, "goose executable is required for packaging validation"

    source = tmp_path / "source"
    shutil.copytree(PLUGIN_ROOT, source, ignore=shutil.ignore_patterns("__pycache__"))
    run("git", "init", "-q", cwd=source)
    run("git", "add", ".", cwd=source)
    run(
        "git",
        "-c",
        "user.name=principled-dev test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-qm",
        "test plugin",
        cwd=source,
    )

    home = tmp_path / "home"
    home.mkdir()
    env = {**os.environ, "HOME": str(home)}
    install = run(goose, "plugin", "install", f"file://{source}", env=env)
    for path in skill_paths():
        assert f"principled-dev:{path.parent.name}" in install.stdout

    skills = run(goose, "skills", "list", env=env)
    for path in skill_paths():
        assert f"principled-dev:{path.parent.name}" in skills.stdout


def test_recipes_validate_and_match_primary_skills():
    goose = shutil.which("goose")
    assert goose
    expected = {"make-feature", "adversarial-review", "explain-diff", "signoff"}
    recipes = {path.stem: path for path in (PLUGIN_ROOT / "recipes").glob("*.yaml")}
    assert set(recipes) == expected
    for name, path in recipes.items():
        result = run(goose, "recipe", "validate", str(path))
        assert "valid" in result.stdout
        content = path.read_text(encoding="utf-8")
        assert name in content
        assert "goose_provider:" not in content
        assert "goose_model:" not in content


def test_slash_command_fragment_is_unique_and_complete():
    path = PLUGIN_ROOT / "config" / "slash-commands.yaml"
    content = path.read_text(encoding="utf-8")
    commands = [line.split('"')[1] for line in content.splitlines() if "command:" in line]
    assert commands == ["make-feature", "adversarial-review", "explain-diff", "signoff"]
    assert len(commands) == len(set(commands))
