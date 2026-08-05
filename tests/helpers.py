"""Scratch-repo helpers shared across signoff-mcp tests."""

import subprocess


def git(path, *args, check=True):
    proc = subprocess.run(["git", *args], cwd=path, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {proc.stderr}")
    return proc


def init_repo(path, branch="main"):
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", branch)
    git(path, "config", "user.email", "tester@example.com")
    git(path, "config", "user.name", "Tester")
    git(path, "config", "commit.gpgsign", "false")
    return path


def commit_file(path, name, content, msg):
    (path / name).write_text(content)
    git(path, "add", name)
    git(path, "commit", "-q", "-m", msg)
    return git(path, "rev-parse", "HEAD").stdout.strip()
