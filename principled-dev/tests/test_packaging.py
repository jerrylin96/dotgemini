import json
import os
import shutil
import subprocess
from pathlib import Path


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


def test_plugin_installs_and_namespaces_skills(tmp_path):
    goose = shutil.which("goose")
    assert goose, "goose executable is required for packaging validation"

    source = tmp_path / "source"
    shutil.copytree(PLUGIN_ROOT, source)
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
    assert "principled-dev:ponytail" in install.stdout

    skills = run(goose, "skills", "list", env=env)
    assert "principled-dev:ponytail" in skills.stdout
