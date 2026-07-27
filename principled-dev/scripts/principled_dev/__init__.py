"""Small, standard-library lifecycle primitives for principled-dev."""

from .git import Git, GitError, is_within, repository_id
from .lock import FileLock
from .worktrees import WorktreeError, WorktreeManager

__all__ = [
    "FileLock",
    "Git",
    "GitError",
    "WorktreeError",
    "WorktreeManager",
    "is_within",
    "repository_id",
]
