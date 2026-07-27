"""Durable feature and disposable review worktree management."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Iterable

from .git import Git, GitError, is_within, repository_id
from .lock import FileLock


class WorktreeError(RuntimeError):
    """A managed worktree cannot be safely created or removed."""


_SAFE_NAME = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]*\Z")
_SHA = re.compile(r"\A[0-9a-f]{40,64}\Z")


class WorktreeManager:
    def __init__(self, repository: str | Path, cache_root: str | Path):
        self.repository = Path(repository).resolve(strict=True)
        self.git = Git(self.repository)
        self.root = Path(cache_root).resolve(strict=False) / repository_id(self.repository)
        self.feature_root = self.root / "features"
        self.review_root = self.root / "reviews"
        self.lock_path = self.root / "worktrees.lock"

    def feature_path(self, branch: str) -> Path:
        if not _SAFE_NAME.fullmatch(branch):
            raise ValueError("feature branch must be one safe path component")
        path = self.feature_root / branch
        self._require_managed(path, self.feature_root)
        return path

    def review_path(self, commit: str) -> Path:
        commit = self.git.resolve_commit(commit)
        path = self.review_root / commit
        self._require_managed(path, self.review_root)
        return path

    def create_feature(self, branch: str, commit: str) -> Path:
        expected_head = self.git.resolve_commit(commit)
        expected_branch = f"refs/heads/{branch}"
        path = self.feature_path(branch)
        with FileLock(self.lock_path):
            if path.exists():
                feature = Git(path)
                try:
                    dirty = feature.is_dirty()
                    actual_head = feature.head()
                    actual_branch = feature.symbolic_branch()
                except GitError as error:
                    raise WorktreeError(f"invalid feature worktree: {path}") from error
                if dirty:
                    raise WorktreeError(f"dirty feature worktree preserved: {path}")
                if actual_branch != expected_branch:
                    raise WorktreeError(
                        f"feature branch mismatch: expected {expected_branch}, got {actual_branch}"
                    )
                if actual_head != expected_head:
                    raise WorktreeError(
                        f"feature HEAD mismatch: expected {expected_head}, got {actual_head}"
                    )
                return path
            if self._branch_exists(expected_branch):
                raise WorktreeError(f"feature branch already exists outside managed worktree: {branch}")
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                self.git.worktree_add(path, expected_head, branch=branch)
            except GitError as error:
                self._clean_failed_path(path)
                raise WorktreeError(f"could not create feature worktree: {path}") from error
            self._verify(path, expected_head, expected_branch)
            return path

    def remove_feature(self, branch: str) -> None:
        path = self.feature_path(branch)
        with FileLock(self.lock_path):
            if not path.exists():
                return
            feature = Git(path)
            try:
                if feature.is_dirty():
                    raise WorktreeError(f"dirty feature worktree preserved: {path}")
            except GitError as error:
                raise WorktreeError(f"invalid feature worktree preserved: {path}") from error
            try:
                self.git.worktree_remove(path)
            except GitError as error:
                raise WorktreeError(f"could not safely remove feature worktree: {path}") from error

    def create_review(self, commit: str) -> Path:
        expected_head = self.git.resolve_commit(commit)
        path = self.review_path(expected_head)
        with FileLock(self.lock_path):
            if path.exists():
                try:
                    if (
                        Git(path).head() == expected_head
                        and Git(path).symbolic_branch() is None
                        and not Git(path).is_dirty()
                    ):
                        return path
                except GitError:
                    pass
                self._discard_review(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                self.git.worktree_add(path, expected_head)
            except GitError as error:
                self._clean_failed_path(path)
                raise WorktreeError(f"could not create review worktree: {path}") from error
            self._verify(path, expected_head, None)
            return path

    def prune_reviews(self, keep: Iterable[str] = ()) -> list[Path]:
        keep_heads = {self.git.resolve_commit(commit) for commit in keep}
        removed: list[Path] = []
        with FileLock(self.lock_path):
            if not self.review_root.exists():
                return removed
            for path in sorted(self.review_root.iterdir()):
                if not path.is_dir() or not _SHA.fullmatch(path.name) or path.name in keep_heads:
                    continue
                self._discard_review(path)
                removed.append(path)
        return removed

    def _discard_review(self, path: Path) -> None:
        self._require_managed(path, self.review_root)
        try:
            self.git.worktree_remove(path, force=True)
        except GitError:
            if path.exists():
                shutil.rmtree(path)
            self.git.run("worktree", "prune")

    def _clean_failed_path(self, path: Path) -> None:
        self._require_managed(path, self.root)
        if path.exists():
            shutil.rmtree(path)
        self.git.run("worktree", "prune", check=False)

    def _branch_exists(self, branch_ref: str) -> bool:
        return self.git.run("show-ref", "--verify", "--quiet", branch_ref, check=False).returncode == 0

    @staticmethod
    def _require_managed(path: Path, root: Path) -> None:
        if path.resolve(strict=False) == root.resolve(strict=False) or not is_within(path, root):
            raise WorktreeError(f"refusing path outside managed cache: {path}")

    @staticmethod
    def _verify(path: Path, expected_head: str, expected_branch: str | None) -> None:
        actual = Git(path)
        if actual.head() != expected_head or actual.symbolic_branch() != expected_branch:
            raise WorktreeError(f"created worktree has unexpected HEAD or branch: {path}")
