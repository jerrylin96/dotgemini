"""Minimal checked Git subprocess wrapper."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


class GitError(RuntimeError):
    """A Git command failed."""


def is_within(path: str | Path, root: str | Path) -> bool:
    """Return whether path is inside root after resolving symlinks."""
    try:
        Path(path).resolve(strict=False).relative_to(Path(root).resolve(strict=False))
        return True
    except ValueError:
        return False


class Git:
    def __init__(self, worktree: str | Path):
        self.worktree = Path(worktree).resolve(strict=False)

    def run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ("git", "-C", str(self.worktree), *args),
            capture_output=True,
            text=True,
        )
        if check and result.returncode:
            detail = result.stderr.strip() or result.stdout.strip()
            raise GitError(f"git {' '.join(args)} failed: {detail}")
        return result

    def common_dir(self) -> Path:
        value = self.run("rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()
        return Path(value).resolve(strict=True)

    def head(self) -> str:
        return self.run("rev-parse", "--verify", "HEAD^{commit}").stdout.strip()

    def resolve_commit(self, revision: str) -> str:
        return self.run("rev-parse", "--verify", f"{revision}^{{commit}}").stdout.strip()

    def symbolic_branch(self) -> str | None:
        result = self.run("symbolic-ref", "-q", "HEAD", check=False)
        if result.returncode == 1:
            return None
        if result.returncode:
            detail = result.stderr.strip() or result.stdout.strip()
            raise GitError(f"git symbolic-ref -q HEAD failed: {detail}")
        return result.stdout.strip()

    def is_dirty(self) -> bool:
        return bool(self.run("status", "--porcelain=v1", "--untracked-files=all").stdout)

    def worktree_add(self, path: str | Path, commit: str, *, branch: str | None = None) -> None:
        args = ["worktree", "add", "--no-checkout"]
        if branch is None:
            args.append("--detach")
        else:
            args.extend(("-b", branch))
        args.extend((str(path), commit))
        self.run(*args)
        Git(path).run("checkout", "-q", "--force", commit if branch is None else branch)

    def worktree_remove(self, path: str | Path, *, force: bool = False) -> None:
        args = ["worktree", "remove"]
        if force:
            args.append("--force")
        args.append(str(path))
        self.run(*args)


def repository_id(repository: str | Path) -> str:
    common_dir = str(Git(repository).common_dir()).encode()
    return hashlib.sha256(common_dir).hexdigest()[:16]
